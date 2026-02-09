Found the bug! The client logs say:
`DEBUG: Running flag is False, exiting loop`

This means the **"Engine Start" switch was never turned on**.
In the code, the variable `self.running` defaults to `False`, and I forgot to set it to `True` when you click "Connect". So the client connects, logs in, checks the engine status ("Oh, it's off"), and immediately disconnects.

## The Fix
I will modify `client.py` to turn on the "engine" (`self.running = True`) as soon as you click the Connect button.

## Action
1.  **Modify `client.py`**.
2.  **You verify**: Rerun the client on Mac. This time it will stay connected!
