---
name: iteration-verdict
description: Manage bounded AI project revision and acceptance in Quick Check or Strict Arbitration. Freeze requirements, verify structured evidence, run self-check or independent blind review, issue revision orders, and produce a traceable verdict. Use for concrete deliverables that need repeatable acceptance; do not use for ordinary Q&A or simple copyediting without a deliverable and acceptance criteria.
metadata:
  short-description: 管理AI迭代修订，完成盲评并输出可追溯裁定。
  version: 2.1.0
---

# 迭代裁决

## 目标

管理一个具体 AI 项目的有限轮修订与最终验收。成果可以是代码、网页、文档、数据报告、设计、游戏、音乐或其他可检查交付物。

本 Skill 负责冻结标准、组织制作或评审、记录证据、生成修订单和输出裁定。它不替代用户判断主观价值，也不允许制作方把自己的自评伪装成独立评审。

## 开始前必须选择模式

如果用户没有明确指定模式，只发送下面的询问并停止，不要同时开始制作：

```text
运行版本：iteration-verdict 2.1.0

请选择本次项目的评审模式。选择后将在本次运行中锁定。

1. Quick Check
一个 AI 完成项目、基础检查和有限轮自我修订。适合小任务或个人工作。结果会标记为 single_reviewer，不声称具有独立评审。

2. Strict Arbitration
项目 AI 制作项目，裁判 AI 在独立上下文中盲评；脚本验证测试、数字和文件；用户进行最终确认。不合格时裁判只发修订单，项目 AI 修改后再提交复评。无法提供独立裁判时，不能伪装运行 Strict。
 Skill 会优先自动建立隔离评审上下文；若启动失败会重试一次，仍失败时自动回退到 Quick Check，并在报告中明确标记 Strict 独立性未满足。

请回复 quick 或 strict。
```

模式写入运行状态并锁定。需要切换模式时结束当前运行，建立新运行。

## Strict 启动前检查

选择 Strict 后，在开始制作前立即执行以下步骤：

1. 在当前项目创建 `quality-loop/<run_id>/`。
2. 建立 `run.json`，写入 `mode`、`builder_id`、冻结合同、阈值和轮数。
3. 优先尝试使用宿主提供的子任务、Agent 或新上下文机制建立独立裁判，并预留 `reviewer_id`。
4. 确认最终可以再次联系用户进行接受或拒绝。

独立裁判启动失败时重试一次。仍然失败时，不要停在预检步骤，也不要要求用户自己开新聊天；自动建立有效模式为 Quick Check 的回退运行：

```json
{
  "requested_mode": "strict",
  "mode": "quick",
  "fallback_reason": "宿主未提供可隔离的独立裁判上下文"
}
```

回退后继续完成项目、自检、报告和有限修订，但在报告中明确写出 `strict_satisfied: false`。不得把回退结果描述为 Strict 合格。

最终聊天答复必须先说明：

```text
Strict 独立性未满足：独立裁判未返回有效评审。
```

然后才能说明 Quick 回退后的技术结果。不要先写“项目已完成”或“已通过”，再在后续段落补充回退信息。

不要先完成整个项目，再事后补一个“独立评审”标签。

## 共同流程

1. **理解需求。** 明确目标、交付物、受众、禁止事项、验收截止时间和可用材料。
2. **冻结合同。** 读取 [运行状态结构](references/state-schema.md)，把需求转为 `P0/P1/P2`、可观察通过条件和所需证据。
3. **选择项目配置。** 读取 [项目类型配置](references/project-profiles.md) 中与当前项目相符的部分。没有匹配类型时使用通用规则。
4. **制作成果。** 按冻结合同执行。项目制作方可以自行检查并修复，但内部自检不等于正式评审。
5. **收集证据。** 按 [证据规则](references/evidence-rules.md) 记录测试、截图、日志、文件检查或用户确认。
6. **执行对应模式。** Quick Check 使用单评审者自检；Strict Arbitration 使用 [严格仲裁协议](references/review-protocol.md)。
7. **运行门禁。** 把完整运行状态交给脚本检查：

   ```bash
   python scripts/verdict_gate.py --input <run.json> --markdown-output <verdict.md>
   ```

   用户终审前生成中间报告时使用 `verdict.pending.md`；收到最终决定并更新 `user_decision` 后，才生成 `verdict.md`。

