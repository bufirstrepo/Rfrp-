"""Durable commit journal and crash recovery for C21.

Write-ahead order for one transaction:
  1. approval record   (the signed VALIDATION_APPROVAL, the staged output's digest, the expected head)
  2. head record       (compare-and-swap applied: the new head)  -- or an outcome record (conflict/aborted)
  3. receipt record    (the signed COMMIT_RECEIPT)
Each record is framed as [4-byte length][4-byte CRC32][canonical CBOR] and fsynced. On restart,
recovery drops a torn tail, replays the journal, and resolves every approval that has no receipt.
Receipts are deterministic (Ed25519 over canonical bytes), so a recovered receipt is byte-identical
to the one an uncrashed run would have written.

Crash points stop the worker with SIGKILL: no cleanup, no atexit handlers, no buffered writes
flushed. Records already fsynced survive, as they would after a process crash (not a power loss).

Run as a worker:  python3 -m arfpkit.journal <root> <crash_at> <input.cbor>
"""
import os
import signal
import sys
import zlib
from pathlib import Path

from .canon import art, decode, encode, oid, same
from .cose import fixture_key, verify1
from .rules import Reject

CRASH_POINTS = ("none", "after-approval", "torn-head", "after-head", "after-receipt")
KILLED = -signal.SIGKILL if hasattr(signal, "SIGKILL") else 137      # worker return code after hard_stop


def hard_stop():
    """Die the way a crashed process does."""
    if hasattr(signal, "SIGKILL"):
        os.kill(os.getpid(), signal.SIGKILL)
    os._exit(137)                                                     # platforms without SIGKILL


