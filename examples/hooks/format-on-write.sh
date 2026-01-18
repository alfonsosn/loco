#!/bin/bash
# PostToolUse hook: Auto-format files after Write or Edit
#
# Add to config.json:
# {
#   "hooks": {
#     "PostToolUse": [
#       {
#         "matcher": "write|edit",
#         "hooks": [
#           { "type": "command", "command": "/path/to/format-on-write.sh" }
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
    exit 0  # No file path, nothing to do
fi

# Check if file exists
if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Determine formatter based on extension
EXT="${FILE_PATH##*.}"
FORMATTED=false
MESSAGE=""

case "$EXT" in
    py)
        if command -v black &> /dev/null; then
            black -q "$FILE_PATH" 2>/dev/null && FORMATTED=true && MESSAGE="Formatted with black"
        elif command -v autopep8 &> /dev/null; then
            autopep8 -i "$FILE_PATH" 2>/dev/null && FORMATTED=true && MESSAGE="Formatted with autopep8"
        fi
        ;;
    js|ts|jsx|tsx|json)
        if command -v prettier &> /dev/null; then
            prettier --write "$FILE_PATH" 2>/dev/null && FORMATTED=true && MESSAGE="Formatted with prettier"
        fi
        ;;
    go)
        if command -v gofmt &> /dev/null; then
            gofmt -w "$FILE_PATH" 2>/dev/null && FORMATTED=true && MESSAGE="Formatted with gofmt"
        fi
        ;;
    rs)
        if command -v rustfmt &> /dev/null; then
            rustfmt "$FILE_PATH" 2>/dev/null && FORMATTED=true && MESSAGE="Formatted with rustfmt"
        fi
        ;;
esac

# Output result as JSON
if [ "$FORMATTED" = true ]; then
    echo "{\"additional_context\": \"[Hook: $MESSAGE]\"}"
fi

exit 0
