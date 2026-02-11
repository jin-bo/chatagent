# Tool Confirmation Feature

## 概述

为 ChatAgent 添加了工具确认功能，在执行 Shell 和 Web 工具前需要用户明确确认，提高安全性。

## 改动内容

### 修改的文件

1. **chatagent/tools/base.py**
   - 在 `Tool` 基类添加 `requires_confirmation` 属性（默认 False）

2. **chatagent/tools/shell.py**
   - `ShellTool` 设置 `requires_confirmation = True`

3. **chatagent/tools/web.py**
   - `WebFetchTool` 设置 `requires_confirmation = True`
   - `GoogleSearchTool` 设置 `requires_confirmation = True`

4. **chatagent/agent.py**
   - 添加 `confirmation_callback` 参数
   - 在工具执行前检查 `requires_confirmation`
   - 如需确认则调用回调函数
   - 记录确认结果到日志

5. **chatagent/cli.py**
   - 添加 `confirm_tool_execution()` 方法
   - 使用 rich.Confirm 显示确认提示
   - 将确认回调传递给 agent

6. **README.md**
   - 添加工具确认功能说明
   - 更新特性列表

### 新增文件

1. **test_tool_confirmation.py**
   - 测试 `requires_confirmation` 属性
   - 测试确认回调机制
   - 测试无回调时的行为
   - 所有测试通过 ✅

2. **TOOL_CONFIRMATION.md**
   - 功能文档（中文）
   - 使用示例和说明

## 工作流程

```
1. LLM 决定使用工具
   ↓
2. Agent 检查工具的 requires_confirmation 属性
   ↓
3. 如果为 True 且有回调函数：
   - 暂停执行
   - 调用 confirmation_callback
   - CLI 显示确认提示
   - 等待用户输入 (y/n)
   ↓
4a. 用户确认 (y)         4b. 用户拒绝 (n)
    ↓                        ↓
    执行工具                 取消执行
    ↓                        ↓
    返回结果                 通知 LLM 已取消
```

## 需要确认的工具

| 工具 | 原因 |
|------|------|
| `run_shell_command` | 可能执行危险命令、修改系统 |
| `web_fetch` | 可能访问敏感网站、产生网络流量 |
| `google_web_search` | 可能暴露搜索意图、产生网络请求 |

## 确认提示示例

```
⚠️  Tool Confirmation Required
Tool: run_shell_command
Description: Execute a shell command and return its output. Use with caution as it can execute any command.
Arguments:
  • command: ls -la
  • working_directory: .
  • timeout: 30

Do you want to execute this tool? (y/n):
```

## 使用方法

### 用户使用

无需配置，自动生效：

```bash
uv run python main.py

You: List all files in current directory

# 系统会显示确认提示
⚠️  Tool Confirmation Required
Tool: run_shell_command
...
Do you want to execute this tool? (y/n): y

# 确认后执行
```

### 开发者添加新工具

```python
class MyTool(Tool):
    @property
    def requires_confirmation(self) -> bool:
        """Set to True for tools that perform risky operations."""
        return True  # 需要确认

    def execute(self, **kwargs) -> str:
        # 工具实现
        pass
```

## 安全优势

1. **防止意外执行** - 用户可以在执行前检查命令
2. **透明度** - 显示完整的工具参数
3. **可控性** - 用户决定是否执行
4. **审计** - 所有确认决定记录在日志中

## 向后兼容性

- ✅ 不影响现有工具（默认不需要确认）
- ✅ 无需修改配置
- ✅ 可选功能（如果没有回调函数，工具正常执行）

## 测试

运行测试：

```bash
uv run python test_tool_confirmation.py
```

所有测试通过：
- ✅ Shell & Web 工具需要确认
- ✅ 文件操作工具不需要确认
- ✅ Agent 接受确认回调
- ✅ 确认回调签名正确
- ✅ 无回调时正常工作

## 未来改进

可能的增强：
- 添加"总是允许"选项
- 添加"总是拒绝"选项
- 配置哪些工具需要确认
- 记住用户的确认偏好
- 批量确认多个工具调用

---

**特性状态**: ✅ 已实现并测试
**版本**: 0.2.0
**最后更新**: 2026-02-11
