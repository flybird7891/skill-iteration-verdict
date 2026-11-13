from __future__ import annotations

import copy
import unittest

from scripts.verdict_gate import evaluate_run
from scripts.validate_review import validate_review_against_run


def evidence(kind: str = "screenshot") -> dict[str, str]:
    return {
        "kind": kind,
        "artifact": "round-01/artifact",
        "locator": "check-location",
        "observation": "预期结果已观察到。",
        "verified_at": "2026-11-13T16:00:00+08:00",
    }


def requirement(
    requirement_id: str = "R1",
    priority: str = "P0",
    status: str = "active",
    evidence_kind: str = "screenshot",
) -> dict[str, object]:
    return {
        "id": requirement_id,
        "text": f"需求 {requirement_id}",
        "priority": priority,
        "source": "user-original",
        "pass_condition": "可观察结果成立",
        "required_evidence": [evidence_kind],
        "status": status,
    }


def result(
    requirement_id: str = "R1",
    status: str = "met",
    evidence_kind: str = "screenshot",
) -> dict[str, object]:
    return {
        "id": requirement_id,
        "status": status,
        "reason": "依据证据完成判断。",
        "evidence": [evidence(evidence_kind)],
        "suggested_fix": "补齐通过条件。",
    }


def quick_run() -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "run_id": "quick-test",
        "title": "Quick 测试",
        "mode": "quick",
        "builder_id": "builder",
        "profile": "general",
        "threshold": 0.8,
        "evidence_coverage_min": 1.0,
        "max_rounds": 3,
        "current_round": 1,
        "submission_version": "round-01",
        "contract": [requirement()],
        "review": {
            "reviewer_mode": "single_reviewer",
            "reviewer_id": "self",
            "reviewed_artifact_version": "round-01",
            "results": [result()],
        },
        "history": [],
    }


def strict_run() -> dict[str, object]:
    run = quick_run()
    run["run_id"] = "strict-test"
    run["title"] = "Strict 测试"
    run["mode"] = "strict"
    run["review"] = {
        "reviewer_mode": "independent_reviewer",
        "reviewer_id": "judge-01",
        "reviewed_artifact_version": "round-01",
        "results": [result()],
    }
    run["user_decision"] = {
        "decision": "accepted",
        "decided_at": "2026-11-13T16:30:00+08:00",
        "notes": "接受。",
    }
    return run


class QuickModeTests(unittest.TestCase):
    def test_quick_pass(self) -> None:
        self.assertEqual(evaluate_run(quick_run())["verdict"], "qualified")

    def test_quick_p0_failure_requests_revision(self) -> None:
        run = quick_run()
        run["review"]["results"][0]["status"] = "unmet"
        result_data = evaluate_run(run)
        self.assertEqual(result_data["verdict"], "revision_required")
        self.assertEqual(result_data["revision_orders"][0]["requirement_id"], "R1")

    def test_quick_fails_at_round_limit(self) -> None:
        run = quick_run()
        run["max_rounds"] = 1
        run["review"]["results"][0]["status"] = "unmet"
        self.assertEqual(evaluate_run(run)["verdict"], "failed")

    def test_quick_requires_single_reviewer(self) -> None:
        run = quick_run()
        run["review"]["reviewer_mode"] = "independent_reviewer"
        with self.assertRaisesRegex(ValueError, "single_reviewer"):
            evaluate_run(run)


