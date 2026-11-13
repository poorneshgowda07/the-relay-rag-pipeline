import time
import math
import random
import threading
from typing import Dict, Any, Generator, Tuple, Optional
from config import GROQ_MODEL, GROQ_RPM_LIMIT, GROQ_TPM_LIMIT, GROQ_RPD_LIMIT, STANDIN_CALIBRATION

class RateLimitException(Exception):
    def __init__(self, message: str, limit_type: str, retry_after: float):
        super().__init__(message)
        self.message = message
        self.limit_type = limit_type
        self.retry_after = retry_after
        self.status_code = 429
        self.error_body = {
            "error": {
                "message": message,
                "type": limit_type,
                "code": "rate_limit_exceeded"
            }
        }

class DailyBudgetExhaustedException(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        self.status_code = 429
        self.error_body = {
            "error": {
                "message": message,
                "type": "requests_per_day",
                "code": "daily_quota_exhausted"
            }
        }

class StandinModelService:
    """
    High-fidelity stand-in model service simulating Groq free-tier (llama-3.1-8b-instant).
    Calibrated against measured Groq API latency, sliding-window rate limits,
    concurrency queueing slowdown, and streaming delivery.
    """
    
    def __init__(
        self,
        rpm_limit: int = GROQ_RPM_LIMIT,
        tpm_limit: int = GROQ_TPM_LIMIT,
        rpd_limit: int = GROQ_RPD_LIMIT,
        sleep_scale: float = 0.01
    ):
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        self.rpd_limit = rpd_limit
        self.sleep_scale = sleep_scale
        
        self.lock = threading.Lock()
        self.request_timestamps = []       # [(timestamp, token_count)]
        self.daily_requests_count = 0
        self.active_in_flight = 0
        self.peak_queue_length = 0
        
        # Calibration profile
        self.ttft_p50 = STANDIN_CALIBRATION["ttft_p50_ms"]
        self.ttft_p95 = STANDIN_CALIBRATION["ttft_p95_ms"]
        self.ms_per_token = STANDIN_CALIBRATION["ms_per_token"]
        self.slowdown_factor = STANDIN_CALIBRATION["concurrency_slowdown_factor"]
        self.tail_stall_prob = STANDIN_CALIBRATION["tail_stall_probability"]
        self.tail_stall_ms = STANDIN_CALIBRATION["tail_stall_extra_ms"]

    def reset_window(self):
        with self.lock:
            self.request_timestamps.clear()
            self.active_in_flight = 0
            self.peak_queue_length = 0

    def set_limits(self, rpm: Optional[int] = None, tpm: Optional[int] = None, rpd: Optional[int] = None):
        with self.lock:
            if rpm is not None:
                self.rpm_limit = rpm
            if tpm is not None:
                self.tpm_limit = tpm
            if rpd is not None:
                self.rpd_limit = rpd

    def _clean_sliding_window(self, now: float):
        one_minute_ago = now - 60.0
        self.request_timestamps = [entry for entry in self.request_timestamps if entry[0] > one_minute_ago]

    def _check_rate_limits(self, estimated_tokens: int, now: Optional[float] = None) -> Optional[Tuple[str, float]]:
        current_time = now if now is not None else time.time()
        self._clean_sliding_window(current_time)
        
        # Check daily limit
        if self.daily_requests_count >= self.rpd_limit:
            return ("daily", 28800.0)
            
        # Check RPM
        current_rpm = len(self.request_timestamps)
        if current_rpm >= self.rpm_limit:
            oldest_req = self.request_timestamps[0][0]
            retry_after = max(0.5, round(60.0 - (current_time - oldest_req), 2))
            return ("rpm", retry_after)
            
        # Check TPM
        current_tpm = sum(tokens for _, tokens in self.request_timestamps)
        if (current_tpm + estimated_tokens) > self.tpm_limit:
            oldest_req = self.request_timestamps[0][0]
            retry_after = max(0.5, round(60.0 - (current_time - oldest_req), 2))
            return ("tpm", retry_after)
            
        return None

    def _sample_ttft(self, in_flight: int) -> float:
        """Sample time to first token using log-normal distribution + concurrency penalty."""
        mu = math.log(self.ttft_p50)
        sigma = 0.42
        sample_ms = random.lognormvariate(mu, sigma)
        
        # Concurrency contention slowdown
        contention_mult = 1.0 + (self.slowdown_factor * (in_flight ** 1.3))
        ttft_ms = sample_ms * contention_mult
        
        # Occasional tail stall (noisy neighbor / engine GC)
        if random.random() < self.tail_stall_prob:
            ttft_ms += self.tail_stall_ms
            
        return max(75.0, ttft_ms)

    def generate_streaming(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 400,
        timestamp: Optional[float] = None
    ) -> Generator[Dict[str, Any], None, None]:
        prompt_tokens = max(10, len(prompt + system_prompt) // 4)
        req_time = timestamp if timestamp is not None else time.time()
        
        with self.lock:
            self.active_in_flight += 1
            if self.active_in_flight > self.peak_queue_length:
                self.peak_queue_length = self.active_in_flight
                
            in_flight = self.active_in_flight
            
            # Rate limit check
            limit_hit = self._check_rate_limits(prompt_tokens + 150, now=req_time)
            if limit_hit:
                limit_type, retry_after = limit_hit
                self.active_in_flight -= 1
                if limit_type == "daily":
                    raise DailyBudgetExhaustedException(
                        f"Rate limit reached for model `{GROQ_MODEL}` on requests per day (RPD): Limit {self.rpd_limit}, Used {self.daily_requests_count}."
                    )
                elif limit_type == "rpm":
                    raise RateLimitException(
                        f"Rate limit reached for model `{GROQ_MODEL}` on requests per minute (RPM): Limit {self.rpm_limit}, Used {len(self.request_timestamps)}. Please try again in {retry_after}s.",
                        limit_type="rpm",
                        retry_after=retry_after
                    )
                else:
                    current_tpm = sum(t for _, t in self.request_timestamps)
                    raise RateLimitException(
                        f"Rate limit reached for model `{GROQ_MODEL}` on tokens per minute (TPM): Limit {self.tpm_limit}, Used {current_tpm}, Requested {prompt_tokens + 150}. Please try again in {retry_after}s.",
                        limit_type="tpm",
                        retry_after=retry_after
                    )
                    
            # Record request admission
            self.request_timestamps.append((req_time, prompt_tokens + 150))
            self.daily_requests_count += 1

        try:
            # Sample realistic TTFT
            ttft_ms = self._sample_ttft(in_flight)
            if self.sleep_scale > 0:
                time.sleep((ttft_ms / 1000.0) * self.sleep_scale)
            
            # Synthesize response
            reply_text = self._synthesize_response(prompt, system_prompt)
            words = reply_text.split()
            tokens_out = max(1, len(words) * 4 // 3)
            
            # Yield first token marker
            yield {
                "delta": words[0] + " ",
                "is_first": True,
                "ttft_ms": round(ttft_ms, 1),
                "done": False,
                "tokens_in": prompt_tokens,
                "tokens_out": 1
            }
            
            # Streaming remaining tokens
            inter_token_ms = self.ms_per_token + random.uniform(-0.5, 0.8)
            if self.sleep_scale > 0:
                time.sleep((len(words) * inter_token_ms / 1000.0) * self.sleep_scale)
                
            total_simulated_ms = round(ttft_ms + (tokens_out * inter_token_ms), 1)
            
            # Done
            yield {
                "delta": " ".join(words[1:]),
                "is_first": False,
                "ttft_ms": round(ttft_ms, 1),
                "total_simulated_ms": total_simulated_ms,
                "done": True,
                "tokens_in": prompt_tokens,
                "tokens_out": tokens_out,
                "final_text": reply_text
            }
        finally:
            with self.lock:
                self.active_in_flight = max(0, self.active_in_flight - 1)

    def _synthesize_response(self, prompt: str, system_prompt: str) -> str:
        p_lower = prompt.lower()
        
        # Check for citation verification / critique step
        if "verify" in system_prompt.lower() or "check" in system_prompt.lower():
            if "not discussed" in p_lower or "insufficient" in p_lower or "does not contain" in p_lower:
                return "VERIFICATION: REFUSAL_VALID. The query cannot be answered from the provided library chunks."
            else:
                return "VERIFICATION: PASSED. All claims are supported by cited sections and pages."
                
        # Scope triage step
        if "triage classifier" in system_prompt.lower():
            if any(kw in p_lower for kw in ["quantum", "crispr", "bitcoin", "spacex", "blockchain"]):
                return "TARGET_PAPER: Out of Scope\nSEARCH_QUERY: None"
            elif any(kw in p_lower for kw in ["mimi", "moshi", "audio codec", "duplex", "speech"]):
                return "TARGET_PAPER: Moshi\nSEARCH_QUERY: Mimi audio codec frame rate bitrate"
            elif any(kw in p_lower for kw in ["dynamic chunking", "h-net", "tokenizer-free", "byte-level"]):
                return "TARGET_PAPER: Dynamic Chunking\nSEARCH_QUERY: Dynamic chunking H-Net tokenizer-free sequence modeling"
            elif any(kw in p_lower for kw in ["transformer", "attention", "scaled dot-product", "positional encoding"]):
                return "TARGET_PAPER: Attention\nSEARCH_QUERY: scaled dot-product attention formula positional encoding"
            else:
                return "TARGET_PAPER: Multiple\nSEARCH_QUERY: sequence modeling architecture comparison"

        # Check if question is outside library scope
        unanswerable_keywords = ["quantum", "crispr", "bitcoin", "spacex", "protein folding", "alphafold", "blockchain", "gpt-4"]
        if any(kw in p_lower for kw in unanswerable_keywords):
            return "Based on the provided research papers, there is no information or discussion regarding this topic. The library covers only 'Attention Is All You Need', 'Moshi', and 'Dynamic Chunking'."
            
        # Grounded answer synthesis with exact citations
        if "mimi" in p_lower or "frame rate" in p_lower or "bitrate" in p_lower:
            return ("According to 'Moshi: a speech-text foundation model for real-time dialogue' [arXiv:2410.00037v1, Section 3.3 'Neural audio codec Mimi', Page 10], "
                    "Moshi uses Mimi, an autoencoding neural audio codec operating at 12.5 Hz (frame rate of 12.5 frames per second) with an overall bitrate of 1.1 kbps. "
                    "Mimi utilizes Residual Vector Quantization (RVQ) with 8 codebooks for system audio and 8 for user audio, ensuring low latency streaming dialogue.")
                    
        elif "dynamic chunking" in p_lower or "h-net" in p_lower or "tokenizer-free" in p_lower:
            return ("According to 'Dynamic Chunking for End-to-End Hierarchical Sequence Modeling' [arXiv:2507.07955v2, Section 1 'Introduction' & Section 3 'H-Net Architecture', Page 3], "
                    "Dynamic Chunking is an end-to-end tokenizer-free architecture (H-Net) that eliminates heuristic byte-pair encoding (BPE). "
                    "Instead of static subword tokens, H-Net dynamically segments raw bytes into adaptive variable-length hierarchical chunks based on contextual information.")
                    
        elif "scaled dot-product" in p_lower or "multi-head attention" in p_lower or "square root" in p_lower or "1/sqrt(d_k)" in p_lower or "attention is all you need" in p_lower:
            return ("According to 'Attention Is All You Need' [arXiv:1706.03762v7, Section 3.2.1 'Scaled Dot-Product Attention', Page 4], "
                    "attention is computed as softmax((Q * K^T) / sqrt(d_k)) * V. "
                    "The scaling factor 1/sqrt(d_k) is introduced because for large values of d_k, the dot products grow large in magnitude, "
                    "pushing the softmax function into regions with extremely small gradients.")
                    
        elif "latent delay" in p_lower or "inner monologue" in p_lower:
            return ("According to 'Moshi: a speech-text foundation model for real-time dialogue' [arXiv:2410.00037v1, Section 3.4 'Generative audio modeling', Page 12], "
                    "Moshi employs an inner monologue mechanism where text tokens are generated ahead of audio tokens with a small latency offset (~200ms), "
                    "allowing the text backbone to guide coherent phonetic and acoustic speech generation.")
                    
        elif "positional encoding" in p_lower or "sinusoid" in p_lower:
            return ("According to 'Attention Is All You Need' [arXiv:1706.03762v7, Section 3.5 'Positional Encoding', Page 6], "
                    "the model uses sine and cosine functions of different frequencies: PE(pos, 2i) = sin(pos/10000^(2i/d_model)) and "
                    "PE(pos, 2i+1) = cos(pos/10000^(2i/d_model)), allowing the model to easily learn to attend by relative positions.")
                    
        elif "vocabulary size" in p_lower or "bpe tokenizer" in p_lower:
            return ("According to 'Dynamic Chunking for End-to-End Hierarchical Sequence Modeling' [arXiv:2507.07955v2, Section 1 'Introduction', Page 2], "
                    "the byte-level H-Net operates directly on raw bytes and is tokenizer-free, meaning it does not use a subword BPE tokenizer vocabulary. "
                    "Instead of thousands of subword tokens, its base vocabulary consists strictly of the 256 fundamental byte values.")

        else:
            return ("According to the retrieved papers [arXiv:1706.03762v7, Section 3, Page 3; arXiv:2410.00037v1, Section 2, Page 4], "
                    "the architecture addresses sequence modeling challenges through attention mechanisms and dynamic representation without fixed token constraints.")

# Global standin service instance
standin_service = StandinModelService()
