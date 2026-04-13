import queue
import threading
from dataclasses import dataclass, field
from typing import ClassVar

import ui
import runtime
from runtime import USER_AGENT_NAME, current_agent, set_current_agent
from anthropic.types import Message

# 对话历史超过此条数时触发压缩，避免 context 超出模型限制
_HISTORY_COMPRESS_THRESHOLD = 400
# 压缩后保留最近 N 条，保留一半让模型还有足够上下文
_HISTORY_COMPRESS_KEEP = 20

# 每个 agent 启动时用自己的名字渲染此模板
_SYSTEM_PROMPT = """\
你是 mini-cc 系统中名为 `{name}` 的 agent。
你可以使用工具和 skill 来完成任务。

## 多 agent 协同

- **启动**：`SpawnAgent(name="唯一名字", prompt="任务内容", auto_shutdown=true/false)`
  - `auto_shutdown=true`：一次性任务，完成后自动将结果发回并关闭，适合不需要反复交互的场景
  - `auto_shutdown=false`：常驻 agent，需要持续协同或多轮交互时使用，需手动发送 shutdown 关闭
- **查看**：`ListAgents()` 列出所有运行中的 agent 及状态
- **通信**：`SendMessage(to="<名字>", content="...")`
- **关闭**：`SendMessage(to="<名字>", content="", type="shutdown")`

## Skills

消息中出现 `/skill名称 参数` 时，调用 `Skill(name="...", args="...")` 加载该 skill 并执行。

{skills_section}
## 风格

简洁。直接做，不要旁白。用用户消息使用的语言回复。
"""


