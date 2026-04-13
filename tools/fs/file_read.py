from pydantic import BaseModel, Field

from ..base import Tool


class FileRead(Tool):
    name = "FileRead"
    description = "从磁盘读取文件，返回其完整内容作为字符串。"

    class Input(BaseModel):
        path: str = Field(description="文件的绝对或相对路径。")

    def display(self, inp: dict) -> str:
        return inp.get("path", "")

    def execute(self, path: str) -> str:
        with open(path, "r", errors="replace") as f:
            return f.read()
