I will modify `client.py` to correctly parse custom ports from the input address, instead of forcing the default `8080` port.

## Problem
Currently, the client uses `DEFAULT_PORT = 8080` and constructs the URL as `http://{host}:{DEFAULT_PORT}/ws` if it thinks it's an IP address. It doesn't check if the user already provided a port (e.g., `49.232.240.214:10080`).

## Solution
1.  **Smart Parsing**: Update the `connect_to_server` method in `client.py`.
2.  **Logic**:
    - Check if the input string contains a port (e.g., has a colon `:` after the IP/domain).
    - If a port is present, use it.
    - If no port is present, fallback to `8080` (or `80`/`443` for http/https).
    - Handle full URLs (starting with `http://` or `ws://`) by preserving them as-is.

## Execution
1.  **Edit `client.py`**: Rewrite the connection logic to support inputs like `49.232.240.214:10080`.
2.  **Restart Client**: Relaunch the client so you can connect to your server immediately.
