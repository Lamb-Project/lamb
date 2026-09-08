#!/usr/bin/env python3
"""Compare two document cache test runs and generate latency comparison graph.

The primary metric is doc_rag_time_ms (document fetch time), which shows the
direct impact of caching. The total_time_ms boxplot is included for context
but may show small differences since LLM inference dominates total latency.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_summary(path: Path) -> dict:
    if not path.exists():
        print(f"ERROR: {path} not found")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict]:
    results = []
    with open(path) as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results


def generate_comparison_graph(
    no_cache_data: list[dict], with_cache_data: list[dict],
    no_cache_summary: dict, with_cache_summary: dict,
    output_path: Path,
):
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    ax1 = axes[0]
    no_cache_total = sorted([r["total_time_ms"] for r in no_cache_data if r.get("status") == 200])
    with_cache_total = sorted([r["total_time_ms"] for r in with_cache_data if r.get("status") == 200])

    positions = [1, 2]
    bp = ax1.boxplot(
        [no_cache_total, with_cache_total],
        positions=positions, widths=0.5,
        labels=["No cache", "With cache"],
        patch_artist=True,
    )
    bp["boxes"][0].set_facecolor("#f87171")
    bp["boxes"][1].set_facecolor("#4ade80")

    ax1.set_ylabel("Total request time (ms)")
    ax1.set_title("Total Request Latency (LLM-dominated)")
    ax1.grid(True, alpha=0.3, axis="y")

    no_mean = statistics.mean(no_cache_total) if no_cache_total else 0
    with_mean = statistics.mean(with_cache_total) if with_cache_total else 0
    ax1.text(1, no_mean, f"μ={no_mean:.0f}ms", ha="center", va="bottom", fontsize=9, color="#dc2626")
    ax1.text(2, with_mean, f"μ={with_mean:.0f}ms", ha="center", va="bottom", fontsize=9, color="#16a34a")

    ax2 = axes[1]
    no_cache_doc = sorted([r["doc_rag_time_ms"] for r in no_cache_data if r.get("doc_rag_time_ms") is not None])
    with_cache_doc = sorted([r["doc_rag_time_ms"] for r in with_cache_data if r.get("doc_rag_time_ms") is not None])

    bp2 = ax2.boxplot(
        [no_cache_doc, with_cache_doc],
        positions=positions, widths=0.5,
        labels=["No cache", "With cache"],
        patch_artist=True,
    )
    bp2["boxes"][0].set_facecolor("#f87171")
    bp2["boxes"][1].set_facecolor("#4ade80")

    ax2.set_ylabel("Document RAG fetch time (ms)")
    ax2.set_title("Document RAG Latency (primary metric)")
    ax2.grid(True, alpha=0.3, axis="y")

    no_doc_mean = statistics.mean(no_cache_doc) if no_cache_doc else 0
    with_doc_mean = statistics.mean(with_cache_doc) if with_cache_doc else 0
    ax2.text(1, no_doc_mean, f"μ={no_doc_mean:.0f}ms", ha="center", va="bottom", fontsize=9, color="#dc2626")
    ax2.text(2, with_doc_mean, f"μ={with_doc_mean:.0f}ms", ha="center", va="bottom", fontsize=9, color="#16a34a")

    doc_savings = no_doc_mean - with_doc_mean
    doc_savings_pct = (doc_savings / no_doc_mean * 100) if no_doc_mean > 0 else 0
    fig.suptitle(
        f"Document RAG Cache Impact\n"
        f"Doc RAG savings: {doc_savings:.0f}ms avg ({doc_savings_pct:.1f}%) | "
        f"Cache hit rate: {with_cache_summary.get('cache_hit_rate', 0)}%",
        fontsize=14, fontweight="bold",
    )
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Graph saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Compare document cache test runs")
    parser.add_argument("no_cache_dir", help="Path to no_cache run directory")
    parser.add_argument("with_cache_dir", help="Path to with_cache run directory")
    args = parser.parse_args()

    no_cache_dir = Path(args.no_cache_dir)
    with_cache_dir = Path(args.with_cache_dir)

    no_cache_summary = load_summary(no_cache_dir / "summary.json")
    with_cache_summary = load_summary(with_cache_dir / "summary.json")

    no_cache_data = load_jsonl(no_cache_dir / "requests.jsonl")
    with_cache_data = load_jsonl(with_cache_dir / "requests.jsonl")

    print("=== COMPARISON ===")
    print(f"{'Metric':<30} {'No cache':>15} {'With cache':>15} {'Delta':>15}")
    print("-" * 75)

    metrics = [
        ("Total time mean (ms)", "total_time_ms", "mean"),
        ("Total time median (ms)", "total_time_ms", "median"),
        ("Doc RAG time mean (ms)", "doc_rag_time_ms", "mean"),
        ("Doc RAG time median (ms)", "doc_rag_time_ms", "median"),
        ("Error rate (%)", "error_rate", None),
    ]

    for label, key, subkey in metrics:
        if subkey:
            v1 = no_cache_summary.get(key, {}).get(subkey, 0)
            v2 = with_cache_summary.get(key, {}).get(subkey, 0)
        else:
            v1 = no_cache_summary.get(key, 0)
            v2 = with_cache_summary.get(key, 0)
        delta = v2 - v1
        print(f"{label:<30} {v1:>15.1f} {v2:>15.1f} {delta:>+15.1f}")

    print(f"\nCache hit rate: {with_cache_summary.get('cache_hit_rate', 0)}%")
    print(f"Cache hits: {with_cache_summary.get('cache_hits', 0)}")
    print(f"Cache misses: {with_cache_summary.get('cache_misses', 0)}")

    output_path = with_cache_dir.parent / "cache_comparison.png"
    generate_comparison_graph(
        no_cache_data, with_cache_data,
        no_cache_summary, with_cache_summary,
        output_path,
    )

    comparison = {
        "no_cache": no_cache_summary,
        "with_cache": with_cache_summary,
        "delta": {
            "total_time_mean_ms": round(
                with_cache_summary.get("total_time_ms", {}).get("mean", 0)
                - no_cache_summary.get("total_time_ms", {}).get("mean", 0), 1
            ),
            "doc_rag_time_mean_ms": round(
                with_cache_summary.get("doc_rag_time_ms", {}).get("mean", 0)
                - no_cache_summary.get("doc_rag_time_ms", {}).get("mean", 0), 2
            ),
        },
    }
    comparison_file = with_cache_dir.parent / "comparison.json"
    with open(comparison_file, "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"\nComparison saved: {comparison_file}")


if __name__ == "__main__":
    main()
