"""Git integration for loco - smart commit messages and PR descriptions."""

import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class GitStatus:
    """Git repository status."""

    is_repo: bool
    branch: str | None = None
    staged_files: list[str] = None
    unstaged_files: list[str] = None
    untracked_files: list[str] = None
    ahead: int = 0
    behind: int = 0

    def __post_init__(self):
        if self.staged_files is None:
            self.staged_files = []
        if self.unstaged_files is None:
            self.unstaged_files = []
        if self.untracked_files is None:
            self.untracked_files = []

    def has_changes(self) -> bool:
        """Check if there are any changes to commit."""
        return bool(self.staged_files or self.unstaged_files)

    def has_staged_changes(self) -> bool:
        """Check if there are staged changes."""
        return bool(self.staged_files)


def run_git_command(args: list[str], check: bool = True) -> tuple[bool, str, str]:
    """Run a git command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=check,
        )
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr
    except FileNotFoundError:
        return False, "", "git command not found"


def is_git_repo() -> bool:
    """Check if current directory is in a git repository."""
    success, _, _ = run_git_command(["rev-parse", "--git-dir"], check=False)
    return success


def get_current_branch() -> str | None:
    """Get the current git branch name."""
    success, stdout, _ = run_git_command(["branch", "--show-current"], check=False)
    if success and stdout.strip():
        return stdout.strip()
    return None


def get_git_status() -> GitStatus:
    """Get comprehensive git status."""
    if not is_git_repo():
        return GitStatus(is_repo=False)

    branch = get_current_branch()

    # Get staged files
    success, stdout, _ = run_git_command(["diff", "--cached", "--name-only"], check=False)
    staged = stdout.strip().split("\n") if success and stdout.strip() else []

    # Get unstaged files
    success, stdout, _ = run_git_command(["diff", "--name-only"], check=False)
    unstaged = stdout.strip().split("\n") if success and stdout.strip() else []

    # Get untracked files
    success, stdout, _ = run_git_command(["ls-files", "--others", "--exclude-standard"], check=False)
    untracked = stdout.strip().split("\n") if success and stdout.strip() else []

    # Get ahead/behind info
    ahead, behind = 0, 0
    success, stdout, _ = run_git_command(["rev-list", "--left-right", "--count", "HEAD...@{u}"], check=False)
    if success and stdout.strip():
        parts = stdout.strip().split("\t")
        if len(parts) == 2:
            ahead = int(parts[0])
            behind = int(parts[1])

    return GitStatus(
        is_repo=True,
        branch=branch,
        staged_files=staged,
        unstaged_files=unstaged,
        untracked_files=untracked,
        ahead=ahead,
        behind=behind,
    )


def get_staged_diff() -> str | None:
    """Get diff of staged changes."""
    success, stdout, _ = run_git_command(["diff", "--cached"], check=False)
    if success and stdout.strip():
        return stdout
    return None


def get_unstaged_diff() -> str | None:
    """Get diff of unstaged changes."""
    success, stdout, _ = run_git_command(["diff"], check=False)
    if success and stdout.strip():
        return stdout
    return None


def get_all_diff() -> str | None:
    """Get diff of all changes (staged + unstaged)."""
    staged = get_staged_diff() or ""
    unstaged = get_unstaged_diff() or ""

    combined = ""
    if staged:
        combined += staged
    if unstaged:
        if combined:
            combined += "\n\n"
        combined += unstaged

    return combined if combined else None


def get_commit_history(base_branch: str = "main", limit: int = 50) -> list[dict[str, str]]:
    """Get commit history from base branch to HEAD."""
    # Try main, then master
    for branch in [base_branch, "master", "origin/main", "origin/master"]:
        success, stdout, _ = run_git_command(
            ["log", f"{branch}..HEAD", "--pretty=format:%H|%s|%an|%ae|%ad", f"-{limit}"],
            check=False,
        )
        if success and stdout.strip():
            commits = []
            for line in stdout.strip().split("\n"):
                parts = line.split("|", 4)
                if len(parts) >= 5:
                    commits.append({
                        "hash": parts[0],
                        "subject": parts[1],
                        "author": parts[2],
                        "email": parts[3],
                        "date": parts[4],
                    })
            return commits

    return []


def get_branch_diff(base_branch: str = "main") -> str | None:
    """Get diff from base branch to HEAD."""
    # Try main, then master
    for branch in [base_branch, "master", "origin/main", "origin/master"]:
        success, stdout, _ = run_git_command(["diff", f"{branch}...HEAD"], check=False)
        if success:
            return stdout if stdout.strip() else None

    return None


def stage_all_changes() -> bool:
    """Stage all changes (git add .)."""
    success, _, _ = run_git_command(["add", "."], check=False)
    return success


def create_commit(message: str, allow_empty: bool = False) -> tuple[bool, str]:
    """Create a git commit with the given message."""
    args = ["commit", "-m", message]
    if allow_empty:
        args.append("--allow-empty")

    success, stdout, stderr = run_git_command(args, check=False)
    output = stdout + stderr
    return success, output


COMMIT_MESSAGE_PROMPT = """Generate a conventional commit message for these changes.

Follow the conventional commits format:
<type>(<scope>): <subject>

[optional body]

[optional footer]

Types: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert

Rules:
- Subject line: max 50 chars, lowercase, no period
- Body: wrap at 72 chars, explain what and why
- Be specific and concise
- Focus on the intent, not the implementation details

Diff:
```
{diff}
```

Generate only the commit message, no explanation."""


PR_DESCRIPTION_PROMPT = """Generate a GitHub pull request description for this branch.

Branch: {branch}
Base: {base_branch}

Commits:
{commits}

Diff summary:
{diff_summary}

Generate a PR description with:
1. A clear title (one line summary)
2. ## Summary section - what and why
3. ## Changes section - bullet points of key changes
4. ## Testing section - how to test/verify

Use markdown formatting. Be concise but complete."""


def generate_commit_message_prompt(diff: str) -> str:
    """Generate the prompt for commit message generation."""
    # Truncate diff if too long (keep first 5000 chars)
    if len(diff) > 5000:
        diff = diff[:5000] + "\n\n... (diff truncated)"

    return COMMIT_MESSAGE_PROMPT.format(diff=diff)


def generate_pr_description_prompt(
    branch: str,
    base_branch: str,
    commits: list[dict[str, str]],
    diff: str,
) -> str:
    """Generate the prompt for PR description generation."""
    # Format commits
    commits_text = "\n".join([
        f"- {c['subject']} ({c['hash'][:7]})"
        for c in commits[:10]  # Limit to 10 most recent
    ])

    # Summarize diff (just count files and lines)
    diff_lines = diff.split("\n")
    files_changed = len([l for l in diff_lines if l.startswith("diff --git")])
    additions = len([l for l in diff_lines if l.startswith("+")])
    deletions = len([l for l in diff_lines if l.startswith("-")])

    diff_summary = f"{files_changed} files changed, +{additions} -{deletions} lines"

    # Include a sample of the diff
    diff_sample = "\n".join(diff_lines[:100])
    if len(diff_lines) > 100:
        diff_sample += "\n... (diff truncated)"

    return PR_DESCRIPTION_PROMPT.format(
        branch=branch,
        base_branch=base_branch,
        commits=commits_text,
        diff_summary=f"{diff_summary}\n\n```\n{diff_sample}\n```",
    )