8. **按裁定行动。** `qualified` 或 `qualified_with_caveats` 时停止。`revision_required` 时只按修订单继续。达到轮数上限、证据不足或出现争议时如实停止。

## Quick Check

- 一个 AI 同时承担制作和自检。
- 自检结果必须标记 `reviewer_mode: single_reviewer`。
- 可以使用脚本做基础验证，但不能声称拥有独立评审。
- P0 未满足、证据覆盖不足或质量分未达阈值时，不得输出合格。
- 用户最终确认可选；未发生时记录 `user_decision.decision: not_required`。

Quick Check 不是“只看完成声明”。数字、文件、构建和关键功能仍应使用可检查证据。

## Strict Arbitration

Strict 分为内部制作循环和外部裁决循环。

### 内部制作循环

项目 AI 可以像 Quick Check 一样制作、自检和自行修复。正式提交后，该轮版本冻结，后续修改进入下一轮。

### 外部裁决循环

1. 项目 AI 提交当前版本、证据和已知限制。
2. 先执行确定性验证。
3. 裁判 AI 在独立上下文中盲评。
4. 用户进行最终接受或拒绝。
5. 系统计算裁定。
6. 未通过时生成修订单，项目 AI 修改并提交新版本。
7. 复评只重点检查本轮修复、证据和新出现的回归，同时保留 P0 全覆盖。

裁判只能读取评审包，不能读取制作过程的完整对话或制作者的预期分数。裁判不得修改被评审版本。

如果创建独立裁判后调用失败，重试一次。仍失败时自动进入带有明确原因的 Quick 回退，不能让整个流程停在半途。没有说明原因的回退是静默降级，禁止发生。

运行状态必须记录 `builder_id` 和 `reviewer_id`。Strict 中两者必须不同，否则不能视为独立裁决。

### 自动评审上下文

宿主支持子任务、Agent 或独立会话时，由 Skill 自动完成以下步骤，不要求用户手动复制材料：

1. 创建冻结评审包。
2. 使用不含制作历史的全新上下文启动裁判。
3. 只把评审包路径和评审规则交给裁判。
4. 要求裁判只读，不修改成果。
5. 保留裁判任务标识并等待其终止状态；启动确认不是评审完成。
6. 等待裁判返回结构化 JSON。
7. 先把评审文件交给脚本校验：

   ```bash
   python scripts/validate_review.py --run <run.json> --review <review.json>
   ```

8. 校验通过后把评审结果写入 `run.json`。
9. 自动运行门禁、生成待终审报告并询问用户最终决定。

用户仍然只需要在同一个对话中选择初始模式，并完成最终接受或拒绝。

同一个 Strict 运行应保存裁判的 `reviewer_session_id`，并优先在后续修订轮次中恢复同一个裁判会话。裁判可以保留自己的上一轮评审和修订单，但不能获得制作方聊天历史。继续使用同一个裁判可以减少重复启动失败，同时保持制作与评审分离。

只有原裁判会话不可恢复时，才创建新的裁判会话。此时必须记录新 `reviewer_id`、替换原因，并把完整合同、当前冻结版本和所需证据重新交给裁判。

裁判任务的下发、等待和结果验证必须按照 [自动评审协议](references/automation-protocol.md) 执行。

“任务已接收”“准备开始”“请确认任务”等回复不是评审结果。只有评审文件真实存在、包含 R1–RN 全部结果、通过结构校验，才算裁判完成。

每次评审必须有独立尝试目录：

```text
quality-loop/<run_id>/review-attempts/attempt-1/
├── task.md
├── response.md
└── review.json
```

