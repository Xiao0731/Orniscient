from __future__ import annotations

import argparse
from typing import Sequence

try:
    from subjective_aggregate import main as aggregate_main
    from subjective_answer import main as answer_main
    from subjective_common import SUPPORTED_PROMPT_MODES
    from subjective_judge import main as judge_main
    from subjective_rubrics import DEFAULT_SUBJECTIVE_DATASET_ORDER
except ModuleNotFoundError:
    from evaluation.subjective_aggregate import main as aggregate_main
    from evaluation.subjective_answer import main as answer_main
    from evaluation.subjective_common import SUPPORTED_PROMPT_MODES
    from evaluation.subjective_judge import main as judge_main
    from evaluation.subjective_rubrics import DEFAULT_SUBJECTIVE_DATASET_ORDER


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the minimal subjective pipeline: answer -> judge -> aggregate.")
    parser.add_argument("--question-root", type=str, default="question")
    parser.add_argument("--out-dir", type=str, default="evaluation/results_subjective")
    parser.add_argument("--fewshot-root", type=str, default="evaluation/fewshot_examples")
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_SUBJECTIVE_DATASET_ORDER)
    parser.add_argument("--modes", nargs="*", default=list(SUPPORTED_PROMPT_MODES))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")

    parser.add_argument("--answer-question-workers", type=int, default=4)
    parser.add_argument("--answer-max-tokens", type=int, default=1024)
    parser.add_argument("--answer-temperature", type=float, default=0.0)
    parser.add_argument("--answer-retries", type=int, default=2)
    parser.add_argument("--answer-print-every", type=int, default=20)

    parser.add_argument("--judge-question-workers", type=int, default=4)
    parser.add_argument("--judge-workers", type=int, default=2)
    parser.add_argument("--judge-max-tokens", type=int, default=512)
    parser.add_argument("--judge-temperature", type=float, default=0.0)
    parser.add_argument("--judge-request-retries", type=int, default=2)
    parser.add_argument("--judge-parse-retries", type=int, default=1)
    parser.add_argument("--judge-print-every", type=int, default=20)

    parser.add_argument("--skip-answer", action="store_true")
    parser.add_argument("--skip-judge", action="store_true")
    parser.add_argument("--skip-aggregate", action="store_true")
    return parser.parse_args(argv)


def _append_scope_args(cmd: list[str], args: argparse.Namespace, *, include_question_root: bool) -> list[str]:
    if include_question_root:
        cmd.extend(["--question-root", args.question_root])
    cmd.extend(["--out-dir", args.out_dir])
    if args.models:
        cmd.append("--models")
        cmd.extend(args.models)
    if args.datasets:
        cmd.append("--datasets")
        cmd.extend(args.datasets)
    if args.modes:
        cmd.append("--modes")
        cmd.extend(args.modes)
    if args.limit > 0:
        cmd.extend(["--limit", str(args.limit)])
    if args.resume:
        cmd.append("--resume")
    return cmd


def build_answer_argv(args: argparse.Namespace) -> list[str]:
    cmd: list[str] = []
    _append_scope_args(cmd, args, include_question_root=True)
    cmd.extend(["--fewshot-root", args.fewshot_root])
    cmd.extend(["--answer-question-workers", str(args.answer_question_workers)])
    cmd.extend(["--max-workers", str(args.answer_question_workers)])
    cmd.extend(["--max-tokens", str(args.answer_max_tokens)])
    cmd.extend(["--temperature", str(args.answer_temperature)])
    cmd.extend(["--retries", str(args.answer_retries)])
    cmd.extend(["--print-every", str(args.answer_print_every)])
    return cmd


def build_judge_argv(args: argparse.Namespace) -> list[str]:
    cmd: list[str] = []
    _append_scope_args(cmd, args, include_question_root=True)
    cmd.extend(["--judge-question-workers", str(args.judge_question_workers)])
    cmd.extend(["--max-workers", str(args.judge_question_workers)])
    cmd.extend(["--judge-workers", str(args.judge_workers)])
    cmd.extend(["--max-tokens", str(args.judge_max_tokens)])
    cmd.extend(["--temperature", str(args.judge_temperature)])
    cmd.extend(["--retries", str(args.judge_request_retries)])
    cmd.extend(["--judge-retries", str(args.judge_parse_retries)])
    cmd.extend(["--print-every", str(args.judge_print_every)])
    return cmd


def build_aggregate_argv(args: argparse.Namespace) -> list[str]:
    cmd: list[str] = ["--out-dir", args.out_dir]
    if args.models:
        cmd.append("--models")
        cmd.extend(args.models)
    if args.datasets:
        cmd.append("--datasets")
        cmd.extend(args.datasets)
    if args.modes:
        cmd.append("--modes")
        cmd.extend(args.modes)
    return cmd


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    if not args.skip_answer:
        print("[PIPELINE] Stage 1/3: subjective_answer")
        answer_main(build_answer_argv(args))
    if not args.skip_judge:
        print("[PIPELINE] Stage 2/3: subjective_judge")
        judge_main(build_judge_argv(args))
    if not args.skip_aggregate:
        print("[PIPELINE] Stage 3/3: subjective_aggregate")
        aggregate_main(build_aggregate_argv(args))

    print(f"Done. Subjective pipeline completed for output root: {args.out_dir}")


if __name__ == "__main__":
    main()
