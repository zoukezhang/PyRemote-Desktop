The "Lock Screen Black/Unresponsive" issue is caused by Windows **Secure Desktop** isolation.
Even with Administrator privileges, standard applications (like our script) are often blocked from:
1.  **Capturing the Lock Screen** (Resulting in a frozen or black image).
2.  **Injecting Password Input** (Resulting in "cannot type").

Commercial software like ToDesk works because it installs a **System Service** (running as `SYSTEM` user) to bypass this. We are running as a normal User/Admin application.

### My Solution Strategy
While I cannot turn this script into a full System Service instantly (too risky/complex), I can implement **three powerful workarounds**:

1.  **Prevent Locking (Keep Awake)**: I will add code to tell Windows "Do not sleep or lock screen" while the connection is active. This prevents the problem from happening.
2.  **Direct Input Injection (Low Level)**: I will replace `pyautogui`'s keyboard typing with **DirectX Scancodes** (via `ctypes SendInput`). This is a much lower-level method that often bypasses Windows UI protection, potentially allowing you to type the password even on the lock screen.
3.  **Wake Screen**: I'll add logic to simulate a "Wake Up" action (moving mouse/pressing Shift) to verify if we can dismiss the lock curtain.

### Action Plan
1.  **Update `server.py`**:
    *   Add `prevent_system_sleep()` function.
    *   Implement `SendInput` with **Scancodes** (hardware-level key simulation) to replace `pyautogui.write`.
    *   This gives the best chance of typing the password on the login screen.
2.  **Update `client.py`**:
    *   Add a **"Send Ctrl+Alt+Del"** (Simulated) button? No, SAS is protected.
    *   Add a **"Wake / Unlock"** button that sends `Space` + `Wait` to lift the curtain.

Let's try the **Direct Input** method first. It's the most likely fix for "Cannot input password".
