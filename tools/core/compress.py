from ..base import Tool


class Compress(Tool):
    """
    压缩 agent 对话历史，原地截断传入的 messages 列表。
    exposed=False：由 agent 主动触发，不暴露给 LLM。
    """
    name = "Compress"
    exposed = False
    description = ""
    input_schema = {}

    def execute(self, messages: list, keep: int) -> int:
        """截断 messages，保留最后 keep 条，返回压缩前的条数。"""
        before = len(messages)
        messages[:] = messages[-keep:]
        return before
