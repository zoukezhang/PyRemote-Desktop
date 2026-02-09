The error `AttributeError: 'NoneType' object has no attribute 'call_soon_threadsafe'` confirms that `self.loop` is `None` when `send_json` is called.

Even though I added `self.loop = loop` in the previous step, it seems it might be getting cleared or not set correctly in the context where `send_json` runs, or perhaps `run_async_connect` failed and cleaned up, setting it to None?

Wait, looking at the previous turn's code change:
```python
    def run_async_connect(self):
        # ...
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loop = loop  # <--- I added this
        try:
            loop.run_until_complete(self.connect_to_server())
        except Exception as e:
            print(f"Loop error: {e}")
        finally:
            loop.close()
            # self.loop = None # I did NOT add this, but if loop closes, it's dead anyway.
```

The error happens in `send_json`:
```python
    def send_json(self, data):
        if self.ws and not self.ws.closed:
            asyncio.run_coroutine_threadsafe(self.ws.send_json(data), self.loop)
```

The traceback shows:
`File "/Users/zouyike/远程软件开发/client.py", line 400, in send_json`
`asyncio.run_coroutine_threadsafe(self.ws.send_json(data), self.loop)`
`File ... asyncio/tasks.py ... loop.call_soon_threadsafe(callback)`

If `self.loop` was `None`, `run_coroutine_threadsafe` would raise an error *before* calling `call_soon_threadsafe` inside it?
Wait, `run_coroutine_threadsafe(coro, loop)`.
If `loop` is passed as `None`, `asyncio` might not check it immediately?
Actually, `run_coroutine_threadsafe` implementation:
```python
def run_coroutine_threadsafe(coro, loop):
    if not iscoroutine(coro):
        raise TypeError('A coroutine object is required')
    future = concurrent.futures.Future()
    def callback():
        # ...
    loop.call_soon_threadsafe(callback)
    return future
```
Yes, if `loop` is `None`, `loop.call_soon_threadsafe` raises `AttributeError: 'NoneType' object has no attribute 'call_soon_threadsafe'`.

So `self.loop` IS `None`.

**Why is `self.loop` None?**
1.  Maybe `run_async_connect` hasn't reached the assignment line? (Unlikely if connection succeeded and UI switched).
2.  Maybe `connect_to_server` failed?
    The user said "只能看画面，无法点击" (Can see screen, cannot click).
    This means `connect_to_server` succeeded, `listen_loop` is running (receiving frames).
    So `run_async_connect` is currently blocked at `loop.run_until_complete(self.connect_to_server())`.

**Wait!**
`self.connect_to_server()` calls `await self.listen_loop(ws)`.
`self.listen_loop(ws)` runs forever until connection closes.
So `loop.run_until_complete` waits forever.
So `self.loop = loop` (which is BEFORE `run_until_complete`) *should* have executed.

**Let's look at the file content again.**
I might have made a mistake in *where* I inserted the line or if I actually saved it.
Or maybe `self.loop` is overwritten somewhere?
In `__init__`, `self.loop = None`.

**Let's Read the file `client.py` to be absolutely sure.**
And also, I will add a check in `send_json` to print if loop is None.

**Another possibility:**
The `on_mouse_move` event fires *before* `self.loop` is set?
No, `bind` happens in `switch_to_desktop_ui`, which happens *after* `auth_result` 'ok'.
And `auth_result` 'ok' happens inside `connect_to_server`.
And `connect_to_server` is called by `run_until_complete`.
And `self.loop = loop` is *before* `run_until_complete`.

So `self.loop` MUST be set.

**Unless...**
Is it possible `self` in `on_mouse_move` is not the same instance? No.

**Wait, I see the error log provided by user:**
`AttributeError: 'NoneType' object has no attribute 'call_soon_threadsafe'`

This confirms `self.loop` is `None`.

**Let's re-read the `client.py` file carefully.**
Maybe the previous `SearchReplace` failed silently or I messed up the indentation?
I'll read it now.

**Also, there was a connection error log in the user input:**
`aiohttp.client_exceptions.ClientConnectorError: Cannot connect to host 192.168.1.48:8080`
This was probably a failed attempt before success? Or maybe it's related?
If connection failed, `switch_to_desktop_ui` wouldn't be called, so no mouse events would fire.
So the "Can see screen" part implies a *successful* connection later.

**Hypothesis:**
Maybe `self.loop` is being reset to `None`?
I don't see where.

**Let's check `client.py` content.**
