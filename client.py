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
        
        ctk.CTkLabel(self.input_card, text="伙伴设备码 (IP)", font=("Arial", 12)).pack(anchor="w", padx=15, pady=(15, 5))
        self.entry_ip = ctk.CTkEntry(self.input_card, placeholder_text="例如: 192.168.1.5", height=35)
        self.entry_ip.pack(fill="x", padx=15, pady=(0, 15))
        self.entry_ip.insert(0, "127.0.0.1") 
        
        ctk.CTkLabel(self.input_card, text="访问验证码", font=("Arial", 12)).pack(anchor="w", padx=15, pady=(0, 5))
        self.entry_pass = ctk.CTkEntry(self.input_card, show="*", placeholder_text="输入6位数字", height=35)
        self.entry_pass.pack(fill="x", padx=15, pady=(0, 20))
        
        # Connect Button
        self.btn_connect = ctk.CTkButton(self.main_frame, text="立即连接", command=self.connect, 
                                         font=("Arial", 14, "bold"), height=40)
        self.btn_connect.pack(pady=30, fill="x", padx=30)
        
        # Footer
        ctk.CTkLabel(self.main_frame, text="安全加密连接 | 极速传输", text_color="gray", font=("Arial", 10)).pack(side="bottom", pady=20)
        
    def connect(self):
        self.host = self.entry_ip.get().strip()
        self.password = self.entry_pass.get().strip()
        
        if not self.host or not self.password:
            messagebox.showwarning("输入错误", "请输入伙伴设备码和验证码")
            return
            
        # Start connection in separate thread to not freeze UI
        self.running = True
        self.btn_connect.configure(state="disabled", text="正在连接...")
        threading.Thread(target=self.run_async_connect, daemon=True).start()

    def run_async_connect(self):
        # 1. Diagnose Connection First
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
                                # Start listening loop
                                print("DEBUG: Starting Listen Loop...")
                                await self.listen_loop(ws)
                            else:
                                print("DEBUG: Auth Failed")
                                self.root.after(0, lambda: messagebox.showerror("验证失败", "密码错误"))
                                self.root.after(0, self.reset_login_ui)
                                return
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
        
        self.frame_count = 0
        self.start_fps_timer()
        
        # Menu
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)
        
        # 1. Settings Menu
        self.settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="设置", menu=self.settings_menu)
        
        # Quality
        self.quality_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label="画质", menu=self.quality_menu)
        self.quality_menu.add_command(label="高清 (80%)", command=lambda: self.update_remote_settings(quality=80))
        self.quality_menu.add_command(label="平衡 (50%)", command=lambda: self.update_remote_settings(quality=50))
        self.quality_menu.add_command(label="流畅 (30%)", command=lambda: self.update_remote_settings(quality=30))
        self.quality_menu.add_command(label="极速 (10%)", command=lambda: self.update_remote_settings(quality=10))
        
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
        self.monitor_menu.add_command(label="屏幕 1", command=lambda: self.update_remote_settings(monitor=1))
        self.monitor_menu.add_command(label="屏幕 2", command=lambda: self.update_remote_settings(monitor=2))
        self.monitor_menu.add_command(label="屏幕 3", command=lambda: self.update_remote_settings(monitor=3))

        # 2. File Menu
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="文件", menu=self.file_menu)
        self.file_menu.add_command(label="发送文件到远程...", command=self.upload_file)

        # 3. Clipboard Menu
        self.clipboard_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="剪贴板", menu=self.clipboard_menu)
        self.clipboard_menu.add_command(label="发送本地剪贴板", command=self.send_clipboard)
        self.clipboard_menu.add_command(label="获取远程剪贴板", command=self.get_clipboard)

        # Bindings
        self.canvas.bind('<Motion>', self.on_mouse_move)
        self.canvas.bind('<Button-1>', lambda e: self.on_mouse_click(e, 'left', 'mousedown'))
        self.canvas.bind('<ButtonRelease-1>', lambda e: self.on_mouse_click(e, 'left', 'mouseup'))
        
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

    def start_fps_timer(self):
        def _update_fps():
            if not self.running: return
            self.fps_label.config(text=f"FPS: {self.frame_count}")
            self.frame_count = 0
            self.root.after(1000, _update_fps)
        _update_fps()

    async def handle_message(self, data):
        msg_type = data.get('type')
        
        if msg_type == 'frame':
            self.frame_count += 1
            # Calculate Latency
            if 'ts' in data:
                latency = int((time.time() * 1000) - data['ts'])
                self.update_latency_display(latency)
            
            img_data = base64.b64decode(data['data'])
            image = Image.open(io.BytesIO(img_data))
            self.update_image_safe(image)
            
        elif msg_type == 'clipboard_text':
            text = data.get('text', '')
            self.root.after(0, lambda: pyperclip.copy(text))
            self.root.after(0, lambda: messagebox.showinfo("剪贴板", "远程剪贴板已复制到本地！"))
            
        elif msg_type == 'notification':
            title = data.get('title', '通知')
            msg = data.get('message', '')
            self.root.after(0, lambda: messagebox.showinfo(title, msg))

    def update_remote_settings(self, quality=None, fps=None, monitor=None):
        payload = {'action': 'update_settings'}
        if quality is not None: payload['quality'] = quality
        if fps is not None: payload['fps'] = fps
        if monitor is not None: payload['monitor'] = monitor
        
        self.send_json(payload)
        # Feedback
        print(f"DEBUG: Sent Settings Update: {payload}")

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
        if 'meta' in key or 'win' in key: return 'command'
        
        if len(key) == 1: return key
        return key

    # --- Features ---
    def send_clipboard(self):
        try:
            text = pyperclip.paste()
            self.send_json({'action': 'clipboard_set', 'text': text})
            messagebox.showinfo("剪贴板", "本地剪贴板已发送到远程！")
        except Exception as e:
            messagebox.showerror("错误", f"剪贴板错误: {e}")

    def get_clipboard(self):
        self.send_json({'action': 'clipboard_get'})

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
