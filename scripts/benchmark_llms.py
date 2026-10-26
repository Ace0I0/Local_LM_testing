from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import platform
import re
import statistics
import sys
import time
from typing import Any
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_SCRIPTS = REPO_ROOT / "Python_Scripts"
if str(PYTHON_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PYTHON_SCRIPTS))

import load_llm_sam as artemis  # noqa: E402


DEFAULT_SUITE = REPO_ROOT / "benchmarks" / "artemis-prompts.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "benchmark-results"
DEFAULT_URL = "http://127.0.0.1:8080/v1/chat/completions"
_SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_MARKDOWN = re.compile(r"(?m)[\x60*]|__|^\s*(?:#{1,6}|>|[-+]\s|\d+\.\s)")
_REASONING = re.compile(r"</?(?:think|analysis)>", re.IGNORECASE)


def load_suite(path: Path) -> dict[str, Any]:
    try:
        suite = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load prompt suite {path}: {exc}") from exc

    if not isinstance(suite, dict):
        raise ValueError("Prompt suite must be a JSON object.")
    if not isinstance(suite.get("suite_id"), str) or not suite["suite_id"].strip():
        raise ValueError("Prompt suite requires a non-empty suite_id.")
    if not isinstance(suite.get("version"), int):
        raise ValueError("Prompt suite requires an integer version.")

    cases = suite.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Prompt suite requires at least one case.")

    case_ids: list[str] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Every prompt case must be a JSON object.")
        case_id = case.get("id")
        prompt = case.get("prompt")
        max_words = case.get("max_words")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("Every prompt case requires a non-empty id.")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"Prompt case {case_id!r} requires non-empty prompt text.")
        if not isinstance(max_words, int) or max_words <= 0:
            raise ValueError(f"Prompt case {case_id!r} requires a positive max_words value.")
        for field in ("required_any", "forbidden"):
            values = case.get(field, [])
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise ValueError(f"Prompt case {case_id!r} field {field!r} must be a string list.")
        case_ids.append(case_id)

    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Prompt case IDs must be unique.")
    return suite


def validate_label(label: str) -> str:
    if not _SAFE_LABEL.fullmatch(label):
        raise ValueError("Model label may contain only letters, numbers, dots, underscores, and hyphens.")
    return label


def build_payload(case: dict[str, Any], api_model: str) -> tuple[dict[str, Any], dict[str, Any]]:
    user_text = case["prompt"]
    route = artemis.route_intent(user_text)
    system_prompt, debug = artemis.build_system_prompt(
        artemis.load_identity(),
        artemis.load_mode(),
        user_text,
        route=route,
    )
    settings = artemis.get_generation_settings(user_text)
    payload = {
        "model": api_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": debug["response_tokens"],
        "temperature": settings["temperature"],
    }
    prompt_info = {
        "case_id": case["id"],
        "route_intent": debug["route_intent"],
        "route_topics": debug["route_topics"],
        "estimated_prompt_tokens": debug["estimated_final_prompt_tokens"],
        "response_token_limit": debug["response_tokens"],
        "temperature": settings["temperature"],
    }
    return payload, prompt_info


