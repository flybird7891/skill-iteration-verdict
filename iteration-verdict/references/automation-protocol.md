# 自动评审协议

本协议用于自动调度独立裁判，防止裁判只确认任务却不执行评审。

## 建立尝试目录

每次尝试使用独立目录：

```text
quality-loop/<run_id>/review-attempts/attempt-1/
├── task.md
├── response.md
└── review.json
```

父运行先创建目录和 `task.md`，再启动新上下文。新上下文不能继承制作对话历史。

在 Codex 环境中使用子 Agent 时，启动任务必须采用无父对话历史的全新上下文（例如 `fork_turns="none"`）。如果启动接口返回 agent ID、任务 ID、session ID 或“已接收”，只表示任务已经创建，不代表评审完成。

第一次评审成功后，把裁判的 Agent ID 或 session ID 写入运行状态。后续修订轮次优先恢复这个裁判会话，并向它提供：

- 当前冻结版本。
- 更新后的证据。
- 上一轮修订单。
- 当前验收合同。

不要向裁判提供制作过程聊天。复用裁判会话不等于允许它读取制作上下文；它仍然只能看到评审材料。

如果原会话已经失效，记录 `reviewer_session_id` 替换原因，并使用新 ID 启动完整评审。不要因为第一轮成功就假定第二轮也会自动成功。

父运行必须使用宿主提供的等待机制持续到子任务进入完成、失败或中断的终止状态，然后读取实际回复和文件。不能看到启动确认就立即认定评审失败，也不能把确认文字当作评审结果。

## 裁判任务模板

下发任务时必须把绝对路径替换为实际路径，并包含以下完整指令：

```text
你现在是 iteration-verdict 的独立裁判。这不是任务确认请求，而是立即执行的评审任务。

只读取以下评审包：
<REVIEW_PACKET_ABSOLUTE_PATH>

严格阅读：
- request.md
- contract 或 review-response-schema
- artifact/
- evidence/
- 其他评审说明

禁止：
- 读取制作过程聊天。
- 修改 artifact/。
- 降低验收标准。
- 只回复“收到”“已确认”“准备开始”。

必须执行：
1. 逐项检查合同中的全部有效需求。
2. 为每项给出 met、partial、unmet 或 unverifiable。
3. 为每项提供理由和对应证据。
4. 将合法评审 JSON 写入：
   <REVIEW_OUTPUT_ABSOLUTE_PATH>
5. 写入后重新读取文件，确认 JSON 可解析且包含全部需求。

在文件写入并验证前，不要返回最终答复。

最终回复只报告：
REVIEW_COMPLETE: <REVIEW_OUTPUT_ABSOLUTE_PATH>

如果无法完成，必须写入包含 error 字段的失败文件并在最终回复中报告失败原因。
```

## 结果验收

父运行必须等待裁判结束，然后检查：

1. `<response.md>` 是否只有确认文字。
2. `<review.json>` 是否存在。
3. JSON 是否可解析。
4. `reviewer_id` 是否与 `builder_id` 不同。
5. `reviewed_artifact_version` 是否匹配冻结版本。
6. 结果是否覆盖全部有效需求，且没有重复或缺失。
7. 证据对象结构是否完整。

以上任一项失败，记为一次失败尝试，不得判定裁判完成。

然后运行：

```bash
python scripts/validate_review.py --run <run.json> --review <review.json>
```

只有返回退出码 `0` 且输出 `"valid": true` 时，评审文件才可写入运行状态。

## 常见失败判断

- 启动后马上得到“任务已接收”：继续等待，不算完成。
- 子任务已终止但没有 `review.json`：记为失败。
- `review.json` 为空或 JSON 无效：记为失败。
- 评审只包含部分需求：记为失败。
- 评审者 ID 与预留 ID 或版本不一致：记为失败。

## 重试

第一次失败后重新建立 `attempt-2/`，任务消息中必须明确写出：

```text
上一次尝试只返回了确认或空结果，没有生成合法 review.json。
本次必须实际执行评审并写入文件；不要回复确认信息。
```

仍然失败时，保存两次尝试记录，并使用 `strict_satisfied: false` 的自动回退路径继续。不得卡住整个流程。

最终答复的第一句必须说明 Strict 未满足及其原因，再报告 Quick 回退后的技术状态。
