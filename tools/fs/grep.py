import os
import re

from pydantic import BaseModel, Field

from ..base import Tool


class Grep(Tool):
    name = "Grep"
    description = (
        "在文件中递归搜索正则匹配。返回 `file:line:content` 格式的匹配行。"
        "跳过隐藏文件和目录（以 '.' 开头）。"
    )

    class Input(BaseModel):
        pattern: str = Field(description="Python 正则表达式。")
        path: str = Field(default=".", description="要搜索的目录或文件，默认为 '.'。")

    def display(self, inp: dict) -> str:
        path = inp.get("path", ".")
        pattern = inp.get("pattern", "")
        return f"{pattern}, {path}" if path != "." else pattern

    def execute(self, pattern: str, path: str = ".") -> str:
        try:
            rx = re.compile(pattern)
        except re.error as e:
            raise ValueError(f"正则表达式无效: {e}")

        results: list[str] = []

        def search_file(fp: str) -> None:
            try:
                with open(fp, "r", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if rx.search(line):
                            results.append(f"{fp}:{i}:{line.rstrip()}")
            except OSError:
                pass

        if os.path.isfile(path):
            search_file(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fn in files:
                    if not fn.startswith("."):
                        search_file(os.path.join(root, fn))
        else:
            raise ValueError(f"{path} 不是文件也不是目录")

        return "\n".join(results) if results else "（无匹配）"
