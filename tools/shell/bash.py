import subprocess

from pydantic import BaseModel, Field

from ..base import Tool


class Bash(Tool):
    name = "Bash"
    description = (
        "通过 /bin/sh 运行一条 shell 命令。返回 stdout 和 stderr 的合并"
        "输出。60 秒后超时。退出码非零时，会在输出末尾附加退出码。"
    )

    class Input(BaseModel):
        command: str = Field(description="要运行的 shell 命令。")

    def display(self, inp: dict) -> str:
        return inp.get("command", "")

    def execute(self, command: str) -> str:
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=60,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError("命令 60 秒内未完成，已超时")

        out = result.stdout or ""
        err = result.stderr or ""
        combined = out + ("\n" if out and err else "") + err
        if result.returncode != 0:
            combined += f"\n[退出码 {result.returncode}]"
        return combined.strip() or "（无输出）"
