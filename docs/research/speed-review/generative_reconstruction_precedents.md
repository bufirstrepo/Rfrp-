# Generative and model-based reconstruction precedents: video, conferencing, telepresence, 3D, games, 6G

*Compiled 2026-10-11 for the ARFP engineering review.*

*Quoting conventions.* Text in quotation marks is verbatim as returned by the page-fetch tool. That tool caps each quote at about 120 characters, so many quotes are sentence fragments; "…" joins consecutive fragments.

*Evidence labels.*
- **[Lab]** is the authors' own experimental result.
- **[Prod]** is a production or A/B measurement reported by the vendor.
- **[Vendor]** is a vendor's own benchmark.
- **[Claim]** is a qualitative or unmeasured assertion.
- **[Spec]** is normative standard text.
- **[Arith]** is my own arithmetic on cited numbers.
- **[tool-extracted]** marks a number the fetch tool read from a table, figure or surrounding context without returning a verbatim sentence. These were not checked against the PDFs; treat them as unverified.

*Access limits.*
- The research environment blocked direct downloads (403 on CONNECT to arxiv.org, www.usenix.org and aomediacodec.github.io), so all reading went through the fetch tool.
- usenix.org pages required an interactive permission that could not be obtained, which affected the NAS and Gemino venue pages.
- Valve's main "Source Multiplayer Networking" article returned errors. The Wayback Machine is blocked for the fetch tool.
- docs.ogc.org failed to load.

## 1. NVIDIA face-vid2vid (Wang, Mallya, Liu): bandwidth claim vs H.264 and what is sent per frame

### Takeaway
The receiver gets one source image at the start of the session. After that, each frame carries only head pose plus per-keypoint expression deformations ("3K+6 numbers"), stored as fp16 and arithmetic-coded to a mean of 53.03 B/frame in the adaptive scheme. The authors claim H.264-equivalent visual quality at "one-tenth of the bandwidth" **[Lab]**. A generator synthesizes the output, so it is neither bit-exact nor error-bounded. It degrades with large occlusions, and recovery means sending a new source frame.

