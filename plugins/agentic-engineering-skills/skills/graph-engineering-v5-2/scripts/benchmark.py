#!/usr/bin/env python3
"""Opt-in Graph Engineering V5 benchmark candidate recorder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.graph_v5.packaging import (
    BenchmarkError,
    promotion_gate,
    validate_benchmark_result,
    validate_promotion_profile,
    write_benchmark_candidate,
)


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BenchmarkError(f"cannot read explicit benchmark input: {path}") from error


def evaluate_promotion(*, corpus: object, profile: object, result: object) -> dict[str, object]:
    """Evaluate hard gates only; never installs or promotes a package."""

    validated_profile = validate_promotion_profile(profile, corpus=corpus)
    validated_result = validate_benchmark_result(result)
    if validated_profile.test_only:
        raise BenchmarkError("test-only promotion profile cannot promote V5")
    passed, failures = promotion_gate(validated_profile, validated_result)
    return {"status": "eligible" if passed else "rejected", "failures": list(failures)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark.py",
        description="Record one explicit V5 test-only benchmark candidate without graphctl side effects.",
    )
    parser.add_argument("--corpus", required=True, help="Explicit benchmark corpus JSON.")
    parser.add_argument("--profile", required=True, help="Explicit immutable promotion profile JSON.")
    parser.add_argument("--result", required=True, help="Explicit complete benchmark result JSON.")
    parser.add_argument("--output-root", required=True, help="New caller-selected candidate directory.")
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Evaluate hard promotion gates only; does not install, deploy, or mutate a run store.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    corpus_path = Path(args.corpus)
    profile_path = Path(args.profile)
    result_path = Path(args.result)
    try:
        if args.promote:
            receipt = evaluate_promotion(
                corpus=_read_json(corpus_path),
                profile=_read_json(profile_path),
                result=_read_json(result_path),
            )
        else:
            receipt = write_benchmark_candidate(
                corpus_path=corpus_path,
                profile_path=profile_path,
                result_path=result_path,
                output_root=Path(args.output_root),
            )
    except BenchmarkError as error:
        parser.error(str(error))
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
