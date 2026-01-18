# 🚂 LoCo Documentation Index

Welcome! This directory contains comprehensive documentation for **LoCo** (LLM Coding), an open-source TUI-based AI coding assistant.

## 📚 Documentation Files

### 1. [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md) (14KB)
**Deep Technical Analysis**

A comprehensive technical deep-dive into LoCo's architecture, design patterns, and implementation details.

**Contents:**
- Project overview and statistics
- Architecture breakdown and component analysis
- Feature deep dive (Tools, Skills, Agents, Hooks)
- Code quality assessment
- Design patterns used
- Comparison with alternatives (Claude Code, Cursor, Aider)
- Future enhancement ideas
- Learning points for developers

**Best for:** Developers who want to understand how LoCo works internally, contribute to the project, or learn about building LLM-powered TUI applications.

---

### 2. [QUICK_START_DEMO.md](./QUICK_START_DEMO.md) (8.8KB)
**Practical Usage Guide**

A hands-on guide with examples, workflows, and best practices for using LoCo effectively.

**Contents:**
- Installation and initial setup
- Configuration examples
- 7 example workflows:
  - Understanding codebases
  - Making code changes
  - Using skills for code review
  - Using agents for exploration
  - Complex multi-step tasks
  - Hook automation
  - Session management
- Slash commands reference
- Tips & tricks
- Troubleshooting

**Best for:** Users who want to get started quickly, learn effective usage patterns, or find solutions to common problems.

---

### 3. [TOOL_FLOW.md](./TOOL_FLOW.md) (29KB)
**Visual Architecture & Flow Diagrams**

Detailed visual representations of how LoCo processes requests and executes tools.

**Contents:**
- High-level architecture diagram
- Request flow charts
- Tool execution sequences
- Multi-tool interaction examples
- Skill system integration
- Agent system flow
- Hook system execution
- Streaming response flow
- Session persistence
- Complete user journey walkthrough

**Best for:** Visual learners, architects, and anyone who wants to understand the data flow and interaction patterns in LoCo.

---

## 🎯 Quick Navigation

### For New Users
1. Start with [README.md](./README.md) for project overview
2. Follow [QUICK_START_DEMO.md](./QUICK_START_DEMO.md) for hands-on examples
3. Reference [TOOL_FLOW.md](./TOOL_FLOW.md) to understand how things work

### For Developers
1. Read [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md) for technical details
2. Study [TOOL_FLOW.md](./TOOL_FLOW.md) for architecture insights
3. Check [examples/](./examples/) for skills, agents, and hooks

### For Contributors
1. Understand architecture from [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md)
2. Review design patterns in [TOOL_FLOW.md](./TOOL_FLOW.md)
3. Follow coding patterns from existing code

---

## 📖 Documentation by Topic

