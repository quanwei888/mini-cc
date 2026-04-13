from pydantic import BaseModel

from ..base import Tool


class ListAgents(Tool):
    name = "ListAgents"
    description = "列出当前所有运行中的 agent 及其状态。"

    class Input(BaseModel):
        pass

    def execute(self) -> str:
        from agent import Agent  # 延迟导入，避免循环依赖

        if not Agent.registry:
            return "当前没有运行中的 agent"
        lines = [f"- {name}（{a.status}）" for name, a in Agent.registry.items()]
        return "\n".join(lines)
