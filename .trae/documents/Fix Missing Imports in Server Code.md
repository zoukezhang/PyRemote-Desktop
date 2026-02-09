I found the bug! The "Server closed connection" error is happening because I forgot to include some standard libraries (`json`, `base64`, `io`) in the new `server.py` code. This causes the server to crash as soon as you try to connect.

## The Fix
I will add the missing imports to `server.py`.

## Action Required
1.  **I will update `server.py`** now.
2.  **You MUST update the `server.py` on your Windows machine** again with this new code.
3.  **Restart the Server**: Close and reopen the server on Windows.
4.  **Connect**: It should work perfectly now.
