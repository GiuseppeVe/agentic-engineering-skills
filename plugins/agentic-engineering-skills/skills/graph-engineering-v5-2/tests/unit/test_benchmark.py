from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.graph_v5.packaging import (
    BenchmarkError,
    REQUIRED_RESULT_METRICS,
    REQUIRED_THRESHOLDS,
    canonical_json_bytes,
    validate_benchmark_result,
    validate_promotion_profile,
)


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "scripts" / "benchmark.py"


def corpus_payload() -> dict[str, object]:
    return {
        "schema_version": "v1",
        "corpus_id": "graph-v5-test-corpus",
        "test_only": True,
        "workload_classes": [
            "healthy-user-journey",
            "seeded-failure-user-journey",
        ],
        "seed": "fixed-v5-fixture-seed",
    }


def corpus_digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def profile_payload(corpus: dict[str, object] | None = None) -> dict[str, object]:
    corpus = corpus or corpus_payload()
    return {
        "schema_version": "v1",
        "profile_id": "promotion-profile.test.v1",
        "immutable": True,
        "test_only": True,
        "workload_corpus_digest": corpus_digest(corpus),
        "trial_method": "fixed-seed-single-trial-test-fixture",
        "thresholds": {
            "max_product_work_time_seconds": 60.0,
            "max_reproduction_latency_seconds": 30.0,
            "min_resolved_on_run_head_rate": 1.0,
            "max_interaction_count": 0.0,
            "max_false_ready_count": 0.0,
            "max_controller_fallback_count": 0.0,
            "max_read_only_write_count": 0.0,
            "min_restart_recovery_rate": 1.0,
            "max_control_overhead_rate": 0.5,
            "min_v4_relative_throughput": 1.0,
        },
        "v4_baseline": {
            "label": "test-only-v4-baseline",
            "digest": "a" * 64,
        },
    }


def result_payload() -> dict[str, object]:
    return {
        "schema_version": "v1",
        "metrics": {
            "product_work_time_seconds": 12.0,
            "reproduction_latency_seconds": 4.0,
            "resolved_on_run_head_rate": 1.0,
            "interaction_count": 0.0,
            "false_ready_count": 0.0,
            "controller_fallback_count": 0.0,
            "read_only_write_count": 0.0,
            "restart_recovery_rate": 1.0,
            "control_overhead_rate": 0.2,
            "v4_relative_throughput": 1.5,
        },
    }