@dataclass
class Agent:
    """
    单个 agent 的完整生命周期。

    每个 agent 运行在独立线程中，拥有自己的对话历史（messages）。
    外部通过 registry[name] 队列向它发送消息，它从队列读取后驱动 LLM，
    LLM 可能调用工具，工具结果再次送入 LLM，直到 end_turn。

    main agent 由 main.py 启动，负责与用户交互。
    sub agent 由 SpawnAgent 工具创建，完成任务后可 auto_shutdown 自动关闭。
    """

    registry: ClassVar[dict[str, "Agent"]] = {}  # 全局注册表：name -> Agent

    name: str
    auto_shutdown: bool = False                                      # True 时 end_turn 后自动关闭并回报结果
    spawned_by: str = field(default=USER_AGENT_NAME)                 # 创建者名字，关闭时用于回报
    messages: list = field(default_factory=list)                     # Anthropic messages 格式的对话历史
    system: str = field(init=False)                                  # 由 name 渲染，见 __post_init__
    inbox: queue.Queue = field(default_factory=queue.Queue)          # 收件箱，外部通过 SendMessage 写入
    cancel: threading.Event = field(default_factory=threading.Event) # 打断标志，Ctrl+C 时 set()
    status: str = "starting"                                         # 显示在状态栏的当前状态

    def __post_init__(self):
        skills = runtime.skills_section()
        skills_section = skills + "\n" if skills else ""
        self.system = _SYSTEM_PROMPT.format(name=self.name, skills_section=skills_section)

    @classmethod
    def spawn(cls, name: str, prompt: str | None = None, auto_shutdown: bool = False) -> "Agent":
        """创建并启动一个新 agent：构造实例、注册到全局表、起线程、可选发首条消息。"""
        if name in cls.registry:
            raise ValueError(f"已存在名为 '{name}' 的 agent")
        spawned_by = current_agent()
        agent = cls(name=name, auto_shutdown=auto_shutdown, spawned_by=spawned_by)
        cls.registry[name] = agent
        threading.Thread(target=agent.run, daemon=True, name=name).start()
        if prompt:
            agent.inbox.put({"from": spawned_by, "type": "text", "content": prompt})
        return agent

    # ── LLM 调用 ────────────────────────────────────────────────────────────

    def _chat(self, tool_schemas: list, cancel) -> Message | None:
        """
        发起一次流式 LLM 调用，返回完整 response。

        流式过程中持续检测 cancel 标志（由 Ctrl+C 触发），
        一旦打断立即返回 None。出错时将错误追加到历史后也返回 None，
        调用方收到 None 即可跳出推理循环等待下一条消息。
        """
        try:
            with runtime.get_tool("LLM").stream(self.system, tool_schemas, self.messages) as s:
                for _ in s:
                    if cancel.is_set():
                        ui.output(title="已打断", bullet="warn")
                        return None
                return s.get_final_message()
        except Exception as e:
            self.messages.append({"role": "user", "content": f"[LLM 错误] {e}"})
            return None

    # ── 内容序列化 ──────────────────────────────────────────────────────────

    @staticmethod
    def _content_to_dicts(blocks) -> list[dict]:
        """
        将 Anthropic response.content blocks 转为普通 dict 列表。

        Anthropic SDK 返回的 blocks 是强类型对象，无法直接序列化进 messages，
        需转换后才能追加到对话历史供下一轮使用。
        """
        result = []
        for b in blocks:
            if b.type == "text":
                result.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                result.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
        return result

    # ── 工具执行 ────────────────────────────────────────────────────────────

    def _execute_tool(self, block) -> dict:
        """
        执行单个工具调用，返回符合 Anthropic 格式的 tool_result dict。

        tool_result 会作为下一轮 user 消息送入 LLM，LLM 通过 tool_use_id 对应结果。
        执行前后都有 UI 输出，方便用户观察工具调用过程。
        """
        tool_name = block.name
        inp = block.input

        tool = runtime.get_tool(tool_name)
        display_arg = tool.display(inp) if tool else ""
        label = f"{tool_name}({display_arg})" if display_arg else tool_name
        ui.output(title=label, bullet="tool")

        if tool is None:
            result = f"错误: 未知工具 '{tool_name}'"
            ui.output(content=result, bullet="error")
        else:
            try:
                result = tool.execute(**inp)
                ui.output(content=str(result), bullet="result")
            except Exception as e:
                result = f"错误: {type(e).__name__}: {e}"
                ui.output(content=str(result), bullet="error")

        return {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": str(result),
        }

    def _execute_tools(self, resp) -> list[dict]:
        """遍历 response 中所有 tool_use block，串行执行，返回结果列表。"""
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                self.status = f"● {block.name}"
                results.append(self._execute_tool(block))
        return results

    # ── 生命周期 ────────────────────────────────────────────────────────────

    def _close(self) -> None:
        """
        注销 agent：从全局注册表中删除，并向 spawner 发送关闭通知。

        注销后此 agent 的线程自然退出（run() 返回），
        其他 agent 再也无法向它发消息。
        """
        del Agent.registry[self.name]
        #if self.spawned_by in Agent.registry:
        #    runtime.get_tool("SendMessage").execute(
        #        to=self.spawned_by, content=f"agent '{self.name}' 已关闭"
        #    )

    # ── 主循环 ──────────────────────────────────────────────────────────────

    def run(self) -> None:
        """
        agent 主循环，在独立线程中运行。

        外层循环：等新消息 → 收件 → 压缩历史 → 推理
        内层循环由 _run_inference() 负责：LLM → 执行工具 → LLM → … 直到 end_turn
        """
        set_current_agent(self.name)
        self.status = "idle"
        while True:
            if not self._receive_and_queue():
                return
            self._maybe_compress()
            self._run_inference(runtime.get_tool_schemas())
            self.status = "idle"

    def _receive_and_queue(self) -> bool:
        """
        从 inbox 收取所有待处理消息，追加到 messages。

        先阻塞等到至少一条，再非阻塞排空队列，批量处理减少 LLM 调用次数。
        遇到 shutdown 消息时关闭自身并返回 False，通知 run() 退出线程。
        """
        msgs = [self.inbox.get()]
        while not self.inbox.empty():
            msgs.append(self.inbox.get_nowait())

        for m in msgs:
            if m["type"] == "shutdown":
                self._close()
                return False
            self.messages.append({"role": "user", "content": f"[from {m['from']}] {m['content']}"})

        self.cancel.clear()
        return True

    def _maybe_compress(self) -> None:
        """超出阈值时原地截断对话历史，防止 context 溢出。"""
        if len(self.messages) > _HISTORY_COMPRESS_THRESHOLD:
            before = runtime.get_tool("Compress").execute(self.messages, _HISTORY_COMPRESS_KEEP)
            ui.output(title=f"历史已压缩：{before} → {len(self.messages)} 条", bullet="warn")

    def _run_inference(self, tool_schemas: list) -> None:
        """
        LLM 推理循环：调用 LLM → 执行工具 → 再次调用 LLM → … 直到 end_turn 或被打断。

        end_turn 且 auto_shutdown=True 时，将结果发回 spawner 并关闭自身。
        """
        while True:
            self.status = "running"

            resp = self._chat(tool_schemas, self.cancel)
            if resp is None:
                break

            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            if runtime.is_user_agent(self.spawned_by) and text:
                ui.output(title=text, bullet="llm")

            self.messages.append({
                "role": "assistant",
                "content": self._content_to_dicts(resp.content),
            })

            if resp.stop_reason == "end_turn":
                if self.auto_shutdown:
                    if text:
                        runtime.get_tool("SendMessage").execute(to=self.spawned_by, content=text)
                    self._close()
                    return
                break

            tool_results = self._execute_tools(resp)
            self.status = "running"
            self.messages.append({"role": "user", "content": tool_results})
