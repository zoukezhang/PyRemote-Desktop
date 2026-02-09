I will fix the UI truncation issues in `client.py` and ensure the interface is responsive and fully visible.

## Problem
The "Connect" button in the client window is cut off at the bottom. This is because the window height is fixed (`300x200`) and too small for the content, especially with the padding and font sizes used.

## Solution
1.  **Increase Window Size**: Change the client login window geometry from `300x200` to `350x300`.
2.  **Use Layout Weights**: Instead of hardcoded padding that might push content off-screen, I'll ensure the main container can expand properly.
3.  **Check `server.py`**: Although the user screenshot is from the client, I'll double-check `server.py` geometry too (already increased to `450x650` in the previous step, so likely fine, but I'll verify).

## Execution
1.  **Stop** client.
2.  **Modify `client.py`**: Increase height to `300`.
3.  **Restart `client.py`**.
