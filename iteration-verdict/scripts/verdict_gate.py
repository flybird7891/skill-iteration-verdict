#!/usr/bin/env python3
"""Validate an iteration-verdict run and render a traceable verdict."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


MODES = {"quick", "strict"}
PRIORITIES = {"P0", "P1", "P2"}
REQUIREMENT_STATES = {"active", "withdrawn", "superseded"}
REVIEW_STATES = {"met", "partial", "unmet", "unverifiable"}
USER_DECISIONS = {
    "accepted",
    "accepted_with_caveats",
    "rejected",
    "not_required",
    "awaiting_user_decision",
}
STATUS_SCORES = {"met": 1.0, "partial": 0.5, "unmet": 0.0, "unverifiable": 0.0}
PRIORITY_WEIGHTS = {"P0": 3.0, "P1": 2.0, "P2": 1.0}
PASSING_VERDICTS = {"qualified", "qualified_with_caveats"}


def finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def text_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return [text(item, f"{field}[{index}]") for index, item in enumerate(value, 1)]


def evidence_object(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    required = ("kind", "artifact", "locator", "observation", "verified_at")
    return {key: text(value.get(key), f"{field}.{key}") for key in required}


def contract_requirement(value: Any, index: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"contract[{index}] must be an object")

    requirement_id = text(value.get("id"), f"contract[{index}].id")
    priority = text(value.get("priority"), f"{requirement_id}.priority").upper()
    if priority not in PRIORITIES:
        raise ValueError(f"{requirement_id}.priority must be P0, P1, or P2")

    state = text(value.get("status", "active"), f"{requirement_id}.status").lower()
    if state not in REQUIREMENT_STATES:
        allowed = ", ".join(sorted(REQUIREMENT_STATES))
        raise ValueError(f"{requirement_id}.status must be one of: {allowed}")

    requirement = {
        "id": requirement_id,
        "text": text(value.get("text"), f"{requirement_id}.text"),
        "priority": priority,
        "source": text(value.get("source"), f"{requirement_id}.source"),
        "status": state,
        "required_evidence": text_list(
            value.get("required_evidence"), f"{requirement_id}.required_evidence"
        ),
        "pass_condition": value.get("pass_condition", ""),
    }
    if state == "active":
        requirement["pass_condition"] = text(
            value.get("pass_condition"), f"{requirement_id}.pass_condition"
        )
    elif not isinstance(requirement["pass_condition"], str):
        raise ValueError(f"{requirement_id}.pass_condition must be a string")

    if "weight" in value:
        weight = finite_number(value["weight"], f"{requirement_id}.weight")
        if weight <= 0:
            raise ValueError(f"{requirement_id}.weight must be positive")
        requirement["weight"] = weight
        requirement["weight_source"] = "explicit"
    else:
        requirement["weight"] = PRIORITY_WEIGHTS[priority]
        requirement["weight_source"] = "priority_default"
    return requirement


def review_result(value: Any, index: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"review.results[{index}] must be an object")
    requirement_id = text(value.get("id"), f"review.results[{index}].id")
    status = text(value.get("status"), f"{requirement_id}.status").lower()
    if status not in REVIEW_STATES:
        allowed = ", ".join(sorted(REVIEW_STATES))
        raise ValueError(f"{requirement_id}.status must be one of: {allowed}")
    raw_evidence = value.get("evidence", [])
    if not isinstance(raw_evidence, list):
        raise ValueError(f"{requirement_id}.evidence must be a list")
    evidence = [
        evidence_object(item, f"{requirement_id}.evidence[{evidence_index}]")
        for evidence_index, item in enumerate(raw_evidence, 1)
    ]
    suggested_fix = value.get("suggested_fix", "")
    if not isinstance(suggested_fix, str):
        raise ValueError(f"{requirement_id}.suggested_fix must be a string")
    return {
        "id": requirement_id,
        "status": status,
        "reason": text(value.get("reason"), f"{requirement_id}.reason"),
        "evidence": evidence,
        "suggested_fix": suggested_fix.strip(),
    }


def history_entry(value: Any, index: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"history[{index}] must be an object")
    round_number = integer(value.get("round"), f"history[{index}].round")
    if round_number < 1:
        raise ValueError(f"history[{index}].round must be positive")
    raw_results = value.get("results")
    if not isinstance(raw_results, list):
        raise ValueError(f"history[{index}].results must be a list")
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for result_index, raw in enumerate(raw_results, 1):
        if not isinstance(raw, dict):
            raise ValueError(
                f"history[{index}].results[{result_index}] must be an object"
            )
        result_id = text(
            raw.get("id"), f"history[{index}].results[{result_index}].id"
        )
        if result_id in seen:
            raise ValueError(f"duplicate history result id: {result_id}")
        seen.add(result_id)
        status = text(raw.get("status"), f"{result_id}.history_status").lower()
        if status not in REVIEW_STATES:
            raise ValueError(f"{result_id}.history_status is invalid")
        results.append({"id": result_id, "status": status})
    return {"round": round_number, "results": results}


def user_decision(value: Any, mode: str) -> dict[str, str]:
    if value is None:
        if mode == "strict":
            return {
                "decision": "awaiting_user_decision",
                "decided_at": "",
                "notes": "",
            }
        return {"decision": "not_required", "decided_at": "", "notes": ""}
    if not isinstance(value, dict):
        raise ValueError("user_decision must be an object")
    decision = text(value.get("decision"), "user_decision.decision").lower()
    if decision not in USER_DECISIONS:
        allowed = ", ".join(sorted(USER_DECISIONS))
        raise ValueError(f"user_decision.decision must be one of: {allowed}")
    if mode == "strict" and decision == "not_required":
        raise ValueError(
            "strict mode uses awaiting_user_decision or a final user decision"
        )
    if mode == "quick" and decision == "awaiting_user_decision":
        raise ValueError("quick mode uses not_required or an optional final decision")
    decided_at = value.get("decided_at", "")
    notes = value.get("notes", "")
    if not isinstance(decided_at, str) or not isinstance(notes, str):
        raise ValueError("user_decision.decided_at and notes must be strings")
    if decision not in {"not_required", "awaiting_user_decision"} and not decided_at.strip():
        raise ValueError("user_decision.decided_at is required")
    return {
        "decision": decision,
        "decided_at": decided_at.strip(),
        "notes": notes.strip(),
    }


def validate_review(
    value: Any, mode: str, version: str, builder_id: str
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("review must be an object")
    reviewer_mode = text(value.get("reviewer_mode"), "review.reviewer_mode").lower()
    expected_mode = "single_reviewer" if mode == "quick" else "independent_reviewer"
    if reviewer_mode != expected_mode:
        raise ValueError(f"{mode} review requires reviewer_mode={expected_mode}")

    reviewer_id = value.get("reviewer_id", "")
    if not isinstance(reviewer_id, str):
        raise ValueError("review.reviewer_id must be a string")
    if mode == "strict" and not reviewer_id.strip():
        raise ValueError("strict mode requires review.reviewer_id")
    if mode == "strict" and reviewer_id.strip() == builder_id:
        raise ValueError("strict reviewer_id must differ from builder_id")

    reviewed_version = text(
        value.get("reviewed_artifact_version"), "review.reviewed_artifact_version"
    )
    if reviewed_version != version:
        raise ValueError(
            "review.reviewed_artifact_version must match submission_version"
        )

    raw_results = value.get("results")
    if not isinstance(raw_results, list) or not raw_results:
        raise ValueError("review.results must be a non-empty list")
    results = [
        review_result(raw, index) for index, raw in enumerate(raw_results, 1)
    ]
    return {
        "reviewer_mode": reviewer_mode,
        "reviewer_id": reviewer_id.strip(),
        "reviewed_artifact_version": reviewed_version,
        "results": results,
        "notes": str(value.get("notes", "")).strip(),
    }


def evaluate_run(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")

    schema_version = text(data.get("schema_version"), "schema_version")
    if schema_version != "2.0":
        raise ValueError("schema_version must be 2.0")
    mode = text(data.get("mode"), "mode").lower()
    if mode not in MODES:
        raise ValueError("mode must be quick or strict")
    requested_mode = text(data.get("requested_mode", mode), "requested_mode").lower()
    if requested_mode not in MODES:
        raise ValueError("requested_mode must be quick or strict")
    if requested_mode == "quick" and mode == "strict":
        raise ValueError("strict mode cannot fulfill a quick request")
    fallback_reason = data.get("fallback_reason", "")
    if not isinstance(fallback_reason, str):
        raise ValueError("fallback_reason must be a string")
    fallback_applied = requested_mode == "strict" and mode == "quick"
    if fallback_applied and not fallback_reason.strip():
        raise ValueError("strict-to-quick fallback requires fallback_reason")
    if not fallback_applied:
        fallback_reason = ""
    builder_id = text(data.get("builder_id"), "builder_id")

    threshold = finite_number(data.get("threshold", 0.8), "threshold")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0.0 and 1.0")
    coverage_min = finite_number(
        data.get("evidence_coverage_min", 1.0), "evidence_coverage_min"
    )
    if not 0.0 <= coverage_min <= 1.0:
        raise ValueError("evidence_coverage_min must be between 0.0 and 1.0")

    max_rounds = integer(data.get("max_rounds", 3), "max_rounds")
    if not 1 <= max_rounds <= 5:
        raise ValueError("max_rounds must be between 1 and 5")
    current_round = integer(data.get("current_round"), "current_round")
    if not 1 <= current_round <= max_rounds:
        raise ValueError("current_round must be between 1 and max_rounds")

    version = text(data.get("submission_version"), "submission_version")
    raw_contract = data.get("contract")
    if not isinstance(raw_contract, list) or not raw_contract:
        raise ValueError("contract must be a non-empty list")
    contract = [
        contract_requirement(raw, index)
        for index, raw in enumerate(raw_contract, 1)
    ]
    seen_contract_ids: set[str] = set()
    for requirement in contract:
        if requirement["id"] in seen_contract_ids:
            raise ValueError(f"duplicate requirement id: {requirement['id']}")
        seen_contract_ids.add(requirement["id"])
    active = [item for item in contract if item["status"] == "active"]
    if not active:
        raise ValueError("contract must contain at least one active requirement")

    review = validate_review(data.get("review"), mode, version, builder_id)
    result_by_id = {item["id"]: item for item in review["results"]}
    if len(result_by_id) != len(review["results"]):
        raise ValueError("duplicate review result id")
    active_ids = {item["id"] for item in active}
    result_ids = set(result_by_id)
    if result_ids != active_ids:
        missing = sorted(active_ids - result_ids)
        extra = sorted(result_ids - active_ids)
        raise ValueError(
            f"review results must match active contract; missing={missing}, extra={extra}"
        )

    decision_record = user_decision(data.get("user_decision"), mode)
    raw_history = data.get("history", [])
    if not isinstance(raw_history, list):
        raise ValueError("history must be a list")
    history = [
        history_entry(raw, index) for index, raw in enumerate(raw_history, 1)
    ]
    history_rounds = [item["round"] for item in history]
    if len(set(history_rounds)) != len(history_rounds):
        raise ValueError("history contains duplicate round numbers")
    if any(round_number >= current_round for round_number in history_rounds):
        raise ValueError("history rounds must be earlier than current_round")

    total_weight = 0.0
    weighted_score = 0.0
    p0_failures: list[str] = []
    needs_evidence = [item for item in active if item["required_evidence"]]
    covered_ids: set[str] = set()
    requirement_rows: list[dict[str, Any]] = []
    for requirement in active:
        result = result_by_id[requirement["id"]]
        status = result["status"]
        score = STATUS_SCORES[status]
        total_weight += requirement["weight"]
        weighted_score += requirement["weight"] * score
        if requirement["priority"] == "P0" and status != "met":
            p0_failures.append(requirement["id"])

        accepted_kinds = set(requirement["required_evidence"])
        covered = bool(
            accepted_kinds
            and any(item["kind"] in accepted_kinds for item in result["evidence"])
        )
        if covered:
            covered_ids.add(requirement["id"])
        requirement_rows.append(
            {
                **requirement,
                "review_status": status,
                "score": score,
                "reason": result["reason"],
                "evidence": result["evidence"],
                "suggested_fix": result["suggested_fix"],
                "evidence_covered": covered if requirement["required_evidence"] else None,
            }
        )

    quality_score = round(weighted_score / total_weight, 6)
    evidence_coverage = (
        round(len(covered_ids) / len(needs_evidence), 6) if needs_evidence else 1.0
    )
    p0_pass = not p0_failures
    score_pass = quality_score >= threshold
    coverage_pass = evidence_coverage >= coverage_min
    technical_pass = p0_pass and score_pass and coverage_pass

    latest = max(history, key=lambda item: item["round"], default=None)
    regressions: list[dict[str, str]] = []
    if latest:
        previous = {item["id"]: item["status"] for item in latest["results"]}
        for requirement in active:
            if (
                previous.get(requirement["id"]) == "met"
                and result_by_id[requirement["id"]]["status"] != "met"
            ):
                regressions.append(
                    {
                        "id": requirement["id"],
                        "priority": requirement["priority"],
                        "previous": "met",
                        "current": result_by_id[requirement["id"]]["status"],
                    }
                )

    rounds_remaining = max_rounds - current_round
    user_state = decision_record["decision"]
    if mode == "quick":
        if technical_pass:
            if user_state == "rejected":
                verdict = (
                    "revision_required" if rounds_remaining > 0 else "failed"
                )
                reason = "技术检查通过，但用户拒绝接受。"
            elif user_state == "accepted_with_caveats":
                verdict = "qualified_with_caveats"
                reason = "技术检查通过，用户有条件接受。"
            elif fallback_applied:
                verdict = "qualified_with_caveats"
                reason = "独立裁判不可用，已自动回退为 Quick Check；Strict 独立性未满足。"
            else:
                verdict = "qualified"
                reason = "单评审者自检通过，且没有用户拒绝记录。"
        else:
            verdict = "revision_required" if rounds_remaining > 0 else "failed"
            reason = "技术门禁未通过。"
    else:
        if user_state == "awaiting_user_decision":
            verdict = "awaiting_user_decision"
            reason = "独立评审已结束，等待用户终审后才能形成最终裁定。"
        elif not technical_pass:
            if rounds_remaining > 0:
                verdict = "revision_required"
                reason = "技术门禁未通过，仍有修订轮次。"
            elif user_state in {"accepted", "accepted_with_caveats"}:
                verdict = "user_accepted_unqualified"
                reason = "用户接受，但技术门禁仍未通过。"
            else:
                verdict = "failed"
                reason = "技术门禁未通过，且没有后续轮次。"
        elif user_state == "accepted":
            verdict = "qualified"
            reason = "技术门禁与用户终审均通过。"
        elif user_state == "accepted_with_caveats":
            verdict = "qualified_with_caveats"
            reason = "技术门禁通过，用户有条件接受。"
        else:
            verdict = "disputed"
            reason = "技术门禁通过，但用户拒绝接受，形成主观争议。"

    issues = [
        row for row in requirement_rows if row["review_status"] != "met"
    ]
    revision_orders = []
    if verdict in {"revision_required", "awaiting_user_decision"}:
        for row in issues:
            revision_orders.append(
                {
                    "issue_id": f"I-{row['id']}-{current_round}",
                    "requirement_id": row["id"],
                    "priority": row["priority"],
                    "problem": row["reason"],
                    "required_change": row["suggested_fix"]
                    or "修复至满足通过条件并补充所需证据。",
                    "acceptance_test": row["pass_condition"],
                    "scope_limit": "只修复本问题及其必要影响，不降低其他已通过要求。",
                    "round": current_round,
                }
            )

    return {
        "schema_version": schema_version,
        "run_id": text(data.get("run_id"), "run_id"),
        "title": text(data.get("title"), "title"),
        "mode": mode,
        "requested_mode": requested_mode,
        "fallback_applied": fallback_applied,
        "fallback_reason": fallback_reason.strip(),
        "strict_satisfied": requested_mode == "strict" and mode == "strict",
        "builder_id": builder_id,
        "profile": text(data.get("profile", "general"), "profile"),
        "threshold": threshold,
        "evidence_coverage_min": coverage_min,
        "max_rounds": max_rounds,
        "current_round": current_round,
        "rounds_remaining": rounds_remaining,
        "submission_version": version,
        "contract": contract,
        "review": review,
        "user_decision": decision_record,
        "quality_score": quality_score,
        "evidence_coverage": evidence_coverage,
        "p0_pass": p0_pass,
        "score_pass": score_pass,
        "coverage_pass": coverage_pass,
        "technical_pass": technical_pass,
        "p0_failures": p0_failures,
        "regressions": regressions,
        "requirements": requirement_rows,
        "issues": issues,
        "revision_orders": revision_orders,
        "verdict": verdict,
        "reason": reason,
    }


def md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def render_markdown(result: dict[str, Any]) -> str:
    reviewer_note = (
        "单评审者：制作与检查由同一 AI 完成。"
        if result["mode"] == "quick"
        else f"独立评审：{result['review']['reviewer_id']} 盲评冻结版本。"
    )
    lines = [
        f"# 迭代裁决报告：{result['title']}",
        "",
        f"- 运行编号：{result['run_id']}",
        f"- 模式：`{result['mode']}`",
        f"- 请求模式：`{result['requested_mode']}`",
        f"- 项目 AI：{result['builder_id']}",
        f"- 项目配置：`{result['profile']}`",
        f"- 当前轮次：{result['current_round']} / {result['max_rounds']}",
        f"- 冻结版本：{result['submission_version']}",
        f"- 最终裁定：`{result['verdict']}`",
        f"- 裁定理由：{result['reason']}",
        f"- 评审独立性：{reviewer_note}",
        "",
        "## 门禁摘要",
        "",
        "| 指标 | 结果 |",
        "|---|---:|",
        f"| P0 全部通过 | {'是' if result['p0_pass'] else '否'} |",
        f"| 质量分 | {result['quality_score']:.4f} / 阈值 {result['threshold']:.4f} |",
        (
            f"| 证据覆盖率 | {result['evidence_coverage']:.4f} / "
            f"最低 {result['evidence_coverage_min']:.4f} |"
        ),
        "",
        "## 需求台账",
        "",
        "| 编号 | 优先级 | 需求 | 状态 | 得分 | 证据覆盖 | 检查结果 |",
        "|---|---|---|---|---:|---|---|",
    ]
    for row in result["requirements"]:
        covered = "不需要" if row["evidence_covered"] is None else (
            "是" if row["evidence_covered"] else "否"
        )
        lines.append(
            f"| {md(row['id'])} | {row['priority']} | {md(row['text'])} | "
            f"`{row['review_status']}` | {row['score']:.2f} | {covered} | "
            f"{md(row['reason'])} |"
        )

    if result["fallback_applied"]:
        lines.extend(
            [
                "",
                "## 自动回退",
                "",
                f"- 请求模式：`{result['requested_mode']}`",
                f"- 有效模式：`{result['mode']}`",
                f"- 原因：{result['fallback_reason']}",
                "- `strict_satisfied: false`，当前结论不能视为 Strict 合格。",
            ]
        )

    evidence_rows = [
        (row["id"], item)
        for row in result["requirements"]
        for item in row["evidence"]
    ]
    if evidence_rows:
        lines.extend(
            [
                "",
                "## 证据摘要",
                "",
                "| 需求 | 类型 | 位置 | 观察结果 |",
                "|---|---|---|---|",
            ]
        )
        for requirement_id, item in evidence_rows:
            lines.append(
                f"| {md(requirement_id)} | {md(item['kind'])} | "
                f"{md(item['locator'])} | {md(item['observation'])} |"
            )

    if result["p0_failures"]:
        lines.extend(
            [
                "",
                "## P0 未通过",
                "",
                *[f"- `{item}`" for item in result["p0_failures"]],
            ]
        )
    if result["regressions"]:
        lines.extend(["", "## 回归项", ""])
        for item in result["regressions"]:
            lines.append(
                f"- `{item['id']}`（{item['priority']}）："
                f"{item['previous']} → {item['current']}"
            )

    lines.extend(["", "## 用户决定", ""])
    lines.extend(
        [
            f"- 决定：`{result['user_decision']['decision']}`",
            f"- 时间：{result['user_decision']['decided_at'] or '未提供'}",
            f"- 说明：{result['user_decision']['notes'] or '无'}",
        ]
    )

    if result["revision_orders"]:
        lines.extend(
            [
                "",
                "## 修订单",
                "",
                "| 问题 | 需求 | 优先级 | 必需修改 | 复评条件 |",
                "|---|---|---|---|---|",
            ]
        )
        for order in result["revision_orders"]:
            lines.append(
                f"| {md(order['issue_id'])} | {md(order['requirement_id'])} | "
                f"{order['priority']} | {md(order['required_change'])} | "
                f"{md(order['acceptance_test'])} |"
            )

    lines.extend(
        [
            "",
            "## 审计限制",
            "",
            "- 本报告依据提交的合同、评审结果和证据计算。",
            "- `partial`、`unmet` 和 `unverifiable` 都不等于合格。",
            "- 用户接受技术不合格版本时仍保留不合格技术结论。",
            "",
        ]
    )
    return "\n".join(lines)


def load_input(path: str) -> Any:
    source = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    if not source.strip():
        raise ValueError("input JSON is empty")
    return json.loads(source)


def write_text(path: str, content: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate an iteration-verdict run and render a verdict."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to run JSON, or '-' to read standard input.",
    )
    parser.add_argument(
        "--markdown-output",
        default="",
        help="Optional Markdown verdict path; prints to stdout when omitted.",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Optional JSON result path.",
    )
    parser.add_argument(
        "--strict-exit",
        action="store_true",
        help="Return exit code 1 unless the verdict is qualified or qualified_with_caveats.",
    )
    args = parser.parse_args()

    try:
        result = evaluate_run(load_input(args.input))
        markdown = render_markdown(result)
        if args.markdown_output:
            write_text(args.markdown_output, markdown)
        else:
            print(markdown)
        if args.json_output:
            write_text(
                args.json_output,
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"verdict_gate: {exc}", file=sys.stderr)
        return 2

    if args.strict_exit and result["verdict"] not in PASSING_VERDICTS:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
