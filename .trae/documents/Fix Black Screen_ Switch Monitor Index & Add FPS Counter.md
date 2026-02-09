User, the "Black Screen" usually means one of two things:
1.  **No Signal**: The server isn't sending any pictures (0 FPS).
2.  **Black Signal**: The server is sending pictures, but they are pitch black (e.g., monitor capture failed).

To distinguish these and fix it, I will:
1.  **Update `server.py`**:
    *   Switch to **Monitor 0** (All Monitors mode), which is more compatible.
    *   Add a **"Heartbeat" Log**: It will print "Sending frame..." every second so you can verify it's working.
2.  **Update `client.py`**:
    *   Add a **Frame Counter (FPS)** in the top-left corner.
    *   If it stays at **0**, we know it's a connection/server logic issue.
    *   If it changes (e.g., **15**), we know the server is capturing a black image (permission/driver issue).

## Action
I will update both files. Please apply the changes to your Windows server and Mac client.
