The error "Unable to connect" when the IP and Port are correct (and PgyVPN shows "P2P") is almost always caused by the **Windows Firewall** on the **Server** computer blocking the connection from the new PgyVPN network.

## Solution
1.  **Client Update**: Update the error message to be more helpful (specifically mentioning Windows Firewall).
2.  **Server Update (Crucial)**: Add a **"One-Click Allow Firewall"** button to the Server UI.
    -   This button will execute a Windows command (`netsh`) to automatically open port 8080, saving you from digging into system settings.

## Execution
1.  **Stop** processes.
2.  **Update `client.py`**: Revise error messages.
3.  **Update `server.py`**: Add the firewall configuration feature.
4.  **Restart**: You (or the server side) will need to click the new "Allow Firewall" button on the Windows Server.
