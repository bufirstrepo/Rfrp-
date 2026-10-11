# External review supplied with the GitHub handoff

**Received:** 2026-10-11  
**Source:** text pasted by the project owner in the conversation; reviewer identity not independently established.  
**Purpose:** preserve critique, research hypotheses, and suggested next work.  
**Status:** reviewer assessment, not measured project evidence or an adopted specification amendment.

The review text below is preserved as supplied. References to earlier replies, an X pitch, a Grok reply, and a telepresence document are part of the review; those artifacts were not supplied in this import. The closing offer to implement Stage 1 is quoted source material, not a record that Stage 1 was implemented. See [Roadmap](../ROADMAP.md) for the proposed response to the review.

---

Now that I can see the whole project: the consolidated handoff is the best document in the set by a wide margin, and it's genuinely good work. It isn't genius, though, and the strongest evidence against that word is the handoff itself.

**What changed my read**

It resolves most of what I raised over the last two replies:
- It no longer assumes learned decoding is reproducible across devices.
- A decoder name doesn't count as evidence of fidelity.
- A sender's check doesn't certify a different receiver's output.
- Signing a receipt can't stand in for actually verifying the result.
- Making one publisher the authority avoids the clash between the two consistency models.
- IPComp is gone.

It also adds things I didn't raise:
- error budgets that hold across multiple transforming hops
- separate records for the bytes, the evidence about them, and who's allowed to use them
- delegated budgets that can't be duplicated
- loop prevention, even though the dependency graph itself has no cycles
- failed attempts counted against the planner
- a required negative result

The corrections table and maturity labels show more discipline about what's proven than most early protocol proposals.

So my opinion of the design went up. My opinion of the novelty and performance claims didn't, because by the doc's own account nothing in it is evidence for those.

**Why "genius" is the wrong word**
- **Your handoff rules it out.** It says no performance or novelty result exists, and that the discussion "did not establish that the combination is unique." Its claims-discipline section forbids claiming novelty from the architecture alone.
- **The pasted paragraph is the same one from your first message.** Its strongest words are "promising" and "worthwhile direction." Even Grok's pitch reply, the most enthusiastic thing you've shared, stopped short of genius.
- **The genius-sounding part is the part your spec puts off.**
  - It calls AI "optional planner machinery."
  - It won't accept AI-decoded (Latent) outputs without a declared reference and a named checker.
  - It says "a recipe cannot reconstruct arbitrary unseen information for free."
  - What's specified and buildable now is the coordination layer, not AI compression. Your X pitch and your spec describe different systems, so align the pitch before anyone reads both.
- **Nothing has run yet,** per the doc's own status line.

**What it actually is**

It's a careful synthesis, which is what most successful protocols are. QUIC folded lessons from TCP, TLS 1.3 and SPDY into one design. That's a real compliment, and it comes with a measurable bar.

If there's an original contribution, I'd look for it in how the spec handles approximate outputs:
- Most systems either demand exact reproduction (builds, content addressing, video decoders) or allow approximation without tracking it (lossy transcoding pipelines).
- Yours does neither. Accepted approximations get their own identities, can't quietly serve as the base for each other's patches, and carry end-to-end error budgets across hops.
- That's where your comparison with Named Function Networking and Compute First Networking should focus. It's also what a draft or paper should lead with, after the attorney conversation if you're filing.

**What's still worth adding**
- **Reuse existing standards before designing new ones.** This answers the question your own prior-work section asks.
  - Deterministic CBOR (RFC 8949 §4.2) or JCS (RFC 8785) settles much of your canonical-encoding list.
  - COSE covers signatures.
  - The IETF's SCITT work, which isn't in your source list, already defines signed statements and receipts.
- **Put a time limit on Stage 1.** Its exit condition mostly maps onto what HTTP already does (conditional updates, digests, RFC 9842 compression dictionaries), so it can only show you match HTTP, not beat it. The demo that shows something distinctive is Stage 4: one receiver jumps the camera while another still needs the shared work, passing test cases C15–C18 with every link's traffic counted.
- **Predict the negative case.** My guess is ARFP wins on large, shared, structured objects and loses on small, frequent updates, where negotiation and evidence overhead dominate. Those updates belong on a datagram channel like the one in the telepresence doc.
- **Make test case C28 real.** Have two different implementers, even two different AI models given only the spec, each build one side. Every divergence points to an ambiguity in the spec, and it's the cheapest interoperability test a solo builder can run.
- **Keep telepresence separate for now.** Its shared scene graph lets multiple people write at once, which v0.1 deliberately leaves out.
- **Find a second party.** What turns an architecture into a protocol is someone who wants to build the other end. Until then it's a design for one system, which is still worth building.

What would earn a stronger word than "good" is that Stage 4 demo running, plus one honest negative result. Want me to start Stage 1 here: schemas for the core objects, the state machine, and test cases C01–C05 as runnable fixtures?
