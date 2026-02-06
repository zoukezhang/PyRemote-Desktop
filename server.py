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
from PIL import Image, ImageDraw
from pyngrok import ngrok, conf

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
        self.running = False
        self.loop = None
        self.server_thread = None
        self.ngrok_token = ""
        
        # Coordinate Scaling
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.monitor_left = 0
        self.monitor_top = 0
        self.monitor_index = 0 # Default to Monitor 0 (or smart detect)
        
        # File Transfer State
        self.receiving_file = False
        self.file_handle = None
        self.file_name = ""
        self.file_size = 0
        self.file_received = 0
        
        # SSH Tunnel Variables
        self.ssh_process = None
        
        # Performance Settings (Default: Balanced)
        self.target_res = (1280, 720) # Default
        self.jpeg_quality = 30  # <--- Fix: Lower quality for speed
        self.target_fps = 30    # <--- Fix: Higher FPS target since we optimized input
        
        # Setup GUI
        self.root = ctk.CTk()
        self.root.title("远程桌面服务端 - Pro")
        self.root.geometry("500x800") 
        self.root.resizable(False, True)
        
        self.setup_ui()
        
    def setup_ui(self):
        # 1. Hero Header (Status)
        self.header_frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
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
        self.conn_frame = ctk.CTkFrame(self.root)
        self.conn_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(self.conn_frame, text="连接信息", font=("Arial", 14, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        # IPv4
        self.create_info_row(self.conn_frame, "本机局域网 IP:", self.ip)
        
        # PgyVPN
        pgy_ip = self.get_pgy_ip()
        self.pgy_val = self.create_info_row(self.conn_frame, "蒲公英虚拟 IP:", pgy_ip if pgy_ip else "未检测到")
        
        # Password
        self.pass_val = self.create_info_row(self.conn_frame, "访问验证码:", self.password, is_password=True)
        
        # Refresh Btn
        ctk.CTkButton(self.conn_frame, text="刷新验证码", command=self.refresh_password, height=24, width=100).pack(pady=10)

        # 3. Settings Card
        self.settings_frame = ctk.CTkFrame(self.root)
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

        # 4. Tools Card (Firewall & Tunnel)
        self.tools_frame = ctk.CTkFrame(self.root)
        self.tools_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(self.tools_frame, text="高级工具", font=("Arial", 14, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        # Firewall
        ctk.CTkButton(self.tools_frame, text="一键放行防火墙 (修复连接失败)", command=self.fix_firewall, fg_color="transparent", border_width=1).pack(fill="x", padx=15, pady=5)
        
        # Ngrok
        self.use_ngrok = ctk.BooleanVar()
        self.chk_ngrok = ctk.CTkSwitch(self.tools_frame, text="启用 Ngrok 公网穿透", variable=self.use_ngrok)
        self.chk_ngrok.pack(anchor="w", padx=15, pady=10)
        ctk.CTkButton(self.tools_frame, text="配置 Ngrok 令牌", command=self.set_ngrok_token, height=24).pack(fill="x", padx=15, pady=(0, 15))

        # Handle Close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

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

    def generate_password(self):
        chars = string.digits
        return ''.join(secrets.choice(chars) for _ in range(6))

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
        
        # 1. Start Tunnel if enabled
        tunnel_started = False
        
        if self.use_ngrok.get():
            if self.start_ngrok():
                tunnel_started = True
        
        # 2. Start Web Server
        self.server_thread = threading.Thread(target=self.run_async_server, daemon=True)
        self.server_thread.start()

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
        self.app.router.add_get('/ws', self.handle_ws)
        self.app.on_startup.append(self.on_startup)
        
        self.runner = web.AppRunner(self.app)
        self.loop.run_until_complete(self.runner.setup())
        self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        
        try:
            self.loop.run_until_complete(self.site.start())
            self.loop.run_forever()
        except Exception as e:
            print(f"Server error: {e}")

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
                            else:
                                print("DEBUG: Auth Failed")
                                await ws.send_json({'type': 'auth_result', 'status': 'error'})
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
            
        else:
            # Run mouse/keyboard in executor
            await self.loop.run_in_executor(None, self._process_command_sync, action, data, ws)

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
                    w, h = pyautogui.size()
                    tx = int(data['xp'] * w)
                    ty = int(data['yp'] * h)
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
                pyperclip.copy(data.get('text', ''))
            elif action == 'clipboard_get':
                # This needs to be async sent back, but we are in sync thread
                # We can schedule it back to loop
                text = pyperclip.paste()
                asyncio.run_coroutine_threadsafe(ws.send_json({'type': 'clipboard_text', 'text': text}), self.loop)
            elif action == 'type_text':
                pyautogui.write(data.get('text', ''))
        except Exception as e:
            print(f"DEBUG: Input error: {e}")

    async def stream_screen(self, app):
        print("DEBUG: Starting screen stream task...")
        try:
            sct = mss.mss()
            print(f"DEBUG: MSS Monitors found: {len(sct.monitors)}")
            
            # Use Primary Monitor (Index 1) for reliable coordinate mapping
            # Monitor 0 (All) can cause scaling issues if multi-monitor
            if len(sct.monitors) > 1:
                # Use selected monitor index
                # Ensure index is valid
                idx = self.monitor_index
                if idx == 0: # Auto/Primary
                     monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                elif idx < len(sct.monitors):
                     monitor = sct.monitors[idx]
                else:
                     monitor = sct.monitors[1] # Fallback
            else:
                monitor = sct.monitors[0]
                
            print(f"DEBUG: Using monitor: {monitor}")
            
            # Calculate Scaling Factor (Logical Points vs Physical Pixels)
            w_log, h_log = pyautogui.size()
            w_phy = monitor['width']
            h_phy = monitor['height']
            
            self.scale_x = w_log / w_phy
            self.scale_y = h_log / h_phy
            self.monitor_left = monitor['left']
            self.monitor_top = monitor['top']
            
            print(f"DEBUG: Screen Scale Factor: X={self.scale_x:.2f}, Y={self.scale_y:.2f}")
            print(f"DEBUG: Screen Offset: Left={self.monitor_left}, Top={self.monitor_top}")
            
        except Exception as e:
            print(f"DEBUG: Failed to init MSS: {e}")
            return

        frame_count = 0
        while True:
            # Check for monitor update
            if self.monitor_index != 0:
                try:
                    if self.monitor_index < len(sct.monitors):
                         monitor = sct.monitors[self.monitor_index]
                         # Update scaling if monitor changed
                         w_phy = monitor['width']
                         h_phy = monitor['height']
                         self.scale_x = w_log / w_phy
                         self.scale_y = h_log / h_phy
                         self.monitor_left = monitor['left']
                         self.monitor_top = monitor['top']
                except:
                    pass

            auth_clients = [ws for ws, state in self.clients.items() if state['authenticated']]
            if not auth_clients:
                await asyncio.sleep(0.2)
                continue
            
            # Rate Control
            start_time = time.time()
            
            try:
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                # Removed Red Dot Drawing Code as requested

                # Resize
                if self.target_res:
                    img.thumbnail(self.target_res, Image.Resampling.LANCZOS)

                # Grayscale Conversion
                if self.use_grayscale.get():
                    img = img.convert('L')

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=self.jpeg_quality)
                img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                # Include Timestamp for Latency Check
                msg = {
                    'type': 'frame', 
                    'data': img_str,
                    'ts': time.time() * 1000 # ms
                }
                
                for ws in auth_clients:
                    try:
                        await ws.send_json(msg)
                    except Exception as e:
                        print(f"DEBUG: Failed to send frame to client: {e}")
                
                frame_count += 1
                if frame_count % 15 == 0: # Print every ~1 second at 15fps
                    print(f"DEBUG: [Heartbeat] Sent frame {frame_count}. Target FPS: {self.target_fps}")
                    
            except Exception as e:
                print(f"DEBUG: Screen capture error: {e}")
                import traceback
                traceback.print_exc()
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
