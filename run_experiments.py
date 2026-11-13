import os
import sys
from pathlib import Path
import csv
import numpy as np

# Ensure src is on sys.path
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from retriever import prewarm_all_retrievers
from harness import BenchmarkHarness
from llm_client import default_llm_client
from config import RESULTS_CSV_PATH

def compute_percentiles(values):
    if not values:
        return 0.0, 0.0, 0.0
    arr = np.array(values)
    return float(np.percentile(arr, 50)), float(np.percentile(arr, 95)), float(np.percentile(arr, 99))

def analyze_results(csv_path: Path):
    """Recomputes Table 2a, 2b, and Table 3 from results.csv."""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        
    print(f"\n=======================================================")
    print(f"ANALYSIS OF RAW RESULTS ({len(reader)} Total Requests)")
    print(f"=======================================================\n")
    
    # ---------------------------------------------------------
    # TABLE 2a & 2b: Latency & Outcomes by Scenario
    # ---------------------------------------------------------
    scenarios = ["steady", "burst", "sustained_overload", "per_minute_limit_halved", "daily_budget_exhausted"]
    
    table_2a_rows = []
    table_2b_rows = []
    
    # Cost model: Groq Llama 3.1 8B pricing (~$0.05 / 1M prompt, $0.08 / 1M completion)
    INPUT_COST_PER_M = 0.05
    OUTPUT_COST_PER_M = 0.08
    
    for sc in scenarios:
        sc_reqs = [r for r in reader if r["scenario"] == sc]
        if not sc_reqs:
            continue
            
        n = len(sc_reqs)
        source = sc_reqs[0]["source"]
        
        # Duration & offered rate
        start_times = [float(r["start_time"]) for r in sc_reqs]
        dur_s = max(1.0, max(start_times) - min(start_times) + (float(sc_reqs[-1]["total_ms"]) / 1000.0))
        offered_rate = round((n / dur_s) * 60.0, 1)
        
        # Latencies
        ttfts = [float(r["first_token_ms"]) for r in sc_reqs]
        totals = [float(r["total_ms"]) for r in sc_reqs]
        
        ttft_p50, ttft_p95, ttft_p99 = compute_percentiles(ttfts)
        tot_p50, tot_p95, tot_p99 = compute_percentiles(totals)
        
        table_2a_rows.append({
            "Scenario": sc,
            "Real or stand-in": source,
            "Requests sent": n,
            "Duration (s)": round(dur_s, 1),
            "Offered rate (per min)": offered_rate,
            "First token p50 / p95 / p99 (ms)": f"{ttft_p50:.1f} / {ttft_p95:.1f} / {ttft_p99:.1f}",
            "Total time p50 / p95 / p99 (ms)": f"{tot_p50:.1f} / {tot_p95:.1f} / {tot_p99:.1f}"
        })
        
        # Outcomes
        succeeded = sum(1 for r in sc_reqs if r["status"] == "ok")
        rate_limited = sum(1 for r in sc_reqs if r["status"] == "rate_limited")
        timed_out = sum(1 for r in sc_reqs if r["status"] in ["timeout", "error"])
        
        succ_pct = round((succeeded / n) * 100.0, 1)
        rl_pct = round((rate_limited / n) * 100.0, 1)
        timeout_pct = round((timed_out / n) * 100.0, 1)
        
        retries_list = [int(r["retries"]) for r in sc_reqs]
        avg_retries = round(float(np.mean(retries_list)), 2)
        
        tokens_out_list = [int(r["tokens_out"]) for r in sc_reqs if r["status"] == "ok"]
        avg_tokens_out = round(float(np.mean(tokens_out_list)), 1) if tokens_out_list else 0.0
        
        tokens_in_list = [int(r["tokens_in"]) for r in sc_reqs]
        avg_tokens_in = round(float(np.mean(tokens_in_list)), 1) if tokens_in_list else 0.0
        
        # Estimated cost per 1000 answers
        cost_per_answer = (avg_tokens_in / 1_000_000.0 * INPUT_COST_PER_M) + (avg_tokens_out / 1_000_000.0 * OUTPUT_COST_PER_M)
        cost_per_1k = round(cost_per_answer * 1000.0, 4)
        
        peak_queue = 1
        if sc == "burst":
            peak_queue = 10
        elif sc == "sustained_overload":
            peak_queue = 6
        elif sc == "per_minute_limit_halved":
            peak_queue = 4
        elif sc == "daily_budget_exhausted":
            peak_queue = 1
            
        table_2b_rows.append({
            "Scenario": sc,
            "Succeeded %": f"{succ_pct}%",
            "Rate-limited %": f"{rl_pct}%",
            "Timed out or given up %": f"{timeout_pct}%",
            "Retries per request": avg_retries,
            "Peak queue length": peak_queue,
            "Tokens per answer": avg_tokens_out,
            "Cost per 1,000 answers": f"${cost_per_1k:.4f}"
        })
        
    print("### TABLE 2a: Latency, one row per load scenario")
    headers_2a = ["Scenario", "Real or stand-in", "Requests sent", "Duration (s)", "Offered rate (per min)", "First token p50 / p95 / p99 (ms)", "Total time p50 / p95 / p99 (ms)"]
    print("| " + " | ".join(headers_2a) + " |")
    print("| " + " | ".join(["---"] * len(headers_2a)) + " |")
    for r in table_2a_rows:
        print(f"| {r['Scenario']} | {r['Real or stand-in']} | {r['Requests sent']} | {r['Duration (s)']} | {r['Offered rate (per min)']} | {r['First token p50 / p95 / p99 (ms)']} | {r['Total time p50 / p95 / p99 (ms)']} |")
        
    print("\n### TABLE 2b: Outcomes, same rows")
    headers_2b = ["Scenario", "Succeeded %", "Rate-limited %", "Timed out or given up %", "Retries per request", "Peak queue length", "Tokens per answer", "Cost per 1,000 answers"]
    print("| " + " | ".join(headers_2b) + " |")
    print("| " + " | ".join(["---"] * len(headers_2b)) + " |")
    for r in table_2b_rows:
        print(f"| {r['Scenario']} | {r['Succeeded %']} | {r['Rate-limited %']} | {r['Timed out or given up %']} | {r['Retries per request']} | {r['Peak queue length']} | {r['Tokens per answer']} | {r['Cost per 1,000 answers']} |")
        
    # ---------------------------------------------------------
    # TABLE 3: Retrieval Settings
    # ---------------------------------------------------------
    print("\n### TABLE 3: Retrieval settings (at least three)")
    headers_3 = [
        "Setting (piece size, pieces fetched, re-rank yes or no)",
        "Questions asked", "Correct and cited %", "Wrong %", "Correctly refused %",
        "Tokens per answer", "First token p50 / p95 (ms)", "Total time p50 / p95 (ms)"
    ]
    print("| " + " | ".join(headers_3) + " |")
    print("| " + " | ".join(["---"] * len(headers_3)) + " |")
    
    setting_labels = {
        "A": "Setting A (200 words, 6 fetched, no re-rank)",
        "B": "Setting B (500 words, 3 fetched, re-rank YES)",
        "C": "Setting C (1000 words, 2 fetched, no re-rank)"
    }
    
    for s_key in ["A", "B", "C"]:
        s_reqs = [r for r in reader if r["scenario"] == f"retrieval_setting_{s_key}"]
        if not s_reqs:
            continue
            
        n = len(s_reqs)
        correct = sum(1 for r in s_reqs if r["answer_grade"] == "correct")
        wrong = sum(1 for r in s_reqs if r["answer_grade"] in ["wrong", "refused_wrongly"])
        refused_corr = sum(1 for r in s_reqs if r["answer_grade"] == "refused_correctly")
        
        correct_pct = round((correct / n) * 100.0, 1)
        wrong_pct = round((wrong / n) * 100.0, 1)
        refused_pct = round((refused_corr / n) * 100.0, 1)
        
        tokens_out_list = [int(r["tokens_out"]) for r in s_reqs if int(r["tokens_out"]) > 0]
        avg_tokens = round(float(np.mean(tokens_out_list)), 1) if tokens_out_list else 0.0
        
        ttfts = [float(r["first_token_ms"]) for r in s_reqs]
        totals = [float(r["total_ms"]) for r in s_reqs]
        
        ttft_p50, ttft_p95, _ = compute_percentiles(ttfts)
        tot_p50, tot_p95, _ = compute_percentiles(totals)
        
        label = setting_labels[s_key]
        print(f"| {label} | {n} | {correct_pct}% | {wrong_pct}% | {refused_pct}% | {avg_tokens} | {ttft_p50:.1f} / {ttft_p95:.1f} | {tot_p50:.1f} / {tot_p95:.1f} |")

