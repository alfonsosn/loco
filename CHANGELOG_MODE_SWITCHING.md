# Mode Switching Feature

## Summary
Implemented a visual mode switching system similar to Claude Code, where users can toggle between different input modes using `Shift+Tab`. The TUI now provides clear visual feedback about which mode is active.

## Changes Made

### 1. New Mode System (`src/loco/ui/console.py`)

#### Added `InputMode` enum:
- `CHAT`: Normal AI chat mode (cyan `>` prompt)
- `BASH`: Direct bash command execution (yellow `!` prompt)
- Extensible for future modes (PLAN, EDIT, etc.)

#### Mode Configuration:
Each mode has:
- **Symbol**: Prompt character (`>` for chat, `!` for bash)
- **Color**: Both prompt_toolkit color and Rich color
- **Hint**: Status text shown below input (e.g., "! bash mode (shift+Tab to cycle)")

#### Visual Feedback:
- **Colored separators**: In bash mode, separator lines change to yellow
- **Mode hints**: Below the input, shows current mode and how to switch
- **Dynamic prompt**: Prompt symbol and color change based on mode

### 2. Mode Cycling
- **Keyboard shortcut**: `Shift+Tab` cycles through available modes
- **Persistent**: Mode persists across inputs until changed
- **Property-based**: Uses Python properties for clean API

### 3. CLI Integration (`src/loco/cli.py`)

#### Main Loop Updates:
- `get_input()` now returns `(text, mode)` tuple
- Handles bash mode directly (no need for `!` prefix when in bash mode)
- Still supports inline `!` prefix in chat mode for backwards compatibility
- Slash commands (like `/help`) work in all modes

#### Command Line Flag:
- `--bash` / `-b` flag: Start loco in bash mode
- Updated help text to explain mode system

#### Updated Help Command:
- New "Input Modes" section explaining the feature
- Instructions on using `Shift+Tab` to cycle modes

### 4. User Experience

#### Chat Mode (`>` in cyan):
```
  ───────────────────────────────────────────────
  > How do I list files?
  ───────────────────────────────────────────────
```

#### Bash Mode (`!` in yellow):
```
  ───────────────────────────────────────────────
  ! ls -la
  ───────────────────────────────────────────────
  ! bash mode (shift+Tab to cycle)
```

### 5. Benefits

1. **Clear Visual Feedback**: Users immediately know what mode they're in
2. **Reduced Errors**: Less likely to accidentally execute bash commands as AI prompts
3. **Ergonomic**: No need to type `!` repeatedly when running multiple bash commands
4. **Extensible**: Easy to add new modes (plan mode, edit mode, etc.)
5. **Consistent with Claude Code**: Familiar UX for users of similar tools

## Testing

To test the feature:

1. Start loco: `loco`
2. Notice the cyan `>` prompt (chat mode)
3. Press `Shift+Tab` - prompt changes to yellow `!` (bash mode)
4. Type a command like `ls` - it executes directly without needing `!` prefix
5. See the mode hint below: "! bash mode (shift+Tab to cycle)"
6. Press `Shift+Tab` again to return to chat mode

Or start directly in bash mode: `loco --bash`

## Future Enhancements

The mode system is designed to support additional modes:

- **Plan Mode** (`⏸`): For step-by-step planning (like Claude Code)
- **Edit Mode** (`⏵`): For accepting/reviewing edits
- **Agent Mode**: For running sub-agents

These can be added by:
1. Adding new enum values to `InputMode`
2. Adding configuration to `MODE_CONFIG`
3. Implementing mode-specific behavior in the CLI loop
