from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.knowledge_RAG.cli.common import add_common_args, base_legacy_cmd, run_command, write_manifest_for_args
from evaluation.knowledge_RAG.cli.dry_run import run_dry_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run subjective evaluation with unified knowledge_RAG modes.")
    add_common_args(parser)
    parser.add_argument("--fewshot-root", type=str, default="evaluation/fewshot_examples")
    parser.add_argument("--modes", nargs="*", default=["zero_shot", "few_shot", "cot"])
    parser.set_defaults(dataset_group="subjective")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.dry_run:
        return run_dry_run(args, "subjective", modes=args.modes)
    out_dir = write_manifest_for_args(args, "subjective", modes=args.modes)
    cmd = base_legacy_cmd(args, "subjective", out_dir)
    if "kg_subjective_answer.py" not in cmd[1]:
        cmd.extend(["--fewshot-root", args.fewshot_root])
    if args.modes and "kg_subjective_answer.py" not in cmd[1]:
        cmd.extend(["--modes", *args.modes])
    return run_command(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
