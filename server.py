import socket
import threading
import secrets
import string
import subprocess
import time
import json
import base64
import io
import asyncio
import tkinter as tk
import customtkinter as ctk
import os
import sys
import ctypes
from tkinter import messagebox, simpledialog, ttk
import mss
import pyautogui
import pyperclip
from aiohttp import web
from PIL import Image, ImageDraw, ImageGrab
from pyngrok import ngrok, conf

# Audio Support
try:
    import pyaudiowpatch as pyaudio
except ImportError:
    try:
        import pyaudio
    except ImportError:
        pyaudio = None
        print("DEBUG: PyAudio not found. Audio disabled.")

# --- Direct Input & Power Management Helpers ---

# Ctypes Structures for SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)
class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]

class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

def press_key_scancode(hexKeyCode):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(0, hexKeyCode, 0x0008, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def release_key_scancode(hexKeyCode):
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.ki = KeyBdInput(0, hexKeyCode, 0x0008 | 0x0002, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(1), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

# Prevent System Sleep
def prevent_system_sleep():
    try:
        # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED = 0x80000003
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000003)
        print("DEBUG: System sleep prevention enabled.")
    except Exception as e:
        print(f"DEBUG: Failed to prevent sleep: {e}")

# Map Common Keys to Scancodes (Partial)
SCANCODES = {
    'enter': 0x1C, 'esc': 0x01, 'backspace': 0x0E, 'tab': 0x0F, 'space': 0x39,
    'left': 0x4B, 'up': 0x48, 'right': 0x4D, 'down': 0x50,
    'shift': 0x2A, 'ctrl': 0x1D, 'alt': 0x38,
    'a': 0x1E, 'b': 0x30, 'c': 0x2E, 'd': 0x20, 'e': 0x12, 'f': 0x21, 'g': 0x22,
    'h': 0x23, 'i': 0x17, 'j': 0x24, 'k': 0x25, 'l': 0x26, 'm': 0x32, 'n': 0x31,
    'o': 0x18, 'p': 0x19, 'q': 0x10, 'r': 0x13, 's': 0x1F, 't': 0x14, 'u': 0x16,
    'v': 0x2F, 'w': 0x11, 'x': 0x2D, 'y': 0x15, 'z': 0x2C,
    '1': 0x02, '2': 0x03, '3': 0x04, '4': 0x05, '5': 0x06, '6': 0x07, '7': 0x08, '8': 0x09, '9': 0x0A, '0': 0x0B
}

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if __name__ == '__main__':
    # Moved to bottom of file
    pass

# Disable pyautogui fail-safe (Must be global or in class)
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# Set Theme
ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class RemoteDesktopServer:
    def __init__(self):
        self.app = web.Application()
        self.runner = None
        self.site = None
        self.clients = {} # ws -> {'authenticated': bool}
        self.password = self.generate_password()
        self.port = 8080
        self.ip = self.get_local_ip()
        self.public_url = None
        self.device_id = self.generate_device_id()
        self.signal_server_url = "http://localhost:9000" # Local simulation of public server
        self.running = False
        self.loop = None
        self.server_thread = None
        self.ngrok_token = ""
        self.use_tunnel = None # Initialized in UI (CTk variable needs root)
        
        # Coordinate Scaling
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.monitor_left = 0
        self.monitor_top = 0
        self.monitor_index = 0 # Default to Monitor 0 (or smart detect)
        self.force_full_frame = False # Flag to force a full frame update (e.g., new client)
        
        # File Transfer State
        self.receiving_file = False
        self.file_handle = None
        self.file_name = ""
        self.file_size = 0
        self.file_received = 0
        
        # SSH Tunnel Variables
        self.ssh_process = None
        
        # Audio Variables
        self.audio_p = None
        self.audio_stream = None
        self.audio_thread = None
        self.audio_running = False
        self.audio_config = {'rate': 48000, 'channels': 2}
        
        # Performance Settings (Default: Balanced)
        self.target_res = (1280, 720) # Default
        self.jpeg_quality = 30  # <--- Fix: Lower quality for speed
        self.target_fps = 30    # <--- Fix: Higher FPS target since we optimized input
        
        # Setup GUI
        self.root = ctk.CTk()
        self.root.title("远程桌面服务端 - Pro")
        self.root.geometry("500x900") # Increased height
        self.root.resizable(False, True)
        
        self.setup_ui()
        
    def setup_ui(self):
        # Create Scrollable Frame for Main Content
        self.main_scroll = ctk.CTkScrollableFrame(self.root, fg_color="transparent")
        self.main_scroll.pack(fill="both", expand=True)
        
        # 1. Hero Header (Status)
        self.header_frame = ctk.CTkFrame(self.main_scroll, corner_radius=0, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        title = ctk.CTkLabel(self.header_frame, text="远程桌面控制", font=("SF Pro Display", 24, "bold"))
        title.pack(anchor="w")
        
        self.status_dot = ctk.CTkLabel(self.header_frame, text="●", font=("Arial", 24), text_color="red")
        self.status_dot.pack(side="left")
        
        self.status_text = ctk.CTkLabel(self.header_frame, text=" 服务已停止", font=("Arial", 14), text_color="gray")
        self.status_text.pack(side="left", padx=5)

        self.btn_start = ctk.CTkSwitch(self.header_frame, text="启动服务", command=self.toggle_server, font=("Arial", 14, "bold"))
        self.btn_start.pack(side="right")
        
        # Admin Indicator / Button
        if is_admin():
            ctk.CTkLabel(self.header_frame, text="[管理员模式]", text_color="gold", font=("Arial", 12)).pack(side="right", padx=10)
        else:
            ctk.CTkButton(self.header_frame, text="重启为管理员", command=self.restart_as_admin, height=24, fg_color="#FF5555", hover_color="#CC0000").pack(side="right", padx=10)
        
        # 2. Connection Card
        self.conn_frame = ctk.CTkFrame(self.main_scroll)
        self.conn_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(self.conn_frame, text="连接信息", font=("Arial", 14, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        # IPv4
        self.create_info_row(self.conn_frame, "本机局域网 IP:", self.ip)
        
        # Device ID (New)
        self.create_info_row(self.conn_frame, "设备 ID (公网):", self.device_id)
        
        # PgyVPN
        pgy_ip = self.get_pgy_ip()
        self.pgy_val = self.create_info_row(self.conn_frame, "蒲公英虚拟 IP:", pgy_ip if pgy_ip else "未检测到")
        
        # Password
        self.pass_val = self.create_info_row(self.conn_frame, "访问验证码:", self.password, is_password=True)
        
        # Refresh Btn
        ctk.CTkButton(self.conn_frame, text="刷新验证码", command=self.refresh_password, height=24, width=100).pack(pady=10)

        # 3. Chat Card (New)
        self.chat_frame_ui = ctk.CTkFrame(self.main_scroll)
        self.chat_frame_ui.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(self.chat_frame_ui, text="在线聊天", font=("Arial", 14, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        self.chat_history = ctk.CTkTextbox(self.chat_frame_ui, height=100, state="disabled")
        self.chat_history.pack(fill="x", padx=15, pady=(0, 5))
        
        self.chat_input_frame = ctk.CTkFrame(self.chat_frame_ui, fg_color="transparent")
        self.chat_input_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        self.chat_entry = ctk.CTkEntry(self.chat_input_frame, placeholder_text="发送消息给客户端...")
        self.chat_entry.pack(side="left", fill="x", expand=True)
        self.chat_entry.bind("<Return>", lambda e: self.send_chat())
        
        self.btn_send = ctk.CTkButton(self.chat_input_frame, text="发送", width=60, command=self.send_chat)
        self.btn_send.pack(side="right", padx=(5, 0))

        # 4. Settings Card
        self.settings_frame = ctk.CTkFrame(self.main_scroll)
        self.settings_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(self.settings_frame, text="画质与性能", font=("Arial", 14, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        # Resolution
        ctk.CTkLabel(self.settings_frame, text="分辨率").pack(anchor="w", padx=15)
        self.combo_res = ctk.CTkComboBox(self.settings_frame, values=["原画", "1920x1080", "1280x720 (推荐)", "800x600"], command=self.update_settings)
        self.combo_res.set("1280x720 (推荐)")
        self.combo_res.pack(fill="x", padx=15, pady=(0, 10))
        
        # FPS
        ctk.CTkLabel(self.settings_frame, text="帧率限制").pack(anchor="w", padx=15)
        self.combo_fps = ctk.CTkComboBox(self.settings_frame, values=["30 FPS", "15 FPS (标准)", "5 FPS"], command=self.update_settings)
        self.combo_fps.set("15 FPS (标准)")
        self.combo_fps.pack(fill="x", padx=15, pady=(0, 10))
        
        # Grayscale
        self.use_grayscale = ctk.BooleanVar()
        self.chk_gray = ctk.CTkSwitch(self.settings_frame, text="黑白模式 (极速)", variable=self.use_grayscale)
        self.chk_gray.pack(anchor="w", padx=15, pady=(5, 15))

        # Signal Server
        ctk.CTkLabel(self.settings_frame, text="信令服务器 (公网/局域网 IP:端口)").pack(anchor="w", padx=15, pady=(10, 0))
        self.entry_signal_server = ctk.CTkEntry(self.settings_frame, placeholder_text="http://localhost:9000")
        self.entry_signal_server.insert(0, "http://localhost:9000")
        self.entry_signal_server.pack(fill="x", padx=15, pady=(0, 10))
        self.entry_signal_server.bind("<KeyRelease>", self.update_signal_url)

        # 4. Tools Card (Firewall & Tunnel)
        self.tools_frame = ctk.CTkFrame(self.main_scroll)
        self.tools_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(self.tools_frame, text="高级工具", font=("Arial", 16, "bold"), text_color="white").pack(anchor="w", padx=15, pady=(15, 5)) # High contrast font
        
        # Firewall
        ctk.CTkButton(self.tools_frame, text="一键放行防火墙 (修复连接失败)", command=self.fix_firewall, fg_color="transparent", border_width=1, text_color=("gray10", "gray90")).pack(fill="x", padx=15, pady=5)
        
        # Cloud Tunnel (New)
        self.use_tunnel = ctk.BooleanVar(value=True)
        self.chk_tunnel = ctk.CTkSwitch(self.tools_frame, text="启用云端隧道 (免公网IP/穿透)", variable=self.use_tunnel, font=("Arial", 12))
        self.chk_tunnel.pack(anchor="w", padx=15, pady=10)

        # Ngrok
        self.use_ngrok = ctk.BooleanVar()
        self.chk_ngrok = ctk.CTkSwitch(self.tools_frame, text="启用 Ngrok 公网穿透", variable=self.use_ngrok, font=("Arial", 12))
        self.chk_ngrok.pack(anchor="w", padx=15, pady=10)
        ctk.CTkButton(self.tools_frame, text="配置 Ngrok 令牌", command=self.set_ngrok_token, height=24).pack(fill="x", padx=15, pady=(0, 15))

        # SSH Tunnel
        ctk.CTkLabel(self.tools_frame, text="自建 SSH 隧道 (高级)", font=("Arial", 14, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        self.use_ssh = ctk.BooleanVar()
        self.chk_ssh = ctk.CTkSwitch(self.tools_frame, text="启用 SSH 转发", variable=self.use_ssh, command=self.toggle_ssh_ui, font=("Arial", 12))
        self.chk_ssh.pack(anchor="w", padx=15, pady=5)
        
        self.ssh_frame = ctk.CTkFrame(self.tools_frame, fg_color="transparent") # Transparent background
        # Don't pack immediately, toggle with switch
        
        # SSH Host
        ctk.CTkLabel(self.ssh_frame, text="服务器 IP:", font=("Arial", 12)).pack(anchor="w", padx=5)
        self.entry_ssh_host = ctk.CTkEntry(self.ssh_frame, placeholder_text="1.2.3.4")
        self.entry_ssh_host.pack(fill="x", padx=5, pady=2)
        
        # SSH User
        ctk.CTkLabel(self.ssh_frame, text="用户名:", font=("Arial", 12)).pack(anchor="w", padx=5)
        self.entry_ssh_user = ctk.CTkEntry(self.ssh_frame, placeholder_text="root")
        self.entry_ssh_user.insert(0, "root")
        self.entry_ssh_user.pack(fill="x", padx=5, pady=2)
        
        # Remote Port
        ctk.CTkLabel(self.ssh_frame, text="远程端口 (映射到本机8080):", font=("Arial", 12)).pack(anchor="w", padx=5)
        self.entry_ssh_port = ctk.CTkEntry(self.ssh_frame, placeholder_text="8080")
        self.entry_ssh_port.insert(0, "8080")
        self.entry_ssh_port.pack(fill="x", padx=5, pady=2)

        # Handle Close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Auto Start
        self.root.after(500, self.auto_start)

    def auto_start(self):
        print("DEBUG: Auto starting server...")
        self.btn_start.select()
        self.toggle_server()

    def send_chat(self):
        text = self.chat_entry.get().strip()
        if not text: return
        
        self.chat_entry.delete(0, tk.END)
        self.append_chat("我", text)
        
        # Broadcast
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.broadcast_chat(text), self.loop)

    def append_chat(self, sender, text):
        self.chat_history.configure(state="normal")
        self.chat_history.insert(tk.END, f"[{sender}]: {text}\n")
        self.chat_history.see(tk.END)
        self.chat_history.configure(state="disabled")

    async def broadcast_chat(self, text):
        msg = {'type': 'chat', 'sender': 'Server', 'message': text}
        for ws, state in self.clients.items():
            if state['authenticated']:
                try:
                    await ws.send_json(msg)
                except: pass

    def toggle_ssh_ui(self):
        if self.use_ssh.get():
            self.ssh_frame.pack(fill="x", padx=15, pady=5)
        else:
            self.ssh_frame.pack_forget()

    def restart_as_admin(self):
        try:
            script_path = os.path.abspath(sys.argv[0])
            params = f'"{script_path}"'
            if len(sys.argv) > 1:
                params += " " + " ".join([f'"{x}"' for x in sys.argv[1:]])
            
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, os.getcwd(), 1)
            self.on_close() # Close current instance
        except Exception as e:
            messagebox.showerror("提权失败", f"无法重启为管理员: {e}")

    def create_info_row(self, parent, label, value, is_password=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=2)
        ctk.CTkLabel(row, text=label, width=100, anchor="w").pack(side="left")
        
        val_label = ctk.CTkEntry(row, border_width=0, fg_color="transparent", font=("Arial", 12, "bold"))
        val_label.insert(0, value)
        val_label.configure(state="readonly")
        val_label.pack(side="right", fill="x", expand=True)
        return val_label

    def update_settings(self, choice=None):
        # Resolution
        res_str = self.combo_res.get()
        if "原画" in res_str: self.target_res = None
        elif "1920" in res_str: self.target_res = (1920, 1080)
        elif "1280" in res_str: self.target_res = (1280, 720)
        elif "800" in res_str: self.target_res = (800, 600)
            
        # FPS
        fps_str = self.combo_fps.get()
        if "30" in fps_str: self.target_fps = 30
        elif "15" in fps_str: self.target_fps = 15
        elif "5" in fps_str: self.target_fps = 5
        
        print(f"Settings Updated: Res={self.target_res}, FPS={self.target_fps}")

    def update_signal_url(self, event=None):
        self.signal_server_url = self.entry_signal_server.get().strip()
        # print(f"DEBUG: Signal Server URL updated to {self.signal_server_url}")

    def generate_password(self):
        chars = string.digits
        return ''.join(secrets.choice(chars) for _ in range(6))

    def generate_device_id(self):
        # Generate a 9-digit ID
        return ''.join(secrets.choice(string.digits) for _ in range(9))

    async def register_device_loop(self):
        """Periodically register device ID with signal server"""
        import aiohttp
        from urllib.parse import urlparse
        
        while self.running:
            try:
                # 1. Default: LAN IP
                final_ip = self.ip
                final_port = self.port
                mode = 'direct'
                
                # 2. Priority: Ngrok Public URL (if enabled)
                if self.public_url:
                    try:
                        u = urlparse(self.public_url)
                        final_ip = u.hostname
                        # Handle port (default 80/443 if not specified)
                        if u.port:
                            final_port = u.port
                        else:
                            final_port = 443 if u.scheme == 'https' else 80
                        print(f"DEBUG: Using Ngrok URL for registration: {final_ip}:{final_port}")
                    except:
                        pass
                elif self.use_tunnel.get():
                     mode = 'tunnel'
                else:
                    # 3. Fallback: PgyVPN / VPN IP detection
                    try:
                        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
                        for info in infos:
                            curr = info[4][0]
                            if curr.startswith("172.") or curr.startswith("10."):
                                final_ip = curr
                                break
                    except: pass
                
                async with aiohttp.ClientSession() as session:
                    payload = {
                        'device_id': self.device_id,
                        'port': final_port,
                        'ip': final_ip,
                        'mode': mode
                    }
                    async with session.post(f"{self.signal_server_url}/register", json=payload) as resp:
                        if resp.status == 200:
                            pass # Silent success
                        else:
                            print(f"DEBUG: Registration failed: {resp.status}")
            except Exception as e:
                print(f"DEBUG: Signal Server Error: {e}")
            
            await asyncio.sleep(30) # Heartbeat every 30s

    async def maintain_tunnel_loop(self):
        """Maintains a persistent WebSocket connection to Signal Server for Tunneling"""
        import aiohttp
        
        while self.running:
            if not self.use_tunnel.get():
                await asyncio.sleep(2)
                continue
                
            url = f"{self.signal_server_url}/device/{self.device_id}"
            print(f"DEBUG: Connecting to Tunnel: {url}")
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url) as ws:
                        print("DEBUG: Tunnel Connected")
                        self.status_dot.configure(text_color="#00FF00")
                        self.status_text.configure(text=" 云端隧道已连接", text_color="#00FF00")
                        
                        # Keep alive loop
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = msg.data
                                if data == "CLIENT_CONNECTED":
                                    print("DEBUG: Tunnel Client Connected")
                                    self.clients[ws] = {'authenticated': False}
                                    # Send initial state
                                    # await ws.send_json({'type': 'auth_req'}) # Client sends auth first
                                elif data == "CLIENT_DISCONNECTED":
                                    print("DEBUG: Tunnel Client Disconnected")
                                    if ws in self.clients:
                                        del self.clients[ws]
                                else:
                                    # Normal Command
                                    try:
                                        # Parse JSON
                                        cmd = json.loads(data)
                                        action = cmd.get('action')
                                        
                                        if action == 'auth':
                                            if cmd.get('password') == self.password:
                                                self.clients[ws]['authenticated'] = True
                                                await ws.send_json({'type': 'auth_result', 'status': 'ok'})
                                                await ws.send_json({'type': 'audio_config', 'rate': self.audio_config['rate'], 'channels': self.audio_config['channels']})
                                                await ws.send_json({'type': 'sync_time', 'server_time': time.time() * 1000})
                                                self.force_full_frame = True
                                            else:
                                                await ws.send_json({'type': 'auth_result', 'status': 'error'})
                                        elif ws in self.clients and self.clients[ws]['authenticated']:
                                            await self.process_command(ws, action, cmd)
                                            
                                    except json.JSONDecodeError:
                                        pass
                                    except Exception as e:
                                        print(f"Tunnel Cmd Error: {e}")
                                        
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                print(f"Tunnel Error: {ws.exception()}")
                                break
            except Exception as e:
                print(f"Tunnel Connection Failed: {e}")
                self.status_text.configure(text=" 隧道连接断开", text_color="orange")
            
            await asyncio.sleep(5) # Retry delay

    def refresh_password(self):
        self.password = self.generate_password()
        self.set_readonly_text(self.pass_val, self.password)

    def set_readonly_text(self, entry, text):
        entry.configure(state="normal")
        entry.delete(0, tk.END)
        entry.insert(0, text)
        entry.configure(state="readonly")

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def get_pgy_ip(self):
        try:
            # Get all IPs
            infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
            for info in infos:
                ip = info[4][0]
                # PgyVPN usually uses 172.x.x.x
                if ip.startswith("172.") and not ip.startswith("127."):
                     return f"{ip}:{self.port}"
            return None
        except:
            return None

    def set_ngrok_token(self):
        token = simpledialog.askstring("Ngrok 令牌", "请输入您的 Ngrok Authtoken:\n(在 ngrok.com 免费获取)")
        if token:
            self.ngrok_token = token
            try:
                ngrok.set_auth_token(token)
                messagebox.showinfo("成功", "Ngrok 令牌已保存！")
            except Exception as e:
                messagebox.showerror("错误", f"保存令牌失败: {e}")

    def fix_firewall(self):
        try:
            cmd = f'netsh advfirewall firewall add rule name="Allow Remote Desktop {self.port}" dir=in action=allow protocol=TCP localport={self.port}'
            ps_cmd = f"Start-Process netsh -ArgumentList 'advfirewall firewall add rule name=\"Allow Remote Desktop {self.port}\" dir=in action=allow protocol=TCP localport={self.port}' -Verb RunAs"
            subprocess.run(["powershell", "-Command", ps_cmd], shell=True)
            
            messagebox.showinfo("防火墙设置", "已尝试添加防火墙规则。\n\n请重试连接客户端。")
        except Exception as e:
            messagebox.showerror("错误", f"设置防火墙失败: {e}\n请尝试以管理员身份运行本程序。")

    def start_audio(self):
        if not pyaudio: return
        if self.audio_running: return
        
        try:
            self.audio_p = pyaudio.PyAudio()
            loopback = None
            try:
                # 1. Try PyAudioWPatch specific method
                if hasattr(self.audio_p, 'get_default_wasapi_loopback'):
                    loopback = self.audio_p.get_default_wasapi_loopback()
                else:
                    # 2. Manual search for WASAPI loopback (Fallback)
                    wasapi_info = self.audio_p.get_host_api_info_by_type(pyaudio.paWASAPI)
                    default_speakers = self.audio_p.get_default_output_device_info()
                    
                    if not default_speakers["isLoopbackDevice"]:
                        for i in range(self.audio_p.get_device_count()):
                            dev = self.audio_p.get_device_info_by_index(i)
                            if dev["hostApi"] == wasapi_info["index"] and dev["name"] == default_speakers["name"]:
                                loopback = dev
                                break
            except Exception as e:
                print(f"DEBUG: Audio Device Search Error: {e}")
                
            if not loopback:
                print("DEBUG: WASAPI Loopback not found. Audio disabled.")
                return

            print(f"DEBUG: Using Audio Device: {loopback['name']}")
            
            self.audio_config['rate'] = int(loopback['defaultSampleRate'])
            self.audio_config['channels'] = int(loopback['maxInputChannels'])
            
            self.audio_stream = self.audio_p.open(
                format=pyaudio.paInt16,
                channels=self.audio_config['channels'],
                rate=self.audio_config['rate'],
                input=True,
                input_device_index=loopback['index'],
                frames_per_buffer=1024
            )
            
            self.audio_running = True
            self.audio_thread = threading.Thread(target=self.audio_loop, daemon=True)
            self.audio_thread.start()
            print(f"DEBUG: Audio Started ({self.audio_config['rate']}Hz, {self.audio_config['channels']}ch)")
            
        except Exception as e:
            print(f"DEBUG: Audio Start Failed: {e}")
            self.stop_audio()

    def stop_audio(self):
        self.audio_running = False
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except: pass
            self.audio_stream = None
        
        if self.audio_p:
            try:
                self.audio_p.terminate()
            except: pass
            self.audio_p = None

    def audio_loop(self):
        while self.audio_running and self.audio_stream:
            try:
                data = self.audio_stream.read(1024)
                if not data: continue
                
                b64_data = base64.b64encode(data).decode('utf-8')
                msg = {'type': 'audio', 'data': b64_data}
                
                if self.loop and self.loop.is_running():
                     asyncio.run_coroutine_threadsafe(self.broadcast_audio(msg), self.loop)
                     
            except Exception as e:
                pass
    
    async def broadcast_audio(self, msg):
        # Broadcast to all auth clients
        # Copy keys to avoid size change during iteration
        for ws, state in list(self.clients.items()):
            if state.get('authenticated', False):
                try:
                    await ws.send_json(msg)
                except:
                    pass

    def toggle_server(self):
        if not self.running:
            self.start_server()
        else:
            self.stop_server()

    def start_server(self):
        self.running = True
        self.status_dot.configure(text_color="#00FF00") # Green
        self.status_text.configure(text=" 服务运行中", text_color="#00FF00")
        
        # Prevent Sleep
        prevent_system_sleep()
        
        # Windows Priority Boost
        if os.name == 'nt':
            try:
                import psutil
                p = psutil.Process(os.getpid())
                # HIGH_PRIORITY_CLASS = 0x00000080 (128)
                # REALTIME_PRIORITY_CLASS = 0x00000100 (256) - Too dangerous
                p.nice(psutil.HIGH_PRIORITY_CLASS)
                print("DEBUG: Process Priority set to HIGH")
            except Exception as e:
                print(f"DEBUG: Failed to set priority: {e}")
        
        # Start Audio
        self.start_audio()
        
        # 1. Start Tunnel if enabled
        tunnel_started = False
        
        if self.use_ngrok.get():
            if self.start_ngrok():
                tunnel_started = True
                
        if self.use_ssh.get():
            self.start_ssh_tunnel()
            tunnel_started = True
        
        # 2. Start Web Server
        self.server_thread = threading.Thread(target=self.run_async_server, daemon=True)
        self.server_thread.start()

    def start_ssh_tunnel(self):
        host = self.entry_ssh_host.get().strip()
        user = self.entry_ssh_user.get().strip()
        remote_port = self.entry_ssh_port.get().strip()
        
        if not host or not user or not remote_port:
            messagebox.showwarning("SSH 错误", "请填写完整的 SSH 信息")
            return

        print(f"DEBUG: Starting SSH Tunnel to {user}@{host}...")
        
        # Command: ssh -R remote_port:localhost:local_port user@host -N
        # -N: Do not execute a remote command (just forward)
        # -o StrictHostKeyChecking=no: Avoid prompts
        cmd = [
            "ssh",
            "-R", f"{remote_port}:127.0.0.1:{self.port}",
            f"{user}@{host}",
            "-N",
            "-o", "StrictHostKeyChecking=no"
        ]
        
        try:
            # On Windows, we need to hide the console window
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            self.ssh_process = subprocess.Popen(cmd, startupinfo=startupinfo)
            
            # Show Info
            messagebox.showinfo("SSH 隧道", f"隧道启动中...\n请在客户端输入: {host}:{remote_port}\n\n(注意：需要先配置好 SSH 免密登录)")
            
        except Exception as e:
            messagebox.showerror("SSH 错误", f"启动 SSH 失败: {e}\n请确保系统已安装 OpenSSH 客户端")

    def start_ngrok(self):
        try:
            # Close existing tunnels
            tunnels = ngrok.get_tunnels()
            for t in tunnels:
                ngrok.disconnect(t.public_url)
            
            tunnel = ngrok.connect(self.port, "http")
            self.public_url = tunnel.public_url
            display_url = self.public_url.replace("https://", "").replace("http://", "")
            # self.set_readonly_text(self.id_label, display_url) # Removed ID label in new UI, maybe add back?
            return True
        except Exception as e:
            messagebox.showerror("Ngrok 错误", f"启动隧道失败: {e}\n您设置令牌了吗？")
            return False

    def stop_server(self):
        self.running = False
        self.stop_audio()
        self.status_dot.configure(text_color="red")
        self.status_text.configure(text=" 服务已停止", text_color="gray")
        
        if self.public_url:
            try:
                ngrok.disconnect(self.public_url)
                self.public_url = None
            except:
                pass
        
        if self.ssh_process:
            self.ssh_process.terminate()
            self.ssh_process = None
        
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.shutdown_site(), self.loop)

    def run_async_server(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        self.app = web.Application()
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_static('/static', 'static')
        self.app.router.add_get('/ws', self.handle_ws)
        self.app.on_startup.append(self.on_startup)
        
        self.runner = web.AppRunner(self.app)
        self.loop.run_until_complete(self.runner.setup())
        self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        
        # Start Registration Task
        self.loop.create_task(self.register_device_loop())
        self.loop.create_task(self.maintain_tunnel_loop())
        
        try:
            self.loop.run_until_complete(self.site.start())
            print(f"DEBUG: Server started on 0.0.0.0:{self.port}")
            self.loop.run_forever()
        except Exception as e:
            print(f"Server error: {e}")

    async def handle_index(self, request):
        return web.FileResponse('./static/index.html')

    async def shutdown_site(self):
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        self.loop.stop()

    async def handle_ws(self, request):
        print(f"DEBUG: New connection request from {request.remote}")
        try:
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            
            # TCP_NODELAY optimization (Disable Nagle's Algorithm)
            # This is critical for real-time streaming to prevent packet buffering
            if ws._writer and ws._writer.transport:
                sock = ws._writer.transport.get_extra_info('socket')
                if sock:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    print("DEBUG: TCP_NODELAY Enabled")
                    
            print("DEBUG: WebSocket Handshake Successful")
            
            self.clients[ws] = {'authenticated': False}
            
            async for msg in ws:
                print(f"DEBUG: Received msg type: {msg.type}")
                if msg.type == web.WSMsgType.TEXT:
                    print(f"DEBUG: Msg content: {msg.data[:50]}...")
                    try:
                        data = json.loads(msg.data)
                        action = data.get('action')
                        print(f"DEBUG: Action: {action}")
                        
                        if action == 'auth':
                            if data.get('password') == self.password:
                                print("DEBUG: Auth Success")
                                self.clients[ws]['authenticated'] = True
                                await ws.send_json({'type': 'auth_result', 'status': 'ok'})
                                await ws.send_json({'type': 'audio_config', 'rate': self.audio_config['rate'], 'channels': self.audio_config['channels']})
                                
                                # Send Server Time for Sync
                                await ws.send_json({'type': 'sync_time', 'server_time': time.time() * 1000})
                                
                                # Force Full Frame for new client
                                self.force_full_frame = True
                            else:
                                print("DEBUG: Auth Failed")
                                await ws.send_json({'type': 'auth_result', 'status': 'error'})
                        elif action == 'ping_sync':
                             # Respond with server time for latency calc
                             client_ts = data.get('client_time', 0)
                             await ws.send_json({'type': 'pong_sync', 'client_time': client_ts, 'server_time': time.time() * 1000})
                             
                        elif self.clients[ws]['authenticated']:
                            await self.process_command(ws, action, data)
                    except Exception as e:
                        print(f"DEBUG ERROR Processing Msg: {e}")
                        import traceback
                        traceback.print_exc()
                        
                elif msg.type == web.WSMsgType.ERROR:
                    print('DEBUG: ws connection closed with exception %s', ws.exception())
        except Exception as e:
            print(f"DEBUG CRITICAL ERROR in handle_ws: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("DEBUG: Connection Closed")
            if 'ws' in locals() and ws in self.clients:
                del self.clients[ws]
        return ws

    async def process_command(self, ws, action, data):
        if action == 'update_settings':
            if 'quality' in data:
                self.jpeg_quality = int(data['quality'])
            if 'fps' in data:
                self.target_fps = int(data['fps'])
            if 'monitor' in data:
                self.monitor_index = int(data['monitor'])
                # Trigger monitor update logic if needed
            print(f"DEBUG: Settings Updated - Quality: {self.jpeg_quality}, FPS: {self.target_fps}, Monitor: {self.monitor_index}")
            
        elif action == 'file_start':
            self.start_file_receive(data)
        elif action == 'file_chunk':
            await self.process_file_chunk(data, ws)
        elif action == 'file_end':
            self.finish_file_receive(ws)
            
        elif action == 'chat':
            msg = data.get('message', '')
            self.root.after(0, lambda: self.append_chat("Client", msg))
            
        elif action == 'list_files':
            await self.send_file_list(ws)
            
        elif action == 'download_request':
            # Handle download in background task
            asyncio.create_task(self.handle_download_request(ws, data))
            
        elif action == 'request_full_frame':
            self.force_full_frame = True
            print("DEBUG: Client requested Full Frame Refresh")
            
        else:
            # Run mouse/keyboard in executor
            await self.loop.run_in_executor(None, self._process_command_sync, action, data, ws)

    async def send_file_list(self, ws):
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            files = []
            for f in os.listdir(desktop):
                path = os.path.join(desktop, f)
                if os.path.isfile(path):
                    size = os.path.getsize(path)
                    files.append({'name': f, 'size': size})
            
            await ws.send_json({'type': 'file_list', 'files': files})
        except Exception as e:
            print(f"List files error: {e}")

    async def handle_download_request(self, ws, data):
        filename = data.get('filename')
        if not filename: return
        
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        path = os.path.join(desktop, filename)
        
        if not os.path.exists(path): return
        
        try:
            size = os.path.getsize(path)
            await ws.send_json({'type': 'download_start', 'filename': filename, 'size': size})
            
            CHUNK_SIZE = 1024 * 64
            with open(path, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk: break
                    b64 = base64.b64encode(chunk).decode('utf-8')
                    await ws.send_json({'type': 'download_chunk', 'data': b64})
                    await asyncio.sleep(0.01) # Throttle
            
            await ws.send_json({'type': 'download_end', 'filename': filename})
            print(f"DEBUG: Sent file {filename}")
        except Exception as e:
            print(f"Download error: {e}")

    def start_file_receive(self, data):
        try:
            filename = data.get('filename', 'unknown_file')
            filesize = data.get('size', 0)
            
            # Save to Desktop
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            save_path = os.path.join(desktop, filename)
            
            self.file_handle = open(save_path, "wb")
            self.file_name = filename
            self.file_size = filesize
            self.file_received = 0
            self.receiving_file = True
            print(f"DEBUG: Starting file receive: {filename} ({filesize} bytes)")
        except Exception as e:
            print(f"DEBUG: Failed to start file receive: {e}")

    async def process_file_chunk(self, data, ws):
        if not self.receiving_file or not self.file_handle: return
        
        try:
            chunk_data = base64.b64decode(data['data'])
            self.file_handle.write(chunk_data)
            self.file_received += len(chunk_data)
            
            # Optional: Send progress back? (Maybe too chatty, client can track its own sending)
        except Exception as e:
            print(f"DEBUG: File write error: {e}")

    def finish_file_receive(self, ws):
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None
        self.receiving_file = False
        print(f"DEBUG: File received successfully: {self.file_name}")
        # Notify client
        asyncio.run_coroutine_threadsafe(ws.send_json({'type': 'notification', 'title': '文件传输', 'message': f'文件 {self.file_name} 已保存到桌面'}), self.loop)

    def _process_command_sync(self, action, data, ws):
        try:
            if action == 'mousemove':
                # Use Percentage Coordinates (Resolution Independent)
                if 'xp' in data and 'yp' in data:
                    # We need to map 0.0-1.0 to the CURRENT monitor's coordinates
                    # self.monitor_left/top/width/height are updated in the stream loop
                    # But stream loop runs in async thread, this runs in executor. 
                    # We should use shared variables.
                    
                    # Default to primary monitor/all if not set yet
                    ml = getattr(self, 'monitor_left', 0)
                    mt = getattr(self, 'monitor_top', 0)
                    mw = getattr(self, 'monitor_width', pyautogui.size()[0])
                    mh = getattr(self, 'monitor_height', pyautogui.size()[1])
                    
                    tx = ml + int(data['xp'] * mw)
                    ty = mt + int(data['yp'] * mh)
                    
                    pyautogui.moveTo(tx, ty)
                else:
                    # Fallback for old protocol (shouldn't happen)
                    pyautogui.moveTo(data['x'], data['y'])
                    
            elif action == 'mousedown':
                pyautogui.mouseDown(button=data.get('button', 'left'))
            elif action == 'mouseup':
                pyautogui.mouseUp(button=data.get('button', 'left'))
            elif action == 'keydown':
                # Try DirectInput for Lock Screen
                key = data['key'].lower()
                if key in SCANCODES:
                    press_key_scancode(SCANCODES[key])
                else:
                    pyautogui.keyDown(data['key'])
            elif action == 'keyup':
                key = data['key'].lower()
                if key in SCANCODES:
                    release_key_scancode(SCANCODES[key])
                else:
                    pyautogui.keyUp(data['key'])
            elif action == 'scroll':
                pyautogui.scroll(data.get('dy', 0))
            elif action == 'clipboard_set':
                try:
                    text = data.get('text', '')
                    pyperclip.copy(text)
                    print(f"DEBUG: Clipboard set to: {text[:20]}...")
                except Exception as e:
                    print(f"DEBUG: Clipboard set error: {e}")
            elif action == 'clipboard_get':
                # Check for Image first
                try:
                    img = ImageGrab.grabclipboard()
                    if isinstance(img, Image.Image):
                        buffer = io.BytesIO()
                        img.save(buffer, format='PNG')
                        b64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                        asyncio.run_coroutine_threadsafe(ws.send_json({'type': 'clipboard_image', 'data': b64_data}), self.loop)
                        return
                except:
                    pass
                
                # Fallback to text
                text = pyperclip.paste()
                asyncio.run_coroutine_threadsafe(ws.send_json({'type': 'clipboard_text', 'text': text}), self.loop)
            elif action == 'type_text':
                pyautogui.write(data.get('text', ''))
        except Exception as e:
            print(f"DEBUG: Input error: {e}")

    def _capture_frame_sync(self, monitor, target_res, use_grayscale, jpeg_quality, prev_img_ref=None):
        # Create new MSS instance for this thread
        import mss
        from PIL import ImageChops
        
        with mss.mss() as sct:
            try:
                try:
                    sct_img = sct.grab(monitor)
                    if not sct_img: return None
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                except Exception:
                    # Fallback to GDI (ImageGrab) for Lock Screen support
                    left = monitor['left']
                    top = monitor['top']
                    right = left + monitor['width']
                    bottom = top + monitor['height']
                    img = ImageGrab.grab(bbox=(left, top, right, bottom))
                
                # Resize (Must be consistent for diff)
                if target_res:
                    img.thumbnail(target_res, Image.Resampling.LANCZOS)

                # Grayscale
                if use_grayscale:
                    img = img.convert('L')
                
                # Differential Update Logic
                diff_box = None
                full_update = True
                
                # We need persistent state for 'prev_img', but we are in a thread pool...
                # We can use a thread-safe dict passed as ref, or just return full frame if complex.
                # Actually, 'prev_img_ref' is a list [prev_image_obj] passed from main loop.
                # Since we run tasks sequentially (mostly), we might get away with it.
                # But wait, run_in_executor runs in parallel if max_workers > 1.
                # For safety, let's just do full frames first, then optimize.
                # ToDesk uses H.264 P-frames which is diff by definition.
                # Implementing ImageChops.difference here:
                
                if prev_img_ref and prev_img_ref[0]:
                    prev_img = prev_img_ref[0]
                    if prev_img.size == img.size and prev_img.mode == img.mode:
                        # Compute diff
                        diff = ImageChops.difference(img, prev_img)
                        bbox = diff.getbbox()
                        if bbox:
                            # Verify if diff is large enough to matter
                            # If diff is tiny, skip? No, even tiny updates matter (typing).
                            # If diff is HUGE (whole screen), send full frame.
                            
                            # Expand bbox slightly to avoid artifacts at edges?
                            # Let's just crop.
                            diff_box = bbox
                            full_update = False
                            
                            # Update reference
                            prev_img_ref[0] = img
                        else:
                            # No change
                            return b'NO_CHANGE'
                
                if full_update:
                    prev_img_ref[0] = img
                    
                buffer = io.BytesIO()
                
                if not full_update and diff_box:
                    # Send partial
                    crop = img.crop(diff_box)
                    crop.save(buffer, format="JPEG", quality=jpeg_quality)
                    
                    # Protocol: [8b ts] + [1b type] + [4b x] + [4b y] + [4b w] + [4b h] + [data]
                    # Type: 0=Full, 1=Partial
                    # We need to return a dict or structured object to main loop
                    return {
                        'type': 'partial',
                        'x': diff_box[0], 'y': diff_box[1],
                        'w': diff_box[2] - diff_box[0],
                        'h': diff_box[3] - diff_box[1],
                        'data': buffer.getvalue()
                    }
                else:
                    img.save(buffer, format="JPEG", quality=jpeg_quality)
                    return {
                        'type': 'full',
                        'data': buffer.getvalue()
                    }

            except Exception as e:
                print(f"Capture error: {e}")
                return None

    async def stream_screen(self, app):
        print("DEBUG: Stream Loop Started (Threaded)")
        import mss
        try:
            # Main thread instance for monitor info only
            main_sct = mss.mss()
        except Exception as e:
            print(f"DEBUG: Failed to init MSS: {e}")
            return

        # Initial Monitor Setup
        monitor = main_sct.monitors[0]
        if len(main_sct.monitors) > 1:
             monitor = main_sct.monitors[1]
             
        self.monitor_left = monitor['left']
        self.monitor_top = monitor['top']
        self.monitor_width = monitor['width']
        self.monitor_height = monitor['height']
        
        frame_count = 0
        current_monitor_idx = -1 
        
        # Thread Pool for Capture/Encode
        import concurrent.futures
        # MUST use max_workers=1 to ensure sequential diffs against 'prev_img'
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        
        # State for Diff
        prev_img_ref = [None] 
        
        while True:
            start_time = time.time()
            
            # Check for monitor update
            if self.monitor_index != current_monitor_idx:
                try:
                    current_monitor_idx = self.monitor_index
                    if current_monitor_idx < len(main_sct.monitors):
                        monitor = main_sct.monitors[current_monitor_idx]
                    else:
                        monitor = main_sct.monitors[1] if len(main_sct.monitors) > 1 else main_sct.monitors[0]
                        
                    self.monitor_left = monitor['left']
                    self.monitor_top = monitor['top']
                    self.monitor_width = monitor['width']
                    self.monitor_height = monitor['height']
                    print(f"DEBUG: Switched to Monitor {current_monitor_idx}")
                    # Reset diff reference on monitor switch
                    prev_img_ref[0] = None
                except Exception:
                    monitor = main_sct.monitors[0]

            auth_clients = [ws for ws, state in self.clients.items() if state['authenticated']]
            
            if not auth_clients:
                await asyncio.sleep(0.2)
                continue
            
            # Check if we need to force a full frame (e.g. new client connected)
            if self.force_full_frame:
                print("DEBUG: Forcing Full Frame Update")
                prev_img_ref[0] = None
                self.force_full_frame = False
            
            # Offload heavy lifting to thread pool
            target_res = self.target_res
            use_gray = self.use_grayscale.get()
            quality = self.jpeg_quality
            
            try:
                # Don't pass 'sct' instance, create new one in thread
                result = await self.loop.run_in_executor(
                    pool, 
                    self._capture_frame_sync, 
                    monitor, target_res, use_gray, quality, prev_img_ref
                )
                
                if result == b'NO_CHANGE':
                    await asyncio.sleep(0.01)
                    continue
                    
                if result:
                    ts = time.time() * 1000 # ms
                    import struct
                    
                    if isinstance(result, dict):
                        if result['type'] == 'full':
                            # Protocol V2: [8b ts] + [1b type=0] + [Data]
                            header = struct.pack('>dB', ts, 0)
                            payload = header + result['data']
                        elif result['type'] == 'partial':
                            # Protocol V2: [8b ts] + [1b type=1] + [2b x] + [2b y] + [2b w] + [2b h] + [Data]
                            # Use Short (H) for coords (0-65535)
                            header = struct.pack('>dBHHHH', ts, 1, 
                                                 result['x'], result['y'], result['w'], result['h'])
                            payload = header + result['data']
                    else:
                        # Legacy Fallback (Shouldn't reach here with new code)
                        header = struct.pack('>d', ts)
                        payload = header + result
                    
                    # Broadcast
                    for ws in auth_clients:
                        try:
                            await ws.send_bytes(payload)
                        except: pass
                    
                    frame_count += 1
                    if frame_count % 60 == 0: 
                        print(f"DEBUG: [Heartbeat] Sent frame {frame_count}. FPS Target: {self.target_fps}")
            
            except Exception as e:
                print(f"Stream loop error: {e}")
                await asyncio.sleep(1)

            # FPS Control
            elapsed = time.time() - start_time
            target_delay = 1.0 / self.target_fps
            sleep_time = max(0, target_delay - elapsed)
            await asyncio.sleep(sleep_time)

    async def on_startup(self, app):
        app['stream_task'] = asyncio.create_task(self.stream_screen(app))

    def on_close(self):
        self.stop_server()
        self.root.destroy()
        import os
        os._exit(0)

    def run(self):
        self.root.mainloop()

if __name__ == '__main__':
    server = RemoteDesktopServer()
    server.run()
