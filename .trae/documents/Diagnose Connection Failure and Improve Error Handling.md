The error "Connect call failed" indicates that the client successfully tried to connect to the custom port `10080`, but the connection was rejected or timed out.

This is usually caused by two things on your cloud server:
1.  **SSH Configuration**: By default, SSH tunnels only bind to `127.0.0.1` (localhost). To allow external connections, `GatewayPorts yes` must be enabled in `sshd_config`.
2.  **Firewall**: The cloud server's security group (e.g., AWS/Aliyun console) might be blocking port `10080`.

I will:
1.  **Improve Client Error Messages**: Update `client.py` to give more specific advice when connection fails (instead of the raw "ssl: default" error).
2.  **Guide You**: Provide the exact commands to fix the server-side SSH configuration.

## Execution
1.  **Update `client.py`**: Add friendly error handling for connection refusals.
2.  **Explain Fix**: Tell you how to enable `GatewayPorts` on your cloud server.
