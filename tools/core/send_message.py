from typing import Literal

from pydantic import BaseModel, Field

from runtime import current_agent

from ..base import Tool


class SendMessage(Tool):
    name = "SendMessage"
    description = (
        "给某个 agent 发消息。`type='text'`（默认）是普通对话消息。"
        "`type='shutdown'` 请求目标 agent 在处理完队列中排在它前面的"
        "消息后停止。触发即返回，不等待。"
    )

    class Input(BaseModel):
        to: str = Field(description="目标 agent 的名字。")
        content: str = Field(description="消息内容。")
        type: Literal["text", "shutdown"] = Field(default="text", description="消息类型，默认为 'text'。")

    def display(self, inp: dict) -> str:
        return inp.get("to", "")

    def execute(self, to: str, content: str, type: str = "text") -> str:
        from agent import Agent  # 延迟导入，避免循环依赖

        if to not in Agent.registry:
            raise ValueError(f"没有名为 '{to}' 的 agent")

        Agent.registry[to].inbox.put({"from": current_agent(), "type": type, "content": content})
        return f"已发送 ({type}) 到 '{to}'"
