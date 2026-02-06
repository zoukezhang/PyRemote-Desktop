# 🚀 PyRemote Desktop Pro

An ultra-low latency, high-performance remote desktop tool written in Python. Designed for speed, security, and developer control.

![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Python](https://img.shields.io/badge/python-3.8+-green.svg)

## ✨ Key Features

*   **⚡ Ultra-Low Latency**: Optimized JPEG streaming with P2P/Direct Connect support (60FPS ready).
*   **🔒 Admin Mode**: Full control over Windows UAC prompts and Lock Screen (Secure Desktop).
*   **📂 File Transfer**: Drag-and-drop file transfer from Client to Remote Desktop.
*   **⌨️ Direct Input**: Hardware-level Scancode injection for gaming and anti-cheat compatibility.
*   **🖱️ Precision Control**: Resolution-independent coordinate mapping (DPI aware).
*   **🛠️ Smart Tools**: 
    *   One-click Firewall Fix
    *   Built-in Ngrok Tunneling support
    *   IPv6 / LAN / PgyVPN auto-detection

## 📦 Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/YOUR_USERNAME/PyRemote-Desktop.git
    cd PyRemote-Desktop
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## 🚀 Usage

### 🖥️ Server (The Computer to Control)
Run the server on the Windows machine you want to control.

```bash
python server.py
```
*   **Note**: To control the Lock Screen or UAC dialogs, click the red **"Restart as Admin"** button in the UI.

### 💻 Client (Your Controller)
Run the client on your Mac/Linux/Windows machine.

```bash
python client.py
```
*   Enter the IP address shown on the Server.
*   Enter the 6-digit access code.
*   Click **Connect**.

## ⚙️ Advanced Features

### File Transfer
1.  Connect to the remote desktop.
2.  Go to **Menu -> File -> Send File to Remote**.
3.  Select a file. It will be saved to the **Remote Desktop**.

### Quality Settings
*   **Menu -> Settings**: Adjust FPS (5/15/30/60) and Quality (Speed/Balanced/HD) in real-time.
*   **Grayscale Mode**: Enable for maximum speed on slow connections.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is open-sourced software licensed under the MIT license.
