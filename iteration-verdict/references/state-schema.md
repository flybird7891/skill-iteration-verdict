# 运行状态结构

`scripts/verdict_gate.py` 接受 UTF-8 JSON。一个文件代表一次锁定模式的运行。

## 顶层字段

```json
{
  "schema_version": "2.0",
  "run_id": "strict-20261113-01",
  "title": "项目名称",
  "mode": "strict",
  "requested_mode": "strict",
  "builder_id": "project-ai-01",
  "reviewer_session_id": "judge-session-01",
  "profile": "game",
  "threshold": 0.8,
  "evidence_coverage_min": 1.0,
  "max_rounds": 3,
  "current_round": 1,
  "submission_version": "round-01",
  "contract": [],
  "review": {},
  "review_attempts": [],
  "user_decision": {},
  "history": []
}
```

- `mode`：`quick` 或 `strict`，必填。
- `requested_mode`：用户最初选择的模式；默认等于 `mode`。
- `builder_id`：执行项目制作的 AI 或运行标识，必填。
- `reviewer_session_id`：可选，Strict 首次成功启动后的裁判 Agent 或会话标识；后续轮次优先恢复该会话。
- `threshold`：P1/P2 加权质量阈值，默认 `0.80`。
- `evidence_coverage_min`：关键证据覆盖率阈值，默认 `1.0`。
- `max_rounds`：本次运行最大轮数，范围 `1–5`。
- `current_round`：当前提交轮次。
- `submission_version`：当前冻结版本标识。
- `profile`：项目类型配置；没有匹配时填写 `general`。
- `review_attempts`：可选审计记录，记录每次裁判尝试的 ID、状态和输出路径。

## 验收合同

```json
{
  "id": "R1",
  "text": "项目必须完成核心操作",
  "priority": "P0",
  "source": "user-original",
  "pass_condition": "连续完成三次操作且无阻塞",
  "required_evidence": [
    "test_output",
    "screenshot"
  ],
  "status": "active",
  "weight": 3
}
```

`required_evidence` 表示可接受的证据类型，至少出现一种才算该需求有证据覆盖。需求状态为 `withdrawn` 或 `superseded` 时不参与本轮评分。

## 评审记录

```json
{
  "reviewer_mode": "independent_reviewer",
  "reviewer_id": "judge-01",
  "reviewed_artifact_version": "round-01",
  "results": [
    {
      "id": "R1",
      "status": "met",
      "reason": "连续三次操作均成功",
      "evidence": [
        {
          "kind": "test_output",
          "artifact": "round-01/artifact",
          "locator": "python tests/run.py",
          "observation": "3/3 操作测试通过",
          "verified_at": "2026-11-13T16:00:00+08:00"
        }
      ],
      "suggested_fix": ""
    }
  ]
}
```

Quick Check 使用 `single_reviewer`。Strict 必须使用 `independent_reviewer`，提供 `reviewer_id`，且 `reviewer_id` 不能等于 `builder_id`。`reviewed_artifact_version` 必须等于 `submission_version`。

如果用户请求 Strict，但宿主在启动和一次重试后仍无法提供独立裁判，可以自动建立有效模式为 `quick` 的运行：

```json
{
  "requested_mode": "strict",
  "mode": "quick",
  "fallback_reason": "宿主未提供可隔离的独立裁判上下文"
}
```

这种回退必须写入报告，`strict_satisfied` 为 `false`，技术通过时最多得到 `qualified_with_caveats`。

每条有效合同需求必须在评审结果中出现且只能出现一次。状态只能是：

- `met`
- `partial`
- `unmet`
- `unverifiable`

## 用户决定

Strict 必填：

```json
{
  "decision": "accepted",
  "decided_at": "2026-11-13T16:30:00+08:00",
  "notes": "整体符合目标"
}
```

可取值：

- `accepted`
- `accepted_with_caveats`
- `rejected`

在裁判完成、用户尚未回复时，Strict 可以省略 `user_decision`，或写成 `awaiting_user_decision`。此时门禁会生成等待终审的中间报告，不会输出合格。

Quick 可以填写 `not_required` 或省略。

## 历史轮次

历史用于回归检查：

```json
[
  {
    "round": 1,
    "results": [
      {
        "id": "R1",
        "status": "met"
      }
    ]
  }
]
```

如果某个 P0 在最近历史轮次中为 `met`，当前轮次却不再是 `met`，脚本会把它列为回归。
