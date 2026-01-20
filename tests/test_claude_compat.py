"""Test Claude Desktop compatibility - .claude/ directory support."""

import tempfile
from pathlib import Path

from loco.skills import SkillRegistry
from loco.agents import AgentRegistry


def test_skills_load_from_claude_directory():
    """Test that skills can be loaded from .claude/skills/."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # Create a skill in .claude/skills/
        claude_skills_dir = project_dir / ".claude" / "skills" / "test-skill"
        claude_skills_dir.mkdir(parents=True)
        
        skill_content = """---
name: test-skill
description: A test skill from .claude directory
user-invocable: true
---

# Test Skill
This is a test skill loaded from .claude/skills/
"""
        (claude_skills_dir / "SKILL.md").write_text(skill_content)
        
        # Discover skills
        registry = SkillRegistry()
        registry.discover(project_dir)
        
        # Verify skill was loaded
        skill = registry.get("test-skill")
        assert skill is not None
        assert skill.name == "test-skill"
        assert skill.description == "A test skill from .claude directory"
        assert ".claude/skills/" in skill.content


def test_skills_precedence_loco_over_claude():
    """Test that .loco/skills/ takes precedence over .claude/skills/."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # Create same skill in both directories
        claude_skills_dir = project_dir / ".claude" / "skills" / "test-skill"
        claude_skills_dir.mkdir(parents=True)
        (claude_skills_dir / "SKILL.md").write_text("""---
name: test-skill
description: From .claude
---
# Claude Version
""")
        
        loco_skills_dir = project_dir / ".loco" / "skills" / "test-skill"
        loco_skills_dir.mkdir(parents=True)
        (loco_skills_dir / "SKILL.md").write_text("""---
name: test-skill
description: From .loco
---
# Loco Version
""")
        
        # Discover skills
        registry = SkillRegistry()
        registry.discover(project_dir)
        
        # .loco/ should win (loaded last)
        skill = registry.get("test-skill")
        assert skill is not None
        assert skill.description == "From .loco"
        assert "Loco Version" in skill.content


def test_agents_load_from_claude_directory():
    """Test that agents can be loaded from .claude/agents/."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # Create an agent in .claude/agents/
        claude_agents_dir = project_dir / ".claude" / "agents"
        claude_agents_dir.mkdir(parents=True)
        
        agent_content = """---
name: test-agent
description: A test agent from .claude directory
tools: read, grep
---

# Test Agent
This is a test agent loaded from .claude/agents/
"""
        (claude_agents_dir / "test-agent.md").write_text(agent_content)
        
        # Discover agents
        registry = AgentRegistry()
        registry.discover(project_dir)
        
        # Verify agent was loaded
        agent = registry.get("test-agent")
        assert agent is not None
        assert agent.name == "test-agent"
        assert agent.description == "A test agent from .claude directory"
        assert ".claude/agents/" in agent.system_prompt


def test_agents_precedence_loco_over_claude():
    """Test that .loco/agents/ takes precedence over .claude/agents/."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # Create same agent in both directories
        claude_agents_dir = project_dir / ".claude" / "agents"
        claude_agents_dir.mkdir(parents=True)
        (claude_agents_dir / "test-agent.md").write_text("""---
name: test-agent
description: From .claude
---
# Claude Version
""")
        
        loco_agents_dir = project_dir / ".loco" / "agents"
        loco_agents_dir.mkdir(parents=True)
        (loco_agents_dir / "test-agent.md").write_text("""---
name: test-agent
description: From .loco
---
# Loco Version
""")
        
        # Discover agents
        registry = AgentRegistry()
        registry.discover(project_dir)
        
        # .loco/ should win (loaded last)
        agent = registry.get("test-agent")
        assert agent is not None
        assert agent.description == "From .loco"
        assert "Loco Version" in agent.system_prompt


def test_both_directories_can_coexist():
    """Test that skills/agents from both directories can coexist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        
        # Create skill in .claude/
        claude_skills_dir = project_dir / ".claude" / "skills" / "claude-skill"
        claude_skills_dir.mkdir(parents=True)
        (claude_skills_dir / "SKILL.md").write_text("""---
name: claude-skill
description: Claude skill
---
# Claude Skill
""")
        
        # Create skill in .loco/
        loco_skills_dir = project_dir / ".loco" / "skills" / "loco-skill"
        loco_skills_dir.mkdir(parents=True)
        (loco_skills_dir / "SKILL.md").write_text("""---
name: loco-skill
description: Loco skill
---
# Loco Skill
""")
        
        # Discover skills
        registry = SkillRegistry()
        registry.discover(project_dir)
        
        # Both should be loaded
        assert registry.get("claude-skill") is not None
        assert registry.get("loco-skill") is not None
        assert len(registry.get_all()) >= 2
