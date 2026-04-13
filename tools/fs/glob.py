from pathlib import Path

from pydantic import BaseModel, Field

from ..base import Tool


class Glob(Tool):
    name = "Glob"
    description = (
        "按 glob 模式匹配文件。支持 '**' 递归匹配（例如 '**/*.py'）。"
        "返回匹配的文件路径，每行一个，按修改时间排序（最新的在前）。"
        "隐藏文件/目录（以 '.' 开头）会被排除。最多返回 200 条。"
    )

    class Input(BaseModel):
        pattern: str = Field(description="Glob 模式，例如 '**/*.py'。")
        path: str = Field(default=".", description="搜索起点目录，默认为 '.'。")

    def display(self, inp: dict) -> str:
        return inp.get("pattern", "")

    def execute(self, pattern: str, path: str = ".") -> str:
        base = Path(path)
        matches = [
            p for p in base.glob(pattern)
            if p.is_file() and not any(part.startswith(".") for part in p.parts)
        ]

        if not matches:
            return "（无匹配）"

        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        lines = [str(p) for p in matches[:200]]
        if len(matches) > 200:
            lines.append(f"... （已截断；共 {len(matches)} 条匹配）")
        return "\n".join(lines)
