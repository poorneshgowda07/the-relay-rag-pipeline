import os
import re
import json
import urllib.request
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader
from config import PAPERS, PAPERS_DIR, DATA_DIR

PAGES_CACHE_FILE = DATA_DIR / "pages_cache.json"

def download_papers():
    """Download arXiv papers if not already present."""
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TheRelayResearch/1.0"
    }
    
    for key, meta in PAPERS.items():
        dest = PAPERS_DIR / meta["filename"]
        if dest.exists() and dest.stat().st_size > 10000:
            continue
        print(f"[Fetcher] Downloading {meta['title']} ({meta['id']}) from {meta['url']}...")
        req = urllib.request.Request(meta["url"], headers=headers)
        with urllib.request.urlopen(req) as resp, open(dest, "wb") as f:
            f.write(resp.read())
        print(f"[Fetcher] Saved {dest} ({dest.stat().st_size} bytes)")

def get_all_pages() -> List[Dict[str, Any]]:
    """Loads all pages from cache or extracts from PDFs once and caches."""
    download_papers()
    if PAGES_CACHE_FILE.exists():
        with open(PAGES_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
            
    print("[Fetcher] Parsing PDFs for the first time...")
    all_pages = []
    section_pattern = re.compile(
        r'^(?:(?:\d+\.?)+\s+[A-Z][A-Za-z0-9\s\-:]{2,40}|Abstract|References|Conclusion|Background|Architecture)$',
        re.MULTILINE
    )
    
    for key, meta in PAPERS.items():
        pdf_path = PAPERS_DIR / meta["filename"]
        reader = PdfReader(str(pdf_path))
        current_section = "Abstract / Intro"
        
        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            raw_text = page.extract_text() or ""
            text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', raw_text)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            for line in lines:
                if section_pattern.match(line) and len(line) < 50:
                    current_section = line
            full_page_text = " ".join(lines)
            all_pages.append({
                "paper_id": meta["id"],
                "paper_title": meta["title"],
                "page": page_num,
                "section": current_section,
                "text": full_page_text
            })
            
    with open(PAGES_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(all_pages, f)
    print(f"[Fetcher] Cached {len(all_pages)} pages to {PAGES_CACHE_FILE}")
    return all_pages

def build_chunked_corpus(chunk_size: int = 500, chunk_overlap: int = 75) -> List[Dict[str, Any]]:
    """Chunks the 3 papers using cached page representations."""
    pages = get_all_pages()
    all_chunks = []
    chunk_id = 0
    
    for p in pages:
        words = p["text"].split()
        if not words:
            continue
            
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)
            
            all_chunks.append({
                "chunk_id": f"{p['paper_id']}_p{p['page']}_c{chunk_id}",
                "paper_id": p["paper_id"],
                "paper_title": p["paper_title"],
                "page": p["page"],
                "section": p["section"],
                "text": chunk_text,
                "word_count": len(chunk_words)
            })
            chunk_id += 1
            if end == len(words):
                break
            start += max(1, (chunk_size - chunk_overlap))
            
    return all_chunks

if __name__ == "__main__":
    pages = get_all_pages()
    print(f"Total pages: {len(pages)}")
    chunks = build_chunked_corpus(500, 75)
    print(f"Total chunks: {len(chunks)}")
