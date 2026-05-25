import asyncio
import websockets
import json
import cv2
import numpy as np
import base64
import math
from ultralytics import YOLO

print("Cargando modelo YOLOv8...")
model = YOLO('yolov8n.pt') 

# Variables globales
prev_cx, prev_cy = 0, 0
parpadeo_hz = 1
nivel_movimiento = "Nulo"
color_hex = "#A855F7"
temp_cpu_pi = 0.0

# Para saber quiénes están conectados (React y Raspberry)
clientes_conectados = set()

async def servidor_ia(websocket):
    global prev_cx, prev_cy, parpadeo_hz, nivel_movimiento, color_hex, temp_cpu_pi
    
    clientes_conectados.add(websocket)
    print(f"Nuevo cliente conectado. Total en la red: {len(clientes_conectados)}")
    
    try:
        async for mensaje in websocket:
            datos = json.loads(mensaje)
            
            # Si el mensaje viene de la CloudBerry (trae el video crudo)
            if datos.get("tipo") == "telemetria_pi":
                temp_cpu_pi = datos.get("cpu_pi", 0.0)
                frame_b64 = datos.get("video")
                
                if frame_b64:
                    # 1. Decodificar la imagen enviada por Wi-Fi
                    img_bytes = base64.b64decode(frame_b64)
                    np_arr = np.frombuffer(img_bytes, np.uint8)
                    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                    # 2. IA (YOLO) hace su magia con la imagen de la Pi
                    resultados = model(frame, conf=0.5, classes=[0], verbose=False)
                    frame_dibujado = resultados[0].plot()

                    # --- LÓGICA DE INTELIGENCIA ---
                    if len(resultados[0].boxes) > 0:
                        caja = resultados[0].boxes[0]
                        x1, y1, x2, y2 = map(int, caja.xyxy[0])
                        
                        cx = (x1 + x2) // 2
                        cy = (y1 + y2) // 2
                        
                        if prev_cx != 0 and prev_cy != 0:
                            distancia = math.sqrt((cx - prev_cx)**2 + (cy - prev_cy)**2)
                            nuevo_hz = min(20, max(1, int(distancia / 4)))
                            parpadeo_hz = int((parpadeo_hz * 0.7) + (nuevo_hz * 0.3))
                            
                            if parpadeo_hz < 3: nivel_movimiento = "Bajo"
                            elif parpadeo_hz < 10: nivel_movimiento = "Medio"
                            else: nivel_movimiento = "Alto"
                        prev_cx, prev_cy = cx, cy

                        h_img, w_img, _ = frame.shape
                        x1, y1 = max(0, x1), max(0, y1)
                        x2, y2 = min(w_img, x2), min(h_img, y2)
                        
                        if x2 > x1 and y2 > y1:
                            recorte = frame[y1:y2, x1:x2]
                            color_promedio_bgr = cv2.resize(recorte, (1, 1))[0][0]
                            b, g, r = map(int, color_promedio_bgr)
                            color_hex = f"#{r:02X}{g:02X}{b:02X}"
                    else:
                        parpadeo_hz = max(1, int(parpadeo_hz * 0.8))
                        if parpadeo_hz == 1: nivel_movimiento = "Nulo"
                        prev_cx, prev_cy = 0, 0
                    # --- FIN LÓGICA ---

                    # 3. Recodificar la imagen ya procesada con las cajas
                    _, buffer = cv2.imencode('.jpg', frame_dibujado, [cv2.IMWRITE_JPEG_QUALITY, 60])
                    frame_procesado_b64 = base64.b64encode(buffer).decode('utf-8')

                    # 4. Difundir los resultados a la red (React y Raspberry)
                    respuesta = {
                        "color": color_hex,
                        "movimiento": nivel_movimiento,
                        "parpadeo": parpadeo_hz,
                        "cpu": temp_cpu_pi,
                        "video": frame_procesado_b64
                    }
                    
                    mensaje_respuesta = json.dumps(respuesta)
                    websockets_a_borrar = set()
                    
                    for cliente in clientes_conectados:
                        try:
                            await cliente.send(mensaje_respuesta)
                        except websockets.exceptions.ConnectionClosed:
                            websockets_a_borrar.add(cliente)
                    
                    clientes_conectados.difference_update(websockets_a_borrar)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clientes_conectados.remove(websocket)
        print("Un cliente se ha desconectado.")

async def main():
    async with websockets.serve(servidor_ia, "0.0.0.0", 8765):
        print("Servidor Cerebro iniciado en ws://0.0.0.0:8765")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())