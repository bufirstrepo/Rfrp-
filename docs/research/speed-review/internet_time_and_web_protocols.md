# Where time and bytes go on today's internet, and deployed web-protocol features that exploit what the receiver already holds

*Compiled 2026-10-11 for the ARFP engineering review. How the quotes were collected: direct `curl` to rfc-editor.org, hpbn.co, chromium.org and similar hosts was blocked in the research environment, so every source was read through a web-fetch tool that pulls verbatim excerpts. That tool caps each quote at about 125 characters, so long sentences appear as consecutive quoted fragments. Text in quotation marks is verbatim as the tool returned it. Text marked "(tool paraphrase)" is the tool's summary, not the source's wording. Evidence tags: **[Measured-prod]** production or real-user data; **[Measured-lab]** lab, emulation or controlled test; **[Spec]** normative standard text; **[Claim]** a vendor or author statement without data shown; **[Projection]** a forecast; **[Arithmetic]** my own calculation from cited numbers.*

## 1. Belshe (2010), "More Bandwidth Doesn't Matter (much)": page load time vs. bandwidth and vs. RTT

### Takeaway
Belshe simulated 25 popular pages. Page load time (PLT) improved very little once bandwidth passed about 5 Mbps: going from 5 to 10 Mbps gave a 5% PLT improvement, and at 10 Mbps pages used only about 16% of the link. Every 20 ms cut from RTT gave a 7–15% PLT reduction across the whole tested range, which Grigorik's HPBN book describes as a "linear" improvement. A 2025 Montana State/Akamai re-test finds the rule does not hold for every page (18% of sites are mainly bandwidth-limited). Treat the 2010 numbers as directionally right but dated.