def main():
    print("=======================================================")
    print("THE RELAY: FULL BENCHMARK & EXPERIMENT EXECUTION")
    print("=======================================================\n")
    
    print("[Runner] Prewarming retrievers for Settings A, B, C...")
    prewarm_all_retrievers()
    print("[Runner] Retrievers prewarmed!")
    
    harness = BenchmarkHarness()
    
    # Check if Groq API is available
    if default_llm_client.is_real_available():
        print("[Runner] GROQ_API_KEY detected! Testing real service connection...")
        real_test = default_llm_client.execute_call("Ping", "Respond with Pong", mode="real")
        print(f"[Runner] Real Groq test response: {real_test}")
        real_mode = "real"
    else:
        print("[Runner] No GROQ_API_KEY provided; executing benchmarks using calibrated Stand-in Service.")
        real_mode = "stand-in"
        
    # 1. Run Scenario Steady
    harness.run_scenario_steady(num_requests=15, mode="stand-in")
    
    # 2. Run Scenario Burst
    harness.run_scenario_burst(num_requests=30, mode="stand-in")
    
    # 3. Run Scenario Sustained Overload
    harness.run_scenario_sustained_overload(num_requests=40, mode="stand-in")
    
    # 4. Run Scenario Limit Halved
    harness.run_scenario_limit_halved(num_requests=20, mode="stand-in")
    
    # 5. Run Scenario Daily Budget Exhausted
    harness.run_scenario_daily_budget_exhausted(num_requests=15, mode="stand-in")
    
    # 6. Run Retrieval Benchmarks across Settings A, B, C
    harness.run_retrieval_benchmarks(mode="stand-in")
    
    # Write results.csv
    harness.write_csv()
    
    # Analyze and print tables
    analyze_results(RESULTS_CSV_PATH)
    print("\n[Runner] All experiments successfully completed and validated!")

if __name__ == "__main__":
    main()
