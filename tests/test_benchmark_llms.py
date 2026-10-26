import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import URLError

from scripts import benchmark_llms


REPO_ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = REPO_ROOT / "benchmarks" / "artemis-prompts.json"


class PromptSuiteTests(unittest.TestCase):
    def test_committed_suite_has_eighteen_unique_non_sensor_cases(self) -> None:
        suite = benchmark_llms.load_suite(SUITE_PATH)
        case_ids = [case["id"] for case in suite["cases"]]

        self.assertEqual(suite["suite_id"], "artemis-llm-v1")
        self.assertEqual(suite["version"], 1)
        self.assertEqual(len(case_ids), 18)
        self.assertEqual(len(set(case_ids)), 18)
        self.assertFalse(
            any(
                word in case["prompt"].lower()
                for case in suite["cases"]
                for word in ("temperature", "humidity")
            )
        )

    def test_duplicate_case_ids_are_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "suite.json"
            path.write_text(
                json.dumps(
                    {
                        "suite_id": "duplicate-suite",
                        "version": 1,
                        "cases": [
                            {"id": "same", "prompt": "first", "max_words": 20},
                            {"id": "same", "prompt": "second", "max_words": 20},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unique"):
                benchmark_llms.load_suite(path)


class RequestAndMetricTests(unittest.TestCase):
    def test_build_payload_uses_the_real_artemis_prompt_path(self) -> None:
        case = {
            "id": "mimic_summary",
            "prompt": "Tell me about mimics.",
            "max_words": 80,
        }

        payload, prompt_info = benchmark_llms.build_payload(case, "local-test")

        self.assertEqual(payload["model"], "local-test")
        self.assertEqual([message["role"] for message in payload["messages"]], ["system", "user"])
        self.assertIn("You are Artemis", payload["messages"][0]["content"])
        self.assertEqual(payload["messages"][1]["content"], case["prompt"])
        self.assertGreater(payload["max_tokens"], 0)
        self.assertEqual(payload["temperature"], 0.65)
        self.assertEqual(prompt_info["case_id"], "mimic_summary")
        self.assertIn("estimated_prompt_tokens", prompt_info)

    def test_extract_metrics_keeps_server_and_end_to_end_rates_distinct(self) -> None:
        response = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
            "timings": {
                "prompt_per_second": 50.0,
                "predicted_per_second": 10.0,
            },
        }

        metrics = benchmark_llms.extract_metrics(response, wall_seconds=2.5)

        self.assertEqual(metrics["prompt_tokens"], 100)
        self.assertEqual(metrics["completion_tokens"], 20)
        self.assertEqual(metrics["total_tokens"], 120)
        self.assertEqual(metrics["server_prompt_tps"], 50.0)
        self.assertEqual(metrics["server_generation_tps"], 10.0)
        self.assertEqual(metrics["end_to_end_output_tps"], 8.0)
        self.assertEqual(metrics["wall_seconds"], 2.5)

    def test_extract_metrics_does_not_invent_missing_or_zero_rates(self) -> None:
        metrics = benchmark_llms.extract_metrics(
            {"usage": {"completion_tokens": 0}},
            wall_seconds=0.0,
        )

        self.assertIsNone(metrics["prompt_tokens"])
        self.assertEqual(metrics["completion_tokens"], 0)
        self.assertIsNone(metrics["total_tokens"])
        self.assertIsNone(metrics["server_prompt_tps"])
        self.assertIsNone(metrics["server_generation_tps"])
        self.assertIsNone(metrics["end_to_end_output_tps"])

    def test_request_digest_ignores_model_name_but_tracks_effective_prompt(self) -> None:
        payload, _ = benchmark_llms.build_payload(
            {"id": "identity", "prompt": "Who are you?", "max_words": 20},
            "first-model",
        )
        other_model = deepcopy(payload)
        other_model["model"] = "second-model"
        changed_request = deepcopy(payload)
        changed_request["temperature"] = 0.1

        self.assertEqual(
            benchmark_llms.request_digest(payload),
            benchmark_llms.request_digest(other_model),
        )
        self.assertNotEqual(
            benchmark_llms.request_digest(payload),
            benchmark_llms.request_digest(changed_request),
        )


class ValidationTests(unittest.TestCase):
    def test_module_import_emits_no_deprecation_warnings(self) -> None:
        environment = dict(os.environ)
        environment["PYTHONPATH"] = "Python_Scripts"
        completed = subprocess.run(
            [
                sys.executable,
                "-W",
                "error::DeprecationWarning",
                "-c",
                "from scripts import benchmark_llms",
            ],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_model_labels_are_safe_result_file_names(self) -> None:
        self.assertEqual(
            benchmark_llms.validate_label("qwen3.5-2b_q4-k-m"),
            "qwen3.5-2b_q4-k-m",
        )

        for unsafe in ("", "../model", "model/name", "model name", "model;echo"):
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(ValueError):
                    benchmark_llms.validate_label(unsafe)

    def test_response_checks_report_each_constraint_failure(self) -> None:
        case = {
            "id": "constraints",
            "prompt": "Answer briefly.",
            "max_words": 5,
            "required_any": ["safe", "secure"],
            "forbidden": ["internet"],
        }
        text = "<think>private</think> **Safe** internet answer with too many words."

        result = benchmark_llms.evaluate_response(case, text)

        self.assertFalse(result["passed"])
        self.assertEqual(
            set(result["failures"]),
            {"reasoning_markup", "markdown", "max_words", "forbidden_content"},
        )
        self.assertTrue(result["checks"]["required_content"])

    def test_response_checks_reject_empty_and_common_markdown(self) -> None:
        case = {"id": "plain", "prompt": "Speak plainly.", "max_words": 20}

        empty = benchmark_llms.evaluate_response(case, "   ")
        markdown_results = [
            benchmark_llms.evaluate_response(case, text)
            for text in ("* item", "\x60code\x60", "*emphasis*")
        ]

        self.assertFalse(empty["checks"]["non_empty"])
        self.assertIn("non_empty", empty["failures"])
        for result in markdown_results:
            self.assertFalse(result["checks"]["markdown"])
            self.assertIn("markdown", result["failures"])


class RunTests(unittest.TestCase):
    def test_failed_request_is_recorded_and_later_repetition_runs(self) -> None:
        response = {
            "choices": [
                {
                    "message": {"content": "Artemis online."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            "timings": {"prompt_per_second": 40.0, "predicted_per_second": 8.0},
        }

        with TemporaryDirectory() as directory:
            root = Path(directory)
            suite_path = root / "suite.json"
            suite_path.write_text(
                json.dumps(
                    {
                        "suite_id": "small-suite",
                        "version": 1,
                        "cases": [
                            {
                                "id": "identity",
                                "prompt": "Who are you?",
                                "max_words": 20,
                                "required_any": ["artemis"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                label="test-model",
                url="http://127.0.0.1:8080/v1/chat/completions",
                api_model="local-test",
                suite=suite_path,
                repeats=2,
                warmups=0,
                timeout=1.0,
                output_dir=root / "results",
            )

            with patch.object(
                benchmark_llms,
                "post_json",
                side_effect=[URLError("offline"), response],
            ):
                result_path = benchmark_llms.run_benchmark(args)

            saved = json.loads(result_path.read_text(encoding="utf-8"))
            observations = saved["observations"]

        self.assertEqual(len(observations), 2)
        self.assertIn("offline", observations[0]["error"])
        self.assertIsNone(observations[0]["response"])
        self.assertIsNone(observations[1]["error"])
        self.assertEqual(observations[1]["response"], "Artemis online.")
        self.assertEqual(observations[1]["metrics"]["server_generation_tps"], 8.0)
        self.assertEqual(len(saved["suite"]["cases"][0]["request_sha256"]), 64)
        self.assertNotIn("system_prompt", saved)
        self.assertNotIn("messages", saved)

    def test_response_without_usage_or_timings_keeps_text_and_null_metrics(self) -> None:
        response = {
            "choices": [
                {
                    "message": {"content": "I am Artemis."},
                    "finish_reason": "stop",
                }
            ]
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            suite_path = root / "suite.json"
            suite_path.write_text(
                json.dumps(
                    {
                        "suite_id": "small-suite",
                        "version": 1,
                        "cases": [
                            {
                                "id": "identity",
                                "prompt": "Who are you?",
                                "max_words": 20,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                label="test-model",
                url="http://127.0.0.1:8080/v1/chat/completions",
                api_model="local-test",
                suite=suite_path,
                repeats=1,
                warmups=0,
                timeout=1.0,
                output_dir=root / "results",
            )
            with patch.object(benchmark_llms, "post_json", return_value=response):
                result_path = benchmark_llms.run_benchmark(args)
            observation = json.loads(result_path.read_text(encoding="utf-8"))[
                "observations"
            ][0]

        self.assertEqual(observation["response"], "I am Artemis.")
        self.assertIsNone(observation["metrics"]["server_prompt_tps"])
        self.assertIsNone(observation["metrics"]["server_generation_tps"])


def sample_run(label: str = "model-a") -> dict:
    return {
        "schema_version": 1,
        "suite": {
            "suite_id": "suite",
            "version": 1,
            "sha256": "abc123",
            "cases": [
                {
                    "id": "identity",
                    "prompt": "Who are you?",
                    "request_sha256": "request-one",
                },
                {
                    "id": "status",
                    "prompt": "Anything to report?",
                    "request_sha256": "request-two",
                },
            ],
        },
        "model": {
            "label": label,
            "api_model": "local-test",
            "url": "http://127.0.0.1:8080/v1/chat/completions",
        },
        "run": {
            "created_at": "2026-10-26T12:00:00+00:00",
            "repeats": 1,
            "warmups": 1,
            "timeout_seconds": 120.0,
            "platform": "Linux-test",
            "machine": "x86_64",
            "python": "3.10.0",
        },
        "observations": [
            {
                "case_id": "identity",
                "repetition": 1,
                "prompt": "Who are you?",
                "response": "I am Artemis.",
                "checks": {"passed": True, "checks": {}, "failures": []},
                "metrics": {
                    "wall_seconds": 2.0,
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                    "server_prompt_tps": 50.0,
                    "server_generation_tps": 10.0,
                    "end_to_end_output_tps": 10.0,
                },
                "error": None,
            },
            {
                "case_id": "status",
                "repetition": 1,
                "prompt": "Anything to report?",
                "response": None,
                "checks": None,
                "metrics": {
                    "wall_seconds": 4.0,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "total_tokens": None,
                    "server_prompt_tps": None,
                    "server_generation_tps": None,
                    "end_to_end_output_tps": None,
                },
                "error": "URLError: offline",
            },
        ],
    }


class ComparisonTests(unittest.TestCase):
    def test_incompatible_runs_are_rejected(self) -> None:
        original = sample_run()
        mutations = {
            "suite_id": lambda run: run["suite"].update(suite_id="other"),
            "version": lambda run: run["suite"].update(version=2),
            "digest": lambda run: run["suite"].update(sha256="different"),
            "case IDs": lambda run: run["suite"].update(
                cases=[
                    {
                        "id": "other",
                        "prompt": "Different",
                        "request_sha256": "request-other",
                    }
                ]
            ),
            "request digests": lambda run: run["suite"]["cases"][0].update(
                request_sha256="different"
            ),
            "repeat count": lambda run: run["run"].update(repeats=2),
        }

        for expected, mutate in mutations.items():
            with self.subTest(expected=expected):
                changed = deepcopy(original)
                mutate(changed)
                with self.assertRaisesRegex(ValueError, expected):
                    benchmark_llms.validate_compatible_runs([original, changed])

    def test_unknown_missing_or_duplicate_observation_pairs_are_rejected(self) -> None:
        original = sample_run()
        mutations = {
            "unknown": lambda run: run["observations"][0].update(case_id="other"),
            "missing": lambda run: run["observations"].pop(),
            "duplicate": lambda run: run["observations"].append(
                deepcopy(run["observations"][0])
            ),
        }

        for expected, mutate in mutations.items():
            with self.subTest(expected=expected):
                changed = deepcopy(original)
                mutate(changed)
                with self.assertRaisesRegex(ValueError, "observation"):
                    benchmark_llms.validate_compatible_runs([original, changed])

    def test_summary_ignores_errors_but_reports_their_count(self) -> None:
        run = sample_run()
        extra = deepcopy(run["observations"][0])
        extra["case_id"] = "status"
        extra["prompt"] = "Anything to report?"
        extra["metrics"]["wall_seconds"] = 4.0
        extra["metrics"]["server_generation_tps"] = 6.0
        extra["metrics"]["end_to_end_output_tps"] = 5.0
        extra["checks"]["passed"] = False
        run["observations"].append(extra)

        summary = benchmark_llms.summarize_run(run)

        self.assertEqual(summary["successful"], 2)
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(summary["automated_check_passes"], 1)
        self.assertEqual(summary["automated_check_rate"], 0.5)
        self.assertEqual(
            summary["metrics"]["wall_seconds"],
            {"count": 2, "mean": 3.0, "median": 3.0, "min": 2.0, "max": 4.0},
        )
        self.assertEqual(summary["metrics"]["server_generation_tps"]["mean"], 8.0)

    def test_summary_keeps_unavailable_metrics_null(self) -> None:
        run = sample_run()
        run["observations"] = [run["observations"][1]]

        summary = benchmark_llms.summarize_run(run)

        self.assertEqual(summary["successful"], 0)
        self.assertEqual(summary["errors"], 1)
        self.assertIsNone(summary["metrics"]["server_generation_tps"])
        self.assertIsNone(summary["automated_check_rate"])

    def test_report_contains_metric_labels_and_raw_responses(self) -> None:
        first = sample_run("model|a")
        second = sample_run("model-b")
        second["observations"][0]["response"] = "Artemis model B response."
        second["observations"][0]["metrics"]["server_generation_tps"] = None

        report = benchmark_llms.render_comparison([first, second])

        self.assertIn("Server generation TPS", report)
        self.assertIn("End-to-end output TPS", report)
        self.assertIn("model\\|a", report)
        self.assertIn("I am Artemis.", report)
        self.assertIn("Artemis model B response.", report)
        self.assertIn("URLError: offline", report)
        self.assertIn("n/a", report)
        self.assertIn("### identity — Who are you?", report)

    def test_compare_writes_a_markdown_report(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first_path = root / "first.json"
            second_path = root / "second.json"
            output = root / "comparison.md"
            first_path.write_text(json.dumps(sample_run("first")), encoding="utf-8")
            second_path.write_text(json.dumps(sample_run("second")), encoding="utf-8")

            actual = benchmark_llms.compare_runs(
                [first_path, second_path],
                output,
            )

            report = output.read_text(encoding="utf-8")

        self.assertEqual(actual, output)
        self.assertIn("# Artemis LLM Comparison", report)
        self.assertIn("first", report)
        self.assertIn("second", report)


if __name__ == "__main__":
    unittest.main()
