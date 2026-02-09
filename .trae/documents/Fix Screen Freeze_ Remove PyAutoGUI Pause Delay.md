The "Freeze on Mouse Move" is a classic performance issue. By default, the `pyautogui` library (used for controlling the mouse) pauses for **0.1 seconds** after every action to be "safe".

When you move your mouse, the client sends dozens of commands per second. If the server pauses for 0.1s for each one, it completely blocks the video stream, causing the "Freeze".

## The Fix
I will modify `server.py` to remove this safety pause (`pyautogui.PAUSE = 0`). This will make mouse movement instant and non-blocking.

## Action
1.  **Update `server.py`**: Set `pyautogui.PAUSE = 0`.
2.  **Optional**: I'll also wrap the mouse control in a thread to ensure it *never* blocks the video stream, even if the computer is slow.

You will need to update `server.py` on Windows one more time.
