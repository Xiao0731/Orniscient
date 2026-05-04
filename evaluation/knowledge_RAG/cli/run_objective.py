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
    parser = argparse.ArgumentParser(description="Run objective evaluation with unified knowledge_RAG modes.")
    add_common_args(parser)
    parser.set_defaults(dataset_group="objective")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.dry_run:
        return run_dry_run(args, "objective")
    out_dir = write_manifest_for_args(args, "objective")
    return run_command(base_legacy_cmd(args, "objective", out_dir))


if __name__ == "__main__":
    raise SystemExit(main())