如果子任务只返回确认信息，该次尝试记为 `acknowledgement_only`。不得把它当作评审通过，也不得省略重试。重试一次仍没有合法 `review.json` 时，才按自动回退规则继续。

裁判返回的评审 JSON 只是中间证据，不是最终裁定。必须把它写入 `run.json` 的 `review`，继续进入用户终审。

## Strict 硬停点

Strict 运行中，以下任一条件未满足时，不得在聊天中宣称项目已经完成，也不得把项目的创建说明当作最终交付：

- 当前轮版本已冻结。
- 独立裁判评审结果已写入 `run.json`。
- 用户已经明确选择 `accepted`、`accepted_with_caveats` 或 `rejected`。
- `verdict_gate.py` 已成功运行。
- `verdict.md` 已生成并可访问。
- 聊天最终答复包含裁定、分数、P0 状态和报告路径。

裁判完成后，向用户提供一个简短终审摘要，并明确询问：

```text
独立裁判已完成：P0 全部通过，质量分 X，证据覆盖 X。
主要结果：<一句话>
尚存限制：<没有则写“无”>

请选择最终决定：
1. accepted：接受
2. accepted_with_caveats：有条件接受，请补充条件
3. rejected：拒绝，请说明需要修改的地方
```

收到用户决定后才能写入 `user_decision` 并运行门禁。用户未回复、离开或无法联系时，运行状态是 `awaiting_user_decision`，不是 `qualified`。

用户决定之前，先生成：

```text
quality-loop/<run_id>/verdict.pending.md
quality-loop/<run_id>/result.pending.json
```

用户做出最终决定并写入 `run.json` 后，再运行门禁并生成最终：

```text
quality-loop/<run_id>/verdict.md
quality-loop/<run_id>/result.json
```

如果只有 `verdict.pending.md`，说明流程停在用户终审，不能称为完整结束。

如果只生成了评审 JSON、截图或项目文件，却没有 `verdict.md`，本次 Strict 运行仍未完成。

如果裁判回复为空、仅有确认文字，或没有生成约定路径的 `review.json`，同样属于未完成评审；不能进入用户终审。

## 验收状态

### 需求状态

- `met`
- `partial`
- `unmet`
- `unverifiable`

### 最终裁定

- `awaiting_user_decision`
- `qualified`
- `qualified_with_caveats`
- `revision_required`
- `disputed`
- `failed`
- `user_accepted_unqualified`

`user_accepted_unqualified` 只表示用户愿意接受已知缺陷，不表示技术验收通过。

`awaiting_user_decision` 是中间状态：技术评审已经完成，但还不能输出最终裁定。

## 硬性规则

- P0 只有全部处于 `met` 才可能通过。
- 结构化证据不能由“已经完成”“检查通过”等文字替代。
- 证据覆盖不足时不得输出合格。
- 用户拒绝主观结果时不得由裁判强行通过。
- 裁判不能用修改项目的方式制造合格结果。
- 无法验证的需求必须标记 `unverifiable`，不能默认满足。
- 单次运行不超过合同设置的轮数上限。
- 需求变化只能标记 `active`、`withdrawn` 或 `superseded`，不能悄悄删除。

## 输出

Quick Check 至少输出：

- 项目成果。
- 验收合同。
- 自检评分。
- `verdict.md` 或聊天中的结论摘要。
- 审计状态。

Strict Arbitration 至少输出：

- 冻结合同和版本清单。
- 裁判评审包与评分表。
- 用户决定。
- 未通过时的结构化修订单。
- 最终裁定书。
- 每轮证据、修复与回归记录。

优先写入项目内的统一目录：

```text
quality-loop/<run_id>/
├── run.json
├── verdict.pending.md
├── result.pending.json
├── verdict.md
├── result.json
├── review-packet/
└── rounds/<round>/
```

## 参考资源

- [运行状态结构](references/state-schema.md)
- [严格仲裁协议](references/review-protocol.md)
- [证据规则](references/evidence-rules.md)
- [项目类型配置](references/project-profiles.md)