class Journal:
    def __init__(self, path):
        self.path = Path(path)

    def _frame(self, rec):
        body = encode(rec)
        return len(body).to_bytes(4, "big") + zlib.crc32(body).to_bytes(4, "big") + body

    def append(self, rec, torn=False):
        frame = self._frame(rec)
        if torn:
            frame = frame[: len(frame) // 2]
        with open(self.path, "ab") as f:
            f.write(frame)
            f.flush()
            os.fsync(f.fileno())

    def scan(self):
        data = self.path.read_bytes() if self.path.exists() else b""
        out, i = [], 0
        while i + 8 <= len(data):
            n = int.from_bytes(data[i:i + 4], "big")
            crc = int.from_bytes(data[i + 4:i + 8], "big")
            body = data[i + 8:i + 8 + n]
            if len(body) < n or zlib.crc32(body) != crc:
                break
            out.append(decode(body))
            i += 8 + n
        return out, i, len(data)

    def truncate(self, length):
        with open(self.path, "r+b") as f:
            f.truncate(length)
            f.flush()
            os.fsync(f.fileno())


class DurableConsumer:
    def __init__(self, root, party, obj):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.staging = self.root / "staging"
        self.staging.mkdir(exist_ok=True)
        self.journal = Journal(self.root / "journal.bin")
        self.party, self.obj = party, obj
        self.key = fixture_key(party)
        self.state = "recovering"
        self.head, self.snapshot, self.receipts = None, 0, {}
        self.crash_at = "none"
        self.actions = []

    # ---------- staging ----------
    def stage(self, data):
        d = art(data)
        path = self.staging / bytes(d[1]).hex()
        with open(path, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        return d

    def staged_ok(self, d):
        path = self.staging / bytes(d[1]).hex()
        return path.exists() and same(art(path.read_bytes()), d)

    def head_id(self):
        return oid(self.head) if self.head else None

    def _crash(self, point):
        if self.crash_at == point:
            hard_stop()

    # ---------- recovery ----------
    def seed(self, head):
        self.journal.append({"rec": "genesis", "head": head})

    def recover(self):
        recs, good, total = self.journal.scan()
        if good < total:
            self.journal.truncate(good)
            self.actions.append("truncated-torn-tail")
        head, snapshot, pending, committed, outcomes, receipts = None, 0, [], {}, {}, {}
        for r in recs:
            kind = r["rec"]
            if kind == "genesis":
                head = r["head"]
            elif kind == "approval":
                pending.append(r)
            elif kind == "head":
                head, snapshot = r["head"], snapshot + 1
                committed[r["txn"]] = r
            elif kind == "outcome":
                outcomes[r["txn"]] = r
            elif kind == "receipt":
                receipts[r["txn"]] = r["signed"]
        self.head, self.snapshot, self.receipts = head, snapshot, receipts
        for a in pending:
            txn = a["txn"]
            if txn in receipts:
                continue
            if txn in committed:
                self._write_receipt(a, committed[txn]["prior"], oid(committed[txn]["head"]), "committed")
                self.actions.append(("receipt-from-commit", txn))
            elif txn in outcomes:
                o = outcomes[txn]
                self._write_receipt(a, o["prior"], None, o["status"])
                self.actions.append(("receipt-from-outcome", txn))
            else:
                self._resolve(a)
                self.actions.append(("resolved-pending-approval", txn))
        self.state = "ready"
        return self.actions

    def admit(self, plan_snapshot):
        """Same snapshot rule as plan eligibility: nothing is admitted during recovery,
        and a plan built against an older snapshot is stale."""
        if self.state != "ready":
            raise Reject("stale-state", "receiver is still recovering")
        if plan_snapshot != self.snapshot:
            raise Reject("stale-state", f"plan assumes snapshot {plan_snapshot}; receiver is at {self.snapshot}")
        return True

    # ---------- commit ----------
    def commit(self, signed_approval, approver_public_key):
        if self.state != "ready":
            raise Reject("stale-state", "receiver is still recovering")
        a = verify1(approver_public_key, signed_approval)
        txn = a["txn"]
        if txn in self.receipts:
            return self.receipts[txn]                                  # idempotent retry
        rec = {"rec": "approval", "txn": txn, "signed": signed_approval, "output": a["output"],
               "expected": a["expected-head"]}
        self.journal.append(rec)
        self._crash("after-approval")
        return self._resolve(rec)

    def _resolve(self, rec):
        a = verify1(self.key.public_key(), rec["signed"])
        prior = self.head_id()
        if not self.staged_ok(rec["output"]):
            self.journal.append({"rec": "outcome", "txn": rec["txn"], "status": "aborted",
                                 "reason": "integrity-failure", "prior": prior})
            return self._write_receipt(rec, prior, None, "aborted")
        exp = rec["expected"]
        if (exp is None and prior is None) or (exp is not None and prior is not None and same(exp, prior)):
            new = {"kind": "head", "object": self.obj, "target": a["target"], "contract": a["contract"],
                   "scope": a["scope"], "output": a["output"]}
            head_rec = {"rec": "head", "txn": rec["txn"], "head": new, "prior": prior}
            if self.crash_at == "torn-head":
                self.journal.append(head_rec, torn=True)
                hard_stop()
            self.journal.append(head_rec)
            self.head, self.snapshot = new, self.snapshot + 1
            self._crash("after-head")
            return self._write_receipt(rec, prior, oid(new), "committed")
        self.journal.append({"rec": "outcome", "txn": rec["txn"], "status": "conflict", "prior": prior})
        return self._write_receipt(rec, prior, None, "conflict")

    def _write_receipt(self, rec, prior, head, status):
        from .cose import sign1
        a = verify1(self.key.public_key(), rec["signed"])
        receipt = {"kind": "receipt", "txn": rec["txn"], "approval": oid(a), "prior-head": prior,
                   "head": head, "status": status}
        signed = sign1(self.key, self.party, receipt)
        self.journal.append({"rec": "receipt", "txn": rec["txn"], "signed": signed})
        self.receipts[rec["txn"]] = signed
        self._crash("after-receipt")
        return signed


def worker(root, crash_at, input_path):
    spec = decode(Path(input_path).read_bytes())
    c = DurableConsumer(root, spec["party"], spec["object"])
    c.recover()
    c.stage(spec["artifact"])
    c.crash_at = crash_at
    c.commit(spec["approval"], c.key.public_key())
    return 0


if __name__ == "__main__":
    sys.exit(worker(sys.argv[1], sys.argv[2], sys.argv[3]))
