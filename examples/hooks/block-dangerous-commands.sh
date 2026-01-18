#!/bin/bash
# PreToolUse hook: Block potentially dangerous bash commands
#
# Add to config.json:
# {
#   "hooks": {
#     "PreToolUse": [
#       {
#         "matcher": "bash",
#         "hooks": [
#           { "type": "command", "command": "/path/to/block-dangerous-commands.sh" }
#         ]
#       }
#     ]
#   }
# }

# Read JSON input from stdin
INPUT=$(cat)

# Extract the command from tool input
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$COMMAND" ]; then
    exit 0  # No command, allow
fi

# List of dangerous patterns to block
DANGEROUS_PATTERNS=(
    "rm -rf /"
    "rm -rf /*"
    "rm -rf ~"
    "> /dev/sda"
    "mkfs."
    "dd if="
    ":(){:|:&};:"  # Fork bomb
    "chmod -R 777 /"
    "curl.*|.*sh"  # Piping curl to shell
    "wget.*|.*sh"
)

# Check for dangerous patterns
for pattern in "${DANGEROUS_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qiE "$pattern"; then
        echo "{\"decision\": \"deny\", \"reason\": \"Command matches dangerous pattern: $pattern\"}"
        exit 0
    fi
done

# Check for sudo with dangerous commands
if echo "$COMMAND" | grep -qE "^sudo.*rm|^sudo.*dd|^sudo.*mkfs"; then
    echo "{\"decision\": \"deny\", \"reason\": \"Blocked sudo with dangerous command\"}"
    exit 0
fi

# Allow the command
exit 0
