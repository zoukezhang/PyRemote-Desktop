import asyncio
from aiohttp import web
import json
import time

# --- Signal Server (Discovery Service) ---
# Maps 9-digit Device IDs to IP:Port addresses.
# In a real-world scenario, this runs on a public VPS.

REGISTRY = {} # {device_id: {'ip': ip, 'port': port, 'last_seen': timestamp, 'mode': 'direct' or 'tunnel'}}
TUNNELS = {} # {device_id: {'device_ws': ws, 'client_ws': ws}}
HEARTBEAT_TIMEOUT = 60 # Seconds

async def handle_register(request):
    try:
        data = await request.json()
        device_id = data.get('device_id')
        port = data.get('port')
        mode = data.get('mode', 'direct') # 'direct' or 'tunnel'
        
        # Get IP from request (Public IP)
        peer_ip = request.remote
        
        # Allow client to override IP
        if 'ip' in data:
            peer_ip = data['ip']
            
        if not device_id:
            return web.json_response({'status': 'error', 'message': 'Missing device_id'}, status=400)
            
        REGISTRY[device_id] = {
            'ip': peer_ip,
            'port': port,
            'mode': mode,
            'last_seen': time.time()
        }
        
        print(f"Registered Device: {device_id} -> {peer_ip}:{port} [{mode}]")
        return web.json_response({'status': 'ok', 'message': 'Registered'})
        
    except Exception as e:
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)

async def handle_device_tunnel(request):
    """WebSocket endpoint for Controlled Device to maintain persistent connection"""
    device_id = request.match_info.get('device_id')
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    print(f"Device {device_id} connected to tunnel.")
    
    if device_id not in TUNNELS:
        TUNNELS[device_id] = {}
    
    TUNNELS[device_id]['device_ws'] = ws
    
    # Update Registry to show this device is available via tunnel
    REGISTRY[device_id] = {
        'ip': 'tunnel', 
        'port': 0, 
        'mode': 'tunnel',
        'last_seen': time.time() + 31536000 # Long timeout for active connection
    }

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = msg.data
                # If it's a heartbeat
                if data == 'ping':
                    await ws.send_str('pong')
                else:
                    # Forward to Client if connected
                    if 'client_ws' in TUNNELS[device_id]:
                        client_ws = TUNNELS[device_id]['client_ws']
                        if not client_ws.closed:
                            await client_ws.send_str(data)
            elif msg.type == web.WSMsgType.BINARY:
                # Forward binary data (Video) to Client
                if 'client_ws' in TUNNELS[device_id]:
                    client_ws = TUNNELS[device_id]['client_ws']
                    if not client_ws.closed:
                        await client_ws.send_bytes(msg.data)
                        
    except Exception as e:
        print(f"Device Tunnel Error: {e}")
    finally:
        print(f"Device {device_id} disconnected from tunnel.")
        if device_id in TUNNELS:
            del TUNNELS[device_id]
        if device_id in REGISTRY and REGISTRY[device_id]['mode'] == 'tunnel':
            del REGISTRY[device_id]
            
    return ws

async def handle_client_tunnel(request):
    """WebSocket endpoint for Controller Client to connect via relay"""
    device_id = request.match_info.get('device_id')
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    print(f"Client connected to tunnel for {device_id}")
    
    if device_id not in TUNNELS or 'device_ws' not in TUNNELS[device_id]:
        await ws.close(code=4004, message=b"Device not online")
        return ws
        
    TUNNELS[device_id]['client_ws'] = ws
    device_ws = TUNNELS[device_id]['device_ws']
    
    # Notify Device that client connected
    await device_ws.send_str("CLIENT_CONNECTED")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                # Forward commands to Device
                if not device_ws.closed:
                    await device_ws.send_str(msg.data)
            elif msg.type == web.WSMsgType.BINARY:
                 if not device_ws.closed:
                    await device_ws.send_bytes(msg.data)
                    
    except Exception as e:
        print(f"Client Tunnel Error: {e}")
    finally:
        print(f"Client disconnected from tunnel {device_id}")
        if device_id in TUNNELS and 'client_ws' in TUNNELS[device_id]:
            del TUNNELS[device_id]['client_ws']
        # Notify Device
        if not device_ws.closed:
             await device_ws.send_str("CLIENT_DISCONNECTED")
            
    return ws

async def handle_lookup(request):
    device_id = request.match_info.get('device_id')
    
    if device_id in REGISTRY:
        info = REGISTRY[device_id]
        # Check if stale (skip check for tunnel mode as it's active)
        if info.get('mode') != 'tunnel' and time.time() - info['last_seen'] > HEARTBEAT_TIMEOUT:
            del REGISTRY[device_id]
            return web.json_response({'status': 'error', 'message': 'Device offline'}, status=404)
            
        return web.json_response({
            'status': 'ok', 
            'ip': info['ip'], 
            'port': info['port'],
            'mode': info.get('mode', 'direct')
        })
    else:
        return web.json_response({'status': 'error', 'message': 'Device not found'}, status=404)

async def handle_heartbeat(request):
    # Same as register, just updates timestamp
    return await handle_register(request)

async def cleanup_task():
    while True:
        await asyncio.sleep(60)
        now = time.time()
        to_remove = []
        for did, info in REGISTRY.items():
            # Don't expire active tunnels based on timestamp alone (they rely on WS connection)
            if info.get('mode') == 'tunnel':
                if did not in TUNNELS:
                    to_remove.append(did)
            elif now - info['last_seen'] > HEARTBEAT_TIMEOUT:
                to_remove.append(did)
        
        for did in to_remove:
            print(f"Pruning stale device: {did}")
            del REGISTRY[did]

async def init_app():
    app = web.Application()
    app.router.add_post('/register', handle_register)
    app.router.add_post('/heartbeat', handle_heartbeat)
    app.router.add_get('/lookup/{device_id}', handle_lookup)
    
    # Tunnel Endpoints
    app.router.add_get('/device/{device_id}', handle_device_tunnel)
    app.router.add_get('/client/{device_id}', handle_client_tunnel)
    
    # Background task for cleanup
    asyncio.create_task(cleanup_task())
    
    return app

if __name__ == '__main__':
    port = 9000
    print(f"Signal Server running on port {port}...")
    web.run_app(init_app(), port=port)