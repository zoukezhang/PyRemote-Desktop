I will convert the project to a Client-Server architecture using native Python scripts, eliminating the need for a web browser.

## 1. Create `client.py` (The Viewer)
- **Technology**: `tkinter` (Standard Python GUI) + `aiohttp` (Network) + `Pillow` (Image Processing).
- **Features**:
    - **Connection Dialog**: Ask user for the Server IP address on startup.
    - **Video Stream**: Receive and display JPEG frames from the server in a native window.
    - **Input Handling**: Capture mouse movements, clicks, and keyboard presses within the window and send them to the server.
    - **Clipboard**: Integrate native clipboard. Ctrl+C/V on the client window will sync with the server automatically (or via menu).
- **Why**: This allows you to copy `client.py` to any Mac or Windows machine, install dependencies, and run it to control the server.

## 2. Update `server.py` (The Host)
- **Optimization**: Keep the existing WebSocket logic (it's efficient) but optimize it for non-browser clients if needed.
- **Cleanup**: Remove the HTML serving parts since we are using a native client now (optional, can keep for backup).

## 3. Dependencies
- Update `requirements.txt` to ensure both Client and Server have necessary libraries (mainly `aiohttp`, `Pillow`, `mss`, `pyautogui`, `pyperclip`).

## How it will work
1.  **Server Computer**: Run `python server.py`.
2.  **Client Computer**: Run `python client.py`. Enter Server IP.
3.  **Control**: The remote screen appears in a window. You can control it just like a native app.
