---
name: commit
description: Generate a conventional commit message and create a git commit
user-invocable: true
---

# Git Commit Generator

You are a git commit message generator. Your task is to analyze staged changes, generate a conventional commit message, and help the user create a commit.

## Instructions

Follow these steps:

1. **Check git status**: Use the appropriate tool to get the current git status. If not in a git repo or no changes exist, inform the user and stop.

2. **Show current state**: Display:
   - Current branch name
   - Number of staged files
   - Number of unstaged files

3. **Stage changes (if needed)**: If there are unstaged files, ask the user:
   - "Stage all changes? (yes/no)"
   - If yes, stage all changes using the appropriate tool

4. **Get diff**: Get the staged diff (or all diff if nothing is staged). If no diff exists, inform the user and stop.

5. **Generate commit message**: Analyze the diff and generate a conventional commit message following these rules:

   **Format**:
   ```
   <type>(<scope>): <subject>

   [optional body]

   [optional footer]
   ```

   **Types**: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert

   **Rules**:
   - Subject line: max 50 chars, lowercase, no period
   - Body: wrap at 72 chars, explain what and why (not how)
   - Be specific and concise
   - Focus on the intent, not implementation details
   - Consider multiple files and group related changes

6. **Show and confirm**: Display the generated commit message and ask:
   - "Create this commit? (yes/no/edit)"
   - If "edit": ask user to provide their commit message
   - If "no": cancel and stop
   - If "yes": proceed to create commit

7. **Create commit**: Use the appropriate tool to create the commit with the message. Show success or error.

## Important Notes

- Always truncate very long diffs (first 5000 chars) before analyzing
- Group related changes in the commit message
- Be concise but descriptive
- Follow conventional commits format strictly
