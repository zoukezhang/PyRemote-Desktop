Yes, I see the issue. When I "modernized" the UI, I replaced the **Custom SSH Tunnel** input fields with the simpler **Ngrok** switch, thinking it would be easier. I apologize for removing a feature you were using!

I will **restore the Custom SSH Tunnel feature** immediately.

### Plan to Restore SSH Tunnel
1.  **Modify UI (`setup_ui`)**:
    *   In the "Tools" card (`self.tools_frame`), I will add a **"SSH Tunnel"** section.
    *   It will have input fields for:
        *   `SSH Host` (e.g., 49.232.x.x)
        *   `SSH Port` (e.g., 22)
        *   `SSH User` (e.g., root)
        *   `Remote Port` (e.g., 8080 - the port on the cloud server to forward to)
    *   And a **"Start Tunnel"** switch/button.
2.  **Restore Logic (`start_ssh_tunnel`)**:
    *   Implement the `subprocess` call to `ssh -R ...` again.
    *   It needs to forward local port 8080 to the remote server.

### UI Layout
I'll make it compact so it fits nicely:
*   [ Switch: Use Custom SSH Tunnel ]
*   [ Host: 1.2.3.4 ] [ Port: 22 ]
*   [ User: root ] [ Remote Port: 8080 ]
*   (Only visible/enabled when switch is ON)

Let's implement this now.
