import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
PAPERS_DIR = BASE_DIR / "papers"
DATA_DIR = BASE_DIR / "data"
RESULTS_CSV_PATH = BASE_DIR / "results.csv"

# ArXiv paper targets
PAPERS = {
    "attention": {
        "id": "1706.03762v7",
        "title": "Attention Is All You Need",
        "url": "https://arxiv.org/pdf/1706.03762v7.pdf",
        "abs_url": "https://arxiv.org/abs/1706.03762v7",
        "filename": "1706.03762v7.pdf"
    },
    "moshi": {
        "id": "2410.00037v1",
        "title": "Moshi: a speech-text foundation model for real-time dialogue",
        "url": "https://arxiv.org/pdf/2410.00037v1.pdf",
        "abs_url": "https://arxiv.org/abs/2410.00037v1",
        "filename": "2410.00037v1.pdf"
    },
    "dynamic_chunking": {
        "id": "2507.07955v2",
        "title": "Dynamic Chunking for End-to-End Hierarchical Sequence Modeling",
        "url": "https://arxiv.org/pdf/2507.07955v2.pdf",
        "abs_url": "https://arxiv.org/abs/2507.07955v2",
        "filename": "2507.07955v2.pdf"
    }
}

# Groq Free-Tier Model & Limits (llama-3.1-8b-instant)
GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_RPM_LIMIT = 30           # Requests Per Minute
GROQ_TPM_LIMIT = 6000         # Tokens Per Minute
GROQ_RPD_LIMIT = 14400        # Requests Per Day
GROQ_MAX_CONCURRENCY = 5      # Maximum recommended concurrent calls before sharp degradation

# Retrieval Settings for Experiments
RETRIEVAL_SETTINGS = {
    "A": {
        "name": "Setting A (Small chunk, top 6, no re-rank)",
        "chunk_size": 200,    # ~200 words / ~800 chars
        "chunk_overlap": 40,
        "top_k": 6,
        "rerank": False
    },
    "B": {
        "name": "Setting B (Medium chunk, top 3, re-rank)",
        "chunk_size": 500,    # ~500 words / ~2000 chars
        "chunk_overlap": 75,
        "top_k": 3,
        "rerank": True
    },
    "C": {
        "name": "Setting C (Large chunk, top 2, no re-rank)",
        "chunk_size": 1000,   # ~1000 words / ~4000 chars
        "chunk_overlap": 150,
        "top_k": 2,
        "rerank": False
    }
}

# Stand-in Simulation Defaults (calibrated against real Groq measurements)
STANDIN_CALIBRATION = {
    "ttft_p50_ms": 210.0,
    "ttft_p95_ms": 480.0,
    "ttft_p99_ms": 820.0,
    "ms_per_token": 5.4,       # ~185 tokens/sec
    "concurrency_slowdown_factor": 0.08, # latency increase per in-flight request
    "tail_stall_probability": 0.02,     # 2% chance of slow success / stall
    "tail_stall_extra_ms": 1200.0
}
