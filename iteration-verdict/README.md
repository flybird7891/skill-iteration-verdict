# 迭代裁决 / Iteration Verdict

当前版本：`2.1.0`

`iteration-verdict` 是一个面向 AI 项目的验收、独立评审与有限轮修订 Skill。

它把模糊需求整理成可检查的验收合同，收集结构化证据，在需要时启动独立裁判上下文，生成修订单，等待用户终审，并输出可追溯的项目裁定。

## 解决的问题

AI 可以很快完成网站、游戏、文档、音乐或其他交付物，但“看起来完成”不等于“满足要求”：

- 关键要求可能被遗漏。
- 页面可能存在未检查的交互或响应式问题。
- 数字、数据和引用可能无法复现。
- 制作 AI 容易忽略自己制造的回归。
- 用户需求可能只在过程中口头变化，没有审计记录。

本 Skill 将这些问题转为明确的合同、证据、评审和裁定流程。

## 主要特性

- 强制在开始前选择评审模式。
- 将需求冻结为 `P0/P1/P2`。
- 支持结构化证据和证据覆盖率检查。
- 支持 Quick Check 单评审者自检。
- 支持 Strict Arbitration 独立盲评。
- 自动生成结构化修订单。
- 检查 P0 否决、质量分、证据覆盖和回归项。
- 区分 AI 技术合格与用户主观接受。
- 保存运行状态、评审记录和最终报告。
- Strict 不可用时可自动回退，并明确标记 `strict_satisfied: false`。

## 两种模式

| 模式 | 角色 | 评审方式 | 用户终审 |
|---|---|---|---|
| Quick Check | 一个 AI | 制作后自检 | 可选 |
| Strict Arbitration | 项目 AI、裁判 AI、验证工具、用户 | 独立盲评和正式裁定 | 必须 |

### Quick Check

适用于个人任务、小型交付物和低风险项目。

```text
冻结需求
→ 一个 AI 制作
→ 自检与基础验证
→ 评分和门禁
→ 有限轮自行修订
→ 输出 Quick 报告
```

结果会标记为：

```text
reviewer_mode: single_reviewer
```

Quick Check 不会声称拥有独立评审。

### Strict Arbitration

适用于正式项目、需要证据留档或需要用户明确验收的交付物。

```text
冻结需求
→ 项目 AI 制作并提交冻结版本
→ 确定性检查和证据收集
→ 自动启动独立裁判
→ 裁判盲评并写出 review.json
→ 校验评审结果
→ 生成待终审报告
→ 用户接受、有条件接受或拒绝
→ 生成最终裁定
```

Strict 中：

- 项目 AI 与裁判的 ID 必须不同。
- 裁判不读取制作过程聊天。
- 裁判不修改被审查版本。
- 裁判只能按冻结合同作出结论。
- 用户保留主观价值判断和最终接受权。

同一个 Strict 运行会保存裁判会话标识，并在后续修订轮次中优先恢复同一个独立裁判会话。裁判只保留合同、冻结版本、证据和自己的历史评审，不获得制作过程聊天。只有原会话失效时才更换裁判，并记录原因。

## 运行要求

- 支持读取 `SKILL.md` 和调用本地脚本的 Codex 或兼容 Agent 环境。
- Python 3.10 或更高版本。
- Python 脚本仅使用标准库，不需要安装第三方依赖。
- Strict 需要宿主提供独立评审上下文、子 Agent 或独立会话能力。

## 安装

将整个 `iteration-verdict` 文件夹放入 Skill 目录，例如：

```text
~/.codex/skills/iteration-verdict/
```

目录应至少包含：

```text
iteration-verdict/
├── SKILL.md
├── README.md
├── MODEL_API_ASSETS.md
├── agents/openai.yaml
├── scripts/
├── references/
├── assets/
└── tests/
```

## 使用方式

在支持 `$skill` 调用的环境中显式调用：

```text
使用 $iteration-verdict 验收这个项目。
```

Skill 会先要求选择模式：

```text
quick
```

或：

```text
strict
```

## 输入

可以使用：

- 原始需求或任务提示词。
- 项目源码、网页、文档、数据或其他成果。
- 测试输出、截图、控制台状态和运行日志。
- 用户指定的验收标准、优先级和禁止事项。
- 已有评审记录或历史轮次。

结构化运行输入的完整字段见 [运行状态结构](references/state-schema.md)。

## 输出

正常 Quick Check 运行：

```text
quality-loop/<run-id>/
├── run.json
├── verdict.md
└── result.json
```

Strict Arbitration 运行：

```text
quality-loop/<run-id>/
├── run.json
├── review-attempts/
│   ├── attempt-1/
│   │   ├── task.md
│   │   ├── response.md
│   │   └── review.json
│   └── attempt-2/
├── verdict.pending.md
├── result.pending.json
├── verdict.md
└── result.json
```

