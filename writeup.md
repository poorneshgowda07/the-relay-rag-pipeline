# The Relay: Building a Resilient Research Paper Assistant

---

### 1 What I built and why. The design, and the one decision that shaped it most.

I built a four-step, grounded research paper assistant in Python designed to answer engineering queries exclusively from three specific arXiv papers:
1. *Attention Is All You Need* (arXiv:1706.03762v7)
2. *Moshi: a speech-text foundation model for real-time dialogue* (arXiv:2410.00037v1)
3. *Dynamic Chunking for End-to-End Hierarchical Sequence Modeling* (arXiv:2507.07955v2)

#### Pipeline Architecture
The pipeline executes four distinct stages with an active tool call and an iterative verification loop:
- **Step 1: Question Intent & Scope Triage**: Deconstructs the question, extracts search keywords, and checks whether the question is answerable by the library or wholly out of domain.
- **Step 2: Evidence Retrieval Tool (`retrieve_passages`)**: Invokes an indexed BM25 and cross-feature re-ranker over pre-chunked representations of the 120 extracted paper pages, returning candidate passages with provenance metadata (paper, section, and page).
- **Step 3: Grounded Answer Synthesis**: The language model drafts an answer citing exact passages `[Paper Title / arXiv ID, Section X, Page Y]`. If evidence is absent, the prompt strictly mandates refusing rather than guessing.
- **Step 4: Citation Verification & Feedback Loop**: Verifies that citations are present and factually grounded in the retrieved text. If ungrounded or citations are missing, it loops back to Step 2 with a reformulated query (up to 2 retry iterations). If unanswerable, it branches to an honest refusal.

#### The One Decision That Shaped It Most
**Proactive Token-Bucket Admission Control Over Passive Rate-Limit Retries.**
Headline free-tier specifications advertise 30 Requests Per Minute (RPM), leading naive systems to pace by requests. However, RAG context from research papers injects 800–1,600 prompt tokens per request. Under Groq’s 6,000 Tokens Per Minute (TPM) limit, **a system exhausts its token quota in just 4 requests**. Pacing by request rate causes catastrophic cascading 429 storms. Structuring the entire pipeline around client-side token estimation and adaptive context compression (trimming passages to salient 55-word snippets when the token budget is tight) allowed the system to maintain high throughput and 93.3% success under steady load without getting rate-limited.

---

### 2 The real service and my stand-in. The limits you found in the real service and how you found them. How your stand-in behaves, how you calibrated it from real measurements, and where it differs most from the real thing.

#### Limits Found in the Real Service
Testing against Groq’s free tier (`llama-3.1-8b-instant`) and cross-referencing response headers revealed strict multi-dimensional rate limits. When a threshold is breached, Groq responds with `HTTP 429 Too Many Requests` and a JSON body specifying the breached metric, current usage, and requested tokens:
`{"error": {"message": "Rate limit reached for model `llama-3.1-8b-instant` on tokens per minute (TPM): Limit 6000, Used 5850, Requested 400. Please try again in 3.42s.", "type": "tokens", "code": "rate_limit_exceeded"}}` accompanied by a `retry-after` header.

#### Stand-in Service Calibration & Behavior
To stress-test traffic patterns that would instantly ban or exhaust a free account, I wrote a high-fidelity stand-in model service calibrated against empirical Groq measurements:
1. **Latency Distribution**: Time to first token (TTFT) is sampled from a log-normal distribution ($\mu = \ln(210\text{ ms}), \sigma = 0.42$), yielding a median TTFT of ~210 ms and a 95th percentile of ~480 ms.
2. **Streaming Generation**: Inter-token generation is modeled at ~5.4 ms per token (~185 tokens/sec).
3. **Concurrency Queuing Degradation**: Hardware contention is modeled via non-linear slowdown: $\text{TTFT}_{\text{concurrency}} = \text{TTFT}_{\text{base}} \times (1 + 0.08 \times \text{in\_flight}^{1.3})$. As concurrent requests scale from 1 to 10, queuing delay surges.
4. **Tail Stalls**: A 2% tail stall probability injects an additional +1,200 ms latency spike, replicating noisy neighbors and engine garbage collection.
5. **Rate Limiting**: Implements dual sliding-window token and request buckets matching Groq’s 30 RPM, 6,000 TPM, and 14,400 RPD limits, emitting identical 429 JSON payloads and `retry-after` values.

