# Terminal Input UX Improvements

## Summary

Updated the terminal input experience to feel more like Claude Code with improved keyboard shortcuts, visual feedback, and padding.

## Changes

### 1. **Multi-line Input Support**
- **Enter** → Submit (default, intuitive for chat)
- **Ctrl+J** → Insert newline (primary method, works in all terminals)
- **Alt+Enter** → Insert newline (alternative method)
- Pasting multi-line content now works seamlessly

### 2. **Visual Separators** 
Added horizontal lines above and below the input area for better visual clarity:
```
────────────────────────────────────
>  your message here
────────────────────────────────────
```

### 3. **Paste Detection**
Shows feedback when pasting multi-line content:
```
Pasted 5 lines
```

### 4. **Horizontal Padding**
Added 2-character padding on both sides for a cleaner look.

### 5. **Updated Welcome Message**
Now includes hint about Ctrl+J:
```
/help for commands · ctrl+j for newline · ctrl+c to exit
```

## Technical Details

**File Modified**: `src/loco/ui/console.py`

- Added custom key bindings using `prompt_toolkit.key_binding.KeyBindings`
- Set `multiline=True` to support pasting, but Enter submits via custom bindings
- Added continuation prompt (`"  "`) for visual indentation on multi-line
- Separator lines use Rich's dim styling for subtle appearance

## Testing

```bash
# Test import
python -c "from loco.ui.console import Console; print('OK')"

# Try it out
loco
# Then:
# - Type and press Enter → submits
# - Type and press Ctrl+J → adds newline
# - Type and press Alt+Enter → adds newline (alternative)
# - Paste multi-line text → shows "Pasted N lines"
```

## User Experience

Before:
- No way to add newlines (Enter always submitted)
- No visual separation between input and output
- No feedback on paste operations
- No horizontal padding

After:
- Enter submits (natural for chat interfaces)
- Ctrl+J or Alt+Enter adds newlines
- Clear visual boundaries around input
- Paste detection with feedback
- Horizontal padding for cleaner look
