import threading

# 线程局部变量：存储当前线程运行的 agent 名
_current_agent = threading.local()

MAIN_AGENT_NAME = "main"
USER_AGENT_NAME = "user"


def current_agent() -> str:
    return getattr(_current_agent, "name", "user")


def set_current_agent(name: str) -> None:
    _current_agent.name = name


def is_user_agent(name: str) -> bool:
    return name == USER_AGENT_NAME


def get_tool(name: str):
    from tools import TOOLS
    return TOOLS[name]


def get_tool_schemas() -> list:
    from tools import TOOLS
    return [t.schema() for t in TOOLS.values() if t.exposed]


def skills_section() -> str:
    """返回可注入 system prompt 的 skill 列表，无 skill 时返回空字符串。"""
    from tools.core.skill import list_skills_with_desc
    skills = list_skills_with_desc()
    if not skills:
        return ""
    lines = ["## 可用 Skills\n"]
    for name, desc in skills:
        lines.append(f"- `{name}`：{desc}" if desc else f"- `{name}`")
    return "\n".join(lines)
