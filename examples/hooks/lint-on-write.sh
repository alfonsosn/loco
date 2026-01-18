#!/bin/bash
# PostToolUse hook: Run linter after Write or Edit and report issues
#
# Add to config.json:
# {
#   "hooks": {
#     "PostToolUse": [
#       {
#         "matcher": "write|edit",
#         "hooks": [
#           { "type": "command", "command": "/path/to/lint-on-write.sh" }
#         ]
#       }
#     ]
#   }
# }

# Read JSON input from stdin
INPUT=$(cat)

# Extract file path from tool input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Determine linter based on extension
EXT="${FILE_PATH##*.}"
LINT_OUTPUT=""

case "$EXT" in
    py)
        if command -v ruff &> /dev/null; then
            LINT_OUTPUT=$(ruff check "$FILE_PATH" 2>&1)
        elif command -v flake8 &> /dev/null; then
            LINT_OUTPUT=$(flake8 "$FILE_PATH" 2>&1)
        elif command -v pylint &> /dev/null; then
            LINT_OUTPUT=$(pylint "$FILE_PATH" --output-format=text 2>&1 | head -20)
        fi
        ;;
    js|ts|jsx|tsx)
        if command -v eslint &> /dev/null; then
            LINT_OUTPUT=$(eslint "$FILE_PATH" 2>&1)
        fi
        ;;
    rb)
        if command -v rubocop &> /dev/null; then
            LINT_OUTPUT=$(rubocop "$FILE_PATH" --format simple 2>&1)
        fi
        ;;
    go)
        if command -v golint &> /dev/null; then
            LINT_OUTPUT=$(golint "$FILE_PATH" 2>&1)
        fi
        ;;
esac

# If there's lint output, include it as additional context
if [ -n "$LINT_OUTPUT" ]; then
    # Escape for JSON
    ESCAPED_OUTPUT=$(echo "$LINT_OUTPUT" | head -20 | jq -Rs .)
    echo "{\"additional_context\": \"[Lint output]:\\n$LINT_OUTPUT\"}"
fi

exit 0
