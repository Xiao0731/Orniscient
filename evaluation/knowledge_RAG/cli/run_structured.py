from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.knowledge_RAG.cli.common import add_common_args, base_legacy_cmd, run_command, write_manifest_for_args
from evaluation.knowledge_RAG.cli.dry_run import run_dry_run


def validate_table_paths(args: argparse.Namespace) -> None:
    selected = set(args.datasets or [])
    if not selected:
        selected = {"List-Global", "Bird-ID", "Bird-Classify"}
    needs_birdbase = bool(selected & {"List-Global", "Bird-ID"})
    needs_order = bool(selected & {"Bird-Classify", "Bird-Classify__Feature-to-Family", "Bird-Classify-Type2"})
    missing: list[str] = []
    if needs_birdbase and not Path(args.birdbase_xlsx).exists():
        missing.append(f"--birdbase-xlsx path not found: {args.birdbase_xlsx}")
    if needs_order and not Path(args.order_xlsx).exists():
        missing.append(f"--order-xlsx path not found: {args.order_xlsx}")
    if missing:
        detail = "\n".join(f"- {item}" for item in missing)
        raise SystemExit(
            "Structured evaluation needs local table files for the selected dataset(s).\n"
            f"{detail}\n"
            "Place the files at data/BIRDBASE.xlsx and data/Order.xlsx, or pass --birdbase-xlsx / --order-xlsx."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run structured evaluation with unified knowledge_RAG modes.")
    add_common_args(parser)
    parser.add_argument("--birdbase-xlsx", type=str, default="data/BIRDBASE.xlsx")
    parser.add_argument("--order-xlsx", type=str, default="data/Order.xlsx")
    parser.add_argument("--list-global-direct-output", dest="list_global_direct_output", action="store_true", default=True)
    parser.add_argument("--no-list-global-direct-output", dest="list_global_direct_output", action="store_false")
    parser.set_defaults(dataset_group="structured")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.dry_run:
        return run_dry_run(args, "structured")
    validate_table_paths(args)
    out_dir = write_manifest_for_args(args, "structured")
    cmd = base_legacy_cmd(args, "structured", out_dir)
    cmd.extend(["--birdbase-xlsx", args.birdbase_xlsx, "--order-xlsx", args.order_xlsx])
    if args.list_global_direct_output:
        cmd.append("--list-global-direct-output")
    return run_command(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
