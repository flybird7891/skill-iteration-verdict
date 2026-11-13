# 证据规则

## 证据对象

每条证据至少包含：

```json
{
  "kind": "test_output",
  "artifact": "round-01/artifact",
  "locator": "python tests/run.py",
  "observation": "3/3 测试通过",
  "verified_at": "2026-11-13T16:00:00+08:00"
}
```

- `kind`：证据类型。
- `artifact`：被检查的成果或版本。
- `locator`：文件位置、命令、页面区域或时间点。
- `observation`：实际观察结果。
- `verified_at`：验证时间。

“已经完成”“检查通过”“应该没问题”等自我声明不能作为有效证据。

## 常见类型

- `test_output`
- `build_log`
- `screenshot`
- `interaction_record`
- `console_state`
- `file_content`
- `data_check`
- `audio_probe`
- `user_confirmation`
- `inspection`

项目配置可以要求上述类型之一，也可以使用自定义类型。

## 证据覆盖

只有同时满足以下条件，一条证据才计入覆盖：

1. 绑定到对应需求。
2. 类型属于该需求的 `required_evidence`。
3. 包含非空位置和观察结果。
4. 对应当前冻结版本。

证据覆盖率只统计需要证据的有效需求：

```text
覆盖需求数 / 需要证据的有效需求数
```

没有需求要求证据时，覆盖率为 `1.0`。

## 可信度

优先使用可重放结果、原始文件、测试输出和可核对截图。无法检查的材料应标成 `unverifiable`，不能算作满足。
