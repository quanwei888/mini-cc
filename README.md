# mini-cc

> **Tool is all you need.**
>
> Agent = LLM + Loop + Tools。连 LLM 本身也不过是一个工具。

「Tool Is All You Need」的配套实现，用 ~500 行 Python 演示多 Agent 系统的核心原理。

> 目前仅在 macOS 上测试过。

## 核心思想

- **Tool is all you need** — 一切皆工具。`SpawnAgent`、`SendMessage`、`LLM`、`Compress` 与 `Bash`、`FileRead` 结构完全相同，agent 自身只是一个调用工具的循环。
- **Agent Loop** — 每个 agent 是独立线程，从收件箱取消息，调用 LLM，执行工具，循环直到任务完成。
- **通信** — 所有消息通过 `SendMessage` 传递，agent 之间地位对等。

## 核心功能

- **文件编辑** — 读取、写入、精确替换，以及 Glob / Grep 搜索
- **Shell 执行** — 运行任意 shell 命令，60 秒超时保护
- **多 agent 协作** — 两种模式，Agent会自主选择：
  - `auto_shutdown=true`：一次性任务，完成后自动将结果发回创建者并关闭
  - `auto_shutdown=false`：常驻 agent，持续运行，支持多轮交互，需协调者主动关闭
- **Skills** — 兼容 Claude Code，读取 `.claude/skills/<name>/SKILL.md`，支持 `$ARGUMENTS` 替换；可用 skill 列表在 agent 启动时注入 system prompt
- **可扩展** — 继承 `Tool` 即可添加任意新工具，自动注册，无需改动框架
- **流式输出 + 打断** — Ctrl+C 随时打断正在进行的请求
- **上下文压缩** — 历史超过阈值自动截断，防止超出模型 context 限制

## 快速开始

```bash
git clone https://github.com/quanwei888/mini-cc.git
cd mini-cc

# 安装依赖
pip install anthropic prompt_toolkit rich

# 配置环境变量
cp .env.example .env
# ANTHROPIC_API_KEY=        必填
# ANTHROPIC_BASE_URL=       自定义服务地址（可选）
# ANTHROPIC_MODEL=          默认 claude-sonnet-4-6
# ANTHROPIC_MAX_TOKENS=     默认 16000

# 运行
./mini-cc
```

如果想在任意目录使用 `mini-cc` 命令（macOS/Linux）：

```bash
ln -sf "$(pwd)/mini-cc" ~/.local/bin/mini-cc
# 确保 ~/.local/bin 在 PATH 中（~/.zshrc 加上）：
# export PATH="$HOME/.local/bin:$PATH"
```

## 使用示例

```
# 读文件
> 读取 agent.py，解释它的结构

# 执行命令
> 统计当前目录有多少行 Python 代码

# 多 agent 协作
> 创建两个 worker，分别分析 agent.py 和 ui.py，完成后汇总

# 修改文件
> 在 README.md 末尾追加一行注释

# 调用 skill（兼容 Claude Code，读取 .claude/skills/<name>/SKILL.md）
> /skill名称 参数
```

**Ctrl+C** — 打断当前请求（再按一次退出）  
**Ctrl+D** — 退出程序

底部状态栏实时显示所有 agent 的工作状态（idle / running / 当前执行的工具名）。

## 工具列表

工具分两类：**用户工具**暴露给 LLM 供其调用；**系统工具**不暴露，由 agent 框架内部调用。

| 工具 | 说明 | 类型 |
|---|---|---|
| `Bash` | 执行 shell 命令 | 用户 |
| `FileRead` | 读取文件内容 | 用户 |
| `FileWrite` | 写入文件（覆盖） | 用户 |
| `FileEdit` | 精确替换文件内容 | 用户 |
| `Glob` | 按模式匹配文件路径 | 用户 |
| `Grep` | 在文件中搜索内容 | 用户 |
| `SpawnAgent` | 创建子 agent | 用户 |
| `SendMessage` | 向 agent 发送消息 | 用户 |
| `ListAgents` | 列出所有运行中的 agent 及状态 | 用户 |
| `Skill` | 加载并执行 `.claude/skills/` 中定义的 skill | 用户 |
| `LLM` | 调用 Anthropic API（流式） | 系统 |
| `Compress` | 截断对话历史，防止超出 context 限制 | 系统 |

## 架构

```
main.py       — 入口：加载工具、启动 main agent、读取用户输入
agent.py      — Agent 类（dataclass）：收消息 → LLM 推理 → 执行工具 → 循环
                Agent.registry 存放所有运行中的 agent
ui.py         — 终端 UI（Rich + prompt_toolkit），带输出锁防止多线程交错
runtime.py    — 基础设施：线程局部 agent 身份、get_tool()、get_tool_schemas()、skills_section()
tools/
  base.py     — Tool 基类与 TOOLS 注册表（exposed 字段区分用户/系统工具）
  fs/         — 文件系统工具（FileRead、FileWrite、FileEdit、Glob、Grep）
  shell/      — Bash
  agent/      — LLM、Compress、SpawnAgent、SendMessage、ListAgents、Skill
```

**依赖方向**：`agent.py → runtime.py ← tools/`，agent 与 tools 之间不直接依赖，通过 runtime 解耦。
