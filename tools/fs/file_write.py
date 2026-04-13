from pathlib import Path

from pydantic import BaseModel, Field

from ..base import Tool


class FileWrite(Tool):
    name = "FileWrite"
    description = "将给定内容写入文件，覆盖已有内容。如果父目录不存在会自动创建。"

    class Input(BaseModel):
        path: str = Field(description="文件路径。")
        content: str = Field(description="要写入的内容。")

    def display(self, inp: dict) -> str:
        return inp.get("path", "")

    def execute(self, path: str, content: str) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"已写入 {len(content)} 个字符到 {path}"
