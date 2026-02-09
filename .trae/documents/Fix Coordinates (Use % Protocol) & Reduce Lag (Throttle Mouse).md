The user reports two distinct issues:
1.  **Coordinates still wrong**: The DPI fix didn't work or wasn't enough.
2.  **Huge Mouse Latency**: When moving the mouse, it lags significantly.
3.  **Video Latency is OK**: If mouse is still, video (clock) is synced.

**Analysis of "Huge Mouse Latency"**:
This is a HUGE clue.
-   Video is fast (low latency).
-   Mouse movement causes lag.
-   This means **sending mouse events is flooding the network or server**, choking the connection.
-   The client sends `mousemove` events *for every single pixel change*.
-   The server receives hundreds of events per second.
-   Even with `run_in_executor`, the overhead of processing these JSON messages, queuing them, and executing `pyautogui` might be too high, or the network bandwidth is consumed by upstream mouse packets (unlikely for text, but possible if RTT is high).
-   **Fix**: We MUST throttle mouse events on the client side. Only send `mousemove` every 50ms or 100ms.

**Analysis of "Coordinates Wrong"**:
-   The DPI scaling calculation `w_log / w_phy` might be wrong if `pyautogui.size()` returns the *scaled* resolution and `monitor['width']` returns the *raw* resolution (or vice versa).
-   Also, `mss` monitor `0` (All Monitors) usually has `monitor['left']` and `monitor['top']` which might be negative if there are multiple screens.
-   But we switched to Monitor 1 (Primary) in the code.
-   If `monitor 1` is 1920x1080 (scaled 150% -> 1280x720 logical).
-   `pyautogui.size()` -> (1280, 720).
-   `monitor['width']` -> 1920.
-   Scale = 1280/1920 = 0.66.
-   Client sends `x=1920` (right edge of image).
-   Server calculates `1920 * 0.66 = 1280`.
-   `pyautogui.moveTo(1280, ...)` -> Moves to right edge of logical screen.
-   This logic *seems* correct.

**Why is it still wrong?**
-   Maybe the client image scaling is wrong?
-   Client: `img_w, img_h = image.size` (This is the received JPEG size).
-   If server resized it: `img.thumbnail(self.target_res)`.
-   Say target is 1280x720. Image sent is 1280x720.
-   Client Canvas is 1920x1080 (fullscreen on Mac).
-   Client scales image up to fit canvas.
-   `scale_x = img_w / new_size[0]`.
-   Wait! `scale_x` is used to convert *Canvas Coords* to *Image Coords*.
-   Event `x` (on canvas) -> `x * scale_x` -> Coordinate on the 1280x720 image.
-   Server receives coordinate relative to 1280x720 image.
-   Server has `monitor` size (e.g. 1920x1080).
-   We need to map "1280x720 image point" to "1920x1080 screen point".
-   My previous DPI fix tried to map "Image Point" to "Logical Screen Point".
-   **BUT**, the `data['x']` received by server is relative to the *resized JPEG*.
-   We need to un-scale the JPEG resize first!

**The Chain of Coordinates:**
1.  **Real Mouse (Mac)**: `event.x` (e.g., 500) on Canvas.
2.  **Client Logic**:
    *   Image displayed size: `new_size` (e.g., 1000x562).
    *   Original JPEG size: `img_w` (e.g., 1280x720).
    *   `scale_x = 1280 / 1000 = 1.28`.
    *   `sent_x = 500 * 1.28 = 640`. (This is correct relative to the 1280x720 JPEG).
3.  **Server Logic**:
    *   Receives `x=640`.
    *   Target Res (JPEG): 1280x720.
    *   Monitor (Physical): 1920x1080.
    *   We need to scale 640 up to 1920 domain: `640 * (1920/1280) = 960`.
    *   **THEN**, we need to handle DPI.
    *   If `pyautogui` expects Logical Coords (1280x720), then `960` is wrong if scaling is 150%?
    *   Actually, `pyautogui` works in Logical Coordinates.
    *   So we need to map "JPEG Coordinate" -> "Logical Coordinate".
    *   We don't know the JPEG resize ratio on the server side easily unless we track it.
    *   **Simpler approach**: Normalize everything to 0.0-1.0 float!

**Proposed Solution (Coordinate Normalization)**:
1.  **Client**: Send `x_percent`, `y_percent` (0.0 to 1.0).
    *   `x_percent = event.x / canvas_width`? No, `event.x / new_size[0]`.
    *   Correction: `event.x` includes margins if centered?
    *   The current client uses `scale_x` which maps to Image Coords.
    *   So `x_percent = (event.x * scale_x) / img_w`.
    *   Simplifies to: `event.x / new_size[0]`. (If `event.x` is relative to image start).
    *   But `event.x` is relative to Canvas 0,0.
    *   If image is centered, we need to subtract offset!
    *   **Wait**, `client.py` uses `anchor=tk.NW` at `0,0`.
    *   So image is always at top-left.
    *   So `x_percent = event.x / new_size_w`.
2.  **Server**: Receive `x_percent`, `y_percent`.
    *   Get Logical Screen Size: `w_log, h_log = pyautogui.size()`.
    *   `target_x = x_percent * w_log`.
    *   `target_y = y_percent * h_log`.
    *   Move there.

This bypasses all resolution scaling, DPI scaling, and JPEG resizing confusion. **It just works.**

**Proposed Solution (Mouse Lag)**:
1.  **Client**: Add throttling. Only send `mousemove` if 50ms has passed since last send.

## Plan
1.  **Update `client.py`**:
    *   Implement Mouse Throttling (limit to 20-30 FPS).
    *   Change protocol to send `x_pct`, `y_pct` (floats 0-1) instead of integers.
2.  **Update `server.py`**:
    *   Update `mousemove` handler to use percentages and `pyautogui.size()`.
    *   Remove the previous DPI scaling logic (it's obsolete with percentages).

This solves both problems elegantly.
