It seems the connection is failing with `OSError: [Errno 51] Connect call failed` and `Port Closed/Filtered. Code: 35`. This strongly suggests that the **Windows Firewall** is blocking the connection on port 8080.

Even though we have a "Fix Firewall" button, it might not have worked correctly or the rule might not be active for the current network profile (Public vs Private).

## The Fix
I will provide a more robust PowerShell command to force-open the firewall port on Windows.

## Action
1.  **I will give you a PowerShell command**.
2.  **You run it on Windows**: Open PowerShell as **Administrator** and paste the command.
3.  **Retry Connection**: Once the rule is added, try connecting from the Mac again.

(No code changes needed for `client.py` or `server.py` this time, this is a system configuration issue on the Windows side.)
