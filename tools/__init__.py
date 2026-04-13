# 导入所有 Tool 子类，触发 __init_subclass__ 自动注册到 TOOLS
from .base import Tool, TOOLS  # noqa: F401

from .fs    import file_read, file_write, file_edit, glob, grep          # noqa: F401
from .shell import bash                                                   # noqa: F401
from .agent import llm, spawn_agent, send_message, skill, compress, list_agents  # noqa: F401
