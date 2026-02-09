I will localize the application interface to Chinese (Simplified) for both the Server and Client applications.

## 1. Localize `server.py` (Host)
- **Window Title**: "远程桌面服务端"
- **Labels**:
    - "Allow Remote Control" -> "允许远程控制"
    - "Device ID" -> "本机设备码"
    - "Password" -> "验证码"
    - "Internet Access (Ngrok)" -> "互联网访问 (Ngrok)"
    - "Enable Public Internet Access" -> "启用公网访问"
    - "Set Ngrok Authtoken" -> "设置 Ngrok 令牌"
    - "Status" -> "状态"
- **Buttons**:
    - "Start Service" -> "启动服务"
    - "Stop Service" -> "停止服务"
- **Messages**: Translate all success/error popups.

## 2. Localize `client.py` (Controller)
- **Window Title**: "远程桌面客户端"
- **Labels**:
    - "Connect to Partner" -> "连接伙伴"
    - "Partner ID" -> "伙伴设备码"
    - "Access Password" -> "访问验证码"
- **Buttons**:
    - "Connect" -> "连接"
    - "Connecting..." -> "连接中..."
- **Menus**:
    - "Clipboard" -> "剪贴板"
    - "Send Local Clipboard" -> "发送本地剪贴板"
    - "Get Remote Clipboard" -> "获取远程剪贴板"

## Execution
1.  **Stop** the running server.
2.  **Edit `server.py`**: Replace English strings with Chinese.
3.  **Edit `client.py`**: Replace English strings with Chinese.
4.  **Restart** to verify the UI.
