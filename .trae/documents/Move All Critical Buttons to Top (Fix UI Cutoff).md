The issue is likely due to **Windows Display Scaling** (e.g., 125% or 150% zoom), which makes all elements larger than on Mac, pushing the bottom content out of view.

## Solution
Instead of fighting with window sizes, I will **move all critical buttons to the top**.
1.  **Move "Firewall Fix" Button to the Top**: I'll place it right below the "Start Service" button.
2.  **Benefit**: Even if the bottom half of the window is cut off, you will still have access to **Start**, **Stop**, and **Firewall Fix** without needing to scroll or resize.

## Execution
1.  **Stop** server.
2.  **Modify `server.py`**: Move the firewall button to the header section.
3.  **Restart**: You will see both buttons at the very top.
