import logging
import threading

import tools  # noqa: F401 — 触发所有 Tool 子类定义，填充 TOOLS

import ui
from agent import Agent
from runtime import set_current_agent, get_tool

logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    set_current_agent("user")
    threading.current_thread().name = "user"

    Agent.spawn("main")

    print("\033[2J\033[H", end="", flush=True)
    with ui.patch_stdout():
        ui.banner()

        _interrupted = False
        while True:
            try:
                line = ui.read_input()
                _interrupted = False
            except EOFError:
                break
            except KeyboardInterrupt:
                if _interrupted:
                    break
                _interrupted = True
                if "main" in Agent.registry:
                    Agent.registry["main"].cancel.set()
                ui.output(title="已打断，再按 Ctrl+C 退出", bullet="warn")
                continue

            line = line.strip()
            if not line:
                continue

            ui.echo_user(line)
            get_tool("SendMessage").execute(to="main", content=line)


if __name__ == "__main__":
    main()