class StrictModeTests(unittest.TestCase):
    def test_strict_requires_independent_review(self) -> None:
        run = strict_run()
        run["review"]["reviewer_mode"] = "single_reviewer"
        with self.assertRaisesRegex(ValueError, "independent_reviewer"):
            evaluate_run(run)

    def test_strict_reviewer_must_differ_from_builder(self) -> None:
        run = strict_run()
        run["review"]["reviewer_id"] = run["builder_id"]
        with self.assertRaisesRegex(ValueError, "differ"):
            evaluate_run(run)

    def test_strict_without_user_decision_is_pending(self) -> None:
        run = strict_run()
        del run["user_decision"]
        self.assertEqual(
            evaluate_run(run)["verdict"], "awaiting_user_decision"
        )

    def test_pending_user_decision_is_not_qualified(self) -> None:
        run = strict_run()
        run["user_decision"] = {
            "decision": "awaiting_user_decision",
            "decided_at": "",
            "notes": "",
        }
        self.assertEqual(
            evaluate_run(run)["verdict"], "awaiting_user_decision"
        )

    def test_strict_pass(self) -> None:
        self.assertEqual(evaluate_run(strict_run())["verdict"], "qualified")

    def test_strict_conditional_acceptance(self) -> None:
        run = strict_run()
        run["user_decision"]["decision"] = "accepted_with_caveats"
        self.assertEqual(
            evaluate_run(run)["verdict"], "qualified_with_caveats"
        )

    def test_strict_user_rejection_creates_dispute(self) -> None:
        run = strict_run()
        run["user_decision"]["decision"] = "rejected"
        self.assertEqual(evaluate_run(run)["verdict"], "disputed")

    def test_user_accepts_unqualified_at_round_limit(self) -> None:
        run = strict_run()
        run["max_rounds"] = 1
        run["review"]["results"][0]["status"] = "unmet"
        self.assertEqual(
            evaluate_run(run)["verdict"], "user_accepted_unqualified"
        )

    def test_strict_fallback_requires_reason(self) -> None:
        run = quick_run()
        run["requested_mode"] = "strict"
        with self.assertRaisesRegex(ValueError, "fallback_reason"):
            evaluate_run(run)

    def test_strict_fallback_is_disclosed_as_caveat(self) -> None:
        run = quick_run()
        run["requested_mode"] = "strict"
        run["fallback_reason"] = "独立裁判上下文不可用"
        result_data = evaluate_run(run)
        self.assertTrue(result_data["fallback_applied"])
        self.assertFalse(result_data["strict_satisfied"])
        self.assertEqual(
            result_data["verdict"], "qualified_with_caveats"
        )


class ContractTests(unittest.TestCase):
    def test_evidence_coverage_failure_blocks_pass(self) -> None:
        run = quick_run()
        run["review"]["results"][0]["evidence"] = []
        self.assertEqual(evaluate_run(run)["verdict"], "revision_required")

    def test_withdrawn_requirement_is_excluded(self) -> None:
        run = quick_run()
        run["contract"].append(
            requirement("R2", status="withdrawn", evidence_kind="test_output")
        )
        self.assertEqual(evaluate_run(run)["verdict"], "qualified")

    def test_duplicate_requirement_ids_are_rejected(self) -> None:
        run = quick_run()
        run["contract"].append(copy.deepcopy(run["contract"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate_run(run)

    def test_review_version_mismatch_is_rejected(self) -> None:
        run = quick_run()
        run["review"]["reviewed_artifact_version"] = "round-02"
        with self.assertRaisesRegex(ValueError, "submission_version"):
            evaluate_run(run)

    def test_regression_is_detected(self) -> None:
        run = quick_run()
        run["current_round"] = 2
        run["submission_version"] = "round-02"
        run["review"]["reviewed_artifact_version"] = "round-02"
        run["review"]["results"][0]["status"] = "partial"
        run["history"] = [
            {"round": 1, "results": [{"id": "R1", "status": "met"}]}
        ]
        result_data = evaluate_run(run)
        self.assertEqual(result_data["regressions"][0]["id"], "R1")


class ReviewValidationTests(unittest.TestCase):
    def test_valid_review_is_accepted(self) -> None:
        run = strict_run()
        review = run.pop("review")
        run.pop("user_decision")
        run["reviewer_id_reserved"] = "judge-01"
        summary = validate_review_against_run(run, review)
        self.assertTrue(summary["valid"])
        self.assertTrue(summary["technical_pass"])
        self.assertEqual(summary["verdict_before_user_decision"], "awaiting_user_decision")

    def test_acknowledgement_is_rejected(self) -> None:
        run = strict_run()
        run.pop("review")
        run.pop("user_decision")
        with self.assertRaisesRegex(ValueError, "acknowledgement"):
            validate_review_against_run(run, "任务已确认")

    def test_reserved_reviewer_must_match(self) -> None:
        run = strict_run()
        review = run.pop("review")
        run.pop("user_decision")
        run["reviewer_id_reserved"] = "judge-expected"
        with self.assertRaisesRegex(ValueError, "reserved reviewer"):
            validate_review_against_run(run, review)


if __name__ == "__main__":
    unittest.main()
