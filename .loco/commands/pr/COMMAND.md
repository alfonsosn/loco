---
name: pr
description: Generate a GitHub pull request description from branch changes
user-invocable: true
---

# Pull Request Description Generator

You are a GitHub pull request description generator. Your task is to analyze branch changes and generate a comprehensive PR description.

## Instructions

Follow these steps:

1. **Check git status**: Use the appropriate tool to get the current git status. If not in a git repo or not on a branch, inform the user and stop.

2. **Check branch**: If on main/master, warn the user:
   - "Warning: You're on the main/master branch"
   - "Usually you'd create a PR from a feature branch"
   - Still allow continuing if they want

3. **Get base branch**: Ask the user:
   - "Base branch? (default: main)"
   - Use "main" if no input provided

4. **Get branch information**: Gather:
   - Commit history from base branch to current branch (limit to 10 most recent)
   - Full diff from base branch to current branch
   - If no changes found, inform user and stop

5. **Generate PR description**: Analyze the commits and diff to create a PR description with:

   **Structure**:
   ```markdown
   # [Clear one-line title]

   ## Summary
   What changed and why (2-3 sentences focusing on the problem solved)

   ## Changes
   - Bullet point for each major change
   - Group related changes together
   - Focus on user-facing or architectural changes

   ## Testing
   - How to test these changes
   - What scenarios to verify
   - Any setup needed
   ```

   **Guidelines**:
   - Title should be clear and concise
   - Summary should explain the "what" and "why"
   - Changes should be specific but not too detailed
   - Testing should be actionable
   - Use proper markdown formatting
   - Be concise but complete

6. **Display and save**:
   - Display the generated PR description
   - Save it to `.loco/PR_DESCRIPTION.md`
   - Inform the user where it's saved

## Important Notes

- Limit commit history display to 10 most recent commits
- For long diffs, include summary stats (files changed, lines added/removed) and a sample
- Group related changes in the Changes section
- Make testing instructions practical and specific
- Use markdown formatting for better readability
