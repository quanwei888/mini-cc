from pathlib import Path

from ..base import Tool


def _skill_dirs() -> list[Path]:
    dirs = []
    for base in [Path.cwd() / ".claude" / "skills", Path.home() / ".claude" / "skills"]:
        if base.is_dir():
            dirs.append(base)
    return dirs



def list_skills_with_desc() -> list[tuple[str, str]]:
    """返回 [(name, description)] 列表，description 从 frontmatter 里读取。"""
    seen: dict[str, str] = {}
    for base in reversed(_skill_dirs()):
        for skill_file in sorted(base.glob("*/SKILL.md")):
            name = skill_file.parent.name
            desc = ""
            content = skill_file.read_text()
            if content.startswith("---"):
                for line in content.splitlines()[1:]:
                    if line.startswith("---"):
                        break
                    if line.startswith("description:"):
                        desc = line[len("description:"):].strip()
            seen[name] = desc
    return list(seen.items())


def _find_skill(name: str) -> Path | None:
    for base in _skill_dirs():
        candidate = base / name / "SKILL.md"
        if candidate.exists():
            return candidate
    return None


class Skill(Tool):
    name = "Skill"
    description = (
        "调用一个定义在 .claude/skills/ 或 ~/.claude/skills/ 中的 skill，"
        "返回展开后的 prompt 内容，然后按其指示执行任务。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "skill 名称（即 SKILL.md 所在目录名）",
            },
            "args": {
                "type": "string",
                "description": "传给 skill 的参数，替换模板中的 $ARGUMENTS",
            },
        },
        "required": ["name"],
    }

    def display(self, inp: dict) -> str:
        args = inp.get("args", "")
        return f"{inp['name']} {args}".strip()

    def execute(self, name: str, args: str = "") -> str:
        path = _find_skill(name)
        if path is None:
            available = [n for n, _ in list_skills_with_desc()]
            hint = f"可用 skill：{', '.join(available)}" if available else "当前无可用 skill"
            return f"未找到 skill '{name}'。{hint}"

        return path.read_text().replace("$ARGUMENTS", args).strip()
