import asyncio
import base64
import json
import io
import sys
import threading
import time
import tkinter as tk
import customtkinter as ctk
from tkinter import simpledialog, messagebox
from PIL import Image, ImageTk
import aiohttp
import pyperclip
import tempfile
import subprocess
import os

try:
    import pyaudio
except ImportError:
    pyaudio = None
    print("Warning: PyAudio not found. Sound will be disabled.")

# Configuration
DEFAULT_PORT = 8080

# Set Theme
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class RemoteDesktopClient:
    def __init__(self, root):
        self.root = root
        self.ws = None
        self.session = None
        self.loop = None
        self.running = False
        self.host = ""
        self.password = ""
        
        # Smart Mode State
        self.auto_quality = False
        self.current_latency = 0
        self.bytes_since_check = 0
        self.last_check_time = time.time()
        
        # Audio
        self.audio_p = None
        self.audio_stream = None
        self.audio_enabled = tk.BooleanVar(value=True) # Default On
        if pyaudio:
            try:
                self.audio_p = pyaudio.PyAudio()
            except Exception as e:
                print(f"Audio init failed: {e}")
        
        # Clock Sync
        self.time_offset = 0 # server_time - client_time
        
        # Setup Login UI
        self.setup_login_ui()
        
    def setup_login_ui(self):
        self.root.title("远程桌面客户端 - Pro")
        self.root.geometry("400x450")
        self.root.resizable(False, False)
        
        # Main Container
        self.main_frame = ctk.CTkFrame(self.root, corner_radius=0)
        self.main_frame.pack(fill="both", expand=True)
        
        # Header
        ctk.CTkLabel(self.main_frame, text="连接伙伴", font=("SF Pro Display", 24, "bold")).pack(pady=(40, 30))
        
        # Input Card
        self.input_card = ctk.CTkFrame(self.main_frame)
        self.input_card.pack(pady=10, padx=30, fill="x")
        
        ctk.CTkLabel(self.input_card, text="伙伴设备码 (ID 或 IP)", font=("Arial", 12)).pack(anchor="w", padx=15, pady=(15, 5))
        self.entry_ip = ctk.CTkEntry(self.input_card, placeholder_text="例如: 123456789 或 192.168.1.5", height=35)
        self.entry_ip.pack(fill="x", padx=15, pady=(0, 15))
        # self.entry_ip.insert(0, "127.0.0.1") 
        
        ctk.CTkLabel(self.input_card, text="访问验证码", font=("Arial", 12)).pack(anchor="w", padx=15, pady=(0, 5))
        self.entry_pass = ctk.CTkEntry(self.input_card, show="*", placeholder_text="输入6位数字", height=35)
        self.entry_pass.pack(fill="x", padx=15, pady=(0, 20))
        
        # Connect Button
        self.btn_connect = ctk.CTkButton(self.main_frame, text="立即连接", command=self.connect, 
                                         font=("Arial", 14, "bold"), height=40)
        self.btn_connect.pack(pady=(20, 10), fill="x", padx=30)
        
        # Settings Toggle
        self.settings_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.settings_frame.pack(fill="x", padx=30)
        
        self.show_settings = ctk.BooleanVar(value=False)
        self.btn_settings = ctk.CTkCheckBox(self.settings_frame, text="显示高级设置", variable=self.show_settings, command=self.toggle_settings)
        self.btn_settings.pack(anchor="w")
        
        self.adv_frame = ctk.CTkFrame(self.main_frame)
        # self.adv_frame.pack(fill="x", padx=30, pady=10) # Hidden by default
        
        ctk.CTkLabel(self.adv_frame, text="信令服务器地址:", font=("Arial", 10)).pack(anchor="w", padx=10, pady=(5,0))
        self.entry_signal = ctk.CTkEntry(self.adv_frame, height=28)
        self.entry_signal.pack(fill="x", padx=10, pady=(0, 10))
        self.entry_signal.insert(0, "http://localhost:9000")

        # Footer
        ctk.CTkLabel(self.main_frame, text="安全加密连接 | 极速传输", text_color="gray", font=("Arial", 10)).pack(side="bottom", pady=20)
        
    def toggle_settings(self):
        if self.show_settings.get():
            self.adv_frame.pack(fill="x", padx=30, pady=10)
        else:
            self.adv_frame.pack_forget()

    def connect(self):
        input_val = self.entry_ip.get().strip()
        self.password = self.entry_pass.get().strip()
        
        if not input_val or not self.password:
            messagebox.showwarning("输入错误", "请输入伙伴设备码和验证码")
            return

        # Check if input is a 9-digit Device ID
        if input_val.isdigit() and len(input_val) == 9:
            try:
                import requests
                signal_url = "http://localhost:9000/lookup/" + input_val
                resp = requests.get(signal_url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    self.host = data['ip']
                    if 'port' in data and str(data['port']) != str(DEFAULT_PORT):
                         self.host = f"{self.host}:{data['port']}"
                else:
                    messagebox.showerror("连接失败", "未找到该设备 ID (设备可能离线)")
                    return
            except Exception as e:
                messagebox.showerror("连接错误", f"无法解析设备 ID: {e}")
                return
        else:
            self.host = input_val
            
        # Start connection in separate thread to not freeze UI
        self.running = True
        self.btn_connect.configure(state="disabled", text="正在连接...")
        threading.Thread(target=self.run_async_connect, daemon=True).start()

    def resolve_device_id(self, device_id):
        """Resolves 9-digit ID to IP:Port via Signal Server"""
        import urllib.request
        import json
        
        signal_server = self.entry_signal.get().strip()
        if not signal_server.startswith("http"):
             signal_server = "http://" + signal_server
             
        url = f"{signal_server}/lookup/{device_id}"
        print(f"DEBUG: Resolving Device ID {device_id} via {url}...")
        
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    
                    if data.get('mode') == 'tunnel':
                        print(f"DEBUG: Resolved to Tunnel Mode")
                        return f"tunnel://{device_id}"
                        
                    ip = data.get('ip')
                    port = data.get('port')
                    print(f"DEBUG: Resolved to {ip}:{port}")
                    return f"{ip}:{port}"
        except Exception as e:
            print(f"DEBUG: Resolution failed: {e}")
            return None
        return None

    def run_async_connect(self):
        # 0. Check for Device ID (9 digits)
        raw_input = self.host.strip()
        if raw_input.isdigit() and len(raw_input) == 9:
            self.root.after(0, lambda: self.btn_connect.configure(text="解析 ID 中..."))
            resolved = self.resolve_device_id(raw_input)
            if resolved:
                self.host = resolved
            else:
                self.root.after(0, lambda: messagebox.showerror("连接失败", "无法解析设备 ID (设备离线或服务器不可达)"))
                self.root.after(0, lambda: self.btn_connect.configure(state="normal", text="立即连接"))
                return

        # 1. Diagnose Connection First (Skip for Tunnel)
        if not self.host.startswith("tunnel://"):
            self.diagnose_connection()
        
        # 2. Run Main Loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loop = loop  # <--- Fix: Assign loop to instance variable
        try:
            loop.run_until_complete(self.connect_to_server())
        except Exception as e:
            print(f"Loop error: {e}")
        finally:
            loop.close()
            self.root.after(0, lambda: self.btn_connect.configure(state="normal", text="立即连接"))

    def diagnose_connection(self):
        import platform
        import subprocess
        import socket
        # Extract IP/Host and Port
        raw = self.host.replace("http://", "").replace("ws://", "")
        if ":" in raw:
            host_part, port_part = raw.rsplit(":", 1)
        else:
            host_part = raw
            port_part = DEFAULT_PORT
        
        try:
            port = int(port_part)
        except:
            port = 8080
            
        print(f"Diagnosing {host_part}:{port}...")
        
        # 1. Ping Check
        # Ping is not always reliable (firewall blocks ICMP), but good first step
        is_online = False
        try:
            param = '-n' if platform.system().lower()=='windows' else '-c'
            cmd = ['ping', param, '1', host_part]
            code = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if code == 0:
                is_online = True
                print("Ping Success!")
        except:
            pass
            
        # 2. TCP Port Check (Crucial)
        is_port_open = False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3) # 3 seconds timeout
            result = sock.connect_ex((host_part, port))
            if result == 0:
                is_port_open = True
                print("Port Open!")
            else:
                print(f"Port Closed/Filtered. Code: {result}")
            sock.close()
        except Exception as e:
            print(f"Socket error: {e}")
            
        # Store result for error message
        self.diag_result = {
            'ping': is_online,
            'port': is_port_open,
            'target': f"{host_part}:{port}"
        }

    async def connect_to_server(self):
        # Ensure loop is set
        if not self.loop:
            self.loop = asyncio.get_running_loop()
            
        # Normalize Input
        raw_host = self.host.strip()
        
        if raw_host.startswith("tunnel://"):
            # Tunnel Mode
            device_id = raw_host.replace("tunnel://", "")
            signal_server = self.entry_signal.get().strip()
            
            # Convert HTTP signal URL to WS URL
            if signal_server.startswith("https://"):
                base = signal_server.replace("https://", "wss://")
            elif signal_server.startswith("http://"):
                base = signal_server.replace("http://", "ws://")
            else:
                base = f"ws://{signal_server}"
                
            # If port is missing in signal server url, add it? 
            # Usually signal server url includes port if non-standard.
            
            url = f"{base}/client/{device_id}"
            print(f"DEBUG: Connecting via Tunnel: {url}")
            
        else:
            # Direct Mode
            # Remove protocol if present
            protocol = "ws"
            if raw_host.startswith("http://"):
                raw_host = raw_host[7:]
            elif raw_host.startswith("https://"):
                raw_host = raw_host[8:]
                protocol = "wss"
            elif raw_host.startswith("ws://"):
                raw_host = raw_host[5:]
            elif raw_host.startswith("wss://"):
                raw_host = raw_host[6:]
                protocol = "wss"
            
            if "ngrok" in raw_host: protocol = "wss"

            # Check for IPv6 or custom port
            address_part = raw_host
            has_port = False
            if raw_host.startswith("["):
                if "]:" in raw_host:
                    has_port = True
            elif ":" in raw_host:
                if raw_host.count(":") == 1:
                    has_port = True
                elif raw_host.count(":") > 1 and not raw_host.startswith("["):
                    address_part = f"[{raw_host}]:{DEFAULT_PORT}"
                    has_port = True 
            
            if not has_port:
                 address_part = f"{raw_host}:{DEFAULT_PORT}"

            url = f"{protocol}://{address_part}/ws"
        
        print(f"DEBUG: Connecting to: {url}")

        try:
            async with aiohttp.ClientSession() as session:
                self.session = session
                async with session.ws_connect(url) as ws:
                    self.ws = ws
                    print("DEBUG: WebSocket Connected")
                    
                    # 1. Send Authentication
                    print("DEBUG: Sending Auth...")
                    await ws.send_json({'action': 'auth', 'password': self.password})
                    
                    # 2. Wait for Auth Response
                    msg = await ws.receive()
                    print(f"DEBUG: Received Auth Response: {msg.type}")
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        print(f"DEBUG: Auth Data: {data}")
                        if data.get('type') == 'auth_result':
                            if data.get('status') == 'ok':
                                # Auth Success! Switch to Desktop UI
                                print("DEBUG: Auth OK! Switching UI...")
                                self.root.after(0, self.switch_to_desktop_ui)
                                # Start Clock Sync
                                asyncio.create_task(self.sync_clock())
                                # Start listening loop
                                print("DEBUG: Starting Listen Loop...")
                                await self.listen_loop(ws)
                            else:
                                print("DEBUG: Auth Failed")
                                self.root.after(0, lambda: messagebox.showerror("验证失败", "密码错误"))
                                self.root.after(0, self.reset_login_ui)
                                return
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        pass # Ignore binary during auth phase
                        
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                         print("DEBUG: Connection Closed during Auth")
                         self.root.after(0, lambda: messagebox.showerror("连接断开", "服务器拒绝了连接"))
                         self.root.after(0, self.reset_login_ui)

        except Exception as e:
            print(f"DEBUG: Connection Error: {e}")
            import traceback
            traceback.print_exc()
            err_msg = str(e)
            if "Connect call failed" in err_msg or "Cannot connect" in err_msg or "timeout" in err_msg.lower():
                # Use Diagnostics Result
                diag = getattr(self, 'diag_result', {})
                ping_ok = diag.get('ping', False)
                port_ok = diag.get('port', False)
                target = diag.get('target', self.host)
                
                reason = "未知错误"
                if ping_ok and not port_ok:
                    reason = (
                        "网络已通，但端口被拦截 (最常见)。\n"
                        "-> 请务必在服务端执行防火墙放行命令！"
                    )
                elif not ping_ok:
                    reason = (
                        "网络不通 (Ping 失败)。\n"
                        "-> 请检查蒲公英是否开启，或 IP 是否输错。"
                    )
                
                friendly_msg = (
                    f"无法连接到 {target}\n\n"
                    f"诊断结果: Ping={'通' if ping_ok else '不通'}, 端口={'开放' if port_ok else '关闭/被拦截'}\n\n"
                    f"建议: {reason}\n\n"
                    "其他原因：\n"
                    "1. 服务端未启动或已停止。\n"
                    "2. 端口输入错误。"
                )
                self.root.after(0, lambda: messagebox.showerror("连接失败", friendly_msg))
            else:
                self.root.after(0, lambda: messagebox.showerror("连接错误", f"连接失败: {e}"))
            
            self.root.after(0, self.reset_login_ui)

    async def listen_loop(self, ws):
        print("DEBUG: Entered Listen Loop")
        try:
            async for msg in ws:
                if not self.running:
                    print("DEBUG: Running flag is False, exiting loop")
                    break
                
                if msg.type == aiohttp.WSMsgType.TEXT:
                    # print(f"DEBUG: Received Msg: {msg.data[:50]}...") # Too verbose for frames
                    data = json.loads(msg.data)
                    await self.handle_message(data)
                
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    # Optimized Binary Frame Protocol
                    try:
                        data = msg.data
                        if len(data) > 9: # At least 9 bytes (ts + type)
                            import struct
                            # Peek Type
                            frame_type = data[8]
                            
                            if frame_type == 0: # Full Frame
                                ts = struct.unpack('>d', data[:8])[0]
                                img_bytes = data[9:]
                                
                                # Render Full (Thread Safe)
                                try:
                                    image = Image.open(io.BytesIO(img_bytes))
                                    # Must use root.after to schedule GUI update on main thread!
                                    self.root.after(0, self.update_image_safe, image)
                                except Exception as e:
                                    print(f"Full Frame Error: {e}")
                                
                            elif frame_type == 1: # Partial Frame
                                # [8b ts] + [1b type] + [2b x] + [2b y] + [2b w] + [2b h] + [data]
                                if len(data) > 17:
                                    ts, _, x, y, w, h = struct.unpack('>dBHHHH', data[:17])
                                    img_bytes = data[17:]
                                    
                                    # Render Partial (Thread Safe)
                                    try:
                                        patch = Image.open(io.BytesIO(img_bytes))
                                        # Schedule on main thread
                                        self.root.after(0, self.update_partial_safe, patch, x, y)
                                    except Exception as e:
                                        print(f"Partial render error: {e}")
                            
                            # Common Latency Calc
                            if 'ts' in locals():
                                self.frame_count += 1
                                now = time.time() * 1000
                                latency = int(now - (ts - self.time_offset))
                                if latency < 0: latency = 0 
                                self.current_latency = latency
                                self.root.after(0, self.update_latency_display, latency)

                    except Exception as e:
                        print(f"Decode Error: {e}")
                        pass

                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    print("DEBUG: WS Closed")
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f"DEBUG: WS Error: {ws.exception()}")
                    break
        except Exception as e:
            print(f"DEBUG: Listen Loop Exception: {e}")
            import traceback
            traceback.print_exc()
        
        print("DEBUG: Exiting Listen Loop")
        self.root.after(0, lambda: messagebox.showinfo("断开连接", "服务器已关闭连接"))
        self.root.after(0, self.on_close)

    def reset_login_ui(self):
        self.btn_connect.configure(state="normal", text="立即连接")
        self.running = False

    def switch_to_desktop_ui(self):
        # Destroy Login UI widgets
        # NOTE: customtkinter uses specific destroy methods sometimes, but widget.destroy() is universal
        for widget in self.root.winfo_children():
            widget.destroy()
            
        # Configure Window
        self.root.title(f"远程桌面 - {self.host}")
        self.root.geometry("1280x720")
        self.root.resizable(True, True)
        
        # Use Standard TK Canvas for Image Drawing (Performant)
        # CTk doesn't have a direct Canvas replacement that is faster for raw pixel pushing
        self.canvas = tk.Canvas(self.root, bg='black', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Latency Label
        self.latency_label = tk.Label(self.root, text="延迟: -- ms", bg="black", fg="#00FF00", font=("Arial", 10))
        self.latency_label.place(relx=1.0, rely=0.0, anchor=tk.NE, x=-10, y=10)
        
        # FPS Label
        self.fps_label = tk.Label(self.root, text="FPS: 0", bg="black", fg="#00FFFF", font=("Arial", 10))
        self.fps_label.place(relx=0.0, rely=0.0, anchor=tk.NW, x=10, y=10)
        
        # Speed Label
        self.speed_label = tk.Label(self.root, text="Speed: 0 KB/s", bg="black", fg="#FF00FF", font=("Arial", 10))
        self.speed_label.place(relx=0.0, rely=0.0, anchor=tk.NW, x=80, y=10)
        
        self.frame_count = 0
        self.start_fps_timer()
        self.start_network_monitor()
        
        # Menu
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)
        
        # 1. Settings Menu
        self.settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="设置", menu=self.settings_menu)
        
        # Quality
        self.quality_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label="画质", menu=self.quality_menu)
        self.quality_menu.add_command(label="自动 (智能领航)", command=lambda: self.set_auto_quality(True))
        self.quality_menu.add_separator()
        self.quality_menu.add_command(label="高清 (80%)", command=lambda: self.update_remote_settings(quality=80))
        self.quality_menu.add_command(label="平衡 (50%)", command=lambda: self.update_remote_settings(quality=50))
        self.quality_menu.add_command(label="流畅 (30%)", command=lambda: self.update_remote_settings(quality=30))
        self.quality_menu.add_command(label="极速 (10%)", command=lambda: self.update_remote_settings(quality=10))
        
        # View
        self.view_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.menu_bar.add_cascade(label="视图", menu=self.view_menu)
        self.view_menu.add_command(label="全屏模式 (Esc退出)", command=self.toggle_fullscreen)

        # FPS
        self.fps_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label="帧率", menu=self.fps_menu)
        self.fps_menu.add_command(label="60 FPS", command=lambda: self.update_remote_settings(fps=60))
        self.fps_menu.add_command(label="30 FPS", command=lambda: self.update_remote_settings(fps=30))
        self.fps_menu.add_command(label="15 FPS", command=lambda: self.update_remote_settings(fps=15))
        self.fps_menu.add_command(label="5 FPS", command=lambda: self.update_remote_settings(fps=5))
        
        # Monitor
        self.monitor_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label="切换屏幕", menu=self.monitor_menu)
        self.monitor_menu.add_command(label="全部屏幕 (监控墙)", command=lambda: self.update_remote_settings(monitor=0))
        self.monitor_menu.add_separator()
        self.monitor_menu.add_command(label="屏幕 1", command=lambda: self.update_remote_settings(monitor=1))
        self.monitor_menu.add_command(label="屏幕 2", command=lambda: self.update_remote_settings(monitor=2))
        self.monitor_menu.add_command(label="屏幕 3", command=lambda: self.update_remote_settings(monitor=3))

        # Audio Toggle
        self.settings_menu.add_checkbutton(label="启用声音", onvalue=True, offvalue=False, variable=self.audio_enabled)

        # 2. File Menu
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="文件", menu=self.file_menu)
        self.file_menu.add_command(label="发送文件到远程...", command=self.upload_file)
        self.file_menu.add_command(label="从远程下载文件...", command=self.request_file_list)

        # 3. Clipboard Menu
        self.clipboard_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="剪贴板", menu=self.clipboard_menu)
        self.clipboard_menu.add_command(label="发送本地剪贴板", command=self.send_clipboard)
        self.clipboard_menu.add_command(label="获取远程剪贴板", command=self.get_clipboard)

        # Bindings
        self.canvas.bind('<Motion>', self.on_mouse_move)
        self.canvas.bind('<Button-1>', lambda e: self.on_mouse_click(e, 'left', 'mousedown'))
        self.canvas.bind('<ButtonRelease-1>', lambda e: self.on_mouse_click(e, 'left', 'mouseup'))

        # Chat Button (Overlay)
        self.btn_chat = tk.Button(self.root, text="💬", bg="black", fg="white", font=("Arial", 16), command=self.toggle_chat, borderwidth=0)
        self.btn_chat.place(relx=1.0, rely=1.0, anchor=tk.SE, x=-20, y=-20)
        
        # Display Mode
        self.scale_mode = 'fit' # fit, stretch, original

        # Chat Window (Hidden by default)
        self.chat_window = None

        # Mac often maps Button-2 to Right Click, Button-3 to Middle or Right depending on mouse
        if sys.platform == 'darwin':
            self.canvas.bind('<Button-2>', lambda e: self.on_mouse_click(e, 'right', 'mousedown'))
            self.canvas.bind('<ButtonRelease-2>', lambda e: self.on_mouse_click(e, 'right', 'mouseup'))
            self.canvas.bind('<Button-3>', lambda e: self.on_mouse_click(e, 'middle', 'mousedown'))
            self.canvas.bind('<ButtonRelease-3>', lambda e: self.on_mouse_click(e, 'middle', 'mouseup'))
        else:
            self.canvas.bind('<Button-3>', lambda e: self.on_mouse_click(e, 'right', 'mousedown'))
            self.canvas.bind('<ButtonRelease-3>', lambda e: self.on_mouse_click(e, 'right', 'mouseup'))
            self.canvas.bind('<Button-2>', lambda e: self.on_mouse_click(e, 'middle', 'mousedown'))
            self.canvas.bind('<ButtonRelease-2>', lambda e: self.on_mouse_click(e, 'middle', 'mouseup'))
        
        self.root.bind('<MouseWheel>', self.on_scroll)
        self.root.bind('<Button-4>', lambda e: self.on_scroll(e, 1))
        self.root.bind('<Button-5>', lambda e: self.on_scroll(e, -1))
        
        self.root.bind('<KeyPress>', self.on_key_down)
        self.root.bind('<KeyRelease>', self.on_key_up)
        
        self.image_item = None
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.img_w = 1
        self.img_h = 1
        
        # Mouse Throttling
        self.last_mouse_time = 0
        self.mouse_interval = 0.05 # 50ms = 20 FPS cap for mouse events
        
        # Fullscreen State
        self.is_fullscreen = False

    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)
        if self.is_fullscreen:
            self.root.bind("<Escape>", self.toggle_fullscreen)
        else:
            self.root.unbind("<Escape>")

    def set_auto_quality(self, enabled):
        self.auto_quality = enabled
        if enabled:
            messagebox.showinfo("智能模式", "已开启智能画质调节\n系统将根据网络延迟自动调整画质与帧率。")
        else:
            messagebox.showinfo("智能模式", "已关闭智能画质调节")

    def start_network_monitor(self):
        """Smart Adaptive Engine: Adjusts quality based on latency"""
        def _monitor_loop():
            if not self.running: return
            
            if self.auto_quality and self.frame_count > 0: # Only adjust if receiving frames
                # Simple Adaptive Logic
                # High Latency (>200ms) -> Low Quality, Low FPS
                # Medium Latency (100-200ms) -> Medium Quality
                # Low Latency (<50ms) -> High Quality, High FPS
                
                # We use a weighted average or just current snapshot
                current = self.current_latency
                
                # We need to send updates only if state changes significantly to avoid flooding
                # But for now, let's just log or implement a simple hysteresis
                
                new_quality = None
                new_fps = None
                
                if current > 300:
                    new_quality = 10
                    new_fps = 5
                elif current > 150:
                    new_quality = 30
                    new_fps = 15
                elif current > 80:
                    new_quality = 50
                    new_fps = 30
                elif current < 40:
                    new_quality = 80
                    new_fps = 60
                    
                # Send update if we have a decision
                if new_quality:
                    # We can optimize by storing last sent values and only sending diffs
                    # For now, just fire and forget (server handles it efficiently)
                    asyncio.run_coroutine_threadsafe(
                        self.update_remote_settings_async(quality=new_quality, fps=new_fps),
                        self.loop
                    )
            
            self.root.after(2000, _monitor_loop) # Check every 2 seconds
            
        _monitor_loop()

    async def update_remote_settings_async(self, quality=None, fps=None, monitor=None):
        if not self.ws: return
        payload = {'action': 'update_settings'}
        if quality is not None: payload['quality'] = quality
        if fps is not None: payload['fps'] = fps
        if monitor is not None: payload['monitor'] = monitor
        try:
            await self.ws.send_json(payload)
        except: pass

    def set_scale_mode(self, mode):
        self.scale_mode = mode
        if hasattr(self, 'current_image_obj') and self.current_image_obj:
            self.update_image_safe(self.current_image_obj)

    def update_image_safe(self, image):
        try:
            self.current_image_obj = image # Keep reference
            
            # Scale if needed (Fit to window)
            win_w = self.canvas.winfo_width()
            win_h = self.canvas.winfo_height()
            
            # Only scale if window is valid
            if win_w > 1 and win_h > 1:
                img_w, img_h = image.size
                
                if self.scale_mode == 'fit':
                    # Aspect Ratio
                    ratio = min(win_w / img_w, win_h / img_h)
                    new_w = int(img_w * ratio)
                    new_h = int(img_h * ratio)
                elif self.scale_mode == 'stretch':
                    # Stretch to fill
                    new_w = win_w
                    new_h = win_h
                else: # original
                    new_w = img_w
                    new_h = img_h
                
                self.scale_x = new_w / img_w
                self.scale_y = new_h / img_h
                self.img_w = new_w
                self.img_h = new_h
                
                if new_w != img_w or new_h != img_h:
                    image = image.resize((new_w, new_h), Image.Resampling.NEAREST) # Nearest is fast
                
            self.tk_image = ImageTk.PhotoImage(image)
            
            # Center the image
            self.canvas.delete("all")
            self.canvas.create_image(win_w // 2, win_h // 2, anchor=tk.CENTER, image=self.tk_image)
            
        except Exception as e:
            print(f"Render Error: {e}")

    def update_partial_safe(self, patch, x, y):
        try:
            # We need to paste 'patch' onto 'self.current_image_obj' at (x,y)
            # Then redraw. This seems inefficient to re-scale the whole thing?
            # Ideally, we should scale the PATCH and draw it on Canvas directly?
            # But scaling coordinates is tricky if aspect ratio changes.
            # Best way: Maintain a master "virtual framebuffer" (full resolution) in memory.
            # Apply patches to that.
            # Then scale THAT to window size and render.
            
            if not hasattr(self, 'current_image_obj') or not self.current_image_obj:
                print("DEBUG WARNING: Received partial frame but no base image! Requesting Full Frame...")
                # Request full frame immediately
                if self.loop:
                    asyncio.run_coroutine_threadsafe(
                        self.ws.send_json({'action': 'request_full_frame'}),
                        self.loop
                    )
                return # Can't patch nothing
                
            # 1. Update Master Framebuffer
            self.current_image_obj.paste(patch, (x, y))
            
            # 2. Render (Full refresh for now, optimization: only redraw dirty region on canvas?)
            # Since we resize for window fit, we have to resize the whole thing usually.
            # Unless we are 1:1.
            self.update_image_safe(self.current_image_obj)
            
        except Exception as e:
            print(f"Partial Update Error: {e}")

    def toggle_chat(self):
        if self.chat_window and self.chat_window.winfo_exists():
            self.chat_window.destroy()
            self.chat_window = None
            return
            
        self.chat_window = tk.Toplevel(self.root)
        self.chat_window.title("聊天")
        self.chat_window.geometry("300x400")
        self.chat_window.attributes("-topmost", True)
        
        # History
        self.chat_history = tk.Text(self.chat_window, state="disabled")
        self.chat_history.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Input
        input_frame = tk.Frame(self.chat_window)
        input_frame.pack(fill="x", padx=5, pady=5)
        
        self.chat_entry = tk.Entry(input_frame)
        self.chat_entry.pack(side="left", fill="x", expand=True)
        self.chat_entry.bind("<Return>", lambda e: self.send_chat())
        
        btn_send = tk.Button(input_frame, text="发送", command=self.send_chat)
        btn_send.pack(side="right", padx=(5, 0))

    def send_chat(self):
        text = self.chat_entry.get().strip()
        if not text: return
        
        self.chat_entry.delete(0, tk.END)
        self.append_chat("我", text)
        
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.ws.send_json({'action': 'chat', 'message': text}), self.loop)

    def append_chat(self, sender, text):
        if not self.chat_window or not self.chat_window.winfo_exists():
            # If closed, maybe flash button?
            return
            
        self.chat_history.configure(state="normal")
        self.chat_history.insert(tk.END, f"[{sender}]: {text}\n")
        self.chat_history.see(tk.END)
        self.chat_history.configure(state="disabled")

    def request_file_list(self):
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.ws.send_json({'action': 'list_files'}), self.loop)
            
    def show_file_list(self, files):
        win = tk.Toplevel(self.root)
        win.title("远程文件列表 (桌面)")
        win.geometry("400x500")
        
        listbox = tk.Listbox(win)
        listbox.pack(fill="both", expand=True, padx=10, pady=10)
        
        for f in files:
            size_mb = f['size'] / 1024 / 1024
            listbox.insert(tk.END, f"{f['name']} ({size_mb:.2f} MB)")
            
        def _download():
            sel = listbox.curselection()
            if not sel: return
            index = sel[0]
            filename = files[index]['name']
            
            # Start Download
            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.ws.send_json({'action': 'download_request', 'filename': filename}),
                    self.loop
                )
            win.destroy()
            messagebox.showinfo("下载", f"开始下载 {filename}...\n文件将保存到当前目录。")
            
        btn = tk.Button(win, text="下载选中文件", command=_download)
        btn.pack(pady=10)

    def update_latency_display(self, latency):
        self.latency_label.config(text=f"延迟: {latency} ms")
        if latency < 50: self.latency_label.config(fg="#00FF00")
        elif latency < 150: self.latency_label.config(fg="#FFFF00")
        else: self.latency_label.config(fg="#FF0000")

    def start_fps_timer(self):
        def _update_fps():
            if not self.running: return
            self.fps_label.config(text=f"FPS: {self.frame_count}")
            self.frame_count = 0
            self.root.after(1000, _update_fps)
        _update_fps()

    async def sync_clock(self):
        """Perform simple NTP-like clock synchronization"""
        print("DEBUG: Starting Clock Sync...")
        # Average over 5 samples
        offsets = []
        for _ in range(5):
            try:
                t1 = time.time() * 1000
                await self.ws.send_json({'action': 'ping_sync', 'client_time': t1})
                await asyncio.sleep(0.5)
            except: break
            
    async def handle_message(self, data):
        msg_type = data.get('type')
        
        if msg_type == 'pong_sync':
            t1 = data.get('client_time', 0)
            server_ts = data.get('server_time', 0)
            t2 = time.time() * 1000
            
            rtt = t2 - t1
            # Offset = Server - Client
            # server_ts is approx at t1 + rtt/2
            offset = server_ts - (t1 + rtt/2)
            
            # Update offset (using simple moving average or just last value)
            # For simplicity, we just use the latest valid one, maybe average later if needed
            self.time_offset = offset
            print(f"DEBUG: Clock Synced. RTT={rtt:.1f}ms, Offset={offset:.1f}ms")

        elif msg_type == 'frame':
            self.frame_count += 1
            # Calculate Latency
            if 'ts' in data:
                latency = int((time.time() * 1000) - data['ts'])
                self.current_latency = latency # Update for Smart Engine
                self.root.after(0, self.update_latency_display, latency)
            
            img_data = base64.b64decode(data['data'])
            image = Image.open(io.BytesIO(img_data))
            self.root.after(0, self.update_image_safe, image)
            
        elif msg_type == 'clipboard_image':
            try:
                b64_data = data.get('data')
                img_data = base64.b64decode(b64_data)
                
                # Save to temp file
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                    f.write(img_data)
                    temp_path = f.name
                
                # Use osascript to set clipboard on Mac
                if sys.platform == 'darwin':
                    # AppleScript to set clipboard to image file
                    cmd = f'set the clipboard to (read (POSIX file "{temp_path}") as JPEG picture)'
                    subprocess.run(['osascript', '-e', cmd])
                else:
                    # Windows/Linux (Partial support, Pyperclip doesn't do images)
                    # For Windows, we could use win32clipboard if available, but client is Mac in this env.
                    messagebox.showinfo("提示", "图片已接收，但当前系统暂不支持直接写入剪贴板。\n已保存到临时文件: " + temp_path)
                    
                self.root.after(0, lambda: messagebox.showinfo("剪贴板", "远程图片已复制到本地剪贴板！"))
                
                # Cleanup temp file? If we delete it too fast, clipboard might lose reference on some OS
                # Better to leave it or delete on exit.
                
            except Exception as e:
                print(f"Clipboard Image Error: {e}")
                self.root.after(0, lambda: messagebox.showerror("错误", f"剪贴板图片接收失败: {e}"))

        elif msg_type == 'clipboard_text':
            text = data.get('text', '')
            self.root.after(0, lambda: pyperclip.copy(text))
            self.root.after(0, lambda: messagebox.showinfo("剪贴板", "远程剪贴板已复制到本地！"))
            
        elif msg_type == 'notification':
            title = data.get('title', '通知')
            msg = data.get('message', '')
            self.root.after(0, lambda: messagebox.showinfo(title, msg))

        elif msg_type == 'chat':
            sender = data.get('sender', 'Unknown')
            msg = data.get('message', '')
            # If window not open, show notification or small indicator
            if not self.chat_window or not self.chat_window.winfo_exists():
                self.btn_chat.config(bg="red") # Flash red
            
            self.append_chat(sender, msg)
            
        elif msg_type == 'file_list':
            files = data.get('files', [])
            self.root.after(0, lambda: self.show_file_list(files))
            
        elif msg_type == 'download_start':
            self.download_filename = data.get('filename')
            self.download_size = data.get('size')
            self.download_handle = open(self.download_filename, 'wb')
            print(f"DEBUG: Starting download {self.download_filename}")
            
        elif msg_type == 'download_chunk':
            if getattr(self, 'download_handle', None):
                chunk = base64.b64decode(data['data'])
                self.download_handle.write(chunk)
        
        elif msg_type == 'download_end':
            if getattr(self, 'download_handle', None):
                self.download_handle.close()
                self.download_handle = None
                filename = data.get('filename')
                self.root.after(0, lambda: messagebox.showinfo("下载完成", f"文件 {filename} 已保存"))

        elif msg_type == 'audio_config':
            if not self.audio_p: return
            rate = data.get('rate', 48000)
            channels = data.get('channels', 2)
            
            if self.audio_stream:
                try:
                    self.audio_stream.stop_stream()
                    self.audio_stream.close()
                except: pass
            
            try:
                self.audio_stream = self.audio_p.open(
                    format=pyaudio.paInt16,
                    channels=channels,
                    rate=rate,
                    output=True
                )
                print(f"DEBUG: Audio Output Started ({rate}Hz, {channels}ch)")
            except Exception as e:
                print(f"DEBUG: Audio Output Init Failed: {e}")

        elif msg_type == 'audio':
            if self.audio_stream and self.audio_enabled.get():
                try:
                    raw_data = base64.b64decode(data['data'])
                    self.audio_stream.write(raw_data)
                except: pass

    def update_remote_settings(self, quality=None, fps=None, monitor=None):
        if not self.loop: return
        asyncio.run_coroutine_threadsafe(
            self.update_remote_settings_async(quality, fps, monitor),
            self.loop
        )

    def upload_file(self):
        from tkinter import filedialog
        file_path = filedialog.askopenfilename()
        if not file_path: return
        
        # Run in thread to not block UI
        threading.Thread(target=self._upload_file_thread, args=(file_path,), daemon=True).start()

    def _upload_file_thread(self, file_path):
        import os
        filename = os.path.basename(file_path)
        filesize = os.path.getsize(file_path)
        
        # 1. Start
        self.send_json({'action': 'file_start', 'filename': filename, 'size': filesize})
        
        # 2. Send chunks
        chunk_size = 1024 * 64 # 64KB
        sent_bytes = 0
        
        try:
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk: break
                    
                    b64_chunk = base64.b64encode(chunk).decode('utf-8')
                    self.send_json({'action': 'file_chunk', 'data': b64_chunk})
                    
                    sent_bytes += len(chunk)
                    # Optional: Update local progress bar (if we had one)
                    time.sleep(0.01) # Small throttle to avoid flooding
            
            # 3. End
            self.send_json({'action': 'file_end'})
            self.root.after(0, lambda: messagebox.showinfo("传输完成", f"文件 {filename} 发送成功"))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("传输错误", f"发送失败: {e}"))

    def update_latency_display(self, latency):
        color = "#00FF00" # Green
        if latency > 100: color = "#FFFF00" # Yellow
        if latency > 300: color = "#FF0000" # Red
        
        self.root.after(0, lambda: self.latency_label.config(text=f"延迟: {latency} ms", fg=color))

    def update_image_safe(self, image):
        # Calculate scaling to fit window
        try:
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                img_w, img_h = image.size
                ratio = min(canvas_width/img_w, canvas_height/img_h)
                new_size = (int(img_w * ratio), int(img_h * ratio))
                
                self.scale_x = img_w / new_size[0]
                self.scale_y = img_h / new_size[1]
                
                # Store current display size for % calculation
                self.display_w = new_size[0]
                self.display_h = new_size[1]
                
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(image)
            
            def _update():
                if not self.running: return
                self.canvas.config(width=image.width, height=image.height)
                if self.image_item is None:
                    self.image_item = self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)
                else:
                    self.canvas.itemconfig(self.image_item, image=photo)
                self.photo = photo 
                
            self.root.after(0, _update)
        except:
            pass

    def send_json(self, data):
        if self.ws and not self.ws.closed:
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.ws.send_json(data), self.loop)
            else:
                pass # Loop not ready yet

    # --- Input Handling ---

    def on_mouse_move(self, event):
        # Throttle
        now = time.time()
        if now - self.last_mouse_time < self.mouse_interval:
            return
        self.last_mouse_time = now
        
        # Calculate Percentage
        if not hasattr(self, 'display_w') or self.display_w == 0: return
        
        xp = event.x / self.display_w
        yp = event.y / self.display_h
        
        # Clamp
        xp = max(0.0, min(1.0, xp))
        yp = max(0.0, min(1.0, yp))
        
        self.send_json({'action': 'mousemove', 'xp': xp, 'yp': yp})

    def on_mouse_click(self, event, button, action):
        if not hasattr(self, 'display_w') or self.display_w == 0: return
        
        xp = event.x / self.display_w
        yp = event.y / self.display_h
        
        xp = max(0.0, min(1.0, xp))
        yp = max(0.0, min(1.0, yp))
        
        # Update pos then click
        self.send_json({'action': 'mousemove', 'xp': xp, 'yp': yp})
        self.send_json({'action': action, 'button': button})

    def on_scroll(self, event, direction=None):
        dy = 0
        if direction:
            dy = direction * 10
        elif event.delta:
            dy = event.delta
            if sys.platform == 'darwin':
                dy = dy 
            else:
                dy = int(dy / 120) * 10
        
        self.send_json({'action': 'scroll', 'dy': dy})

    def on_key_down(self, event):
        key = self.map_key(event)
        if key:
            self.send_json({'action': 'keydown', 'key': key})

    def on_key_up(self, event):
        key = self.map_key(event)
        if key:
            self.send_json({'action': 'keyup', 'key': key})

    def map_key(self, event):
        key = event.keysym.lower()
        if key == 'return': return 'enter'
        if key == 'space': return 'space'
        if key == 'backspace': return 'backspace'
        if key == 'tab': return 'tab'
        if key == 'escape': return 'esc'
        if 'shift' in key: return 'shift'
        if 'control' in key: return 'ctrl'
        if 'alt' in key: return 'alt'
        
        # Mac Command -> Windows Ctrl Mapping
        if 'meta' in key or 'win' in key or 'command' in key: 
            return 'ctrl'
        
        if len(key) == 1: return key
        return key

    def send_clipboard(self):
        # 1. Try Image First
        # Note: On Mac, GrabClipboard might fail if not focused or no image
        try:
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                b64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                self.update_remote_settings() # Dummy call to get loop? No, use loop directly
                if self.loop:
                    asyncio.run_coroutine_threadsafe(
                        self.ws.send_json({'action': 'clipboard_image', 'data': b64_data}),
                        self.loop
                    )
                messagebox.showinfo("成功", "图片已发送到远程剪贴板！")
                return
        except Exception as e:
            # print(f"Clipboard Image Error: {e}")
            pass
            
        # 2. Fallback to Text
        try:
            text = pyperclip.paste()
            if text:
                if self.loop:
                    asyncio.run_coroutine_threadsafe(
                        self.ws.send_json({'action': 'clipboard_set', 'text': text}),
                        self.loop
                    )
                messagebox.showinfo("成功", "文本已发送到远程剪贴板！")
            else:
                messagebox.showwarning("剪贴板", "剪贴板为空")
        except Exception as e:
            messagebox.showerror("错误", f"剪贴板错误: {e}")

    def get_clipboard(self):
        if self.loop:
             asyncio.run_coroutine_threadsafe(
                self.ws.send_json({'action': 'clipboard_get'}),
                self.loop
             )

    def on_close(self, event=None):
        self.running = False
        self.root.destroy()
        sys.exit(0)

def main():
    root = ctk.CTk()
    client = RemoteDesktopClient(root)
    root.protocol("WM_DELETE_WINDOW", client.on_close)
    root.mainloop()

if __name__ == '__main__':
    main()
