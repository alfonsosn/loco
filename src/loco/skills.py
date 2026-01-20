"""Skills system for loco - reusable prompts that teach the LLM specific tasks."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from loco.config import get_config_dir


@dataclass
class Skill:
    """A skill definition loaded from a SKILL.md file."""

    name: str
    description: str
    content: str  # Full markdown content (instructions)
    allowed_tools: list[str] | None = None
    model: str | None = None
    user_invocable: bool = True
    path: Path | None = None

    def get_system_prompt_addition(self) -> str:
        """Get the content to add to system prompt when skill is active."""
        return f"""
--- SKILL: {self.name} ---
{self.content}
--- END SKILL ---
"""


@dataclass
class SkillRegistry:
    """Registry for discovering and managing skills."""

    skills: dict[str, Skill] = field(default_factory=dict)
    _discovered: bool = False

    def discover(self, project_dir: Path | None = None) -> None:
        """Discover skills from all locations.

        Locations (in precedence order, later overrides earlier):
        1. User skills: ~/.config/loco/skills/
        2. Claude Desktop skills: .claude/skills/ (for compatibility)
        3. Project skills: .loco/skills/ (highest priority)

        Note: .claude/ support enables seamless integration with Claude Desktop
        configurations. Both .claude/ and .loco/ can coexist in the same project.
        """
        self.skills.clear()

        # User skills (lowest precedence)
        user_skills_dir = get_config_dir() / "skills"
        self._load_skills_from_dir(user_skills_dir)

        # Project directory to search
        search_dir = project_dir if project_dir else Path.cwd()

        # Claude Desktop skills (middle precedence)
        claude_skills_dir = search_dir / ".claude" / "skills"
        self._load_skills_from_dir(claude_skills_dir)

        # Loco project skills (highest precedence)
        loco_skills_dir = search_dir / ".loco" / "skills"
        self._load_skills_from_dir(loco_skills_dir)

        self._discovered = True

    def _load_skills_from_dir(self, skills_dir: Path) -> None:
        """Load all skills from a directory."""
        if not skills_dir.exists():
            return

        # Skills are in subdirectories: skills/skill-name/SKILL.md
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            try:
                skill = self._parse_skill_file(skill_file)
                if skill:
                    self.skills[skill.name] = skill
            except Exception as e:
                # Log but don't fail on individual skill errors
                print(f"Warning: Failed to load skill from {skill_file}: {e}")

    def _parse_skill_file(self, path: Path) -> Skill | None:
        """Parse a SKILL.md file into a Skill object."""
        content = path.read_text()

        # Parse YAML frontmatter
        frontmatter: dict[str, Any] = {}
        body = content

        if content.startswith("---"):
            # Find the closing ---
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
            if match:
                try:
                    frontmatter = yaml.safe_load(match.group(1)) or {}
                except yaml.YAMLError:
                    frontmatter = {}
                body = match.group(2)

        # Extract required fields
        name = frontmatter.get("name", path.parent.name)
        description = frontmatter.get("description", "")

        if not description:
            # Try to extract from first paragraph
            lines = body.strip().split("\n")
            for line in lines:
                if line.strip() and not line.startswith("#"):
                    description = line.strip()
                    break

        # Parse allowed-tools
        allowed_tools = frontmatter.get("allowed-tools")
        if isinstance(allowed_tools, str):
            allowed_tools = [t.strip() for t in allowed_tools.split(",")]

        return Skill(
            name=name,
            description=description,
            content=body.strip(),
            allowed_tools=allowed_tools,
            model=frontmatter.get("model"),
            user_invocable=frontmatter.get("user-invocable", True),
            path=path,
        )

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        if not self._discovered:
            self.discover()
        return self.skills.get(name)

    def get_all(self) -> list[Skill]:
        """Get all discovered skills."""
        if not self._discovered:
            self.discover()
        return list(self.skills.values())

    def get_user_invocable(self) -> list[Skill]:
        """Get all skills that can be manually invoked."""
        return [s for s in self.get_all() if s.user_invocable]

    def get_skill_descriptions(self) -> str:
        """Get a formatted string of all skill descriptions for the LLM."""
        skills = self.get_all()
        if not skills:
            return ""

        lines = ["Available skills (use when relevant):"]
        for skill in skills:
            lines.append(f"- {skill.name}: {skill.description}")

        return "\n".join(lines)

    def match_skills(self, user_input: str, limit: int = 3) -> list[Skill]:
        """Find skills that might be relevant to the user's request.

        This is a simple keyword-based matching. For better results,
        you could use embeddings or LLM-based matching.
        """
        if not self._discovered:
            self.discover()

        user_lower = user_input.lower()
        scored_skills: list[tuple[int, Skill]] = []

        for skill in self.skills.values():
            score = 0
            desc_lower = skill.description.lower()
            name_lower = skill.name.lower()

            # Check if skill name is mentioned
            if name_lower in user_lower:
                score += 10

            # Check keyword overlap
            desc_words = set(desc_lower.split())
            user_words = set(user_lower.split())
            overlap = desc_words & user_words
            score += len(overlap)

            # Check for common task keywords
            task_keywords = {
                "review": ["review", "check", "analyze", "audit"],
                "test": ["test", "testing", "spec", "unit"],
                "debug": ["debug", "fix", "error", "bug", "issue"],
                "refactor": ["refactor", "clean", "improve", "optimize"],
                "document": ["document", "docs", "readme", "comment"],
            }

            for category, keywords in task_keywords.items():
                if any(kw in user_lower for kw in keywords):
                    if any(kw in desc_lower for kw in keywords):
                        score += 5

            if score > 0:
                scored_skills.append((score, skill))

        # Sort by score descending and return top matches
        scored_skills.sort(key=lambda x: x[0], reverse=True)
        return [skill for _, skill in scored_skills[:limit]]


# Global registry instance
skill_registry = SkillRegistry()


def get_skills_system_prompt_section() -> str:
    """Get the skills section to add to the system prompt."""
    descriptions = skill_registry.get_skill_descriptions()
    if not descriptions:
        return ""

    return f"""

{descriptions}

When a skill matches the user's request, you should follow its instructions.
"""
