The coordinate mismatch is caused by **Windows Display Scaling (DPI)**.
For example, if your screen is set to 150% scaling:
-   The server captures the **True 4K/1080p Image** (e.g., 1920 pixels).
-   But the mouse control (`pyautogui`) thinks the screen is **Smaller** (e.g., 1280 points).
-   When you click at 1920 (Right edge), the mouse moves to 1920, which is "Off Screen" or way past the 1280 limit.

## The Fix
I need to teach the server to "translate" the coordinates.
1.  **Calculate Ratio**: Compare the "Image Size" vs. "Mouse System Size".
2.  **Apply Correction**: When you click, shrink the coordinates by that ratio.

## Action
Update `server.py` to automatically detect and apply this scaling factor.
