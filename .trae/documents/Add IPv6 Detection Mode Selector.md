I will modify `server.py` to allow you to choose between "Active Detection" (connecting to public DNS) and "Passive Detection" (checking local interfaces) for IPv6.

## Changes
1.  **UI Update**: Add a dropdown menu next to the "IPv6" label to select the detection mode.
2.  **Logic Update**:
    - Restore the "Passive" detection method (using `socket.getaddrinfo`).
    - Keep the "Active" detection method (using `socket.connect`).
    - Bind the dropdown selection to trigger an immediate refresh of the IPv6 address.

## Execution
1.  **Stop** the running server.
2.  **Edit `server.py`**: Implement the mode selection and dual detection logic.
3.  **Restart**: You can then switch modes to see which one works best for your network.
