import re
import math
import threading
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from config import RETRIEVAL_SETTINGS
from fetcher import build_chunked_corpus

def tokenize(text: str) -> List[str]:
    """Simple alphanumeric tokenizer for BM25 indexing."""
    return re.findall(r'\b[a-zA-Z0-9_\-]{2,}\b', text.lower())

class PaperRetriever:
    """Multi-setting retriever over the 3 arXiv papers with BM25 and cross-feature re-ranking."""
    
    def __init__(self, setting_key: str = "B"):
        self.setting_key = setting_key
        self.config = RETRIEVAL_SETTINGS.get(setting_key, RETRIEVAL_SETTINGS["B"])
        self.chunk_size = self.config["chunk_size"]
        self.chunk_overlap = self.config["chunk_overlap"]
        self.top_k = self.config["top_k"]
        self.rerank = self.config["rerank"]
        
        self.chunks: List[Dict[str, Any]] = []
        self.bm25: Optional[BM25Okapi] = None
        self._load_and_index()
        
    def _load_and_index(self):
        self.chunks = build_chunked_corpus(self.chunk_size, self.chunk_overlap)
        tokenized_corpus = [tokenize(c["text"] + " " + c["section"] + " " + c["paper_title"]) for c in self.chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
    def retrieve(self, query: str, top_k: Optional[int] = None, paper_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        k = top_k if top_k is not None else self.top_k
        query_tokens = tokenize(query)
        if not query_tokens or not self.bm25:
            return []
            
        raw_scores = self.bm25.get_scores(query_tokens)
        
        candidates = []
        for idx, score in enumerate(raw_scores):
            chunk = self.chunks[idx]
            if paper_filter and paper_filter.lower() not in chunk["paper_id"].lower() and paper_filter.lower() not in chunk["paper_title"].lower():
                continue
            candidates.append({
                "chunk": chunk,
                "score": float(score),
                "index": idx
            })
            
        candidates.sort(key=lambda x: x["score"], reverse=True)
        top_candidates = candidates[:max(k * 3, 10)]
        
        if self.rerank:
            # Re-ranker: Combines BM25 with query phrase coverage, title/section affinity, and length penalty
            for cand in top_candidates:
                chunk_text_lower = cand["chunk"]["text"].lower()
                section_lower = cand["chunk"]["section"].lower()
                title_lower = cand["chunk"]["paper_title"].lower()
                
                # Bonus for exact query phrase matches
                phrase_bonus = 0.0
                if query.lower() in chunk_text_lower:
                    phrase_bonus += 3.5
                
                # Bonus for token matches in section title
                section_bonus = sum(1.5 for token in query_tokens if token in section_lower)
                
                # Bonus for target paper mentions in query
                paper_bonus = sum(2.0 for token in query_tokens if token in title_lower)
                
                cand["rerank_score"] = cand["score"] + phrase_bonus + section_bonus + paper_bonus
                
            top_candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
            
        selected = top_candidates[:k]
        
        results = []
        for rank, item in enumerate(selected, 1):
            c = item["chunk"]
            results.append({
                "rank": rank,
                "chunk_id": c["chunk_id"],
                "paper_id": c["paper_id"],
                "paper_title": c["paper_title"],
                "section": c["section"],
                "page": c["page"],
                "text": c["text"],
                "score": item.get("rerank_score", item["score"])
            })
            
        return results

# Shared global retrievers cache with lock
_RETRIEVER_INSTANCES = {}
_RETRIEVER_LOCK = threading.Lock()

def get_retriever(setting_key: str = "B") -> PaperRetriever:
    with _RETRIEVER_LOCK:
        if setting_key not in _RETRIEVER_INSTANCES:
            _RETRIEVER_INSTANCES[setting_key] = PaperRetriever(setting_key)
        return _RETRIEVER_INSTANCES[setting_key]

def prewarm_all_retrievers():
    """Pre-initialize retrievers for settings A, B, and C."""
    for key in ["A", "B", "C"]:
        get_retriever(key)

def retrieve_passages_tool(query: str, setting: str = "B", paper_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Tool function to be invoked by the pipeline agent."""
    retriever = get_retriever(setting)
    return retriever.retrieve(query, paper_filter=paper_filter)

if __name__ == "__main__":
    for s_key in ["A", "B", "C"]:
        r = get_retriever(s_key)
        q = "What is the Mimi neural audio codec and its frame rate in Moshi?"
        res = r.retrieve(q)
        print(f"\n--- Setting {s_key} (Top {len(res)}) ---")
        for hit in res:
            print(f"[{hit['paper_title']} | Sec: {hit['section']} | Page {hit['page']}] (score: {hit['score']:.2f})")
            print(f"Snippet: {hit['text'][:120]}...\n")
