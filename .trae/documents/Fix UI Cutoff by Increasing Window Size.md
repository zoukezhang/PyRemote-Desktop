The user reports that the **top part of the UI is fixed** (Start button is visible), but the **bottom part is cut off** ("下面显示不全"). This is likely because the window height is fixed at `650` pixels, but the content (especially with the new top button and PgyVPN field) now requires more vertical space.

## Solution
1.  **Increase Window Height**: Change `self.root.geometry("450x650")` to `self.root.geometry("450x750")` (or higher) to accommodate all elements.
2.  **Make Resizable**: Enable vertical resizing (`self.root.resizable(False, True)`) so the user can stretch the window if needed.

## Execution
1.  **Stop** server.
2.  **Modify `server.py`**: Increase window height and allow resizing.
3.  **Restart**: The window will be taller, showing the bottom tabs fully.