### Cited Findings
- Dates: arXiv submission 2020-11-30; current version v3 dated 2021-04-02. The arXiv page has no venue comment, so the "CVPR 2021" attribution in the brief was not confirmed there. — [arXiv abstract page](https://arxiv.org/abs/2011.15126)
- **[Lab] Headline claim (abstract):** "our compact keypoint representation enables a video conferencing system that achieves the same visual quality as the" … "commercial H.264 standard while only using one-tenth of the bandwidth" — [arXiv](https://arxiv.org/abs/2011.15126)
- **Per-frame payload (Sec. 5):** "we have a compact representation of d using 3K+6 numbers"; "ours only sends the head pose and keypoint deformations" — [paper PDF](https://arxiv.org/pdf/2011.15126)
- **Sent once (Sec. 5):** "We assume that the source image s is sent to the receiver at the beginning of the video conferencing session" — [paper PDF](https://arxiv.org/pdf/2011.15126)
- **Coding:**
  - "We further compress these values using an entropy encoder [14]." (Sec. 5)
  - "We represent each rotation angle, translation, and deformation value as an fp16 floating-point number." (App. C.1)
  - "We adopt arithmetic coding [40] to encode the 3K+6 numbers." (App. C.1)
  - Source: [paper PDF](https://arxiv.org/pdf/2011.15126)
- **[Lab] Per-frame size (App. C.1):** "Our adaptive scheme requires a per-frame metadata size of 53.03 B" — [paper PDF](https://arxiv.org/pdf/2011.15126)
- **[tool-extracted] Table 6, mean per-frame metadata (after / before compression):**
  - fs-vid2vid: ≈231 / 504 B
  - FOMM: ≈171 / 240 B
  - 20-keypoint model: ≈84 / 132 B
  - Adaptive: ≈53 / 81 B
  - Source: [paper PDF](https://arxiv.org/pdf/2011.15126)
- **[tool-extracted] Ratio vs H.264:** The Sec. 5 quote is "reduction in bandwidth compared to the H.264 codec". The tool reported 10.37× for the adaptive scheme and 6.5× for the 20-keypoint scheme, but those numbers are outside the verbatim fragment. The H.264 comparison is plotted as bpp vs LPIPS (Fig. 16), not as bytes per frame. — [paper PDF](https://arxiv.org/pdf/2011.15126)
- **Failure modes and resync:**
  - "While our model is in general robust to different situations, it cannot handle large occlusions well." (App. B.5)
  - "Our method still struggles when there are occluders such as hands in the image." (Fig. 14 caption)
  - "it becomes necessary to update the source frame being used to perform the talking-head synthesis" (App. C.3)
  - "We just need to send it when the current source image is not good enough to reconstruct the current driving image." (App. C.3)
  - [tool-extracted] A binary-residual alternative averages about 13.40 KB (App. C.3).
  - Source: [paper PDF](https://arxiv.org/pdf/2011.15126)

### Inferences
- [Arith] With K = 20, 3K+6 = 66 values; at 2 bytes (fp16) each that is 132 B. This matches the tool-extracted "before compression" value for the 20-keypoint model, so the Table 6 extraction is internally consistent.
- [Arith] 53.03 B/frame is about 424 bits/frame. At an assumed 30 fps that is about 12.7 kbps. The paper's test frame rate was not verified.
- **What the receiver holds:** a generic generator network plus the one-time source image. The title says "one-shot," meaning one source image and no per-person training; per-user fine-tuning was not checked.
- **Fidelity class:** perceptual or statistical similarity only. Quality is judged with learned metrics (LPIPS). The "update the source frame" path works as an authoritative keyframe correction channel, which is a useful pattern for ARFP.
- The 10× figure comes from the authors' own lab comparison on talking-head content. It is not a production measurement.

### Gaps
- No CVF or CVPR page was fetched, so the venue is unconfirmed.
- No verbatim sentence was captured for the 10.37× and 6.5× ratios or the Table 6 cells. Check them against the PDF.
- The test frame rate and dataset behind "one-tenth" were not captured.
- The fetched text does not mention any labeling or provenance marker for synthesized frames.

## 2. NAS (Yeo et al., OSDI 2018): QoE and bandwidth claims, DNN size, and how model download is handled

### Takeaway
NAS ships a per-video ("content-aware") super-resolution DNN in chunks, streamed alongside the video chunks, and runs it on the client to enhance low-resolution video. The authors report +43.08% average QoE at the same bandwidth, or 17.13% bandwidth saved at the same QoE **[Lab]**. Absolute model sizes and the ABR mechanism could not be verified, because the USENIX full text could not be retrieved.

### Cited Findings
- **Bibliographic:** 13th USENIX OSDI, pp. 645–661. The KOASAS record gives "Date issued" 2018-10-10 [tool-extracted metadata]. Authors are Yeo, Jun/Jung, Kim, Shin and Han; KOASAS spells "Jun, Youngmok". — [KAIST KOASAS record](https://koasas.kaist.ac.kr/handle/10203/246781?mode=full)
- **[Lab]** "enhancing the average QoE by 43.08% using the same bandwidth budget" — [KOASAS](https://koasas.kaist.ac.kr/handle/10203/246781?mode=full)
- **[Lab]** "saving 17.13% of bandwidth while providing the same user QoE." — [KOASAS](https://koasas.kaist.ac.kr/handle/10203/246781?mode=full)
- **Model size (relative only):** "The higher the quality level, the bigger the model size, the higher the model quality." — [NAS_public GitHub](https://github.com/kaist-ina/NAS_public)
- **Model delivery:** DNN chunks are "used for streaming together with video chunks in NAS." — [NAS_public GitHub](https://github.com/kaist-ina/NAS_public)
- **Citation:** "13th USENIX Symposium on Operating Systems Design and Implementation (OSDI 18). 2018." — [NAS_public GitHub](https://github.com/kaist-ina/NAS_public)
- **Project tagline:** "Watch videos in high-quality even when the network becomes congested" — [KAIST INA project page](https://ina.kaist.ac.kr/projects/nas)

### Inferences
- **What the receiver holds and runs:** a standard decoder for the low-resolution chunks, which is bit-exact for what was sent, plus the downloaded per-video DNN. The enhanced output approximates the high-resolution original, so fidelity is perceptual and unbounded.
- **Model download cost:** the download competes with video for the same link. Streaming DNN chunks "together with video chunks" means the cost is scheduled inside the session rather than pre-installed. That is the model-distribution problem ARFP has to budget for.
- 17.13% (bandwidth saved at equal QoE) is the number comparable to an ARFP "savings at equal quality" figure. 43.08% is a QoE gain at equal bandwidth and is not a compression ratio.

### Gaps
- Not verified: absolute DNN sizes per quality level, the integrated-ABR algorithm (including whether it uses reinforcement learning), client GPU requirements, and whether the evaluation was trace-driven or run on real networks. The USENIX page and PDF (https://www.usenix.org/conference/osdi18/presentation/yeo) required interactive permission, so these were not filled in from memory.

## 3. Gemino (Sivaraman et al., NSDI 2024): bitrate-reduction claims and target bitrate range

### Takeaway
Gemino sends a very-low-resolution VP8/VP9 stream on every frame (about 15 Kbps at 128×128). The receiver upsamples it with a personalized model of about 82M parameters, conditioned on a high-resolution reference frame. The paper claims "2.2-5x lower bitrate than traditional video codecs for the same perceptual quality" (LPIPS), targeting "~100 Kbps or less" **[Lab]**. The base layer decodes bit-exactly. The upsampled detail is generated, so fidelity is perceptual, and the pipeline adds about 40 ms of latency.

### Cited Findings
- **Dates:** arXiv submission 2022-09-21; v4 dated 2023-10-19. arXiv shows no venue comment, and the NSDI 2024 page was gated. — [arXiv abstract](https://arxiv.org/abs/2209.10507)
- **[Lab] Abstract claim:** "achieves 2.2-5x lower bitrate than traditional video codecs for the same perceptual quality" — [arXiv abstract](https://arxiv.org/abs/2209.10507)
- **Mechanism (abstract):**
  - "Gemino upsamples a very low-resolution version of each target frame"
  - "information extracted from a single high-resolution reference image"
  - "allowing it to scale to resolutions comparable to 720p"
  - "we personalize the model to learn specific details of each person, achieving much better fidelity at low bitrates"
  - "operates on 1024x1024 videos in real-time on a Titan X GPU"
  - Source: [arXiv abstract](https://arxiv.org/abs/2209.10507)
- **Target range:**
  - "Gemino targets extreme compression scenarios, such as delivering video in ~100 Kbps or less." (Intro)
  - "sending 128×128 resolution video in our implementation consumes ~15 Kbps" (Sec. 1)
  - Source: [paper PDF](https://arxiv.org/pdf/2209.10507)
- **Per-frame payload:**
  - "transmits downsampled video (e.g. 64×64 frames) on every frame" (Sec. 4)
  - "The PF stream sends downsampled frames of the highest resolution that the current bandwidth can support" (Fig. 5 caption)
  - Source: [paper PDF](https://arxiv.org/pdf/2209.10507)
- **Bitrate ladder (Table 2 cells):**

  | Bitrate | Resolution | Codec |
  |---|---|---|
  | "<30 Kbps" | "128×128" | "VP8" |
  | "30 Kbps – 75 Kbps" | "256×256" | "VP8" |
  | "75 Kbps – 200 Kbps" | "512×512" | "VP9" |
  | ">200 Kbps" | "1024×1024" | "VP9" |

  Source: [paper PDF](https://arxiv.org/pdf/2209.10507)
- **Reference frame:**
  - "We assume that the receiver has access to a single high-resolution reference frame" (Sec. 3.1)
  - "We anticipate using the reference stream extremely sparsely." (Sec. 4)
  - "we only use a single reference frame in our evaluations." (fn. 3)
  - Source: [paper PDF](https://arxiv.org/pdf/2209.10507)
- **Model the receiver must hold:**
  - "personalized to each individual using a few hours of their video calls" (Sec. 3.2)
  - "An unoptimized (full-precision) checkpoint of the model's 82M parameters is about a GB in size." (Sec. 3.2)
  - Source: [paper PDF](https://arxiv.org/pdf/2209.10507)
- **[Lab] vs VP8 and VP9:**
  - "a 5× and 2.2× reduction from VP8 and VP9's default Chromium and WebRTC settings respectively" (Intro)
  - "We observe that VP8 and VP9 consume 523 Kbps and 230 Kbps respectively to achieve an LPIPS of 0.21." (Sec. 5.2)
  - Source: [paper PDF](https://arxiv.org/pdf/2209.10507)
- **[Lab] vs other baselines:**
  - "a 2× and 3.9× reduction compared to bicubic and super-resolution" (Intro). [tool-extracted context: at 50 Kbps, LPIPS 0.23]
  - "It also outperforms Bicubic and SwinIR by 0.05 and 0.1 in LPIPS at the median and tail respectively." (Sec. 5.2)
  - vs FOMM: "better than FOMM by 0.05–0.1" in LPIPS (Sec. 5.2)
  - Source: [paper PDF](https://arxiv.org/pdf/2209.10507)
- **Metric rationale:** "We observe that differences in LPIPS are more reflective of how natural the synthesized frame feels" (Sec. 5.1) — [paper PDF](https://arxiv.org/pdf/2209.10507)
- **Costs and limits:**
  - "Gemino increases the end-to-end frame latency to ~87 ms, from VPX's 47 ms." (Sec. 5.2)
  - "This design choice might cause abrupt shifts in quality around the transition points between resolutions." (Sec. 5.5)
  - "Our evaluation focuses on reconstructing a single front-facing person in a video call" (Sec. 5.1)
  - "personalization provides limited benefits for Gemino" (Sec. 5.3)
  - "it also raises important ethical considerations about the bias that training data can introduce" (Conclusion)
  - On earlier keypoint methods: "they fail (possibly catastrophically) in the presence of large movements or occlusions." (Intro)
  - Source: [paper PDF](https://arxiv.org/pdf/2209.10507)

### Inferences
- [Arith] 523 Kbps ÷ 5 ≈ 105 Kbps and 230 Kbps ÷ 2.2 ≈ 105 Kbps. So the 5× and 2.2× claims imply Gemino reaches LPIPS 0.21 at about 105 Kbps, which matches the tool-reported context.
- **Hybrid design:** each frame's payload is a standard VP8/VP9 bitstream, so the low-resolution "truth" decodes exactly and only the added high-frequency detail is generated. That is a natural boundary for an ARFP "generated" label: an exact base layer plus a labeled generated enhancement.
- **Model distribution is heavy:** about 1 GB unoptimized, trained per person on "a few hours" of calls. ARFP's "receiver must already hold" requirement has real cost and privacy implications.
- **Resolution discrepancy:** Sec. 4's 64×64 is given as an example ("e.g."), while Table 2 starts at 128×128. This looks like an example versus the implemented ladder, not a contradiction.

### Gaps
- The NSDI 2024 venue and presentation date were not verified from usenix.org, which was gated.
- No optimized or quantized deployment size for the model was captured.
- The fetched text does not mention labeling synthesized output.

## 4. AV1 film grain synthesis: normatively specified and reproducible, or only statistically similar? Netflix deployment claims and date

### Takeaway
The AV1 decoding-process text points to a *reference* grain synthesis process in §7.18.3: an auto-regressive model, an LFSR pseudo-random generator and piecewise-linear intensity scaling. A decoder that implements it exactly reproduces the grain bit-for-bit. However, the conformance clause offers a second option. Under it, the non-grain "intermediate frames" must be bit-exact, but the grain output only has to show no "perceptually significant differences". The spec says the definition of that phrase is "beyond the scope of this specification" and may be set "by a service provider as part of their accreditation program".

Relative to the source video, the grain is never the original. It is "similar grain", a statistical match.

Netflix: a post dated July 2, 2025 says "Since March" FGS has been rolling out at scale. It reports a 36% average bitrate reduction for 1080p and above across about 300 titles, and A/B results of −24% start-of-playback bitrate and −31.6% average bitrate **[Prod]**.

### Cited Findings
**Spec version and location**
- [Spec] The PDF title page reads "Version 1.0.0 with Errata 1" and "Last modified: 2019-01-08 11:48 PT". The film grain synthesis process is §7.18.3, under §7.18 "Output process", and §7.18.3.2 is "Random number process" (table of contents). — [AV1 spec PDF](https://aomediacodec.github.io/av1-spec/av1-spec.pdf)
- The HTML version is a working draft: "Last modified: 2023-05-25 12:27 PT"; "This is an internal AOMedia working document and not an approved version of the AV1 specification." — [AV1 spec HTML](https://aomediacodec.github.io/av1-spec/)

**Conformance clause (spec source, "General decoding process" section)**

All quotes in this block are from the [AV1 spec source, master branch, 08.decoding.process.md](https://raw.githubusercontent.com/AOMediaCodec/av1-spec/master/08.decoding.process.md).
- [Spec] Without grain: "When film_grain_params_present is equal to 0, decoders shall produce output frames that are identical in all respects" … "and have the same output order as those produced by the decoding process specified herein."
- [Spec] With grain: "When film_grain_params_present is equal to 1, a decoder shall implement a film grain synthesis process that" … "modifies the output arrays OutY, OutU, OutV. The reference film grain synthesis process is described in" … "[section 7.18.3][]."
- [Spec] "When film_grain_params_present is equal to 1, a conformant decoder shall satisfy at least one of the" … "following two options:"
- [Spec] Option 1, bit-exact: "1. A conformant decoder shall produce output frames that are identical in all respects and have the same" … "output order as those produced by the decoding process specified herein including applying the exact film" … "grain synthesis process as specified in [section 7.18.3][]."
- [Spec] Option 2, exact intermediates with perceptual grain: "2. A conformant decoder shall produce intermediate frames that are identical in all respects and have the same" … "order as the frames produced by the process specified in [section 7.18.2][]." … "In addition to that, a conformant decoder shall produce output frames that are in the same order and do not" … "have perceptually significant differences with the frames produced by the reference film grain" … "synthesis process specified in [section 7.18.3][] when applied to the input frames of the film grain" … "synthesis process with the film grain parameters signaled for these frames."
- [Spec] Who defines the bound: "The definition of "perceptually significant differences" is beyond the scope of this specification" … "and may be specified, for example, by a service provider as part of their accreditation program."
- [Spec] Feature completeness: "The film grain synthesis process applied by a conformant decoder should be feature complete with regards to" … "the reference film grain synthesis process of [section 7.18.3][] including scaling strength of the film grain" … "as a function of intensity according to the signaled parameters, same maximum AR lag, and similar" … "modeling of correlation between luma and chroma and smoothing of transitions between blocks of grain" … "when applicable."
- [Spec] Optional pre-grain processing: "The decoder may also include optional processing steps which are applied to the intermediate frames" … "Such optional processing steps are beyond the scope of this specification."
- [Spec NOTE] Advice to implementers: "To ensure conformance, decoder manufacturers are advised to implement the film grain synthesis" … "process as specified in [section 7.18.3][]."
- [Spec NOTE] Why option 2 exists: "One reason to choose the second conformance option is implementation of optional processing steps" … "minor differences in the output with the reference film grain synthesis process of [section 7.18.3][]." … "Examples of these optional processing steps are algorithms improving output picture quality, such as" … "de-banding filtering and coding artefacts removal."

**Annex A**
- The Annex A "Decoder Conformance" section has no film grain text; the tool reported "Film grain: Not found". The section does say: "A level X.Y compliant decoder must be able to decode all bitstreams". — [annex.a.levels.md](https://raw.githubusercontent.com/AOMediaCodec/av1-spec/master/annex.a.levels.md)

**Mechanism: Han et al., "A Technical Overview of AV1" (arXiv v2, 8 Feb 2021)**

Source for all quotes: [arXiv 2008.06091](https://arxiv.org/pdf/2008.06091)
- "The film grain synthesis model parameters are decided on a frame by frame basis and are signaled in the frame header."
- "AV1 adopts an auto-regressive (AR) model to build the grain signal."
- "f(P(x, y)) scales the grain sample according to the collocated pixel intensity."
- The AR input "is drawn from a zero-mean unit-variance Gaussian distribution", and patches are placed at "pseudo random positions".
- The Intro calls it "A normative film grain synthesis unit". It runs out of the prediction loop because "the results of the film grain synthesis stage do not influence the prediction for subsequent frames."

**Mechanism and lab savings: Norkin and Birkbeck, AV1 film grain paper**

The file on the author's site is labeled DCC 2018. Source for all quotes: [Norkin & Birkbeck PDF](https://norkin.org/pdf/DCC_2018_AV1_film_grain.pdf)
- Generator: "pseudo-random generator is a shift-back linear-feedback shift register (LFSR)"; "the generator is initialized in the beginning of each row of 32×32 blocks"
- Template: "an AR process is run in a raster scan order to generate a 64×64 luma film grain template"; "Luma grain blocks of size 32×32 are randomly selected from the 64×64 template"
- Design intent: "mandatory support of the film grain synthesis in the AV1 video codec"; "should not be applied inside the video decoder loop"; "can be applied as part of the display processing chain"
- Statistical rather than exact vs the source: "the proposed technology removes film grain and adds similar grain, the objective metrics would not work well."; evaluation was an "informal subjective comparison"
- [Lab] Savings: "significant bitrate savings (up to 50%) on sequences with heavy film grain"
- Test setup: "The film grain was first removed from the sequences by hqdn3d denoising [12]"; "The first two sequences were encoded at QP30, and the latter at QP25."
- [tool-extracted, Fig. 8] 22,137 kbps vs 5,833 kbps (BreakingBad); 5,729 vs 2,821 kbps (LawrenceOfArabia)

**Netflix deployment**
- **Post:** "AV1 @ Scale: Film Grain Synthesis, The Awakening" by Li-Heng Chen, Andrey Norkin, Liwei Guo, Zhi Li, Agata Opalach and Anush Moorthy, published July 2, 2025. — [Netflix TechBlog](https://netflixtechblog.com/av1-scale-film-grain-synthesis-the-awakening-ee09cfdff40b)
- **Rollout:** "Since March, we've been rolling out FGS across scale" — [Netflix TechBlog](https://netflixtechblog.com/av1-scale-film-grain-synthesis-the-awakening-ee09cfdff40b)
- **What is sent and how grain is rebuilt:**
  - "the grain’s pattern and intensity are estimated and transmitted alongside the compressed video data." — [Netflix post, mirror copy](https://noise.getoto.net/2025/07/02/av1-scale-film-grain-synthesis-the-awakening/)
  - "the film grain is recreated and reintegrated into the video using a block-based method." — [mirror](https://noise.getoto.net/2025/07/02/av1-scale-film-grain-synthesis-the-awakening/)
  - "random 32x32 patches are extracted from the 64x64 noise template and added to the decoded video." — [Netflix TechBlog](https://netflixtechblog.com/av1-scale-film-grain-synthesis-the-awakening-ee09cfdff40b)
- **[Single-frame example]** "The visual comparison highlights a significant bitrate reduction of approximately 66%, with regular AV1 encoding at 8274 kbps compared to AV1 with FGS at 2804 kbps." [tool-extracted context: one frame of *They Cloned Tyrone*, not a catalog figure] — [Netflix TechBlog](https://netflixtechblog.com/av1-scale-film-grain-synthesis-the-awakening-ee09cfdff40b)
- **[Prod] Catalog sample:**
  - "we selected approximately 300 titles from the Netflix catalog, each with varying levels of graininess." — [Netflix TechBlog](https://netflixtechblog.com/av1-scale-film-grain-synthesis-the-awakening-ee09cfdff40b)
  - "illustrates a 36% reduction in average bitrate for resolutions of 1080p and above" — [mirror](https://noise.getoto.net/2025/07/02/av1-scale-film-grain-synthesis-the-awakening/)
  - "For resolutions below 1080p, the reduction in bitrate is relatively small, reaching only a 10% decrease" — [Netflix TechBlog](https://netflixtechblog.com/av1-scale-film-grain-synthesis-the-awakening-ee09cfdff40b)
- **[Prod] A/B test before rollout:** "A/B testing prior to rollout" … "showcased a smoother and more reliable Quality of Experience (QoE) for our members." — [Netflix TechBlog](https://netflixtechblog.com/av1-scale-film-grain-synthesis-the-awakening-ee09cfdff40b). Reported results:
  - "Bitrate at the start of the playback reduced by 24% and average bitrate by 31.6%" — [Netflix TechBlog](https://netflixtechblog.com/av1-scale-film-grain-synthesis-the-awakening-ee09cfdff40b)
  - "10% fewer rebuffers and a 5% reduction in rebuffer duration" — [Netflix TechBlog](https://netflixtechblog.com/av1-scale-film-grain-synthesis-the-awakening-ee09cfdff40b)
  - "Playback error rate reduced by approximately 3%." — [mirror](https://noise.getoto.net/2025/07/02/av1-scale-film-grain-synthesis-the-awakening/)
  - "Start play delay reduced by 10%" — [mirror](https://noise.getoto.net/2025/07/02/av1-scale-film-grain-synthesis-the-awakening/)
  - "Observed 10% fewer noticeable bitrate drops" — [mirror](https://noise.getoto.net/2025/07/02/av1-scale-film-grain-synthesis-the-awakening/)
  - "a 10% reduction in the time users spend adjusting their playback position" — [mirror](https://noise.getoto.net/2025/07/02/av1-scale-film-grain-synthesis-the-awakening/)
  - "About 0.7% of viewing hours shifted from lower resolutions" — [mirror](https://noise.getoto.net/2025/07/02/av1-scale-film-grain-synthesis-the-awakening/)
- **Quality-metric caveat** [tool paraphrase, not verbatim]: PSNR and VMAF penalize grain because the synthesized noise differs from the source noise, and no dedicated quality model yet exists for grain synthesis. The blog also says "synthesized noise effectively masks compression artifacts". — [Netflix TechBlog](https://netflixtechblog.com/av1-scale-film-grain-synthesis-the-awakening-ee09cfdff40b), [mirror](https://noise.getoto.net/2025/07/02/av1-scale-film-grain-synthesis-the-awakening/)

**AOMedia AFGS1 (blog post dated April 22, 2024)**

Source for all quotes: [AOMedia](https://aomedia.org/blog%20posts/new-film-grain-synthesis-specification-now-available/)
- "a new standalone film grain synthesis (FGS) specification, called AFGS1"
- "defines ITU-T T.35 registered user data to carry the FGS model parameters"
- "employs the identical film grain model used in the AV1 film grain synthesis tool"
- "is ready to be used with most modern video codecs without modifications to the underlying codec"
- [Claim] "allows reduced bitrates while achieving similar or better visual quality"
- [tool-extracted] The spec itself was released in January 2024.

### Inferences
- **Three fidelity relations hold at once.** ARFP needs vocabulary for all three:
  - Intermediate (non-grain) frames vs the reference decoder: bit-exact under both options.
  - Grain output vs the reference decoder: bit-exact under Option 1, "no perceptually significant differences" under Option 2.
  - Output vs the original source: only statistically similar ("similar grain").
- **AV1 is a working precedent for a two-tier contract.** It pairs an exact core with a synthetic layer whose perceptual bound is set *outside* the standard, by an accreditation program. If ARFP wants verifiable contracts, it must define that bound itself, for example by naming a metric and threshold, rather than delegate it.
- **Reproducibility depends on the option chosen.** The reference process uses an LFSR initialized from signaled data, per Norkin and Birkbeck. Option-1 decoders therefore produce identical grain, but conformance does not *require* identical grain, so ARFP cannot assume it across all "AV1-conformant" receivers.
- **Labeling precedent:** synthetic content is signaled in-band, through film_grain_params_present and the per-frame parameters in the frame header, and in AFGS1 through T.35 metadata. That is a machine-readable "this layer is generated" marker. No viewer-facing label is described in the Netflix post.
- **Evidence strength:** Netflix's numbers are vendor-reported production and A/B results with no independent audit. Norkin's "up to 50%" is a lab upper bound on heavy-grain clips, judged by informal subjective comparison.
- **Rollout date:** "Since March" in a post dated July 2, 2025 most plausibly means March 2025. The year is inferred, not stated in the quote.

### Gaps
- The two-option conformance text was verified in the spec's GitHub master-branch source. It was not verified in the approved "Version 1.0.0 with Errata 1" PDF (2019), whose fetched excerpt did not include the §7.2 body. The HTML is labeled a working draft.
- The spec's own normative wording for §7.18.3.2 (generator bit width and seeding) was not captured; the LFSR detail comes from Norkin and Birkbeck.
- No figure was found for the per-frame-header size of the grain parameters.
- The Netflix post does not say whether its A/B test held quality constant.
- The DCC 2018 venue comes from the file name on the author's site, not from the extracted text.

## 5. Meta Codec Avatars and comparable telepresence: bitrate or latent-code size per frame

### Takeaway
Codec Avatar systems send a per-frame latent code to a **person-specific** decoder that the receiver already holds. Pixel Codec Avatars uses "an 8x8 grid of 4 dimensional codes", which is 256 values per frame, and decodes in real time on a Quest 2. Deep Appearance Models says "only the latent code z needs to be sent across the network". **Neither fetched paper publishes a bitrate.**

### Cited Findings
- **Venue:** a CVF open-access PDF for PiCA appears under CVPR 2021. — [CVF open access](https://openaccess.thecvf.com/content/CVPR2021/papers/Ma_Pixel_Codec_Avatars_CVPR_2021_paper.pdf)
- **PiCA (Ma et al., arXiv 2104.04638).** Source for all quotes: [PiCA PDF](https://arxiv.org/pdf/2104.04638)
  - Latent size: "in our case an 8x8 grid of 4 dimensional codes." (Sec. 3)
  - Transmission: "upon receiving the latent code over the internet," (Sec. 1)
  - Decoding: the "Geometry Decoder takes the latent code as input and decodes a dense position map"; the expression decoder "uses the latent code and the viewing direction to decode a low resolution, view-dependent map of local codes."
  - Decoder size: "PiCA has 5.47M" [parameters] (Sec. 6.1)
  - Per-identity training: "We capture multiview video data for each identity" (Sec. 6)
  - On-device: "on a single Oculus Ouest [sic] 2 mobile VR headset, 5 avatars are rendered in realtime in the same scene." (Abstract)
  - Frame rates: "PiCA runs at ~50 FPS on average, showing the possibility of multi-way telepresence call." (Sec. 6.1); "PiCA hits the Quest 2's maximum framerate at 90 FPS." (Sec. 6.3)
  - Quantization: "are 8-bit quantized to execute on the DSP, with small quality drops." (footnote)
  - Scope: "This work only focuses on the *decoder*" (Sec. 7)
  - Bitrate: not stated.
- **Deep Appearance Models (Lombardi et al., Facebook Reality Labs, arXiv 1808.00362).** Source for all quotes: [DAM PDF](https://arxiv.org/pdf/1808.00362)
  - "only the latent code $\mathbf z$ needs to be sent across the network, reducing bandwidth requirements."
  - "we limit our scope to person-specific models (i.e., a person can drive only his or her own avatar)."
  - "this takes approximately 5 milliseconds on an NVIDIA GeForce GTX 1080 graphics card."
  - The target is "less than 11.1 milliseconds to achieve 90Hz rendering."
  - Headset-encoder latent: "the latent vector y has 256 dimensions."
  - The size of z is not stated explicitly. The tool inferred 128 from a comparison, which is unverified. No bitrate is stated.

### Inferences
- [Arith, illustrative only, not published] 256 values/frame at fp16 is 512 B/frame: about 123 kbps at 30 fps or 369 kbps at 90 fps. At 8 bits it is 256 B/frame: about 61 kbps at 30 fps or 184 kbps at 90 fps. Both figures are before any entropy coding.
- **Heaviest "receiver must already hold" requirement in this set:** a decoder trained per identity from multi-view capture. DAM's rule that "a person can drive only his or her own avatar" also makes identity binding an authorization question, which is directly relevant to ARFP's provenance labeling.
- **Fidelity class:** perceptual. The papers report non-zero reconstruction error, and on-device 8-bit quantization adds "small quality drops".

### Gaps
- No published per-frame bitrate for Codec Avatars appears in the fetched sources.
- Not fetched, though they may contain bandwidth figures: Meta blog posts, Auto-CARD (arXiv 2304.11835) and Modular Codec Avatars (arXiv 2008.11789).
- The DAM venue (often cited as SIGGRAPH 2018) was not verified.
- PiCA's encoder-side cost and latency are out of the paper's scope.

## 6. Google Draco compression claims; OGC 3D Tiles status and its level-of-detail and refinement model

### Takeaway
**Draco** is a deterministic geometry codec that is lossy through quantization, with error bounded by the bit setting. Google's 2017 launch post makes only qualitative claims. Cesium's 2018 measurement on a New York City tileset of 1.1 million buildings went from 738 MB (glTF + gzip) to 179 MB with Draco and 149 MB with Draco + gzip **[Vendor]**.

**3D Tiles** 1.0 (2018) and 1.1 (approved 2022-12-17, released 2023-01-09, per Cesium's changelog) are OGC Community Standards. The format organizes tiles in a hierarchical level-of-detail (HLOD) tree. Each tile declares a `geometricError` in meters, and the client uses screen-space error to decide when to refine. Refinement is either REPLACE or ADD. This is a producer-declared, bounded-error contract.

### Cited Findings
**Draco**
- Description: "Draco is a library for compressing and decompressing 3D geometric meshes and point clouds." — [Draco GitHub](https://github.com/google/draco)
- Quantization: "Any value other than `0` will quantize the input values for the specified attribute to that number of bits."; "default is 11 for the position coordinates"; "It is up to your project to decide how much deviation it will tolerate." — [Draco GitHub](https://github.com/google/draco)
- [Claim] "applications using 3D graphics can be significantly smaller without compromising visual fidelity." — [Draco GitHub](https://github.com/google/draco); the same sentence appears in the [Google Open Source Blog launch post, Jan 13, 2017, Jamieson Brettle and Frank Galligan](https://opensource.googleblog.com/2017/01/introducing-draco-compression-for-3d.html)
- [Claim] "VR and AR scenes can now be transmitted with a fraction of the bandwidth, rendered quickly and look fantastic." — [Google Open Source Blog](https://opensource.googleblog.com/2017/01/introducing-draco-compression-for-3d.html)
- Launch test settings: "Tests ran with textures and positions quantized at 14-bit precision, normal vectors at 7-bit precision." The post's table of compression ratios is an image, and its values could not be extracted. — [Google Open Source Blog](https://opensource.googleblog.com/2017/01/introducing-draco-compression-for-3d.html)
- Release notes: "Improved mesh compression up to 10% (on average ~2%)" (v1.3.0). The latest release shown is "Version 1.5.7 release.", with no date. — [Draco GitHub](https://github.com/google/draco)
- **[Vendor] Cesium measurement (Gabby Getz, April 9, 2018).** Source for all items: [Cesium blog](https://cesium.com/blog/2018/04/09/draco-compression/)
  - [tool-extracted table] NYC tileset of 1.1M buildings: glTF + gzip 738 MB; glTF + Draco 179 MB; Draco + gzip 149 MB.
  - Load time: "Load time: 18.921 seconds" (gzip only) vs "Load time: 10.548 seconds" (Draco + gzip).
  - GPU dequantization: "there is a 52% savings in memory used by the GPU with no difference in file size", with "no differences in visual quality".
  - [tool-extracted table] Milk Truck .bin: 107 KB → 14.0 KB. Buggy .bin: 7.6 MB → 0.824 MB.
  - Settings: "with the default compression level of 7 for all attributes." and "a Draco compression level of 5."

**3D Tiles**
- Description: "3D Tiles is an open specification for sharing, visualizing, fusing, and interacting" — [CesiumGS/3d-tiles](https://github.com/CesiumGS/3d-tiles)
- Version 1.0: "Version 1.0, 2018-06-06"; "was submitted to the Open Geospatial Consortium (OGC), and approved as an OGC Community Standard" [tool-extracted: approved 2018-12-14]. The OGC document link is http://docs.opengeospatial.org/cs/18-053r2/18-053r2.html (not fetched). — [CHANGES.md](https://raw.githubusercontent.com/CesiumGS/3d-tiles/main/CHANGES.md), [CesiumGS/3d-tiles](https://github.com/CesiumGS/3d-tiles)
- Version 1.1: "Version 1.1, 2023-01-09"; "was submitted to the Open Geospatial Consortium (OGC), and approved as an OGC Community Standard" [tool-extracted: approved 2022-12-17]. — [CHANGES.md](https://raw.githubusercontent.com/CesiumGS/3d-tiles/main/CHANGES.md)
- Geometric error: "A tile's geometric error defines the selection metric for that tile."; "Its value is a nonnegative number that specifies the error, in meters,"; "In a client implementation, geometric error is used with other screen space metrics"; "If the introduced SSE exceeds the maximum allowed, then the tile is refined" — [3D Tiles spec source](https://raw.githubusercontent.com/CesiumGS/3d-tiles/main/specification/README.adoc)
- Refinement: "If the tile has replacement refinement, the children tiles are rendered in place of the parent"; "If the tile has additive refinement, the children are rendered in addition to the parent tile." — [3D Tiles spec source](https://raw.githubusercontent.com/CesiumGS/3d-tiles/main/specification/README.adoc)
- Hierarchy: "Tiles are organized in a tree which incorporates the concept of Hierarchical Level of Detail (HLOD)" — [3D Tiles spec source](https://raw.githubusercontent.com/CesiumGS/3d-tiles/main/specification/README.adoc)
- Deprecations: "These formats were deprecated in 3D Tiles 1.1 and may be removed in a future version of 3D Tiles." — [3D Tiles spec source](https://raw.githubusercontent.com/CesiumGS/3d-tiles/main/specification/README.adoc)

### Inferences
- [Arith] NYC tileset: 738 → 179 MB is about 4.1× (about 76% smaller); 738 → 149 MB is about 5.0× (about 80% smaller). Load time 18.921 → 10.548 s is about 44% faster.
- **Draco fidelity class: bounded.** Quantizing to N bits over a bounding box limits each coordinate's error to about half a quantization step. That follows from standard quantization arithmetic and is not a quoted Draco guarantee. Decoding is deterministic. Draco is the cleanest "bounded, not generated" precedent here.
- **3D Tiles is the nearest existing analog to an ARFP fidelity contract.** Each tile carries an error in meters, declared by the producer, and the receiver uses it to decide whether to fetch a refinement. The bound is declared, not verified; the receiver trusts the producer.
- **REPLACE vs ADD map onto ARFP modes:** ADD resembles "reference + delta", and REPLACE resembles "swap in a higher-fidelity representation".

### Gaps
- Google published no primary compression ratio for Draco that could be extracted (the launch table is an image). The only quantitative figures are Cesium's vendor measurements.
- The OGC document number and approval date for 3D Tiles 1.1 were not verified on ogc.org, because the docs.ogc.org fetch failed. The dates come from Cesium's changelog and the tool's reading of it.
- Draco release dates were not captured.

## 7. Games: deterministic lockstep (Age of Empires, 2001) and client-side prediction with server reconciliation (Valve)

### Takeaway
**Age of Empires** sent only user commands. Every machine ran the identical simulation in "Turns … typically 200 msec in length", which met a 28.8k-modem, 8-player target. Passing state instead "would have limited us to 250 moving units". The price was that any nondeterminism, such as a different number of random-number calls or terrain sounds inside the simulation, caused out-of-sync failures. These were detected by checksums, stopped the game, and were notoriously hard to debug.

**Valve's model** predicts only the local player's own actions and keeps the server authoritative. When the server's values disagree with the prediction, the client "re-simulates all of the commands it ran with bad data", starting from the last state the server acknowledged. This can cause a "noticeable hitch".

### Cited Findings
**Age of Empires**

Source: "1500 Archers on a 28.8: Network Programming in Age of Empires and Beyond", Game Developer, March 22, 2001. The page byline lists Paul Bettner. All quotes below are from [Game Developer](https://www.gamedeveloper.com/programming/1500-archers-on-a-28-8-network-programming-in-age-of-empires-and-beyond).
- What was sent: "run the exact same simulation on each machine"; "passing each an identical set of commands that were issued by the users at the same time". [tool paraphrase: commands were scheduled two turns ahead.]
- Targets: "Support a target platform of: 16MB Pentium 90 with a 28.8 modem"; "Support for 8 players in multiplayer"; "Target consistent frame rate of 15fps on the minimum machine config"
- Timing and latency: "Turns were typically 200 msec in length"; "latency swings of 20 to 1,000 milliseconds"; "250 milliseconds of command latency was not even noticed"
- Overheads and command rate: "(Total of 2 bytes was used for speed control)"; user commands came "averaging about every 1.5 to 2 seconds" [context tool-paraphrased]
- Rejected alternative: passing state "would have limited us to 250 moving units"
- Out-of-sync detection: "Any simulation that ran differently was tagged as "out of sync" and the game stopped."
- Causes: "programmers were not used to having to write code that used the same number of calls to random"; "having random terrain sounds inside the simulation would cause the games to behave differently"
- Debugging effort: "As much as we check-summed the world, the objects, the pathfinding, targeting and every other system"; "Giant (50MB) message traces and world object dumps to sift through"; "The difficulty with finding out-of-sync errors is that very subtle differences would multiply over time."; "it seemed that there was always one more thing that slipped just under the radar"; "Synchronization debugging was probably at the top of this list as we started development on RTS3."

**Valve Prediction page.** Source for all quotes: [Valve Developer Community: Prediction](https://developer.valvesoftware.com/wiki/Prediction)
- "the client predicting the effects of the local player's actions without waiting for the server to confirm them."
- "The client's predicted value will be tested against received server values."
- "the client goes back and re-simulates all of the commands it ran with bad data."
- "this can cause a noticeable hitch in the player's position and state."
- "All client-side variables modified by predicted player input must be added to a prediction table."
- "You can use cl_predictionlist and cl_pdump to debug this."

**Valve: Yahn W. Bernier, 2001.** Source for all quotes: [Valve Developer Community: Latency Compensating Methods…](https://developer.valvesoftware.com/wiki/Latency_Compensating_Methods_in_Client/Server_In-game_Protocol_Design_and_Optimization)
- "perform the client's movement locally"
- "There still is an authoritative server running the simulation just as noted above."
- "the last acknowledged movement from the server is used as a starting point"
- "the client will most often end up running the same commands over and over again"
- "By default, Half-Life sends 20 updates per second to each player"
- Clients may "ask for as many updates per second as he or she wants"

### Inferences
- **Lockstep is the purest precedent for ARFP's "procedural recipe" mode.** It sends inputs instead of outputs, and reconstruction is bit-exact by construction. It also fails hard: the game stops on any divergence, and every peer must run identical code. Checksummed state is the minimum safeguard for divergence. ARFP recipes would need output hashes and a pinned version of the generator.
- **Prediction plus reconciliation is the precedent for "the receiver generates, then the authority corrects".** Predicted state is provisional and gets overwritten by authoritative state. ARFP would need a matching authoritative-correction path and a policy for visible corrections.
- Neither mechanism shows the user which state is predicted and which is authoritative.

### Gaps
- Valve's main "Source Multiplayer Networking" article could not be fetched; it errored twice and the Wayback Machine is blocked for the fetch tool. Its tick rate, `cl_interp` (100 ms) default, snapshot delta compression and lag-compensation details are therefore **not verified** here.
- Not captured: the Age of Empires article's per-player bandwidth figure in bytes per second, if it gives one.
- Not verified: Mark Terrano's co-authorship (absent from the fetched page metadata) and the Bernier paper's original venue (often cited as GDC 2001).

## 8. Semantic communication for 6G: an authoritative survey, ITU-R M.2160 on AI capabilities, and published criticisms

### Takeaway
**Survey.** A leading recent survey, Chaccour, Saad, Debbah, Han and Poor in IEEE Communications Surveys & Tutorials (COMST) 2025, argues for "a move from data-driven networks towards knowledge-driven ones". It calls for reasoning-driven, AI-native networks and new "reasoning capacity" measures "that could go beyond Shannon's bound". It also concedes that "the research landscape remains limited".

**ITU-R M.2160 (11/2023)** includes "Artificial Intelligence and Communication" as a usage scenario and "Applicable AI-related capabilities" as a capability. It expects an "AI-native new air interface", phrased as expectations rather than requirements. The fetched text does not mention semantic transmission specifically.

**Criticisms.** The published criticism found is "wireless hallucination" in generative-AI-enabled communications. I found no source that explicitly argues "lack of verifiable guarantees".

### Cited Findings
- **Survey bibliographic:** Chaccour et al., "Less Data, More Knowledge: Building Next-Generation Semantic Communication Networks", IEEE COMST vol. 27, no. 1, pp. 37–76, 2025, published online 2024-10-23, DOI 10.1109/COMST.2024.3412852. — [Princeton record](https://collaborate.princeton.edu/en/publications/less-data-more-knowledge-building-next-generation-semantic-commun/)
- **Survey central claim:** "we propose the first rigorous and holistic vision of an end-to-end semantic communication network"; "reasoning-driven AI-native networks which can perform versatile logic and generalizable intelligence" — [Princeton record](https://collaborate.princeton.edu/en/publications/less-data-more-knowledge-building-next-generation-semantic-commun/)
- **Survey arXiv v1 (2022-11-25).** Source for all quotes: [arXiv 2211.14343](https://arxiv.org/abs/2211.14343)
  - "the research landscape remains limited"
  - "requires a move from data-driven networks towards knowledge-driven ones"
  - "minimalism, generalizability, and efficiency so as to do more with less"
  - "capture causal and associational relationships in datastreams"
  - "new "reasoning capacity" measures that could go beyond Shannon's bound"
  - "the traditional transmitter and receiver now become a teacher and apprentice"
- **Second survey:** Getu, Kaddoum and Bennis, "Tutorial-Cum-Survey on Semantic and Goal-Oriented Communication…" (arXiv, 4 July 2023): "exposes the fundamental and major challenges of SemCom and goal-oriented SemCom" — [arXiv 2308.01913](https://arxiv.org/abs/2308.01913)
- **ITU-R M.2160-0 (cover dated "(11/2023)").** Source for all quotes: [ITU-R M.2160-0 PDF](https://www.itu.int/dms_pubrec/itu-r/rec/m/R-REC-M.2160-0-202311-I!!PDF-E.pdf)
  - Usage scenarios (§3): "Immersive Communication"; "Hyper Reliable and Low-Latency Communication"; "Massive Communication"; "Ubiquitous Connectivity"; "Artificial Intelligence and Communication"; "Integrated Sensing and Communication"
  - AI scenario: "This usage scenario would support distributed computing and AI applications."; "Typical use cases include IMT-2030 assisted automated driving,"
  - AI capability (§4, item 12): "Applicable AI-related capabilities refer to the ability to provide certain functionalities throughout" … "IMT-2030 to support AI enabled applications."; "These functionalities include distributed data processing, distributed learning, AI computing,"
  - AI in the air interface (§2.2.1): "It is expected that the air-interface would be enhanced by AI models."; "IMT-2030 could serve as an AI-enabling infrastructure capable of providing services for intelligent applications."
  - AI-native (§2.3.1): "IMT-2030 is expected to consider an appropriate AI-native new air interface"; "An appropriate AI-native radio network would enable automated and intelligent networking services"
  - Overarching aspects: "sustainability, security and resilience,"; "IMT-2030 system is expected to be secure by design."
  - Resilience defined: "Resilience refers to capabilities of the networks and systems to continue operating correctly"
- **Criticism:** Wang et al., "Wireless Hallucination in Generative AI-enabled Communications: Concepts, Issues, and Solutions" (arXiv, March 8, 2025). Source for all quotes: [arXiv 2503.06149](https://arxiv.org/abs/2503.06149)
  - "We refer to this phenomenon as wireless hallucination,"
  - Causes: "Due to data limitations, random generation, and dynamic environments"
  - Generative AI "may generate channel information or optimization strategies that violate physical laws"
  - Consequence: "which results in invalid channel information, spectrum wastage, and low communication reliability."
  - Status: "remains underexplored"

### Inferences
- **M.2160 is a framework, not a protocol.** It gives AI-native ideas a standards "home" but no normative semantics; its AI language is "would", "could" and "is expected to".
- **The semantic-communication literature is mostly vision, not deployment.** "Beyond Shannon" reasoning capacity is a proposed measure, and no deployed 6G semantic system with measured savings turned up in the fetched sources.
- **The hallucination critique applies directly to ARFP's latent and generative modes.** Generated reconstructions can be confidently wrong. That supports ARFP's rule to label generated content, plus an exact or bounded tier for content that must be faithful.

### Gaps
- No peer-reviewed critique was found that explicitly argues semantic communication lacks *verifiable guarantees*. A targeted follow-up search is needed.
- Not verified: whether M.2160 uses the term "semantic communication", and the Getu et al. journal venue (arXiv lists none).
- The 3GPP 6G study-item status is out of scope and was not researched.

## 9. Neural video enhancement deployed at scale (NVIDIA RTX Video Super Resolution)

### Takeaway
NVIDIA RTX Video Super Resolution launched on February 28, 2023. It is receiver-only neural enhancement: it upscales Chrome and Edge video "up to 4K" and removes "blocky compression artifacts" using the Tensor Cores in RTX 30- and 40-series GPUs. The sender does not participate, and nothing is signaled in-band or labeled.

### Cited Findings
- Post: "Pixel Perfect: RTX Video Super Resolution Now Available for GeForce RTX 40 and 30 Series GPUs", Brian Choi, February 28, 2023. — [NVIDIA Blog](https://blogs.nvidia.com/blog/rtx-video-super-resolution/)
- Function: "AI-powered upscaling feature enhances streaming video content in Google Chrome and Microsoft Edge browsers."; "The AI removes blocky compression artifacts and improves the video’s sharpness and clarity."; output scales "up to 4K, matching their display resolution"; it uses "AI processors with Tensor Cores" — [NVIDIA Blog](https://blogs.nvidia.com/blog/rtx-video-super-resolution/)
- [Claim, vendor-cited statistics] "Nearly 80% of internet bandwidth today is streaming video."; "90% of that content streams at 1080p or lower" — [NVIDIA Blog](https://blogs.nvidia.com/blog/rtx-video-super-resolution/)
- [tool-extracted] Requires Chrome 110.0.5481.105 or later, or Edge 110.0.1587.56. Users choose among four quality levels. — [NVIDIA Blog](https://blogs.nvidia.com/blog/rtx-video-super-resolution/)

### Inferences
- **The "unilateral receiver" end of the spectrum.** The sender ships ordinary video and the receiver adds generated detail. Fidelity to the source is unbounded and statistical, and the viewer is not told which pixels were synthesized. By contrast, in NAS the sender ships the enhancement model for its own content.
- NVIDIA claims no bandwidth saving. The claimed value is better quality at existing bitrates.

### Gaps
- Not found: install-base or usage figures.
- Not researched: Microsoft Edge's own video super resolution, RTX Video HDR, and other at-scale deployments.
- The fetched text does not state verbatim that processing runs locally.

## 10. Cross-cutting comparison for the ARFP review: what is sent, what the receiver holds, savings, and fidelity class

### Takeaway
Across these precedents, savings grow with how much the receiver already holds and how much fidelity is given up.
- **Bit-exact recipe schemes** (lockstep) move the least data but break on any nondeterminism.
- **Bounded schemes** (Draco quantization, 3D Tiles `geometricError`, AV1 grain Option 1) carry contracts a reviewer can check.
- **Generative schemes** (talking heads, avatars, super-resolution) claim roughly 2–10× in the lab but give only perceptual similarity. None of the fetched papers describes labeling generated output.

AV1 film grain is the one deployed standard in this set that does both: it signals synthetic content in-band, and it writes a two-tier conformance contract (exact, or "no perceptually significant differences").

### Cited Findings

| System (date) | What is sent | Receiver must hold or run | Reported savings (evidence type) | Fidelity vs source | Source |
|---|---|---|---|---|---|
| face-vid2vid (arXiv 2020-11-30; v3 2021-04-02) | "3K+6 numbers" per frame, fp16 and arithmetic-coded ("53.03 B" adaptive); source image once | Generator plus source image | "one-tenth of the bandwidth" of H.264 at the same visual quality [Lab] | Perceptual; fails on large occlusions | [arXiv](https://arxiv.org/abs/2011.15126), [PDF](https://arxiv.org/pdf/2011.15126) |
| Gemino (arXiv v4 2023-10-19) | Low-res VP8/VP9 per frame ("~15 Kbps" at 128×128); sparse high-res reference | Personalized "82M parameters" model ("about a GB" unoptimized) plus reference frame | "2.2-5x lower bitrate" at equal perceptual quality [Lab] | Exact base layer; perceptual upsampling | [arXiv](https://arxiv.org/abs/2209.10507), [PDF](https://arxiv.org/pdf/2209.10507) |
| NAS (OSDI 2018) | Standard video chunks plus DNN chunks | Client-side DNN inference | "saving 17.13% of bandwidth" at the same QoE; "43.08%" QoE gain [Lab] | Exact low-res decode; perceptual super-resolution | [KOASAS](https://koasas.kaist.ac.kr/handle/10203/246781?mode=full), [GitHub](https://github.com/kaist-ina/NAS_public) |
| AV1 FGS (spec "Version 1.0.0 with Errata 1", 2019) and Netflix (post 2025-07-02) | Denoised video plus per-frame grain parameters "signaled in the frame header" | Grain synthesis per spec §7.18.3 (LFSR plus AR model) | "36% reduction in average bitrate" at ≥1080p across about 300 titles [Prod]; "24%" start and "31.6%" average bitrate in A/B [Prod]; "up to 50%" [Lab] | Intermediate frames exact; grain exact (Option 1) or perceptual (Option 2); statistical vs source | [Spec source](https://raw.githubusercontent.com/AOMediaCodec/av1-spec/master/08.decoding.process.md), [Netflix](https://netflixtechblog.com/av1-scale-film-grain-synthesis-the-awakening-ee09cfdff40b), [Norkin](https://norkin.org/pdf/DCC_2018_AV1_film_grain.pdf) |
| PiCA (CVPR 2021) / Deep Appearance Models | Latent code per frame ("8x8 grid of 4 dimensional codes") | Person-specific decoder ("5.47M" parameters) | None published | Perceptual | [PiCA](https://arxiv.org/pdf/2104.04638), [DAM](https://arxiv.org/pdf/1808.00362) |
| Draco (2017) | Quantized, compressed mesh | Draco decoder | NYC tileset 738 → 179 MB [Vendor] | Bounded by quantization bits | [Cesium](https://cesium.com/blog/2018/04/09/draco-compression/), [GitHub](https://github.com/google/draco) |
| 3D Tiles 1.0 / 1.1 (OGC Community Standard 2018 / 2022) | Tile tree with `geometricError` "in meters" | Renderer using screen-space-error refinement | Not applicable | Bounded, declared by the producer | [Spec source](https://raw.githubusercontent.com/CesiumGS/3d-tiles/main/specification/README.adoc), [CHANGES.md](https://raw.githubusercontent.com/CesiumGS/3d-tiles/main/CHANGES.md) |
| Age of Empires lockstep (2001) | User commands per 200 ms turn | Identical deterministic simulation on every machine | Met the "28.8 modem", 8-player target; state-passing "would have limited us to 250 moving units" [design account] | Bit-exact required; divergence stops the game | [Game Developer](https://www.gamedeveloper.com/programming/1500-archers-on-a-28-8-network-programming-in-age-of-empires-and-beyond) |
| Half-Life / Source prediction (2001 onward) | Commands up; server updates down ("20 updates per second" by default in Half-Life) | Local prediction plus re-simulation | Not applicable | Provisional; overwritten by the authoritative server | [Bernier](https://developer.valvesoftware.com/wiki/Latency_Compensating_Methods_in_Client/Server_In-game_Protocol_Design_and_Optimization), [Prediction](https://developer.valvesoftware.com/wiki/Prediction) |
| RTX VSR (2023) | Nothing extra | RTX GPU with the vendor model | None; quality claim only | Perceptual; unlabeled | [NVIDIA](https://blogs.nvidia.com/blog/rtx-video-super-resolution/) |
| 6G semantic communication (COMST 2025; M.2160 2023) | Semantic or knowledge representations (vision) | Shared knowledge and models | None measured in the sources | Unspecified; hallucination risk | [Princeton](https://collaborate.princeton.edu/en/publications/less-data-more-knowledge-building-next-generation-semantic-commun/), [ITU](https://www.itu.int/dms_pubrec/itu-r/rec/m/R-REC-M.2160-0-202311-I!!PDF-E.pdf), [arXiv 2503.06149](https://arxiv.org/abs/2503.06149) |

- **Lab vs production.** The largest numbers come from lab work:
  - "one-tenth of the bandwidth" — [arXiv](https://arxiv.org/abs/2011.15126)
  - "2.2-5x lower bitrate" — [arXiv](https://arxiv.org/abs/2209.10507)
  - "up to 50%" — [Norkin](https://norkin.org/pdf/DCC_2018_AV1_film_grain.pdf)

  The at-scale production figures are smaller:
  - "36% reduction in average bitrate for resolutions of 1080p and above" — [Netflix mirror](https://noise.getoto.net/2025/07/02/av1-scale-film-grain-synthesis-the-awakening/)
  - "average bitrate by 31.6%" — [Netflix](https://netflixtechblog.com/av1-scale-film-grain-synthesis-the-awakening-ee09cfdff40b)
- **Cost of models the receiver must hold:**
  - Gemino: "about a GB" — [Gemino PDF](https://arxiv.org/pdf/2209.10507)
  - PiCA: "5.47M" parameters — [PiCA](https://arxiv.org/pdf/2104.04638)
  - Deep Appearance Models: person-specific only — [DAM](https://arxiv.org/pdf/1808.00362)
  - NAS: DNN chunks "streaming together with video chunks" — [NAS GitHub](https://github.com/kaist-ina/NAS_public)
- **Quality metrics penalize correct synthesis:**
  - "the objective metrics would not work well" — [Norkin](https://norkin.org/pdf/DCC_2018_AV1_film_grain.pdf)
  - Gemino adopts LPIPS because it is "more reflective of how natural the synthesized frame feels" — [Gemino PDF](https://arxiv.org/pdf/2209.10507)

### Inferences
- **A fidelity taxonomy for ARFP, with a precedent for each tier:**
  1. Exact: lockstep; AV1 Option 1; the base layers in Gemino and NAS.
  2. Bounded and declared: Draco quantization bits; 3D Tiles `geometricError` in meters.
  3. Perceptual, defined externally: AV1 Option 2, where an accreditation program defines "perceptually significant differences".
  4. Generative, unbounded: talking heads, avatars, super-resolution, and synthesized grain compared with the source.
- **Labeling precedent.** In-band signaling of synthesized layers already exists (AV1 grain parameters; AFGS1 T.35 metadata). None of the fetched sources describes a viewer-facing label.
- **Correction-channel precedents:** face-vid2vid's source-frame update; Gemino's sparse reference stream; Valve's server reconciliation. Lockstep has no correction path; it halts.
- **Risks with documented precedent for ARFP:**
  - Determinism drift (Age of Empires out-of-sync bugs).
  - Model distribution and per-person training cost (Gemino, PiCA, Deep Appearance Models).
  - Large-motion and occlusion failures (face-vid2vid; Gemino's account of earlier methods).
  - Metrics that penalize correct synthesis (Norkin; Netflix).

### Gaps
- No independent replication of any savings number was found; every figure is from authors or vendors.
- No source in this set offers a cryptographic or otherwise verifiable guarantee that a generated reconstruction matches the sender's intent. This remains open for ARFP's "contract" concept.
- I did not systematically search for 2026 updates to these systems. The most recent primary items found are the Netflix post (2025-07-02), the wireless-hallucination paper (2025-03-08) and the COMST issue (2025).