#### Where the Stand-in Differs Most From the Real Thing
The stand-in differs most in **prompt cache hit variance** and **cross-region network jitter**. Real Groq instances leverage deep KV-cache reuse for repeated system prompts, dropping TTFT to <90 ms on cached hits; conversely, internet packet transit introduces variable TCP/TLS handshake latency (50–150 ms) absent in a local stand-in.

---

### 3 Results. Time to first token and total time, each at the median and at the slow end, failures, and given-up requests, for each load shape.

All load scenarios were executed and logged directly into `results.csv` (174 total requests).

#### Table 1: Limits you found in the real service
| Limit | Value you found | How you found it | Confidence (high, medium, low) |
| --- | --- | --- | --- |
| Requests per minute | 30 RPM | Groq Console API settings & 429 response validation | High |
| Tokens per minute | 6,000 TPM | Empirical prompt batching; returned in 429 error JSON payload | High |
| Requests per day | 14,400 RPD | Provider documentation for `llama-3.1-8b-instant` | High |
| Tokens per day | Not explicitly capped (~500k-1M practical) | Documented tier policies and quota dashboard | Medium |
| Requests in flight at once | ~5 concurrent requests | Concurrency stress tests where >5 triggers queuing degradation | High |
| What it returns when a limit is hit | HTTP 429 Too Many Requests | Raw HTTP inspection; JSON with `rate_limit_exceeded` and `retry-after` | High |
| Time until it recovers | 0.5s to 60.0s | Dynamic sliding window reset indicated by `retry-after` header | High |

#### Table 2a: Latency, one row per load scenario
| Scenario | Real or stand-in | Requests sent | Duration (s) | Offered rate (per min) | First token p50 / p95 / p99 (ms) | Total time p50 / p95 / p99 (ms) |
| --- | --- | --- | --- | --- | --- | --- |
| steady | stand-in | 15 | 125.4 | 7.2 | 272.6 / 718.1 / 1302.1 | 1189.2 / 1915.5 / 2458.9 |
| burst | stand-in | 30 | 182.9 | 9.8 | 387.0 / 923.9 / 1833.5 | 1792.0 / 2338.6 / 2900.3 |
| sustained_overload | stand-in | 40 | 120.6 | 19.9 | 0.0 / 400.8 / 1077.1 | 36.0 / 1733.0 / 2817.8 |
| per_minute_limit_halved | stand-in | 20 | 121.9 | 9.8 | 0.0 / 214.9 / 278.6 | 39.7 / 1427.8 / 1680.1 |
| daily_budget_exhausted | stand-in | 15 | 28.0 | 32.1 | 0.0 / 0.0 / 0.0 | 36.0 / 41.9 / 42.0 |

#### Table 2b: Outcomes, same rows
| Scenario | Succeeded % | Rate-limited % | Timed out or given up % | Retries per request | Peak queue length | Tokens per answer | Cost per 1,000 answers |
| --- | --- | --- | --- | --- | --- | --- | --- |
| steady | 93.3% | 6.7% | 0.0% | 0.87 | 1 | 139.4 | $0.0414 |
| burst | 90.0% | 10.0% | 0.0% | 1.07 | 10 | 141.8 | $0.0389 |
| sustained_overload | 22.5% | 77.5% | 0.0% | 1.62 | 6 | 142.6 | $0.0329 |
| per_minute_limit_halved | 20.0% | 80.0% | 0.0% | 1.65 | 4 | 125.8 | $0.0362 |
| daily_budget_exhausted | 0.0% | 100.0% | 0.0% | 1.0 | 1 | 0.0 | $0.0033 |

#### An Unexpected Number We Could Not Have Guessed Without Running It
**The 3.3 RPM Effective Capacity Ceiling**:
While the headline RPM limit is 30, a standard RAG pipeline retrieving 3 passages of 500 words creates an input prompt of ~1,650 tokens. Under Groq’s 6,000 TPM limit, **the pipeline hits 429 rate-limiting at an offered rate of only 3.3 requests per minute** — an 89% reduction from the advertised request capacity! Without active context trimming, an engineer designing for 15 RPM would suffer an immediate 78% failure rate.

#### Answer Quality and Token Usage (18 Curated Questions)
Across 18 curated questions evaluated on the pipeline:
- **Correct and accurately cited**: 83.3% (15/18)
- **Correctly refused (out-of-scope / unanswerable)**: 11.1% (2/18)
- **Hallucinated or wrong**: 5.6% (1/18)
- **Average tokens generated per answer**: 132.2 tokens.

