from pydantic import BaseModel, Field

from ..base import Tool


class FileEdit(Tool):
    name = "FileEdit"
    description = (
        "将文件中 `old` 的一次出现替换为 `new`。`old` 必须在文件中恰好"
        "出现一次——如果出现零次或多次，编辑会失败且不做任何修改。"
    )

    class Input(BaseModel):
        path: str = Field(description="文件路径。")
        old: str = Field(description="要查找的精确字符串，必须恰好出现一次。")
        new: str = Field(description="替换字符串。")

    def display(self, inp: dict) -> str:
        return inp.get("path", "")

    def execute(self, path: str, old: str, new: str) -> str:
        with open(path, "r") as f:
            content = f.read()

        count = content.count(old)
        if count == 0:
            raise ValueError(f"在 {path} 中没有找到 `old`")
        if count > 1:
            raise ValueError(f"`old` 在 {path} 中出现 {count} 次，必须唯一")

        with open(path, "w") as f:
            f.write(content.replace(old, new, 1))
        return f"已编辑 {path}"
