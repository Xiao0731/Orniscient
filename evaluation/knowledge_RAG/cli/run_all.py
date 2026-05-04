from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.knowledge_RAG.cli.common import run_command
from evaluation.knowledge_RAG.routing.route_configs import DATASET_GROUPS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all unified knowledge_RAG evaluation families.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--knowledge-mode", choices=["none", "text_rag", "kg_v1", "kg_v3", "hybrid"], default="hybrid")
    parser.add_argument("--dataset-group", choices=["objective", "subjective", "structured", "all"], default="all")
    parser.add_argument("--out-root", type=str, default="evaluation/output")
    parser.add_argument("--models", nargs="*", default=["deepseek"])
    parser.add_argument("--objective-datasets", nargs="*", default=None)
    parser.add_argument("--subjective-datasets", nargs="*", default=None)
    parser.add_argument("--structured-datasets", nargs="*", default=None)
    parser.add_argument("--modes", nargs="*", default=["zero_shot", "few_shot", "cot"])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    common = [
        "--question-root", args.question_root,
        "--knowledge-mode", args.knowledge_mode,
        "--out-root", args.out_root,
        "--models", *args.models,
    ]
    if args.resume:
        common.append("--resume")
    if args.dry_run:
        common.append("--dry-run")
    objective = args.objective_datasets or DATASET_GROUPS["objective"]
    subjective = args.subjective_datasets or DATASET_GROUPS["subjective"]
    structured = args.structured_datasets or DATASET_GROUPS["structured"]
    commands = []
    if args.dataset_group in {"objective", "all"}:
        commands.append([sys.executable, "evaluation/knowledge_RAG/cli/run_objective.py", *common, "--dataset-group", "objective", "--datasets", *objective])
    if args.dataset_group in {"subjective", "all"}:
        commands.append([sys.executable, "evaluation/knowledge_RAG/cli/run_subjective.py", *common, "--dataset-group", "subjective", "--datasets", *subjective, "--modes", *args.modes])
    if args.dataset_group in {"structured", "all"}:
        commands.append([sys.executable, "evaluation/knowledge_RAG/cli/run_structured.py", *common, "--dataset-group", "structured", "--datasets", *structured])
    for cmd in commands:
        code = run_command(cmd)
        if code:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
