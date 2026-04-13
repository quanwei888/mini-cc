from __future__ import annotations

import sys
import threading
from contextlib import contextmanager
from io import StringIO
from typing import Literal

from prompt_toolkit import PromptSession, print_formatted_text
from prompt_toolkit.formatted_text import ANSI, FormattedText, merge_formatted_text
from prompt_toolkit.patch_stdout import patch_stdout as _patch_stdout
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown

import runtime

_MAX_CONTENT_LINES = 3
_LINE_SPACING = 1  # 每条输出后额外空行数，0 = 不加
_STYLE = Style.from_dict({
    "prompt":                        "#fb923c bold",
    "bottom-toolbar":                "#555555 noreverse",
    "bottom-toolbar toolbar-name":   "bold #94a3b8",
    "bottom-toolbar toolbar-sep":    "#4b5563",
    "bottom-toolbar toolbar-tool":   "#fb923c",
    "bottom-toolbar toolbar-idle":   "#6b7280",
})

_session: PromptSession | None = None


def _render_markdown(text: str, style: str = "") -> str:
    sio = StringIO()
    console = Console(file=sio, highlight=False, force_terminal=True)
    if style:
        console.print(Markdown(text), style=style)
    else:
        console.print(Markdown(text))
    return sio.getvalue().rstrip()


_COLORS = {
    "llm":    "#f8fafc",
    "tool":   "#22c55e",
    "warn":   "#f59e0b",
    "result": "ansibrightblack",
    "error":  "#f87171",
}


_output_lock = threading.Lock()
_last_speaker: str = ""


def _print(*parts: tuple[str, str]) -> None:
    print_formatted_text(FormattedText(list(parts)))


def _print_tree(text: str, color: str) -> None:
    """└ 前缀的树状结果块。"""
    rows = str(text).splitlines()
    styled: list[tuple[str, str]] = []
    for i, line in enumerate(rows[:_MAX_CONTENT_LINES]):
        styled.append((color, ("└  " if i == 0 else "   ") + line + "\n"))
    remaining = len(rows) - _MAX_CONTENT_LINES
    if remaining > 0:
        styled.append((color, f"   … {remaining} more lines\n"))
    if styled:
        print_formatted_text(FormattedText(styled))


def output(
    title: str = "",
    content: str | None = None,
    bullet: Literal["llm", "tool", "warn", "result", "error"] | None = None,
) -> None:
    global _last_speaker
    t = (title or "").strip()
    if not t and not content:
        return

    with _output_lock:
        current = runtime.current_agent()

        # 发言者切换时加一个空行分隔
        if _last_speaker and _last_speaker != current:
            print()
        _last_speaker = current

        # result / error → 树状块
        if bullet in ("result", "error"):
            _print_tree(content or t, _COLORS[bullet])
            return

        # 子 agent 名（主 agent 不显示）
        sender_tag = ("#94a3b8", f"[{current}] ") if not runtime.is_user_agent(current) and current != runtime.MAIN_AGENT_NAME else None

        # 圆点行
        if t:
            dot_color = _COLORS.get(bullet)
            if dot_color:
                if bullet in ("tool", "warn"):
                    parts: list[tuple[str, str]] = [(dot_color, "● ")]
                    if sender_tag:
                        parts.append(sender_tag)
                    text_color = "#f59e0b" if bullet == "warn" else ""
                    parts.append((text_color, t))
                    _print(*parts)
                else:
                    prefix = FormattedText([(dot_color, "● ")] + ([sender_tag] if sender_tag else []))
                    print_formatted_text(merge_formatted_text([prefix, ANSI(_render_markdown(t))]))
            else:
                prefix = FormattedText([sender_tag] if sender_tag else [])
                print_formatted_text(merge_formatted_text([prefix, ANSI(_render_markdown(t))]))

        # content（灰色 Markdown）
        if content:
            rows = str(content).splitlines()
            preview = "\n".join(rows[:_MAX_CONTENT_LINES])
            if len(rows) > _MAX_CONTENT_LINES:
                preview += f"\n\n*… {len(rows) - _MAX_CONTENT_LINES} more lines*"
            print_formatted_text(ANSI(_render_markdown(preview, style="dim")))

        if _LINE_SPACING:
            print("\n" * (_LINE_SPACING - 1))


def banner() -> None:
    import os
    import shutil
    from tools.agent.llm import MODEL

    cwd = os.getcwd()
    bot = "#fb923c"
    dim = "ansibrightblack"
    line = "─" * shutil.get_terminal_size().columns

    print_formatted_text(FormattedText([
        ("", "\n"),
        (bot, "  ╔═════╗  "), ("bold #f8fafc", "mini-cc\n"),
        (bot, "  ║ ◉ ◉ ║  "), (dim, f"{MODEL}\n"),
        (bot, "  ╚══╤══╝  "), (dim, f"{cwd}\n"),
        (bot, "     │     "), (dim, "Ctrl+C 打断  ·  Ctrl+D 退出\n"),
        ("", "\n"),
        (dim, f"{line}\n"),
    ]))


_AGENT_COLORS = [
    "#60a5fa", "#34d399", "#f472b6", "#a78bfa",
    "#fb923c", "#38bdf8", "#4ade80", "#f87171",
]

def _agent_color(name: str) -> str:
    return _AGENT_COLORS[sum(ord(c) for c in name) % len(_AGENT_COLORS)]


def _toolbar() -> FormattedText:
    from agent import Agent
    n = len(Agent.registry)
    if not n:
        return FormattedText([])
    import shutil
    line = "─" * shutil.get_terminal_size().columns
    parts: list[tuple[str, str]] = [
        ("class:toolbar-sep", f"{line}\n"),
        ("class:toolbar-tool", f" {n} agent"),
        ("class:toolbar-sep", "  │  "),
    ]
    for name, agent in Agent.registry.items():
        status = agent.status
        active = status not in ("idle", "starting")
        parts.append((_agent_color(name), name))
        parts.append(("class:toolbar-tool" if active else "class:toolbar-idle", f":{status}"))
        parts.append(("class:toolbar-sep", "  ·  "))
    parts.pop()  # 去掉最后一个多余的分隔符
    if n == 1:
        parts.append(("class:toolbar-sep", "  │  "))
        parts.append(("class:toolbar-idle", "Ctrl+C 打断  ·  Ctrl+D 退出"))
    return FormattedText(parts)


def echo_user(text: str) -> None:
    print_formatted_text(FormattedText([("#22c55e", f" {text}")]))
    print()


def read_input() -> str:
    global _session
    if _session is None:
        _session = PromptSession(style=_STYLE)
    result = _session.prompt(
        FormattedText([("class:prompt", "> ")]),
        bottom_toolbar=_toolbar,
    )
    # 清掉 prompt_toolkit 留在屏幕上的那一行（绕过 patch_stdout）
    sys.__stdout__.write("\033[1A\033[2K\r")
    sys.__stdout__.flush()
    return result


@contextmanager
def patch_stdout():
    with _patch_stdout():
        yield