def request_digest(payload: dict[str, Any]) -> str:
    effective_request = {
        key: value for key, value in payload.items() if key != "model"
    }
    canonical = json.dumps(
        effective_request,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("Model server response must be a JSON object.")
    return result


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return value


def extract_metrics(response: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    timings = response.get("timings") if isinstance(response.get("timings"), dict) else {}
    prompt_tokens = _number(usage.get("prompt_tokens"))
    completion_tokens = _number(usage.get("completion_tokens"))
    total_tokens = _number(usage.get("total_tokens"))
    server_prompt_tps = _number(timings.get("prompt_per_second"))
    server_generation_tps = _number(timings.get("predicted_per_second"))
    end_to_end_output_tps = None
    if completion_tokens and wall_seconds > 0:
        end_to_end_output_tps = completion_tokens / wall_seconds

    return {
        "wall_seconds": wall_seconds,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "server_prompt_tps": server_prompt_tps,
        "server_generation_tps": server_generation_tps,
        "end_to_end_output_tps": end_to_end_output_tps,
    }


def evaluate_response(case: dict[str, Any], text: str) -> dict[str, Any]:
    lower = text.lower()
    required = [phrase.lower() for phrase in case.get("required_any", [])]
    forbidden = [phrase.lower() for phrase in case.get("forbidden", [])]
    checks = {
        "non_empty": bool(text.strip()),
        "reasoning_markup": _REASONING.search(text) is None,
        "markdown": _MARKDOWN.search(text) is None,
        "max_words": len(text.split()) <= case["max_words"],
        "required_content": not required or any(phrase in lower for phrase in required),
        "forbidden_content": not any(phrase in lower for phrase in forbidden),
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {"passed": not failures, "checks": checks, "failures": failures}


def _response_text(response: dict[str, Any]) -> tuple[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("Model server response does not contain a choice.")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ValueError("Model server response does not contain message content.")
    return message["content"].strip(), choices[0].get("finish_reason")


def _suite_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_benchmark(args: argparse.Namespace) -> Path:
    label = validate_label(args.label)
    suite_path = Path(args.suite)
    suite = load_suite(suite_path)

    prepared_cases = []
    for case in suite["cases"]:
        payload, prompt_info = build_payload(case, args.api_model)
        prepared_cases.append(
            (case, payload, prompt_info, request_digest(payload))
        )

    first_payload = prepared_cases[0][1]
    for _ in range(args.warmups):
        try:
            post_json(args.url, first_payload, args.timeout)
        except Exception as exc:
            print(f"Warm-up failed: {type(exc).__name__}: {exc}", file=sys.stderr)

    observations: list[dict[str, Any]] = []
    for case, payload, prompt_info, _ in prepared_cases:
        for repetition in range(1, args.repeats + 1):
            started = time.perf_counter()
            try:
                response = post_json(args.url, payload, args.timeout)
                wall_seconds = time.perf_counter() - started
                text, finish_reason = _response_text(response)
                observation = {
                    "case_id": case["id"],
                    "repetition": repetition,
                    "prompt": case["prompt"],
                    "prompt_info": prompt_info,
                    "request_settings": {"max_tokens": payload["max_tokens"], "temperature": payload["temperature"]},
                    "response": text,
                    "finish_reason": finish_reason,
                    "checks": evaluate_response(case, text),
                    "metrics": extract_metrics(response, wall_seconds),
                    "usage": response.get("usage", {}),
                    "timings": response.get("timings", {}),
                    "error": None,
                }
            except Exception as exc:
                wall_seconds = time.perf_counter() - started
                observation = {
                    "case_id": case["id"],
                    "repetition": repetition,
                    "prompt": case["prompt"],
                    "prompt_info": prompt_info,
                    "request_settings": {"max_tokens": payload["max_tokens"], "temperature": payload["temperature"]},
                    "response": None,
                    "finish_reason": None,
                    "checks": None,
                    "metrics": extract_metrics({}, wall_seconds),
                    "usage": {},
                    "timings": {},
                    "error": f"{type(exc).__name__}: {exc}",
                }
            observations.append(observation)

    created_at = datetime.now(timezone.utc)
    result = {
        "schema_version": 1,
        "suite": {
            "suite_id": suite["suite_id"],
            "version": suite["version"],
            "sha256": _suite_digest(suite_path),
            "cases": [
                {
                    "id": case["id"],
                    "prompt": case["prompt"],
                    "request_sha256": digest,
                }
                for case, _, _, digest in prepared_cases
            ],
        },
        "model": {"label": label, "api_model": args.api_model, "url": args.url},
        "run": {
            "created_at": created_at.isoformat(),
            "repeats": args.repeats,
            "warmups": args.warmups,
            "timeout_seconds": args.timeout,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "observations": observations,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = created_at.strftime("%Y%m%dT%H%M%S%fZ")
    output_path = output_dir / f"{label}-{timestamp}.json"
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output_path


_SUMMARY_METRICS = (
    "wall_seconds",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "server_prompt_tps",
    "server_generation_tps",
    "end_to_end_output_tps",
)


def validate_compatible_runs(runs: list[dict[str, Any]]) -> None:
    if len(runs) < 2:
        raise ValueError("Comparison requires at least two result files.")

    reference = runs[0]
    checks = (
        ("schema version", lambda run: run.get("schema_version")),
        ("suite_id", lambda run: run.get("suite", {}).get("suite_id")),
        ("version", lambda run: run.get("suite", {}).get("version")),
        ("digest", lambda run: run.get("suite", {}).get("sha256")),
        (
            "case IDs",
            lambda run: [
                case.get("id")
                for case in run.get("suite", {}).get("cases", [])
                if isinstance(case, dict)
            ],
        ),
        (
            "request digests",
            lambda run: [
                case.get("request_sha256")
                for case in run.get("suite", {}).get("cases", [])
                if isinstance(case, dict)
            ],
        ),
        ("repeat count", lambda run: run.get("run", {}).get("repeats")),
    )
    for name, getter in checks:
        expected = getter(reference)
        for run in runs[1:]:
            if getter(run) != expected:
                raise ValueError(f"Cannot compare runs with different {name}.")

    for run in runs:
        cases = run.get("suite", {}).get("cases", [])
        case_ids = [
            case.get("id")
            for case in cases
            if isinstance(case, dict) and isinstance(case.get("id"), str)
        ]
        repeats = run.get("run", {}).get("repeats")
        observations = run.get("observations")
        if not isinstance(repeats, int) or repeats < 1 or not isinstance(observations, list):
            raise ValueError("Benchmark run has invalid observation metadata.")

        expected_pairs = {
            (case_id, repetition)
            for case_id in case_ids
            for repetition in range(1, repeats + 1)
        }
        actual_pairs = [
            (item.get("case_id"), item.get("repetition"))
            for item in observations
            if isinstance(item, dict)
        ]
        if len(actual_pairs) != len(expected_pairs) or set(actual_pairs) != expected_pairs:
            raise ValueError(
                "Benchmark run has missing, unknown, or duplicate observation pairs."
            )


def _metric_summary(values: list[int | float]) -> dict[str, int | float] | None:
    if not values:
        return None
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def summarize_run(run: dict[str, Any]) -> dict[str, Any]:
    observations = run.get("observations", [])
    successful = [item for item in observations if not item.get("error")]
    check_passes = sum(
        1
        for item in successful
        if isinstance(item.get("checks"), dict) and item["checks"].get("passed") is True
    )
    metrics: dict[str, Any] = {}
    for name in _SUMMARY_METRICS:
        values = [
            value
            for item in successful
            if isinstance(item.get("metrics"), dict)
            and (value := _number(item["metrics"].get(name))) is not None
        ]
        metrics[name] = _metric_summary(values)

    return {
        "label": run.get("model", {}).get("label", "unknown"),
        "observations": len(observations),
        "successful": len(successful),
        "errors": len(observations) - len(successful),
        "automated_check_passes": check_passes,
        "automated_check_rate": check_passes / len(successful) if successful else None,
        "metrics": metrics,
    }


def _escape_cell(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _format_metric(summary: dict[str, Any], name: str, statistic: str) -> str:
    metric = summary["metrics"].get(name)
    if metric is None:
        return "n/a"
    value = metric[statistic]
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def render_comparison(runs: list[dict[str, Any]]) -> str:
    validate_compatible_runs(runs)
    summaries = [summarize_run(run) for run in runs]
    suite = runs[0]["suite"]
    lines = [
        "# Artemis LLM Comparison",
        "",
        f"Suite: {suite['suite_id']} version {suite['version']}  ",
        f"Prompt SHA-256: {suite['sha256']}  ",
        "True time-to-first-token is unavailable because these are non-streaming requests.",
        "",
        "## Summary",
        "",
        "| Model | Success | Errors | Automated checks | Median wall seconds | Server prompt TPS | Server generation TPS | End-to-end output TPS | Mean prompt tokens | Mean completion tokens |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in summaries:
        rate = summary["automated_check_rate"]
        check_rate = "n/a" if rate is None else f"{rate * 100:.1f}%"
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_cell(summary["label"]),
                    str(summary["successful"]),
                    str(summary["errors"]),
                    check_rate,
                    _format_metric(summary, "wall_seconds", "median"),
                    _format_metric(summary, "server_prompt_tps", "mean"),
                    _format_metric(summary, "server_generation_tps", "mean"),
                    _format_metric(summary, "end_to_end_output_tps", "mean"),
                    _format_metric(summary, "prompt_tokens", "mean"),
                    _format_metric(summary, "completion_tokens", "mean"),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Responses", ""])
    for case in suite["cases"]:
        case_id = case["id"]
        lines.append(f"### {case_id} — {case['prompt']}")
        lines.append("")
        for run in runs:
            label = run.get("model", {}).get("label", "unknown")
            observations = [
                item for item in run.get("observations", []) if item.get("case_id") == case_id
            ]
            for item in observations:
                lines.append(f"#### {label} — repetition {item.get('repetition')}")
                lines.append("")
                if item.get("error"):
                    lines.append(f"Error: {item['error']}")
                else:
                    lines.append(f"<pre>{html.escape(item.get('response') or '')}</pre>")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def compare_runs(paths: list[Path], output: Path | None = None) -> Path:
    runs: list[dict[str, Any]] = []
    for path in paths:
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot load benchmark result {path}: {exc}") from exc
        if not isinstance(run, dict):
            raise ValueError(f"Benchmark result {path} must be a JSON object.")
        runs.append(run)

    report = render_comparison(runs)
    if output is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = DEFAULT_OUTPUT_DIR / f"comparison-{timestamp}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark local LLMs with Artemis prompts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run the prompt suite against one model server.")
    run.add_argument("--label", required=True, help="Safe name used in the result filename.")
    run.add_argument("--url", default=DEFAULT_URL)
    run.add_argument("--api-model", default="local-qwen")
    run.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    run.add_argument("--repeats", type=int, default=3)
    run.add_argument("--warmups", type=int, default=1)
    run.add_argument("--timeout", type=float, default=120.0)
    run.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    compare = subparsers.add_parser("compare", help="Compare two or more saved model runs.")
    compare.add_argument("results", type=Path, nargs="+")
    compare.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "run":
        if args.repeats < 1 or args.warmups < 0 or args.timeout <= 0:
            raise SystemExit("repeats must be positive, warmups non-negative, and timeout positive")
        print(run_benchmark(args))
        return 0
    if args.command == "compare":
        print(compare_runs(args.results, args.output))
        return 0
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