### Cited Findings
**Original source (Belshe's own post, dated May 24, 2010):**
- Method for the bandwidth sweep: "we've chosen fixed values for packet loss (0%) and round-trip-time (60ms)"; "In this test we're downloading a simulation of 25 of the web's most popular web pages." — [Belshe, belshe.com (May 24, 2010)](https://www.belshe.com/2010/05/24/)
- Method for the RTT sweep: "For this test, we fix the bandwidth at 5Mbps, and vary the RTT from 0ms to 240ms." — [Belshe](https://www.belshe.com/2010/05/24/)
- **[Measured-lab]** Bandwidth: "there are diminishing returns as the bandwidth gets higher"; "An increase from 5Mbps to 10Mbps amounts to a 5% improvement in Page Load Times." — [Belshe](https://www.belshe.com/2010/05/24/)
- **[Measured-lab]** Link utilization: "At 1Mbps, web pages can be downloaded at ~69% of the total bandwidth capacity." "At 10Mbps, however, web pages can only be downloaded at ~16% of the total capacity" — [Belshe](https://www.belshe.com/2010/05/24/)
- **[Measured-lab]** RTT: "Continued reductions in RTT always helps, even when RTT is low."; "reducing the RTT always helps the overall PLT."; "each 20ms yielded 7-15% reduction in PLT." — [Belshe](https://www.belshe.com/2010/05/24/)
- Conclusions: more bandwidth means "the effect on Web Browsing will be a minimal improvement."; "decreasing RTT, regardless of current bandwidth always helps make web browsing faster." — [Belshe](https://www.belshe.com/2010/05/24/)
- The post links to the full paper at `http://docs.google.com/a/chromium.org/viewer?a=v&pid=sites&srcid=Y2hyb21pdW0ub3JnfGRldnxneDoxMzcyOWI1N2I4YzI3NzE2`. I did not fetch it. — [Belshe](https://www.belshe.com/2010/05/24/)

**Reproduction in High Performance Browser Networking (Grigorik), Chapter 10:**
- "the connection bandwidth is incrementally increased from 1 Mbps up to 10 Mbps."; "upgrading the connection from 1 to 2 Mbps nearly halves the page loading time"; "By the time the available bandwidth exceeds 5 Mbps, we are looking at single-digit percent improvements"; "upgrading from 5 Mbps to 10 Mbps results in a mere 5% improvement in page loading times" — [hpbn.co ch. 10, Primer on Web Performance](https://hpbn.co/primer-on-web-performance/)
- "for every 20 millisecond improvement in latency, we have a linear improvement in page loading times". The figure is credited to "Mike Belshe, More Bandwidth Doesn't Matter (Much)". — [hpbn.co ch. 10](https://hpbn.co/primer-on-web-performance/)
- Dated context from about 2013: "an average consumer in the United States is already accessing the Web with 5 Mbps+ of available bandwidth" — [hpbn.co ch. 10](https://hpbn.co/primer-on-web-performance/)
- Grigorik's 2012 blog version: "Upgrading your connection from 1Mbps to 2Mbps halves the PLT, but quickly thereafter we are into diminishing returns."; "In fact, upgrading from 5Mbps to 10Mbps results in a mere 5% improvement in page loading times!"; "For every 20ms improvement in latency, we have a linear improvement in page loading times"; "When Mike Belshe published his study in 2010, average worldwide RTT to Google was ~100ms, and ~60-70ms within the US." — [Grigorik, igvita.com (July 19, 2012)](https://www.igvita.com/2012/07/19/latency-the-new-web-performance-bottleneck/)
- HPBN's general claims: "Latency, not bandwidth, is the performance bottleneck for most websites!" — [hpbn.co ch. 1](https://hpbn.co/primer-on-latency-and-bandwidth/). Also "In most cases, latency, not bandwidth, is the bottleneck for TCP" and "the performance of many web applications is often limited by the roundtrip time between server and client" — [hpbn.co ch. 2](https://hpbn.co/building-blocks-of-tcp/)

**Why the bandwidth goes unused (TCP slow start):**
- "we start with a small congestion window and double it for every roundtrip — i.e., exponential growth."; the initial window was "increased once more to 10 segments by RFC 6928 in April 2013." — [hpbn.co ch. 2](https://hpbn.co/building-blocks-of-tcp/)
- **[Arithmetic in source]** "264 ms to transfer a 64 KB file on a new TCP connection with 56 ms roundtrip time between the client and server!" versus "The same request made on the same connection, but without the cost of the three-way handshake and the penalty of the slow-start phase, now took 96 milliseconds" — [hpbn.co ch. 2](https://hpbn.co/building-blocks-of-tcp/)
- **[Spec]** RFC 6928 (April 2013, Experimental) sets the initial window to "min (10*MSS, max (2*MSS, 14600))". **[Measured-prod]**, from Google front-end experiments: "The average web search latency improvement over all responses in AvgDC is 11.7% (68 ms) and 8.7% (72 ms) in SlowDC." — [RFC 6928](https://www.rfc-editor.org/rfc/rfc6928.txt)

**A recent counterpoint (2025):**
- **[Measured-lab]** Mostafa, Wittie and Goel (Montana State University and Akamai): "Our results show that 18% of websites are primarily limited by bandwidth with others limited by bandwidth to some extent."; "we do not observe the diminishing improvements to page performance of additional bandwidth for all pages"; their results are "Somewhat contrary to results observed by Belshe and Grigorik." — [arXiv 2503.03641v1](https://arxiv.org/html/2503.03641v1)
- Their method: "We chose 43 pages from the list of Alexa top 100 pages, excluding adult content" (plus 2 news sites). Tests start at "bandwidth of 256 Kbps and latency of 180 ms". (tool paraphrase:) bandwidth doubles up to 8 Mbps and then rises in 8 Mbps steps, latency improves in 10 ms steps, NetEm does the emulation, and the metric is Perceptual Speed Index rather than PLT. — [arXiv 2503.03641v1](https://arxiv.org/html/2503.03641v1)

### Inferences
- Belshe's "7–15% per 20 ms" and Grigorik's "linear" do not contradict each other. A constant number of milliseconds saved per 20 ms of RTT is a linear relationship, and the same saving becomes a larger percentage as total PLT shrinks.
- The ~16% link utilization at 10 Mbps is the most direct evidence that 2010-era page loads were limited by round trips (handshakes, slow start, chains of dependent requests) rather than by bytes.
- **[Arithmetic]** Bytes still matter on cold connections because of slow start. In an idealized model (~14.6 KB first flight per RFC 6928, window doubles every RTT, no loss, no receive-window cap), the cumulative bytes delivered after k RTTs are about 14.6 KB × (2^k − 1):

  | RTTs | Cumulative bytes |
  |---|---|
  | 1 | ~15 KB |
  | 2 | ~44 KB |
  | 3 | ~102 KB |
  | 4 | ~219 KB |
  | 5 | ~453 KB |
  | 6 | ~920 KB |

  Shrinking a response below one of these boundaries saves a whole RTT. Shrinking it within a band saves almost nothing. On a warm, reused connection this effect mostly goes away.
- For ARFP: above roughly 5–10 Mbps, cutting bytes on a typical page load improves PLT very little unless it also removes round trips. Any design that adds a negotiation round trip (for example, a separate "do you already have X?" exchange) is likely to make typical web transfers slower overall. Byte savings pay off most on slow links, on the bandwidth-limited minority of pages, and on bulk transfers.

### Gaps
- I did not fetch the original Google Docs paper, so the numbers above come from Belshe's own blog summary and HPBN. The fetch tool did not return HPBN's figure caption text.
- The arXiv paper's venue and exact date are not in the fetched text; the ID 2503 implies a March 2025 submission. It gives no Mbps threshold for diminishing returns.
- I found no large real-user study from 2024–2026 that reproduces Belshe's curves.

## 2. What share of internet traffic is video (Sandvine/AppLogic GIPR; Ericsson Mobility Report)

### Takeaway
The latest explicit percentage in a primary Sandvine source is 65% of all internet traffic, for calendar 2022 (published January 2023). The public text of the 2024, 2025 and 2026 reports I could retrieve gives no single video share:
- 2024: only secondary press puts on-demand streaming at 54% of downstream volume.
- 2025: video "remains the largest application category by volume".
- 2026: the landing page lists only AI-traffic growth figures.

For mobile networks, Ericsson's June 2026 report says video was about 75% of all mobile data traffic at the end of 2025.

### Cited Findings
**Sandvine / AppLogic Networks.** Sandvine's Global Internet Phenomena Report is now published under the AppLogic Networks name.
- **[Measured-prod]** 2023 GIPR (released Jan 17, 2023; covers 2022 data): "video usage grew 24% in 2022, now equating to 65% of all internet traffic." (tool paraphrase:) the data comes from "more than 177 service providers worldwide". The release does not say whether this is downstream or total, or fixed or mobile. Netflix is described as "the individual app generating the most traffic" for the first time. — [Sandvine/AppLogic press release (Jan 2023)](https://www.applogicnetworks.com/press-releases/sandvines-2023-global-internet-phenomena-report-shows-24-jump-in-video-traffic-with-netflix-volume-overtaking-youtube)
- **[Measured-prod]** 2024 GIPR (blog post, April 10, 2024): "a global volume of 33 exabytes per day"; "a per-subscriber volume of 4.2 GB per day across the globe's 6.4 billion mobile and 1.4 billion fixed connections."; "companies like Google, Facebook, and Netflix driving 65% of all fixed traffic and 68% of all mobile traffic." The text gives no video percentage; the charts are images. — [AppLogic blog (Apr 10, 2024)](https://www.applogicnetworks.com/blog/sandvines-2024-global-internet-phenomena-report-global-internet-usage-continues-to-grow)
- 2024 GIPR as reported by trade press (CSI Magazine, 12/04/2024; secondary source):
  - "On-Demand Streaming is the type of video that generates the most traffic". (tool paraphrase:) 7.9 GB per subscriber per day, or 54% of total downstream volume.
  - "Downstream subscriber volume in fixed networks is 14.5 GB".
  - "Social Media is the biggest app category in mobile networks' downstream traffic, with 35%."
  - (tool paraphrase:) mobile is 1.6 GB down and 0.1 GB up per subscriber per day; fixed upstream is 1.2 GB.
  - Source: [CSI Magazine](https://csimagazine.com/csi/sandvine-2024-internet-report.php)
- 2025 GIPR (press release March 3, 2025, via Business Wire): "While video remains the largest application category by volume, with users downloading an average 5.6GB per day"; "Live sports events generate traffic peaks that can exceed normal usage by 30-40%"; AI assistants are used by "only 7% of households in Fixed networks and 4% of mobile users." No video percentage is given. — [Press release, republished](https://press.kgnews.net/newsRead.php?no=1006796). The companion blog (Mar 4, 2025) says "While video remains the largest application category in terms of volume" and that AI assistants are "not significant in terms of volume – yet". — [AppLogic blog](https://applogicnetworks.com/blog/the-2025-global-internet-phenomena-report)
- 2026 GIPR landing page: "90%" labelled "AI traffic growth on fixed networks" and "80%" labelled "AI traffic growth on mobile networks". It does not state the period or baseline. The data is "Grounded in anonymized, aggregated data from tens of millions of subscribers". No video share appears in the page text. — [AppLogic GIPR 2026](https://www.applogicnetworks.com/gipr-2026)
- Historical baseline (2018 GIPR, secondary): "Video streaming accounts for 58% of downstream and 22% of upstream internet traffic."; "Globally, Netflix accounts for 15% of all downstream traffic." — [informitv (Oct 2018)](https://informitv.com/?p=24223)

**Ericsson Mobility Report (mobile networks only):**
- **[Measured/estimate]** June 2026 edition. The edition is inferred from the page's link to `reports/june-2026`. "At the end of 2025, video traffic accounted for around 75 percent of all mobile data traffic." — [Ericsson, mobile traffic update](https://www.ericsson.com/en/reports-and-papers/mobility-report/dataforecasts/mobile-traffic-update)
- "Total monthly global mobile network data traffic exceeded 220 EB in Q2 2026."; "Mobile network data traffic growth continued, rising 23 percent between Q2 2025 and Q2 2026."; "The quarter-on-quarter mobile network data traffic growth between Q1 2026 and Q2 2026 was around 6 percent." — [Ericsson](https://www.ericsson.com/en/reports-and-papers/mobility-report/dataforecasts/mobile-traffic-update)
- **[Projection]** "Total mobile data traffic is expected to grow with a factor of around 2.2 to reach 328 EB per month in 2031." This excludes fixed wireless access (FWA); including FWA, traffic is "reaching 515 EB per month." — [Ericsson, mobile traffic forecast](https://www.ericsson.com/en/reports-and-papers/mobility-report/dataforecasts/mobile-traffic-forecast)

### Inferences
- **[Arithmetic]** 7.9 / 14.5 ≈ 54.5%. That suggests CSI's "54% of downstream" is a share of fixed-network downstream traffic. This is unconfirmed.
- Order of magnitude: video is roughly two-thirds of internet bytes (Sandvine, 2022 data) and about three-quarters of mobile bytes (Ericsson, end of 2025). A byte-saving scheme that ignores video therefore addresses at most about a quarter to a third of traffic volume.
- Video is already heavily compressed by codecs. ARFP "latent/recipe" approaches for video would have to beat modern codecs, which I did not assess here.
- Video streaming is a sustained transfer limited by throughput. Page loads are limited by RTT and CPU (sections 1 and 9). The two halves of internet traffic therefore have different bottlenecks.

### Gaps
- I could not get a primary 2024, 2025 or 2026 Sandvine/AppLogic statement of video's percentage share. The full reports appear to be gated or only in images. The 54% figure is secondary, and its exact wording is a tool paraphrase.
- The Sandvine 65% figure is for 2022 data, so it is likely outdated as of October 2026.
- Ericsson's forecast share of video for 2031 was not on the forecast page I fetched.

## 3. How big typical web pages are (HTTP Archive Web Almanac 2025, Page Weight chapter)

### Takeaway
The latest edition is the Web Almanac 2025 (published January 2026; trend data through July 2025). The median home page is 2,559 KB on mobile and 2,862 KB on desktop. Median requests are 75 (mobile) and 80 (desktop) for home pages, or 72 and 77 for all pages. Median compressed JavaScript is 646 KB (mobile) and 708 KB (desktop). Pages grew about 7–8% year over year. The chapter contains internal inconsistencies, flagged below.

### Cited Findings
- Chapter 14, Page Weight: "Written by Richard Barret and Jamie Indigo"; "Reviewed and analyzed by Dave Smart". The metadata gives the publication date as 2026/01/15 (tool-reported). — [Web Almanac 2025, Page Weight](https://almanac.httparchive.org/nl/2025/page-weight). This URL served the English chapter; the canonical path is `/en/2025/page-weight`.
- **[Measured-prod, crawl data]** Page weight:
  - "The median home page in 2025 was 2.86 MB on desktop and 2.56 MB on mobile."
  - Figure 14.7: "In total, desktop pages were 2,862 KB and mobile were 2,559 KB."
  - Source: [Web Almanac 2025](https://almanac.httparchive.org/nl/2025/page-weight)
- Internal inconsistency: the text says "As of July 2025, the same median page is now 2,362 KB." (mobile), but Figure 14.1 shows "...to 2,559 KB on mobile in July 2025." — [Web Almanac 2025](https://almanac.httparchive.org/nl/2025/page-weight)
- Requests:
  - "The median desktop home page makes 80 requests while its mobile counterpart makes 75." (Fig. 14.37)
  - "The median page makes 77 requests on desktop and 72 on mobile."
  - Figure 14.33's description gives "73 total files" (desktop) and "68 requests in total" (mobile), which is inconsistent with the two figures above.
  - Source: [Web Almanac 2025](https://almanac.httparchive.org/nl/2025/page-weight)
- JavaScript, measured as compressed transfer bytes:
  - "The median desktop page uses 708 KB of JavaScript. This is slightly higher than mobile's 646 KB." (Fig. 14.18)
  - "Median home pages used 664 KB, while their inner page counterparts used 690 KB." (Fig. 14.19)
  - Scope caveats: "It's important to note that this data set represents bytes for compressed JavaScript files." and "Additionally, inlined JavaScript in the HTML page is not represented on this data."
  - Source: [Web Almanac 2025](https://almanac.httparchive.org/nl/2025/page-weight)
  - Lower confidence: the tool also reported a Figure 14.7 caption, "JavaScript accounted for 697 KB on home pages" (desktop home).
- Images: "The median mobile home page used 911 KB of images while inner pages used 354 KB." The desktop home page used "1,058 KB of images". — [Web Almanac 2025](https://almanac.httparchive.org/nl/2025/page-weight)
- Growth:
  - "Year over year, the median home page size grew 7.8% to 2.7 MB."
  - "The median mobile home page is 2.6 MB, growing 8.4% from 2.4 MB in 2024."
  - "In 2025, the median desktop page size reached 2.9 MB, up 7.3% from 2024's median of 2.7 MB."
  - "Inner page weight continued to increase, up 9.5% year over year."
  - Source: [Web Almanac 2025](https://almanac.httparchive.org/nl/2025/page-weight)
- Tail and page type (figure values reported by the tool, not verbatim text):
  - 90th percentile, all pages: desktop 9,179 KB, mobile 8,337 KB (Fig. 14.3).
  - Medians by page type: home 2,710 KB vs. inner 1,866 KB (Fig. 14.4). The text says home pages are "close to 45.8% larger than inner pages".
  - Source: [Web Almanac 2025](https://almanac.httparchive.org/nl/2025/page-weight)

### Inferences
- **[Arithmetic]** 2,559 KB is about 21 Mbit. Fully using the link, that is about 2.1 s of pure transfer at 10 Mbps and about 0.2 s at 100 Mbps. Real page loads do not fill the link (Belshe measured about 16% utilization at 10 Mbps), so wall-clock time is dominated by chains of round trips and by CPU.
- Compressed JavaScript (about 0.65–0.7 MB) is roughly a quarter of median page bytes. It also costs CPU to parse, compile and run, and saving bytes does not reduce that cost (see section 4).
- Much of a site's JavaScript and CSS is unchanged between visits and deploys. HTTP caching and compression dictionaries (deltas against a cached earlier version) already exploit exactly this redundancy.
- Medians of components cannot be added up to get the median page.

### Gaps
- The retrieved text does not explicitly name the crawl month; the trend charts end at July 2025.
- I did not fetch the 2024 chapter separately; 2024 values come only from the 2025 chapter's year-over-year statements.
- The chapter itself is inconsistent on mobile median weight (2,362 vs. 2,559 KB) and on request counts.

## 4. Compression Dictionary Transport (RFC 9842): mechanism, limits, measured savings, support

### Takeaway
RFC 9842 (Standards Track, September 2025; Meenan of Google and Weiss of Shopify) works like this:
- A client names a resource it has already cached by putting that resource's SHA-256 hash in the `Available-Dictionary` request header.
- The server can then reply with `dcb` (Brotli; dictionary used as a "prefix dictionary"; window up to 16 MB) or `dcz` (Zstandard; dictionary used "as a raw dictionary"; window at least max(8 MB, 1.25 × dictionary size), at most 128 MB).
- The advertisement rides on the ordinary request, so the request that uses the dictionary pays no extra round trip.

Results:
- **Production:** Google Search cut average HTML size by 23% versus Brotli, but LCP improved by only 1.7% overall (up to 9% on high-latency networks).
- **Lab tests and demos:** 97–99%+ savings for versioned JavaScript.

Support as of 2026: Chrome and Edge 130+; Firefox "in progress"; Safari not mentioned in any source I found. MDN says "Limited availability". Cloudflare passthrough is in beta.

### Cited Findings
**Spec text from RFC 9842:**
- **[Spec]** Status and authors: "September 2025"; "This is an Internet Standards Track document."; "P. Meenan, Ed." (Google LLC) and "Y. Weiss, Ed." (Shopify Inc.). Abstract: "This document specifies a mechanism for dictionary-based compression in the Hypertext Transfer Protocol (HTTP)." — [RFC 9842](https://www.rfc-editor.org/rfc/rfc9842.html)
- **[Spec]** How the client advertises: `Available-Dictionary` is "a Structured Field Byte Sequence containing the SHA-256 hash of the contents of a single available dictionary." The client "MUST only send a single "Available-Dictionary" request header". — [RFC 9842](https://www.rfc-editor.org/rfc/rfc9842.html)
- **[Spec]** How the server marks a dictionary:
  - `Use-As-Dictionary` is "a Structured Field Dictionary with values for "match", "match-dest", "id", and "type"."
  - "match" "is a String value that provides the URL Pattern to use for request matching." Also: "The URL Pattern used for matching does not support using regular expressions."
  - "type" defaults to "raw", which is "an unformatted blob of bytes suitable for any compression scheme to use."
  - `Dictionary-ID` is "a Structured Field String of up to 1024 characters", and clients "MUST echo the stored "id"".
  - Source: [RFC 9842](https://www.rfc-editor.org/rfc/rfc9842.html)
- **[Spec]** `dcb`: the dictionary is "treated as a prefix dictionary as defined in" RFC 9841 (Shared Brotli). It has a 36-byte header: Magic_Number "4 fixed bytes -- 0xff, 0x44, 0x43, 0x42." followed by "32 bytes. SHA-256 hash digest of the dictionary." — [RFC 9842](https://www.rfc-editor.org/rfc/rfc9842.html)
- **[Spec]** `dcz`: the dictionary "is treated as a raw dictionary as per" RFC 8878 (Zstandard). It has a 40-byte header: "8 fixed bytes -- 0x5e, 0x2a, 0x4d, 0x18, 0x20, 0x00, 0x00, 0x00." followed by the 32-byte SHA-256 of the dictionary (tool paraphrase of the second part). — [RFC 9842](https://www.rfc-editor.org/rfc/rfc9842.html)
- **[Spec]** Window limits:
  - dcb uses "a compression window that is at most 16 MB in size". Clients "MUST be able to decompress resources that were compressed with a window size of up to 16 MB."
  - For dcz, clients must handle "a window size of at least 8 MB or 1.25 times the size of the dictionary, whichever is greater," "up to a maximum of 128 MB". The rationale: "1.25 times the size of the dictionary allows for full delta compression of resources that have grown by 25%."
  - With Brotli, "the full dictionary is available during compression and decompression independent of the compression window."
  - With Zstandard, the dictionary is available "until the size of the input exceeds the compression window."
  - Per the fetch tool, the RFC sets no explicit limit on dictionary size.
  - Source: [RFC 9842](https://www.rfc-editor.org/rfc/rfc9842.html)
- **[Spec]** Round trips: the RFC says nothing explicit about them. On timing it says only "Clients can fetch the provided resource at a time that they determine would be appropriate." — [RFC 9842](https://www.rfc-editor.org/rfc/rfc9842.html)
- **[Spec]** Security and privacy:
  - The match pattern "is guaranteed to be for the same origin that the dictionary is served from".
  - Dictionaries "MUST only be used when both the dictionary and the compressed response are fully readable by the client."
  - Clients "MUST treat dictionaries in the same way that they treat cookies".
  - Servers should consider "disabling compression when any portion of the content comes from uncontrolled sources."
  - Source: [RFC 9842](https://www.rfc-editor.org/rfc/rfc9842.html)

**How it works on the wire (MDN, Chrome, Meenan):**
- "the request will include a SHA-256 hash of the available dictionary in the `Available-Dictionary` header, along with `dcb` and/or `dcz` values in the `Accept-Encoding` header" (example: `Accept-Encoding: gzip, br, zstd, dcb, dcz`). — [MDN (last modified Sep 25, 2026)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Compression_dictionary_transport)
- Stand-alone dictionaries: "The browser downloads this dictionary during idle time". It is referenced via `<link rel="compression-dictionary" href="/dictionary.dat" />` or `Link: </dictionary.dat>; rel="compression-dictionary"`. — [MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Compression_dictionary_transport)
- MDN's restrictions:
  - "Dictionaries must be same-origin with the resource using the dictionary."
  - "Dictionaries are bound by the usual HTTP Cache partitioning and so cannot be shared between origins even if they download the same resources."
  - "browsers may restrict this feature when cookies are disabled or when other extra privacy protections are enabled."
  - Source: [MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Compression_dictionary_transport)
- Chrome's behavior: for dynamic resources it may "fetch the dictionary once the page is idle, and at low priority." Token rename: "the `br-d` and `zstd-d` tokens have been renamed to `dcb`, and `dcz` respectively." — [Chrome blog, Wagner (Mar 6, 2024)](https://developer.chrome.com/blog/shared-dictionary-compression)
- Fallback when anything fails: "If any step or check fails, just pass the original response through unmodified using the default encoding." Deployment requirement: "this does require that all resources used as dictionaries will be immutable and use permanent URLs". — [Meenan, PerfPlanet 2024](https://calendar.perfplanet.com/2024/getting-real-small-with-compression-dictionaries/)

**Measured and claimed savings:**
- **[Measured-prod] Google Search** (May 14, 2025):
  - Setup: uses `dcb`, with a dictionary "built from a representative sample of search results". It is refreshed to keep pace with content "released multiple times a day".
  - Result: it "reduced the average size of the HTML payload across all Chrome users by 23% compared to standard Brotli compression."
  - LCP: an "improvement of 1.7% overall, and up to 9% on high latency networks."
  - Single example: the first request was 107 kB with Brotli; the reload was "nearly half the size at 60 kB".
  - Source: [Chrome blog, Muñoz and Pollard](https://developer.chrome.com/blog/search-compression-dictionaries?hl=en)
- **[Measured-lab] Cloudflare** (Apr 17, 2026). Setup: 200 curl tests from the San Jose point of presence to a Council Bluffs origin, using a 272 KB JavaScript bundle (tool paraphrase of setup).
  - Size: gzip 92.2 KB vs. DCZ 2.6 KB. "That's a 99% reduction from the uncompressed asset, and still 97% smaller than gzip."
  - (tool paraphrase:) on a cache miss, P99 TTFB was about 60 ms faster than gzip; transfer took 1 ms vs. 161 ms (cache miss) and 1 ms vs. 54 ms (cache hit). On a cache hit, "the TTFB gap narrows to a negligible 10ms."
  - Live demo: a ~94 KB bundle redeployed every minute compresses to "roughly 450 bytes", a "99.5% reduction over gzip".
  - Caveat: "results will vary based on the actual delta between the dictionary and the asset."
  - Source: [Cloudflare blog](https://blog.cloudflare.com/shared-dictionaries)
- **[Illustrative]** Angular version-to-version example:
  - "This version of the Angular framework is about 172 KiB uncompressed."
  - Brotli gets it to "about 53 KiB".
  - As a delta from 1.7.9, "the output would be just over 4 KiB" ("nearly 98%").
  - General claim: dictionaries "can—in some cases—deliver" "90% or better compression ratios."
  - Source: [Chrome blog](https://developer.chrome.com/blog/shared-dictionary-compression)
- **[Claim]** "responses anywhere from 60-90+% smaller than using the best non-dictionary compression currently available"; for HTML, "usually leading to 60-90% smaller HTML responses". — [Meenan, PerfPlanet 2024](https://calendar.perfplanet.com/2024/getting-real-small-with-compression-dictionaries/)
- **[Secondary compilation]** Tim Perry, HTTP Toolkit (Feb 23, 2026), summarizing others' tests:
  - YouTube's desktop player "is normally 10MB of JS, normally compressed with Brotli down to 1.8MB for transfer". Using a version from two months earlier as the dictionary "reduces that down to just 384KB (78% smaller than plain Brotli)". With versions a week apart, "down to 172KB (90% smaller than Brotli)".
  - Google Search: "a 50% reduction for returning users".
  - Amazon: "these shrink 60-70% compared to plain Brotli (e.g. 539KB uncompressed HTML = 84KB of Brotli = 10KB of Brotli with a custom dictionary)".
  - Loveholidays: "up to 57% reductions in their JS bundle data transfer size".
  - Discord: "reductions of up to 60% on some messages, but less than 1% on others".
  - Caveat: "the time to actually parse & execute your enormous JavaScript bundle client-side won't change."
  - Source: [httptoolkit.com](https://httptoolkit.com/blog/dictionary-compression-performance-zstd-brotli)

**Browser and CDN support (2024–2026):**
- Chrome: "shipped to stable earlier this year in Chrome 130" (written in 2024). — [Meenan, PerfPlanet 2024](https://calendar.perfplanet.com/2024/getting-real-small-with-compression-dictionaries/)
- "Today, that means Chrome 130+ and Edge 130+, with Firefox support in progress." (April 2026). Safari is not mentioned. — [Cloudflare blog](https://blog.cloudflare.com/shared-dictionaries)
- MDN (Sep 25, 2026): "Limited availability"; "This feature is not Baseline because it does not work in some of the most widely-used browsers."; also flagged "Experimental". — [MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Compression_dictionary_transport)
- Cloudflare's plan and status:
  - "We plan to have an open beta of Phase 1 ready by April 30, 2026." Phase 1 is passthrough; Phases 2 and 3 are Cloudflare-managed and automatic dictionaries, with no timeline for Phase 3. — [Cloudflare blog](https://blog.cloudflare.com/shared-dictionaries)
  - Docs (updated Aug 14, 2026) list every plan as "Yes (beta)". They say "In passthrough mode, Cloudflare does not generate dictionaries or compute deltas."; "Cloudflare forwards the dictionary headers and `dcb`/`dcz` content encodings without modifying or recompressing them."; "compression dictionary transport is HTTPS-only."; "Cross-origin dictionary use is not supported." — [Cloudflare docs](https://developers.cloudflare.com/speed/optimization/content/shared-dictionaries/)

### Inferences
- **No extra RTT on the critical path.** The dictionary hash travels on the same request as `Accept-Encoding`. If the server lacks a match, it falls back to normal encoding. Where a separate dictionary file is used, it is fetched at idle time and low priority: that is an extra request, but not on the critical path. The real costs are elsewhere:
  - dictionary bytes downloaded in advance;
  - server-side precomputation and caching for each (resource, dictionary) pair;
  - per-origin cache partitioning, so a dictionary cannot be shared across sites.
- **This is ARFP's "reference + delta" idea, already deployed.** It identifies receiver-held state by content hash (SHA-256), uses that state as the base, encodes the delta with standard codecs, and falls back safely. dcb/dcz are the baseline any ARFP proposal should be measured against.
- **Big byte savings, small latency gains.** Google Search saved 23% of HTML bytes but gained 1.7% LCP overall (up to 9% on high-latency networks). That ratio is consistent with page loads being limited by RTT and CPU (sections 1 and 9).
- **[Arithmetic]** 128 MB / 1.25 ≈ 102 MB. So dcz's guarantee of full-delta coverage for 25% growth holds only for dictionaries up to about 100 MB.
- Courgette (section 5) shows that a content-aware transform can beat a generic delta by about 9×. Generic dcb/dcz sits at roughly the "bsdiff tier".

### Gaps
- I found no measured production numbers from Akamai or Shopify (Shopify co-authored the RFC). Akamai and Fastly support status was not verified.
- I found no Safari/WebKit status. Firefox's status is only "in progress", per Cloudflare in April 2026.
- The retrieved RFC text does not say whether using a dictionary costs a round trip. "No extra RTT" is my inference from the mechanism.
- I did not verify RFC 8878's definition of a "raw" dictionary or RFC 9841's wording for "prefix dictionary".
- No source quantified the server CPU cost of dictionary compression.

## 5. Google Courgette (Chromium blog, 2009): full vs. bsdiff vs. Courgette update sizes

### Takeaway
For the Chrome 190.1→190.4 developer-channel update, Courgette shrank the download to 78,848 bytes. The full update was 10,385,920 bytes and the bsdiff update was 704,512 bytes. Courgette was therefore about 1/132 of the full update and about 1/9 of bsdiff (my arithmetic).

### Cited Findings
- "Smaller is Faster (and Safer Too)", "Posted by Stephen Adams, Software Engineer", dated 15 July 2009. — [Chromium Blog](https://blog.chromium.org/2009/07/smaller-is-faster-and-safer-too.html) (fetched via the `?hl=fr` variant; the post text is English)
- **[Measured-prod]** "Here are the sizes for the recent 190.1->190.4 update on the developer channel:" "Full update: 10,385,920 bytes"; "bsdiff update: 704,512 bytes"; "Courgette update: 78,848 bytes". — [Chromium Blog](https://blog.chromium.org/2009/07/smaller-is-faster-and-safer-too.html)
- Approach: "we wrote a new diff algorithm that knows more about the kind of data we are pushing - large files containing compiled executables."; "If the update is a tenth of the size, we can push ten times as many per unit of bandwidth." The post links to a design document (`dev.chromium.org/developers/design-documents/software-updates-courgette`) for details. — [Chromium Blog](https://blog.chromium.org/2009/07/smaller-is-faster-and-safer-too.html)

### Inferences
- **[Arithmetic]**
  - Courgette is 0.76% of the full update, about 132× smaller.
  - bsdiff is 6.78% of the full update, about 14.7× smaller.
  - Courgette is about 8.9× smaller than bsdiff.
- For ARFP: a transform that understands the content type gives about another 9× over a generic binary delta. This is the strongest precedent for "recipes" tailored to a content type, as opposed to generic dictionary compression.

### Gaps
- The blog post does not describe the mechanism, and I did not fetch the design doc, so no mechanism details are quoted here.
- It is a single update, so there is no distribution of results.
- I did not research whether Chrome still uses Courgette today.

## 6. Round trips before the first application byte: TCP+TLS 1.2, TCP+TLS 1.3, QUIC, 0-RTT, and the replay caveat

### Takeaway
Round trips before the client can send its first request byte:
- TCP + TLS 1.2: 3 (1 for TCP + 2 for TLS)
- TCP + TLS 1.3: 2
- QUIC: 1
- QUIC with 0-RTT resumption: 0 (the request goes in the first flight)
- TLS 1.3 0-RTT over TCP: still 1, for the TCP handshake, unless TCP Fast Open is used

0-RTT data has no replay protection across connections. The specs therefore require application profiles for 0-RTT and limit HTTP early data to safe methods.

### Cited Findings
**TCP:**
- **[Spec]** "Current TCP only permits data exchange after the three-way handshake (3WHS) [RFC793], which adds one RTT to network latency." TCP Fast Open (TFO) "saves up to one full round-trip time (RTT) compared to the standard TCP," but "TFO deviates from the standard TCP semantics, since the data in the SYN could be replayed" "to an application in some rare circumstances." **[Claim/estimate]** "The authors estimated that TFO improves page load time by 10% to 40% on selected popular Web sites." — [RFC 7413 (Dec 2014, Experimental)](https://www.rfc-editor.org/rfc/rfc7413.txt)
- "each new connection will have a full roundtrip of latency before any application data can be transferred." — [hpbn.co ch. 2](https://hpbn.co/building-blocks-of-tcp/)

**TLS 1.2:**
- **[Spec]** "A full handshake in TLS protocol versions up to TLS 1.2 [RFC5246] requires two full protocol rounds (four flights)" "before the handshake is complete and the protocol parties may begin to send application data."; "When an earlier TLS session is resumed, TLS uses an abbreviated handshake with only three protocol flights."; "A TLS False Start reduces handshake latency to one round trip." — [RFC 7918 (Aug 2016, Informational)](https://www.rfc-editor.org/rfc/rfc7918.txt)
- HPBN says "new TLS connections require two roundtrips for a "full handshake"" and "The abbreviated handshake eliminates a full roundtrip of latency." Its worked example assumes "28 millisecond one-way "light in fiber" delay between New York and London". The TCP handshake "takes one full roundtrip", and at 168 ms "then the tunnel is established and application data can now be sent." — [hpbn.co ch. 4](https://hpbn.co/transport-layer-security-tls/)
- On TLS 1.2: "The handshake requires two additional round-trips between the browser and the server before encrypted data can be sent" "(or one when resuming a previous connection)". — [Cloudflare, Sullivan (Aug 10, 2018)](https://blog.cloudflare.com/rfc-8446-aka-tls-1-3/)

**TLS 1.3:**
- "enables the TLS 1.3 handshake latency to drop from two round-trips to only one round-trip". 0-RTT means "no additional latency cost compared to unencrypted HTTP." — [Cloudflare](https://blog.cloudflare.com/rfc-8446-aka-tls-1-3/)
- **[Spec]** RFC 8446 (August 2018), §1.2: "A zero round-trip time (0-RTT) mode was added, saving a round trip". — [RFC 8446](https://www.rfc-editor.org/rfc/rfc8446.html)
- "One of the design goals for TLS 1.3 is to reduce the latency overhead for setting up the secure connection: 1-RTT for new, and 0-RTT for resumed sessions!" — [hpbn.co ch. 4](https://hpbn.co/transport-layer-security-tls/)

**QUIC:**
- **[Spec]** RFC 9000 (May 2021): "The QUIC handshake combines negotiation of cryptographic and transport parameters."; "QUIC relies on a combined cryptographic and transport handshake to minimize connection establishment latency."; "The handshake is structured to permit the exchange of application data as soon as possible." — [RFC 9000](https://www.rfc-editor.org/rfc/rfc9000.html)
- **[Spec]** RFC 9001 (May 2021): "Absent packet loss, most new connections can be established and secured within a single round trip;" "on subsequent connections between the same client and server, the client can often send application data immediately,"; "QUIC does not use TLS early data. QUIC uses 0-RTT packets to carry early data." — [RFC 9001](https://www.rfc-editor.org/rfc/rfc9001.html)

**The 0-RTT replay caveat:**
- **[Spec]** RFC 8446 §2.3: "The security properties for 0-RTT data are weaker"; "This data is not forward secret, as it is encrypted solely under" (the PSK-derived keys); "There are no guarantees of non-replay between connections." — [RFC 8446](https://www.rfc-editor.org/rfc/rfc8446.html)
- **[Spec]** "However, 0-RTT provides no protection against replay attacks;" — [RFC 9000](https://www.rfc-editor.org/rfc/rfc9000.html)
- **[Spec]** RFC 9001 §9.2: "As described in Section 8 of [TLS13], use of TLS early data comes with an exposure to replay attack."; "QUIC is not vulnerable to replay attack, except via the application protocol information it might carry."; "Disabling 0-RTT entirely is the most effective defense against replay attack." — [RFC 9001 (text)](https://www.rfc-editor.org/rfc/rfc9001.txt)
- **[Spec]** RFC 9001 §5.6: "An application protocol that uses QUIC MUST include a profile that defines acceptable use of 0-RTT;"; "A client therefore MUST NOT use 0-RTT for application data unless specifically requested by the application that is in use."; "the lack of replay protection means that restrictions on their use are necessary to avoid replay attacks on the protocol." — [RFC 9001](https://www.rfc-editor.org/rfc/rfc9001.html)
- **[Spec]** RFC 8470, Using Early Data in HTTP (Sept 2018, Standards Track):
  - "Using TLS early data creates an exposure to the possibility of a replay attack."
  - "The primary risk of using early data is that an attacker might capture and replay the request(s) it contains."
  - Clients "MAY send requests with safe HTTP methods" but "MUST NOT send unsafe methods (or methods whose safety is not known) in early data."
  - "A 425 (Too Early) status code indicates that the server is unwilling to risk processing a request that might be replayed."
  - Source: [RFC 8470](https://www.rfc-editor.org/rfc/rfc8470.txt)
- Explanation of the risk:
  - "If an attacker captures a 0-RTT packet that was sent to server, they can replay it"
  - "An example of dangerous replayed data is anything that changes state on the server."
  - Mitigation: "TLS 1.3 also includes the time elapsed value in the session ticket."
  - Source: [Cloudflare](https://blog.cloudflare.com/rfc-8446-aka-tls-1-3/)

### Inferences
- **[Arithmetic]** Round-trip budget, using HPBN's minimum New York–London fiber RTT of 56 ms. It ignores server think time, packet loss and DNS. "First response byte" is the request time plus one RTT.

  | Setup | RTTs before request is sent | Request sent at | First response byte at |
  |---|---|---|---|
  | TCP + TLS 1.2 full | 3 | 168 ms (matches HPBN) | 224 ms |
  | TCP + TLS 1.2 resumed or False Start | 2 | 112 ms | 168 ms |
  | TCP + TLS 1.3 full | 2 | 112 ms | 168 ms |
  | TCP + TLS 1.3 0-RTT (no TFO) | 1 | 56 ms | 112 ms |
  | QUIC, new connection | 1 | 56 ms | 112 ms |
  | QUIC 0-RTT | 0 | 0 ms | 56 ms |

- On a cold TLS 1.2 connection, handshakes alone cost 3 RTTs (168 ms transatlantic) before any byte of content moves. That is more than the slow-start time needed to deliver about 100 KB (section 1).
- For ARFP: any "what do you hold?" exchange should ride on the request itself, as `Available-Dictionary` does, rather than cost its own round trip. "Fetch recipe X" or "delta against hash H" requests sent as 0-RTT early data must be safe and idempotent. ARFP would also need an application profile and a "too early" mechanism like HTTP's 425 status.

### Gaps
- I could not retrieve RFC 8446 Section 8 and Appendix E.5 verbatim, because the fetch tool truncated the document around §4.2. The replay caveat is quoted instead from RFC 8446 §2.3, RFC 9000, RFC 9001 §9.2 and §5.6, and RFC 8470.
- I did not research how widely TLS 1.3, QUIC/HTTP/3 or 0-RTT are actually deployed.
- I did not review RFC 9218 (Extensible Prioritization).

## 7. Speed of light in fiber and a minimum round-trip time example (New York–London)

### Takeaway
Light in optical fiber travels at about 200,000 km/s: the refractive index is about 1.5, which is roughly two-thirds of the speed of light in vacuum. The minimum New York–London RTT over fiber is 56 ms (28 ms one way). Real routes and the last mile add more.

### Cited Findings
- **[Physics / rule of thumb]** "the rule of thumb is to assume that the speed of light in fiber is around 200,000,000 meters per second" "which corresponds to a refractive index of ~1.5"; "The typical refractive index value of an optical fiber" (tool paraphrase: varies between 1.4 and 1.6); "given that our current speeds are already within ~2/3 of the speed of light". — [hpbn.co ch. 1](https://hpbn.co/primer-on-latency-and-bandwidth/)
- Table 1-1, "Signal latencies in vacuum and fiber". Columns: distance, one-way time in vacuum, one-way time in fiber, round-trip time in fiber. Rows as quoted:
  - "New York to San Francisco 4,148 km 14 ms 21 ms 42 ms"
  - "New York to London 5,585 km 19 ms 28 ms 56 ms"
  - "New York to Sydney 15,993 km 53 ms 80 ms 160 ms"
  - "Equatorial circumference 40,075 km 133.7 ms 200 ms 200 ms"
  - Source: [hpbn.co ch. 1](https://hpbn.co/primer-on-latency-and-bandwidth/)
- Real routes run slower than the table: "the actual RTT between New York and Sydney, over our existing networks," "works out to be in the 200–300 millisecond range." — [hpbn.co ch. 1](https://hpbn.co/primer-on-latency-and-bandwidth/)
- **[Measured, about 2013; dated]** Last mile: "fiber has best average performance (10-20 ms), followed by cable (15-40 ms), and DSL (30-65 ms)."; "In practice this translates into 10-65 ms of latency just to the closest measuring node". — [hpbn.co ch. 1](https://hpbn.co/primer-on-latency-and-bandwidth/)
- Grigorik (2012): "Our data packets travel through fiber, which slows us down by a factor of ~1.52"; "the theoretical limit between New York and London is 37.2ms"; "For example, sending a packet from San Francisco to NYC carries a minimum 40ms RTT." — [igvita.com](https://www.igvita.com/2012/07/19/latency-the-new-web-performance-bottleneck/)

### Inferences
- **[Arithmetic]** 2 × 5,585 km ÷ 299,792 km/s ≈ 37.3 ms. Grigorik's "37.2ms" New York–London "theoretical limit" is therefore the vacuum RTT; HPBN's 56 ms is the fiber RTT.
- **[Arithmetic] Break-even between one RTT and bytes.** One 56 ms RTT costs as much time as sending about 700 KB at 100 Mbps, or about 70 KB at 10 Mbps, on a fully open link. For objects smaller than that, removing one round trip saves more time than removing every byte. For ARFP, each round trip it eliminates is worth at least 56 ms transatlantic and at least 160 ms New York–Sydney. These are physical floors that no protocol can beat.

### Gaps
- I retrieved no current measured transatlantic RTT dataset. The last-mile figures date from about 2013 (HPBN era) and are probably outdated for modern fiber and 5G.

## 8. Chrome's removal of HTTP/2 Server Push (2022) and 103 Early Hints as the replacement

### Takeaway
Chrome disabled HTTP/2 Server Push by default in Chrome 106 (2022). Its reasons:
- low use: 1.25% of HTTP/2 sites, later 0.7%;
- benefits that were "often difficult to realize", with "in many cases performance regressions";
- lack of support in many HTTP/3 implementations.

The replacement is 103 Early Hints (RFC 8297, Experimental, 2017; shipped in Chrome 103). It sends hints that the browser can act on during the server's "think time". Measured gains are real but modest and inconsistent:
- Cloudflare lab, desktop: LCP improved by more than 6.03% at p50 and more than 15.97% at p75.
- Shopify (2021): LCP "over 500ms faster at p50".
- Shopify's 2025 real-user data: modest desktop gains and degradation on mobile.

### Cited Findings
- "Remove HTTP/2 Server Push from Chrome", by Barry Pollard; the page says "Last updated 2022-08-18 UTC." "HTTP/2 Server Push will be disabled by default in Chrome 106". — [Chrome for Developers blog](https://developer.chrome.com/blog/removing-push)
- **[Measured-prod usage + claim]** Stated reasons:
  - "the performance benefits were often difficult to realize"
  - "only 1.25% of HTTP/2 sites making use of this feature."
  - "When rerunning that analysis more recently, we see that 1.25% HTTP/2 support by sites dropped to 0.7%."
  - "Analysis of the use of HTTP/2 Server Push has mixed results" "without a clear net performance gain and in many cases performance regressions."
  - "Push was not implemented in many HTTP/3 servers and clients"
  - "Although the potential for Push sounded great, in reality using it was more problematic than envisaged."
  - Source: [Chrome blog](https://developer.chrome.com/blog/removing-push)
- Recommended alternatives:
  - "103 Early Hints is a much less error-prone alternative with many of the same upsides as Push" with "a lot less of the downsides."
  - "Rather than the server pushing resources, 103 Early Hints sends only hints to the browser"; "This leaves the browser in control of deciding whether it needs these or not".
  - Preload "is not quite as fast as either Server Push nor Early Hints".
  - "All solutions that attempt to load resources early can cause performance degradation and should be used in moderation."
  - Source: [Chrome blog](https://developer.chrome.com/blog/removing-push)
- **[Spec]** RFC 8297 ("December 2017"; "This document defines an Experimental Protocol for the Internet community."; author Kazuho Oku):
  - "This memo introduces an informational HTTP status code that can be used to convey hints" "that help a client make preparations for processing the final response."
  - "a client might recognize a Link header field value containing the relation type "preload"" and "start fetching the target resource."
  - "a server might refrain from sending 103 (Early Hints) responses over HTTP/1.1" "unless the client is known to handle informational responses correctly."
  - Source: [RFC 8297](https://www.rfc-editor.org/rfc/rfc8297.html)
- Chrome documentation (published June 23, 2022; last updated July 10, 2026):
  - What it does: "The browser can use those hints to warm up connections, and request subresources, while waiting for the main resource."
  - Why it helps: "this "server think-time" results in extra latency before the browser can start rendering the page."
  - Support: listed as Chrome 103.
  - Limits: "Only available for navigation requests (that is, the main resource for the top level document)."; "Only supports `preconnect` and `preload` (that is, `prefetch` isn't supported)."; "Early Hints are recommended to only be sent over HTTP/2 or HTTP/3 connections"; "Only cacheable resources can be preloaded using Early Hints or the resource will be double fetched"; other browsers "further restrict 103 early hints to `preconnect` only."
  - **[Claim]** LCP improvement "can go from several hundred milliseconds, as observed by Shopify and by Cloudflare, and up to a second faster."
  - Sources: [Chrome docs](https://developer.chrome.com/docs/web-platform/early-hints); [Chrome blog, Baheux and Pollard](https://developer.chrome.com/blog/early-hints)
- **Cloudflare (June 23, 2022):**
  - **[Measured-lab]** Early tests: "In early benchmarking experiments with Early Hints, we saw performance improvements that were as high as 30%." On an artificial page, "we were able to accelerate the Largest Contentful Paint (LCP) by 20-30%". Caveat: "this result was on an artificial page with mostly large images where Early Hints impact could be maximized."
  - **[Measured-lab]** WebPageTest study of "a little more than 750 URLs": "for 50% of web pages on desktop, Early Hints improved FCP by more than 9.47% and LCP by more than 6.03%."; "For the p75, or the upper 25%, FCP improved by more than 20.4% and LCP by more than 15.97%."
  - Shopify's Black Friday/Cyber Monday 2021 result, quoted from a Shopify tweet: "(LCP over 500ms faster at p50!)". The data type is unclear.
  - Caveats: "We also found examples of pages that performed consistently worse on lower-grade connections."; "it is still possible to _over-_hint non-critical assets and saturate network bandwidth".
  - Source: [Cloudflare blog](https://blog.cloudflare.com/early-hints-performance/)
- **[Measured-prod, real-user data] Shopify (June 11, 2025):**
  - "we aggregated Real User Monitoring (RUM) data from Shopify stores".
  - Desktop: "modest front-end performance improvements, particularly for LCP".
  - Mobile: "pages without Early Hints actually show better TTFB from the 40th percentile onwards". (tool paraphrase:) on mobile, pages without Early Hints beat pages with them on FCP at all percentiles, and LCP degrades at p70 and above.
  - Caveat: the data excludes iOS. "This limitation is particularly relevant for mobile analysis because it excludes all iOS devices."
  - Source: [Shopify Performance blog](https://performance.shopify.com/blogs/blog/early-hints-at-shopify)

### Inferences
- Push failing is a direct lesson for ARFP. Having the sender proactively send what it guesses the receiver needs did not produce net gains at scale. The replacement moved the decision to the receiver: the browser takes hints and decides whether to fetch or use its cache. RFC 9842 follows the same pattern, with the receiver declaring its state in `Available-Dictionary`. ARFP "references" should likewise be driven by the receiver.
- Early Hints is a latency optimization, not a bytes optimization: it turns idle server-think-time RTTs into useful fetches. Its benefit shrinks or reverses when hinted fetches compete for bandwidth on slow mobile links (over-hinting).

### Gaps
- The Chrome post does not detail failure mechanisms; for example, the commonly cited problem of pushing resources the browser already has cached is not stated in the sources retrieved.
- I did not research Firefox or Safari push removal.
- I found no large-scale Chrome-published A/B results for Early Hints.
- Shopify's 2025 numbers appear only in charts, not in the text.

## 9. Measured breakdown of page load time into network-latency-bound, bandwidth-bound, and CPU-bound parts

### Takeaway
WProf (NSDI 2013) measured where time on the critical path goes: computation was up to 35% (HTML parsing alone 10%), DNS about 13%, and server time about 8%. SPDY helped only at high RTTs, and caching gains were "not proportional to saved bytes". Combined with Belshe's finding that pages used only about 16% of a 10 Mbps link, the evidence says typical page loads are dominated by chains of round trips and by CPU, not raw bandwidth. Two qualifications: a 2025 study finds 18% of sites mainly bandwidth-limited, and video and bulk transfers are a separate, throughput-limited regime.

### Cited Findings
- WProf authors: "Xiao Sophia Wang, Aruna Balasubramanian, Arvind Krishnamurthy, and David Wetherall". — [WProf paper (PDF)](https://homes.cs.washington.edu/~arvind/papers/wprof.pdf); [USENIX NSDI '13 page](https://usenix.org/conference/nsdi13/technical-sessions/presentation/wang_xiao)
- Setup: "We experiment with the top 200 most visited websites from Alexa"; "we present results from the 150 websites that provide complete runs."; "We use DummyNet [10] to provide a stable network connection of 10Mbps bandwidth". — [WProf](https://homes.cs.washington.edu/~arvind/papers/wprof.pdf)
- **[Measured-lab]** Where the time goes:
  - "We find that computation is a significant factor that makes up as much as 35% of the critical path"
  - "computation (mostly HTML parsing and JavaScript execution) comprises 35% of the critical path"
  - "HTML parsing costs the most in computation, at 10%."
  - "CSS evaluation and rendering only cost a small fraction of page load time."
  - "DNS lookup incurs almost 13% of the critical path delay."
  - "The server roundabout time is 8% of the critical path."
  - "synchronous JavaScript plays a significant role in page load time by blocking HTML parsing"
  - Source: [WProf](https://homes.cs.washington.edu/~arvind/papers/wprof.pdf)
- **[Measured-lab]** Caching and protocol optimizations:
  - "Caching reduces page load time, but the reduction is not proportional to the number of cached objects"; "Caching gains are not proportional to saved bytes."; "For 50% of the pages, caching decreases page load time by over 40%."
  - "SPDY reduces page load time only for networks with high RTTs and mod pagespeed helps little on an average page."; "under 200ms RTT, SPDY improves page load time by 5%–40% for 30% of the pages."; "SPDY provides few benefits to page load time under low RTTs."
  - Source: [WProf](https://homes.cs.washington.edu/~arvind/papers/wprof.pdf)
- Evidence on bandwidth vs. RTT (details in section 1):
  - Belshe: "At 10Mbps, however, web pages can only be downloaded at ~16% of the total capacity" — [Belshe](https://www.belshe.com/2010/05/24/)
  - The 2025 counterpoint: "18% of websites are primarily limited by bandwidth" — [arXiv 2503.03641v1](https://arxiv.org/html/2503.03641v1)
  - RFC 6928: a larger initial window (fewer slow-start round trips) cut average web search latency "11.7% (68 ms)" — [RFC 6928](https://www.rfc-editor.org/rfc/rfc6928.txt)
- **[Measured-prod]** Bytes vs. latency in production: Google Search's 23% HTML byte cut yielded an "improvement of 1.7% overall, and up to 9% on high latency networks" in LCP. — [Chrome blog](https://developer.chrome.com/blog/search-compression-dictionaries?hl=en)
- CPU is untouched by byte savings: "the time to actually parse & execute your enormous JavaScript bundle client-side won't change." — [httptoolkit.com](https://httptoolkit.com/blog/dictionary-compression-performance-zstd-brotli)

### Inferences
- **Answer to objective (a):** on typical broadband, page loads are limited mainly by round trips (DNS, handshakes, slow start, dependency chains) and by client CPU. Bandwidth dominates mainly on slow links, on heavy or bandwidth-limited pages (about 18% in the 2025 study), and for bulk and video transfers, which are about 65–75% of bytes (section 2).
- For ARFP, a first-order net benefit model is:

  net benefit ≈ (bytes saved ÷ effective throughput) + (RTTs removed × RTT) − (added client decode/reconstruction CPU on the critical path) − (any RTTs added for negotiation or dictionary fetch)

  WProf already puts computation at up to 35% of the critical path (2013, desktop). Reconstructing latents or recipes therefore lands on the part of the critical path that byte savings cannot shrink, and mobile CPUs make that worse.

### Gaps
- WProf is from 2013, on desktop, using a 10 Mbps link with SPDY-era pages. I retrieved no modern (2020s) critical-path breakdown from Google/Chrome or academia, and did not fetch any mobile-specific breakdown.
- Per the fetch tool, WProf does not report separate critical-path shares for TCP connection setup or download time.