### Getting Started
- **Installation**: [QUICK_START_DEMO.md](./QUICK_START_DEMO.md#installation)
- **Configuration**: [QUICK_START_DEMO.md](./QUICK_START_DEMO.md#initial-setup)
- **First Run**: [QUICK_START_DEMO.md](./QUICK_START_DEMO.md#basic-usage)

### Core Features
- **Tools**: [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md#1-tool-system)
- **Skills**: [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md#2-skills-system)
- **Agents**: [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md#3-agent-system)
- **Hooks**: [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md#4-hooks-system)
- **Sessions**: [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md#5-session-management)

### Architecture
- **High-Level Design**: [TOOL_FLOW.md](./TOOL_FLOW.md#high-level-architecture)
- **Request Flow**: [TOOL_FLOW.md](./TOOL_FLOW.md#detailed-request-flow)
- **Tool Execution**: [TOOL_FLOW.md](./TOOL_FLOW.md#3-tool-execution-flow)
- **Design Patterns**: [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md#design-patterns)

### Usage Examples
- **Basic Workflows**: [QUICK_START_DEMO.md](./QUICK_START_DEMO.md#example-workflows)
- **Skills Usage**: [QUICK_START_DEMO.md](./QUICK_START_DEMO.md#3-using-skills-for-code-review)
- **Agent Usage**: [QUICK_START_DEMO.md](./QUICK_START_DEMO.md#4-using-agents-for-exploration)
- **Tips & Tricks**: [QUICK_START_DEMO.md](./QUICK_START_DEMO.md#tips--tricks)

### Advanced Topics
- **Custom Skills**: [examples/skills/](./examples/skills/)
- **Custom Agents**: [examples/agents/](./examples/agents/)
- **Hook Examples**: [examples/hooks/](./examples/hooks/)
- **Configuration**: [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md#-configuration-system)

---

## 🎓 Learning Path

### Beginner (0-1 hour)
1. Read [README.md](./README.md) (5 min)
2. Follow installation in [QUICK_START_DEMO.md](./QUICK_START_DEMO.md) (10 min)
3. Try basic workflows (30 min)
4. Explore slash commands (15 min)

### Intermediate (1-3 hours)
1. Read [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md) feature sections (30 min)
2. Practice with skills and agents (1 hour)
3. Set up hooks for your workflow (30 min)
4. Experiment with different models (30 min)

### Advanced (3+ hours)
1. Study full [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md) (1 hour)
2. Review [TOOL_FLOW.md](./TOOL_FLOW.md) (1 hour)
3. Read source code with insights from docs (2+ hours)
4. Create custom skills/agents (2+ hours)

---

## 🔍 Search Topics

### Common Questions

**Q: How do I switch models?**  
→ [QUICK_START_DEMO.md](./QUICK_START_DEMO.md#3-switch-models-for-different-tasks)

**Q: What's the difference between skills and agents?**  
→ [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md#2-skills-system) vs [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md#3-agent-system)

**Q: How do hooks work?**  
→ [TOOL_FLOW.md](./TOOL_FLOW.md#hook-system-execution)

**Q: Can I use local models?**  
→ [QUICK_START_DEMO.md](./QUICK_START_DEMO.md#4-use-local-models-for-privacy)

**Q: How do I save my work?**  
→ [QUICK_START_DEMO.md](./QUICK_START_DEMO.md#7-session-management)

**Q: How does streaming work?**  
→ [TOOL_FLOW.md](./TOOL_FLOW.md#streaming-response-flow)

**Q: What providers are supported?**  
→ [LOCO_ANALYSIS.md](./LOCO_ANALYSIS.md#-supported-providers)

---

## 📊 Documentation Stats

```
Total Files: 3
Total Size:  ~52KB
Total Lines: 1,393 lines

LOCO_ANALYSIS.md:   453 lines (technical deep-dive)
QUICK_START_DEMO.md: 438 lines (practical guide)
TOOL_FLOW.md:       502 lines (visual diagrams)
```

---

## 🤝 Contributing

Found an error or want to improve the docs?

1. Check the relevant documentation file
2. Make your changes
3. Submit a PR with clear descriptions
4. Follow existing formatting style

**Documentation Style Guide:**
- Use clear, concise language
- Include code examples
- Add visual diagrams where helpful
- Keep consistent formatting
- Link between documents

---

## 🔗 External Resources

### LoCo Project
- **Repository**: https://github.com/showdownlabs/loco
- **Issues**: https://github.com/showdownlabs/loco/issues
- **License**: MIT

### Dependencies
- **LiteLLM**: https://docs.litellm.ai/docs/providers
- **Rich**: https://rich.readthedocs.io/
- **Prompt Toolkit**: https://python-prompt-toolkit.readthedocs.io/
- **Click**: https://click.palletsprojects.com/
- **Pydantic**: https://docs.pydantic.dev/

### Related Tools
- **Aider**: https://aider.chat/
- **Claude Code**: https://claude.ai/
- **Cursor**: https://cursor.sh/

---

## 📝 License

All documentation is provided under the MIT License, same as the LoCo project.

---

## ✨ Credits

Documentation created by the LoCo development team and community contributors.

**Current Documentation Version**: 1.0  
**Last Updated**: January 2025  
**LoCo Version**: 0.1.0

---

**Happy coding with LoCo! 🚂**

For questions or feedback, please open an issue on GitHub.
