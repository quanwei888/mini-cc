from pydantic import BaseModel, Field

from ..base import Tool


class SpawnAgent(Tool):
    name = "SpawnAgent"
    description = (
        "创建一个新 agent，在独立线程中运行。新 agent 与调用者完全隔离，"
        "从空白历史开始。如果提供 `prompt`，会作为第一条消息发给新 agent。"
        "立即返回，不等待新 agent 回复。"
    )

    class Input(BaseModel):
        name: str = Field(description="全局唯一的 agent 名字。")
        prompt: str | None = Field(default=None, description="可选的首条消息。")
        auto_shutdown: bool = Field(default=False, description="完成任务后是否自动关闭。")

    def display(self, inp: dict) -> str:
        name = inp.get("name", "")
        prompt = inp.get("prompt", "")
        auto_shutdown = inp.get("auto_shutdown", False)
        suffix = " [auto_shutdown]" if auto_shutdown else ""
        if not prompt:
            return f"{name}{suffix}"
        truncated = prompt[:60] + "…" if len(prompt) > 60 else prompt
        return f"{name}{suffix}: {truncated}"

    def execute(self, name: str, prompt: str | None = None, auto_shutdown: bool = False) -> str:
        from agent import Agent  # 延迟导入，避免循环依赖

        Agent.spawn(name, prompt, auto_shutdown)
        return f"已创建 '{name}'"
