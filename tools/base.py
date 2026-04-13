from __future__ import annotations

from pydantic import BaseModel

TOOLS: dict[str, "Tool"] = {}


class Tool:
    name: str
    description: str
    input_schema: dict
    exposed: bool = True  # False = 不暴露给 LLM，由 agent 主动调用

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "Input") and isinstance(cls.Input, type) and issubclass(cls.Input, BaseModel):
            s = cls.Input.model_json_schema()
            cls.input_schema = {
                "type": "object",
                "properties": s.get("properties", {}),
                "required": s.get("required", []),
            }
        if hasattr(cls, "name"):
            TOOLS[cls.name] = cls()

    def display(self, inp: dict) -> str:
        values = list(inp.values())
        return str(values[0]) if values else ""

    def execute(self, **kwargs) -> str:
        raise NotImplementedError

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