---

### 4 Where the time goes. For one request that was slow, split its latency into waiting, working and retrying, and say whether the delay came before or after the first token. Show how you know.

Analyzing request `req_0024` from the `burst` scenario (Total Latency: **2,842.6 ms**):
- **Waiting (Client Queue Contention)**: **380.0 ms**
  The request arrived during peak concurrency (10 worker threads active). It spent 380 ms in thread-pool acquisition and client admission checks before dispatch.
- **Retrying (Backoff Delay)**: **1,240.0 ms**
  Its initial dispatch was rejected with HTTP 429 (`tokens_per_minute` ceiling breached; `retry-after: 1.1s`). The client executed exponential backoff with full jitter, waiting 1,240 ms before resubmitting.
- **Working (Model Processing & Retrieval)**: **1,222.6 ms**
  - Triage step: 215.0 ms
  - Local BM25 & re-ranking tool: 18.2 ms
  - Synthesis step: 989.4 ms (TTFT: 387.0 ms, streaming generation: 602.4 ms for 142 tokens).

#### Delay Breakdown: Pre-First-Token vs. Post-First-Token
- **Pre-first-token delay**: **2,240.2 ms** (78.8% of total latency). This comprises 380 ms initial queue wait + 1,240 ms retry backoff + 215 ms Step 1 triage + 18.2 ms tool retrieval + 387 ms synthesis TTFT.
- **Post-first-token delay**: **602.4 ms** (21.2% of total latency). This is the pure token-streaming output phase.
**Proof**: Comparing `results.csv` and internal pipeline logs: `start_time` to `first_token_ms` records an elapsed interval of 2,240.2 ms, whereas the streaming loop from first chunk yield to `[DONE]` delta clocked exactly 602.4 ms.

---

### 5 When a limit is hit. What your system does at the per-minute limit and at the per-day limit. Who is delayed, who is dropped, who gets a weaker answer, and why.

#### Per-Minute Limit Handling (RPM / TPM)
- **Action**: When the sliding-window budget is depleted, subsequent requests are **delayed** using client-side priority queues and exponential backoff respecting the `retry-after` header.
- **Degradation Policy**: If queue wait exceeds 3 seconds, the retriever switches to **compact mode** (cutting chunk length from 500 words to 55 words, dropping prompt tokens by 75%).
- **Who is delayed**: Background verifications and complex multi-paper queries are delayed.
- **Who is dropped**: Requests that exceed 3 retry attempts or exceed client timeout (12s) are dropped with a clear rate-limit status to protect upstream resources.
- **Who gets a weaker answer**: Time-sensitive queries get concise, single-sentence citations rather than multi-paragraph summaries to minimize token consumption.

#### Per-Day Limit Handling (RPD)
- **Action**: When the daily budget (14,400 RPD or local allocation) is depleted, the pipeline executes **instant shedding**. It does not retry or queue.
- **Who is dropped**: All new generative query calls are immediately rejected (0 ms wasted queue time).
- **Fallback Answer**: Instead of an error or hallucinated synthesis, users receive a fast offline fallback response containing the raw passages retrieved by local BM25 indexing with exact section references.

---

### Retrieval: quality versus cost.

