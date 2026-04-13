import os
from pathlib import Path

from anthropic import Anthropic

from ..base import Tool


def _load_dotenv() -> None:
    env_path = Path(__file__).parents[2] / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()

MODEL      = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "16000"))
BASE_URL   = os.environ.get("ANTHROPIC_BASE_URL")  # 未设置时使用 Anthropic 官方地址

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(base_url=BASE_URL) if BASE_URL else Anthropic()
    return _client


class LLM(Tool):
    """
    将 LLM 调用本身封装为工具，统一"一切皆工具"的设计。
    exposed=False：不出现在给 LLM 的工具列表中，由 agent 主动调用。
    """
    name = "LLM"
    exposed = False
    description = ""
    input_schema = {}

    def stream(self, system: str, tool_schemas: list, messages: list):
        """返回流式上下文管理器，供 agent 主循环使用。"""
        return _get_client().messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=tool_schemas,
            messages=messages,
        )
