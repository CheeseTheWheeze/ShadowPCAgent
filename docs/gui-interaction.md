# GUI interaction

## Perception stack

- **Screen capture**: capture active window or full desktop.
- **OCR**: extract text for labels, buttons, and menus.
- **UI element detection**: template matching and ML detectors.
- **Scene graph**: structured representation of detected UI elements.

## Action stack

### High-level actions

- Click by label (e.g., "Save", "Run", "OK").
- Select menu items via text.
- Input text into fields detected by label.

### Low-level actions

- Mouse movement, click, drag.
- Keyboard sequences and shortcuts.

## Reaction loop

- Event-driven hooks where supported by the OS.
- Polling fallback with short intervals for fast reaction time.
- Confirmation step after actions (detect UI state changes).

## Reliability strategies

- Retry on transient failures.
- Use alternate selectors (text → icon → coordinates).
- Cache UI maps for repeated screens.