说明：

- `verdict.pending.md`：裁判完成、等待用户终审。
- `verdict.md`：用户已作出最终决定，运行结束。
- `result.json`：机器可读的评分、P0、证据覆盖和裁定。
- `review.json`：独立裁判的结构化评审结果。

## 最终状态

- `qualified`：技术验收与用户终审均通过。
- `qualified_with_caveats`：通过，但存在已披露的次要限制。
- `awaiting_user_decision`：技术评审完成，等待用户终审。
- `revision_required`：需要按修订单继续。
- `disputed`：技术评审与用户判断存在实质分歧。
- `failed`：未通过、证据不足或达到轮数上限。
- `user_accepted_unqualified`：用户愿意接受，但技术仍不合格。

## 手动运行门禁

在仓库根目录执行：

```powershell
python scripts\verdict_gate.py --input <run.json> --markdown-output <verdict.md> --json-output <result.json>
```

使用严格退出码：

```powershell
python scripts\verdict_gate.py --input <run.json> --markdown-output <verdict.md> --strict-exit
```

`--strict-exit` 在结果不是 `qualified` 或 `qualified_with_caveats` 时返回 `1`。

## 独立评审文件校验

裁判返回 JSON 后、写入运行状态前：

```powershell
python scripts\validate_review.py --run <run.json> --review <review.json>
```

校验内容包括：

- 运行模式是否为 Strict。
- 评审者 ID 是否与预留 ID 一致。
- 评审者 ID 是否不同于项目 AI。
- 评审版本是否匹配冻结版本。
- 是否覆盖全部有效需求。
- 状态、理由和证据对象结构是否合法。

空回复、纯确认文字和缺少 `review.json` 均会被拒绝。

## 报告特征

`verdict.md` 包含：

- 运行编号、模式和当前轮次。
- P0、质量分和证据覆盖率。
- 用户最终决定。
- 需求台账。
- 结构化证据摘要。
- 修订单和回归项。
- 自动回退原因。
- 审计限制。

报告不是简单满意度问卷，而是依据合同、计算结果和证据作出的可追溯结论。

## 示例

仓库包含四组可运行样例：

- `assets/quick-example/`：Quick Check 合格。
- `assets/strict-example/`：Strict 完整通过。
- `assets/strict-revision-example/`：Strict 未通过并生成修订单。
- `assets/strict-fallback-example/`：独立裁判不可用时自动回退并披露限制。

运行示例：

```powershell
python scripts\verdict_gate.py --input assets\quick-example\run.json --markdown-output assets\quick-example\verdict.md
python scripts\verdict_gate.py --input assets\strict-example\run.json --markdown-output assets\strict-example\verdict.md
python scripts\verdict_gate.py --input assets\strict-revision-example\run.json --markdown-output assets\strict-revision-example\verdict.md
python scripts\verdict_gate.py --input assets\strict-fallback-example\run.json --markdown-output assets\strict-fallback-example\verdict.md
```

## 测试

```powershell
python -m unittest discover -s tests -v
```

测试覆盖：

- Quick 和 Strict 模式。
- P0 否决。
- 质量阈值。
- 证据覆盖率。
- 撤回需求。
- 版本不一致。
- 重复需求。
- 回归检测。
- 用户拒绝和附条件接受。
- 独立裁判身份要求。
- 空确认评审拒绝。
- Strict 自动回退。
- 待用户决定状态。

## 严格仲裁协议

完整评审规则见：

- [严格仲裁协议](references/review-protocol.md)
- [自动评审协议](references/automation-protocol.md)
- [证据规则](references/evidence-rules.md)
- [项目类型配置](references/project-profiles.md)

Strict 必须实际启动独立裁判并等待其终止状态。只有 `review.json` 存在且通过校验，才可进入用户终审。若两次尝试均未得到有效评审，Skill 会自动回退 Quick Check，并明确写入：

```text
strict_satisfied: false
```

## 模型、API 与素材

完整声明见 [MODEL_API_ASSETS.md](MODEL_API_ASSETS.md)。

简要说明：

- Skill 不绑定固定 LLM；模型由宿主环境提供。
- 仓库不包含模型权重。
- 脚本不调用外部商业 API，不包含 API 密钥。
- Python 脚本仅使用标准库。
- 示例数据为虚构测试素材，不包含第三方图片、字体或受限数据库。

## 限制

- Strict 的独立性依赖宿主是否支持隔离的评审上下文。
- 同一基础模型即使上下文隔离，仍可能共享知识和偏差，因此仍需确定性测试与用户终审。
- 没有可检查证据时，Skill 不会把需求默认判为通过。
- 用户未回复最终决定时，运行停留在 `awaiting_user_decision`，不生成最终合格裁定。