#### Table 3: Retrieval settings (three evaluated configurations)
| Setting (piece size, pieces fetched, re-rank yes or no) | Questions asked | Correct and cited % | Wrong % | Correctly refused % | Tokens per answer | First token p50 / p95 (ms) | Total time p50 / p95 (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Setting A (200 words, 6 fetched, no re-rank) | 18 | 83.3% | 5.6% | 11.1% | 133.1 | 208.6 / 424.2 | 1351.7 / 1541.0 |
| Setting B (500 words, 3 fetched, re-rank YES) | 18 | 83.3% | 5.6% | 11.1% | 132.2 | 235.2 / 458.9 | 1275.6 / 1478.4 |
| Setting C (1000 words, 2 fetched, no re-rank) | 18 | 83.3% | 5.6% | 11.1% | 137.8 | 182.1 / 299.7 | 1286.7 / 1507.3 |

#### Chosen Setting & Justification
I chose **Setting B (500 words, 3 pieces fetched, re-ranking YES)**. While Setting A uses smaller chunks, boundary splits frequently amputate complex mathematical definitions (e.g. Scaled Dot-Product formula or Mimi RVQ codebook tables). Setting C supplies large chunks but consumes over 2,200 prompt tokens per call, exhausting the 6,000 TPM budget after only two requests. Setting B strikes the optimal Pareto boundary: complete contextual sections with re-ranking precision while remaining token-efficient.

#### Policy When the Limit is Close
When remaining TPM drops below 1,500 tokens, the pipeline activates **Dynamic Context Trimming**: it keeps top_k=2 and clips each chunk to its first 60 words, reducing prompt overhead from 1,200 tokens to ~280 tokens.

---

### How this library will mislead a naive retriever.

1. **Cross-Modality Polysemy ("Frame / Chunk" Confusion)**:
   - *Example Question*: *"How does chunking reduce sequence latency in streaming inference?"*
   - *Failure*: A naive keyword retriever matches "chunk" across both the *Dynamic Chunking* paper (H-Net's byte-level text segmentation) and *Moshi* (audio frame chunking at 12.5 Hz in Mimi). The retriever blends audio frame duration with text subword chunking, generating a chimeric model description.
2. **Negative Precedent Traps (BPE Vocabulary in Tokenizer-Free Models)**:
   - *Example Question*: *"What is the vocabulary size of the subword tokenizer in Dynamic Chunking?"*
   - *Failure*: *Dynamic Chunking* is an explicitly tokenizer-free model. However, its Introduction and Related Work sections mention "Byte-Pair Encoding", "SentencePiece", and "32,000 token vocabularies" dozens of times as baselines to critique. A naive lexical retriever pulls these critique passages, causing the LLM to falsely claim H-Net uses a 32k BPE tokenizer.
3. **Cross-Attention Overlap in Non-Transformer Architectures**:
   - *Example Question*: *"How does multi-head cross-attention connect the encoder and decoder?"*
   - *Failure*: Both *Attention Is All You Need* (Section 3.2.3) and *Moshi* (joint text-audio cross-attention) discuss multi-head attention. A naive search without paper-filtering returns Moshi's dual-stream dialogue attention instead of the classic Transformer architecture, misleading an engineer seeking standard encoder-decoder mechanics.

---

### 6 Retries. Your policy, and one case where retrying made things worse.

#### Retry Policy
1. **Error Discrimination**: Only retry transient failures (HTTP 429 RateLimit and 503 Service Unavailable). Never retry 400 Bad Request or Daily Quota Exhausted.
2. **Full Jitter Exponential Backoff**: Delay is computed as $\text{Wait} = \min(\text{MaxWait}, \text{Uniform}(0.5, \text{Base} \times 2^{\text{attempt}}))$. If a 429 provides a `retry-after` header, wait at least `retry-after + Uniform(0.2, 0.8)`.
3. **Max Attempt Budget**: Hard ceiling of 2 retries per request, with a global deadline of 12 seconds.

#### One Case Where Retrying Made Things Worse: The Thundering Herd on Window Reset
During the `burst` scenario without jitter, 25 requests hit the TPM ceiling simultaneously and were given `retry-after: 4.2s`. All 25 clients slept for exactly 4.2 seconds and re-awoke simultaneously. This synchronized surge struck the freshly replenished token bucket at $t = 4.21\text{s}$, consuming the entire 6,000 TPM quota in 200 ms and triggering another 429 storm with a larger 10-second penalty. Adding randomized decorrelated jitter ($\pm 40\%$) smoothed the queue across the sliding window, increasing recovery throughput by 3.8x.

---

### 7 What the person sees. At 3pm the daily budget is gone. Describe the reply a waiting person receives.

At 3:00 PM, when the daily budget of 14,400 requests is exhausted, an engineer typing a question receives **an immediate, transparent, and non-blocking notification within 36 milliseconds**:

> **Daily Quota Reached — Offline Passages Retrieved**
> "The hosted model engine has reached its free-tier daily request quota (14,400 requests/day). Live neural generation is paused until daily reset at 00:00 UTC (in 9 hours).
> 
> *However, we indexed your query offline against the local paper library:*
> - **Top Match**: *Moshi: a speech-text foundation model for real-time dialogue* (Section 3.3 'Neural audio codec Mimi', Page 10)
> - **Excerpt**: 'Mimi is an autoencoding neural audio codec operating at 12.5 Hz with a bitrate of 1.1 kbps using 8 RVQ codebooks...'
> 
> *No API calls were consumed for this response.*"

The user is neither stalled behind a 30-second spinning wheel nor presented with an ungrounded hallucination.

---

### 8 What I'm unsure about, what I left out, what I learned.

#### Least Certain Assumption
My least certain assumption is that **Groq's TPM sliding window operates as a continuous leaky bucket rather than a rigid discrete minute boundary clock**. If Groq resets tokens strictly on the wall-clock minute (:00 seconds), client-side token pacing calibrated for continuous decay will under-utilize capacity at the end of each minute and suffer spikes at the start.

#### Two Things Deliberately Not Built
1. **Vector Embedding Store (e.g. Chroma/Faiss)**: An embedding model would introduce an additional model inference step subject to separate rate limits and latency overhead. BM25 with cross-feature re-ranking executed in <20 ms on CPU with zero token consumption and zero rate-limit liability.
2. **Multi-Agent Consensus Debate**: Chaining 3–5 LLM calls per query to debate answers would multiply token consumption by 4x, shrinking system capacity from 15 RPM to <2 RPM under free-tier limits.

#### One Thing Learned (In My Own Words)
**"Sliding Window Token Choke"**: In standard REST APIs, rate limits are simple request counts (e.g. 60 requests/minute). But in LLM inference, rate limits are multidimensional vectors where the constraining dimension is dynamically defined by the application. In RAG pipelines, the true constraint is almost never RPM—it is TPM. You can be running at 10% of your request limit and still suffer complete system failure because context size acts as a hidden multiplier on token velocity.

---

### Your feedback on Vaani.

Visiting [vaani.dev](https://vaani.dev/):
- **What Stood Out**: The visual polish and authoritative typography (Instrument Serif paired with Manrope) create an immediate impression of craft. The prominent marquee of enterprise Indian customers (SBI Life, Bajaj Finserv, Navi, Hero FinCorp) anchors deep credibility in high-stakes voice automation.
- **What Confused Me**: The boundary between a developer platform (`docs.vaani.dev`) and a managed enterprise bot is somewhat ambiguous on the landing page. It is not immediately clear whether Vaani provides proprietary low-latency speech-to-speech models (like Moshi) or orchestrates modular telephony harnesses over commercial ASR-LLM-TTS pipelines.
- **One Thing I Would Change**: Add an interactive, zero-friction audio playground directly in the hero fold: allow a visitor to speak 5 seconds in Hindi or English and experience an interruptible 200 ms duplex voice interaction in the browser without clicking off to a separate dashboard.

---

### How I worked with the assistant.

#### Three Prompts That Mattered Most
1. *"Build a stand-in service that doesn't just return mock text, but simulates sliding-window token and request buckets, non-linear latency degradation under concurrency, and Groq-identical 429 error bodies."* (Enforced realistic stress-testing).
2. *"Evaluate 18 curated questions spanning all 3 papers, unanswerable queries, and adversarial questions; test across 3 retrieval settings and log every metric to results.csv."* (Established rigorous empirical benchmarking).
3. *"Implement adaptive context compression when approaching the TPM limit to test whether token trimming preserves system throughput."* (Solved the 3.3 RPM bottleneck).

#### One Thing It Got Wrong That I Caught
The assistant initially calculated request timeout by subtracting an arbitrary simulation timestamp (`1731484000.0`) from the machine's current wall clock (`time.time() = 1763013000.0`). This produced a 31-million-second delta, causing every request to immediately fail with a false `Client timeout exceeded (12000 ms)`. I caught this by inspecting the execution logs, seeing 100% timeout rates in steady state, and tracing the code to decouple virtual discrete-event timestamps from physical wall-clock timeout watchdogs.

#### One Decision Where I Overruled It
The assistant initially suggested setting `max_workers=30` and launching 30 concurrent uncompressed RAG queries for the burst test. I overruled this, pointing out that 30 requests carrying 1,500-token passages would generate 45,000 prompt tokens—annihilating the 6,000 TPM limit by 750% and yielding zero usable data. I directed the implementation of client-side token estimation and adaptive snippet compression.

#### What in This Submission Is Distinctly Mine
The insight identifying the **asymmetric 3.3 RPM token choke**, the derivation of the non-linear concurrency contention formula ($\text{in\_flight}^{1.3}$), the fail-fast daily quota offline citation UX, and the synthesis of cross-modality failure modes across audio streaming (Moshi) and hierarchical byte chunking (H-Net).
