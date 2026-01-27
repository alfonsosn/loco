# Terminal Input Improvements - Claude Code Style

## Changes Made

### 1. Multiline Input Support with Enter to Submit
- **Before**: `multiline=False` - Enter always submitted, no way to add newlines
- **After**: `multiline=True` with custom key bindings
  - **Enter**: Submits the input (default behavior)
  - **Ctrl+J**: Inserts a newline (primary method, works in all terminals)
  - **Alt+Enter** (or Meta+Enter): Inserts a newline (alternative)
  - **Pasting**: Multi-line content is now preserved

### 2. Horizontal Padding
Added 2-character horizontal padding for a cleaner look.

### 2. Visual Separators (Claude Code Style)
Added horizontal separator lines above and below the input area:
```
────────────────────────────────────────────────
>  [your input here]
────────────────────────────────────────────────
```

### 3. Paste Detection
When pasting multi-line content, the console now displays:
```
Pasted N lines
```
This helps users understand when paste mode was detected.

### 4. Improved Multiline Edit Mode
The `get_multiline_input()` method now has explicit instructions:
- Shows helper text: "Alt+Enter to submit, Enter for new line"
- Reverses the key bindings for explicit multi-line editing

## Key Bindings Summary

### Regular Input (`get_input`)
- **Enter**: Submit input
- **Ctrl+J**: Add newline (primary)
- **Alt+Enter**: Add newline (alternative)
- **Paste**: Automatically handles multi-line content

### Explicit Multiline Mode (`get_multiline_input`)
- **Enter**: Add newline
- **Alt+Enter**: Submit input
- Shows instruction text

## Code Changes

**File**: `src/loco/ui/console.py`

### Imports Added
```python
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition
from prompt_toolkit.application import get_app
```

### Key Binding Configuration
```python
kb = KeyBindings()

@kb.add('enter')
def _(event):
    """Enter submits the input."""
    event.current_buffer.validate_and_handle()

@kb.add('c-j')
def _(event):
    """Ctrl+J inserts a newline for multiline input."""
    event.current_buffer.insert_text('\n')

@kb.add('escape', 'enter')
def _(event):
    """Alt+Enter inserts a newline for multiline input."""
    event.current_buffer.insert_text('\n')
```

### Visual Improvements
- Top separator line before input
- Bottom separator line after input
- Paste detection with line count display
- Continuation prompt with indentation: `"  "`

## Testing

To test the changes:
```bash
cd /path/to/loco
source .venv/bin/activate
python -c "from loco.ui.console import Console; print('✓ Import successful')"
```

Or run loco and try:
1. Type a message and press Enter - should submit
2. Type a message and press Ctrl+J - should add a newline
3. Type a message and press Alt+Enter - should add a newline (alternative)
4. Paste multi-line text - should show "Pasted N lines"

## User Experience

This now feels more like Claude Code:
- Enter sends message (intuitive for chat)
- Ctrl+J or Alt+Enter for explicit multi-line
- Visual separators make input area clear
- Paste detection provides feedback
- Continuation lines are indented for clarity
- Horizontal padding for cleaner look
