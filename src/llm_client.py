import os
import time
import random
from typing import Dict, Any, Optional
from config import GROQ_MODEL
from standin_service import standin_service, RateLimitException, DailyBudgetExhaustedException

try:
    from groq import Groq, RateLimitError, APITimeoutError, APIConnectionError
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

class LLMClient:
    """Unified client supporting both real Groq free-tier and calibrated Stand-in service."""
    
    def __init__(self, default_mode: str = "auto"):
        self.default_mode = default_mode
        self.api_key = os.environ.get("GROQ_API_KEY", "").strip()
        self.groq_client = None
        if self.api_key and GROQ_AVAILABLE:
            try:
                self.groq_client = Groq(api_key=self.api_key)
            except Exception as e:
                print(f"[LLMClient] Failed to initialize Groq client: {e}")

    def is_real_available(self) -> bool:
        return bool(self.groq_client and self.api_key)

    def execute_call(
        self,
        prompt: str,
        system_prompt: str = "You are a research assistant answering questions using provided paper citations.",
        mode: Optional[str] = None,
        timeout: float = 12.0,
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Executes a call to either Real Groq or Stand-in model, streaming chunks
        and measuring TTFT and total duration.
        """
        chosen_mode = mode if mode else self.default_mode
        if chosen_mode == "auto":
            chosen_mode = "real" if self.is_real_available() else "stand-in"
            
        start_time = timestamp if timestamp is not None else time.time()
        
        if chosen_mode == "real" and self.is_real_available():
            return self._call_real(prompt, system_prompt, start_time, timeout)
        else:
            return self._call_standin(prompt, system_prompt, start_time, timeout, timestamp=timestamp)

    def _call_real(self, prompt: str, system_prompt: str, start_time: float, timeout: float) -> Dict[str, Any]:
        first_token_time = None
        full_text = []
        tokens_in = max(10, len(prompt + system_prompt) // 4)
        tokens_out = 0
        
        try:
            stream = self.groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=450,
                stream=True,
                timeout=timeout
            )
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    if first_token_time is None:
                        first_token_time = time.time()
                    full_text.append(content)
                    
            now = time.time()
            ttft_ms = (first_token_time - start_time) * 1000.0 if first_token_time else (now - start_time) * 1000.0
            total_ms = (now - start_time) * 1000.0
            reply = "".join(full_text)
            tokens_out = max(1, len(reply.split()) * 4 // 3)
            
            return {
                "source": "real",
                "status": "ok",
                "text": reply,
                "first_token_ms": round(ttft_ms, 1),
                "total_ms": round(total_ms, 1),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "error": None
            }
            
        except RateLimitError as e:
            now = time.time()
            return {
                "source": "real",
                "status": "rate_limited",
                "text": "",
                "first_token_ms": round((now - start_time) * 1000.0, 1),
                "total_ms": round((now - start_time) * 1000.0, 1),
                "tokens_in": tokens_in,
                "tokens_out": 0,
                "error": str(e)
            }
        except (APITimeoutError, TimeoutError) as e:
            now = time.time()
            return {
                "source": "real",
                "status": "timeout",
                "text": "",
                "first_token_ms": round((now - start_time) * 1000.0, 1),
                "total_ms": round((now - start_time) * 1000.0, 1),
                "tokens_in": tokens_in,
                "tokens_out": 0,
                "error": "Request timed out"
            }
        except Exception as e:
            now = time.time()
            return {
                "source": "real",
                "status": "error",
                "text": "",
                "first_token_ms": round((now - start_time) * 1000.0, 1),
                "total_ms": round((now - start_time) * 1000.0, 1),
                "tokens_in": tokens_in,
                "tokens_out": 0,
                "error": str(e)
            }

    def _call_standin(self, prompt: str, system_prompt: str, start_time: float, timeout: float, timestamp: Optional[float] = None) -> Dict[str, Any]:
        first_token_time = None
        full_text = []
        tokens_in = max(10, len(prompt + system_prompt) // 4)
        tokens_out = 0
        
        sim_ttft = None
        sim_total = None
        wall_start = time.time()
        try:
            stream_gen = standin_service.generate_streaming(prompt, system_prompt, timestamp=timestamp)
            for chunk in stream_gen:
                if (time.time() - wall_start) > timeout:
                    raise TimeoutError("Client timeout exceeded")
                if chunk["is_first"]:
                    first_token_time = time.time()
                    sim_ttft = chunk.get("ttft_ms")
                if chunk["delta"]:
                    full_text.append(chunk["delta"])
                if chunk["done"]:
                    sim_total = chunk.get("total_simulated_ms")
                    tokens_in = chunk["tokens_in"]
                    tokens_out = chunk["tokens_out"]
                    
            now = time.time()
            ttft_ms = sim_ttft if sim_ttft is not None else round(((first_token_time - start_time) * 1000.0), 1)
            total_ms = sim_total if sim_total is not None else round(((now - start_time) * 1000.0), 1)
            
            return {
                "source": "stand-in",
                "status": "ok",
                "text": "".join(full_text).strip(),
                "first_token_ms": round(ttft_ms, 1),
                "total_ms": round(total_ms, 1),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "error": None
            }
            
        except (RateLimitException, DailyBudgetExhaustedException) as e:
            retry_val = getattr(e, "retry_after", 5.0)
            return {
                "source": "stand-in",
                "status": "rate_limited",
                "text": "",
                "first_token_ms": 0.0,
                "total_ms": round(random.uniform(28.0, 45.0), 1),
                "tokens_in": tokens_in,
                "tokens_out": 0,
                "retry_after": retry_val,
                "error": str(e)
            }
        except TimeoutError as e:
            now = time.time()
            return {
                "source": "stand-in",
                "status": "timeout",
                "text": "",
                "first_token_ms": round((now - start_time) * 1000.0, 1),
                "total_ms": round((now - start_time) * 1000.0, 1),
                "tokens_in": tokens_in,
                "tokens_out": 0,
                "error": "Request timed out"
            }
        except Exception as e:
            now = time.time()
            return {
                "source": "stand-in",
                "status": "error",
                "text": "",
                "first_token_ms": round((now - start_time) * 1000.0, 1),
                "total_ms": round((now - start_time) * 1000.0, 1),
                "tokens_in": tokens_in,
                "tokens_out": 0,
                "error": str(e)
            }

default_llm_client = LLMClient()
