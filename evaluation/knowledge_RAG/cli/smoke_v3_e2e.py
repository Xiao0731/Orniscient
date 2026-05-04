from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified Harness wrapper for V3 KG E2E smoke test.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--dataset", type=str, default="Bird-Con")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--kg-backend", choices=["neo4j"], default="neo4j")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--intermediate-dir", type=str, default="kg_v2/outputs/intermediate")
    parser.add_argument("--graph-out-dir", type=str, default="kg_v2/outputs/graph_v3_smoke")
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--skip-neo4j", action="store_true")
    parser.add_argument("--clear-smoke-graph", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.no_llm:
        print("[WARN] This smoke test never calls an LLM; proceeding as --no-llm.")
    cmd = [
        sys.executable,
        "kg_v2/Step4_graph/smoke_v3_kg_e2e.py",
        "--intermediate-dir",
        args.intermediate_dir,
        "--graph-out-dir",
        args.graph_out_dir,
        "--sample-size",
        str(args.sample_size),
    ]
    if args.skip_neo4j:
        cmd.append("--skip-neo4j")
    if args.clear_smoke_graph:
        cmd.append("--clear-smoke-graph")
    print("[knowledge_RAG smoke] " + " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
