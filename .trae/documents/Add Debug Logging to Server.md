The "Server closed connection" error means the **Server crashed internally** when handling your connection, likely due to a hidden error that we haven't seen yet.

To fix this, I need to see **why** it's crashing. I will add **Debug Logs** to the `server.py` code.

## Plan
1.  **Modify `server.py`**: Add print statements (`print(...)`) at every critical step (Connect, Receive Message, Process Auth).
2.  **Error Catching**: Wrap the connection logic in a `try...catch` block so it prints the *actual error* instead of just closing the connection silently.
3.  **User Action**: You will update the code, restart the server, and then **tell me what the Black Console Window says** when you try to connect. It will likely print a specific error message (e.g., `NameError`, `ImportError`, etc.).

This is the fastest way to pinpoint the exact missing piece.
