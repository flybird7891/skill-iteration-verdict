#!/usr/bin/env python3
"""Validate an independent reviewer's JSON before recording it in a run."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .verdict_gate import evaluate_run
except ImportError:
    from verdict_gate import evaluate_run


def read_json(path: str, label: str) -> Any:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"{label} is empty")
    return json.loads(text)


def validate_review_against_run(
    run_data: Any, review_data: Any
) -> dict[str, Any]:
    if not isinstance(run_data, dict):
        raise ValueError("run must be a JSON object")
    if not isinstance(review_data, dict):
        raise ValueError("review must be a JSON object, not an acknowledgement")
    if run_data.get("mode") != "strict":
        raise ValueError("review validation is only available for strict runs")

    reserved = run_data.get("reviewer_id_reserved")
    actual = review_data.get("reviewer_id")
    if isinstance(reserved, str) and reserved.strip():
        if actual != reserved.strip():
            raise ValueError(
                f"review.reviewer_id must equal reserved reviewer {reserved.strip()}"
            )

    candidate = copy.deepcopy(run_data)
    candidate["review"] = review_data
    candidate.pop("user_decision", None)
    result = evaluate_run(candidate)
    return {
        "valid": True,
        "reviewer_id": result["review"]["reviewer_id"],
        "reviewed_artifact_version": result["review"]["reviewed_artifact_version"],
        "result_count": len(result["review"]["results"]),
        "technical_pass": result["technical_pass"],
        "quality_score": result["quality_score"],
        "evidence_coverage": result["evidence_coverage"],
        "p0_failures": result["p0_failures"],
        "verdict_before_user_decision": result["verdict"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate an independent reviewer JSON against a strict run."
    )
    parser.add_argument("--run", required=True, help="Strict run JSON path.")
    parser.add_argument("--review", required=True, help="Reviewer JSON path.")
    args = parser.parse_args()

    try:
        summary = validate_review_against_run(
            read_json(args.run, "run"), read_json(args.review, "review")
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"review_validation: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