class BenchmarkPolicyTests(unittest.TestCase):
    def test_source_controlled_test_fixture_binds_corpus_profile_and_metric_oracle(self) -> None:
        corpus = json.loads(
            (ROOT / "fixtures" / "benchmarks" / "corpus.test.v1.json").read_text(encoding="utf-8")
        )
        profile = json.loads(
            (ROOT / "config" / "policy-fixtures" / "promotion-profile.test.v1.json").read_text(
                encoding="utf-8"
            )
        )
        oracle = json.loads(
            (ROOT / "fixtures" / "benchmarks" / "oracles.test.v1.json").read_text(encoding="utf-8")
        )

        validated = validate_promotion_profile(profile, corpus=corpus)
        self.assertTrue(validated.test_only)
        self.assertTrue(oracle["test_only"])
        self.assertEqual(tuple(oracle["required_result_metrics"]), REQUIRED_RESULT_METRICS)

    def test_profile_rejects_each_missing_numeric_threshold(self) -> None:
        corpus = corpus_payload()
        for threshold_name in REQUIRED_THRESHOLDS:
            with self.subTest(threshold_name=threshold_name):
                profile = profile_payload(corpus)
                del profile["thresholds"][threshold_name]  # type: ignore[index]
                with self.assertRaisesRegex(BenchmarkError, "missing numeric threshold"):
                    validate_promotion_profile(profile, corpus=corpus)

    def test_profile_rejects_missing_digest_trial_method_and_immutable_test_marker(self) -> None:
        corpus = corpus_payload()
        for field_name in (
            "workload_corpus_digest",
            "trial_method",
            "immutable",
            "test_only",
        ):
            with self.subTest(field_name=field_name):
                profile = profile_payload(corpus)
                profile.pop(field_name)
                with self.assertRaisesRegex(BenchmarkError, "missing required field"):
                    validate_promotion_profile(profile, corpus=corpus)

    def test_profile_rejects_digest_not_bound_to_explicit_corpus(self) -> None:
        corpus = corpus_payload()
        profile = profile_payload(corpus)
        profile["workload_corpus_digest"] = "b" * 64

        with self.assertRaisesRegex(BenchmarkError, "does not match"):
            validate_promotion_profile(profile, corpus=corpus)

    def test_result_rejects_each_missing_required_metric(self) -> None:
        for metric_name in REQUIRED_RESULT_METRICS:
            with self.subTest(metric_name=metric_name):
                result = result_payload()
                del result["metrics"][metric_name]  # type: ignore[index]
                with self.assertRaisesRegex(BenchmarkError, "missing numeric result metric"):
                    validate_benchmark_result(result)

    def test_benchmark_cli_writes_only_new_explicit_output_for_test_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            corpus_path = root / "corpus.json"
            profile_path = root / "profile.json"
            result_path = root / "result.json"
            run_store_root = root / "run-store"
            output_root = root / "candidate-output"
            run_store_root.mkdir()
            sentinel = run_store_root / "sentinel.bin"
            sentinel.write_bytes(b"run-store-must-not-change")
            corpus = corpus_payload()
            corpus_path.write_bytes(canonical_json_bytes(corpus))
            profile_path.write_bytes(canonical_json_bytes(profile_payload(corpus)))
            result_path.write_bytes(canonical_json_bytes(result_payload()))
            before = sentinel.read_bytes()

            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(BENCHMARK),
                    "--corpus",
                    str(corpus_path),
                    "--profile",
                    str(profile_path),
                    "--result",
                    str(result_path),
                    "--output-root",
                    str(output_root),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            receipt = json.loads(completed.stdout)
            self.assertEqual(receipt["status"], "candidate_recorded")
            self.assertFalse(receipt["promotion_eligible"])
            self.assertEqual(sentinel.read_bytes(), before)
            self.assertEqual(
                json.loads((output_root / "candidate.json").read_text(encoding="utf-8"))["test_only"],
                True,
            )

    def test_benchmark_rejects_existing_or_implicit_output_and_test_profile_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            corpus = corpus_payload()
            corpus_path = root / "corpus.json"
            profile_path = root / "profile.json"
            result_path = root / "result.json"
            output_root = root / "existing-output"
            output_root.mkdir()
            corpus_path.write_bytes(canonical_json_bytes(corpus))
            profile_path.write_bytes(canonical_json_bytes(profile_payload(corpus)))
            result_path.write_bytes(canonical_json_bytes(result_payload()))

            existing = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(BENCHMARK),
                    "--corpus",
                    str(corpus_path),
                    "--profile",
                    str(profile_path),
                    "--result",
                    str(result_path),
                    "--output-root",
                    str(output_root),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            implicit = subprocess.run(
                [sys.executable, "-B", str(BENCHMARK)],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(existing.returncode, 0)
            self.assertIn("output root must be a new directory", existing.stderr)
            self.assertNotEqual(implicit.returncode, 0)
            self.assertIn("--corpus", implicit.stderr)
            self.assertEqual(list(output_root.iterdir()), [])

    def test_test_only_profile_cannot_be_promoted(self) -> None:
        from scripts.benchmark import evaluate_promotion

        corpus = corpus_payload()
        with self.assertRaisesRegex(BenchmarkError, "test-only"):
            evaluate_promotion(
                corpus=corpus,
                profile=profile_payload(corpus),
                result=result_payload(),
            )


if __name__ == "__main__":
    unittest.main()
