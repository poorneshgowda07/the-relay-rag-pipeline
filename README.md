# The Relay: Resilient ArXiv Research Assistant Pipeline

This repository contains the complete implementation, benchmark harness, empirical results, and 2-page write-up for **The Relay** assignment.

---

## Quickstart

### Prerequisites
Python 3.10+ (tested and verified on Python 3.13). Dependencies installed via pip:
```bash
pip install pypdf groq rank_bm25 numpy httpx pydantic
```

### Reproduce All Benchmarks & Tables
To run all 5 load scenarios, evaluate the 3 retrieval configurations across 18 curated questions, regenerate `results.csv`, and output all required markdown tables:
```bash
py -3.13 run_experiments.py
```

*(Note: If a `GROQ_API_KEY` is present in the environment or `.env`, real live calls will be probed; otherwise, the calibrated stand-in model service executes the suite).*

---

## Directory Layout

- **`results.csv`**: Raw benchmark output containing 174 request logs with the exact required schema:
  `request_id, scenario, source, start_time, first_token_ms, total_ms, status, retries, tokens_in, tokens_out, retrieval_setting, answer_grade`.
- **`writeup.md`**: Complete 2-page report using the exact required headings in order, containing all tables, latency breakdowns, Vaani feedback, and reflections.
- **`conversation_history.md`**: Complete unedited conversation transcript between user and assistant.
- **`papers/`**: The three downloaded arXiv research papers at exact required versions:
  - `1706.03762v7.pdf`: *Attention Is All You Need*
  - `2410.00037v1.pdf`: *Moshi: a speech-text foundation model for real-time dialogue*
  - `2507.07955v2.pdf`: *Dynamic Chunking for End-to-End Hierarchical Sequence Modeling*
- **`src/`**:
  - `pipeline.py`: The 4-step pipeline (Triage, Retrieval Tool, Synthesis, Verification Loop).
  - `standin_service.py`: Calibrated Groq free-tier stand-in model service (30 RPM, 6k TPM, RPD, non-linear concurrency contention, streaming, 429 generation).
  - `retriever.py`: BM25 and cross-feature re-ranker with section/page provenance.
  - `fetcher.py`: PDF downloader and page-aware chunking engine.
  - `questions.py`: 18 curated evaluation questions (answerable, unanswerable, cross-paper, adversarial).
  - `harness.py`: Benchmark load generator for steady, burst, sustained overload, limit halved, and daily exhausted scenarios.
  - `llm_client.py`: Unified streaming client interface.
  - `config.py`: Centralized configuration, limits, and file paths.
- **`data/`**: Cached pre-parsed pages (`pages_cache.json`) and corpus representations for instant execution.
