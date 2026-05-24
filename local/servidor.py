import asyncio
import websockets
import json
import cv2
import base64
import math
from ultralytics import YOLO

print("Cargando modelo YOLOv8...")
model = YOLO('yolov8n.pt') 

# Variables globales para mantener el rastro entre fotogramas
prev_cx, prev_cy = 0, 0
parpadeo_hz = 1
nivel_movimiento = "Nulo"
color_hex = "#A855F7"
temp_cpu_pi = 0.0 # <--- NUEVA VARIABLE PARA LA TEMPERATURA DE LA PI

async def enviar_telemetria(websocket):
    global prev_cx, prev_cy, parpadeo_hz, nivel_movimiento, color_hex, temp_cpu_pi
    
    print("¡Un cliente se ha conectado!")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: No se pudo abrir la cámara.")
        return

    try:
        while True:
            # --- NUEVO: ESCUCHAR A LA RASPBERRY PI ---
            try:
                # Esperamos máximo 0.01 segundos a ver si la Pi nos manda su temperatura.
                # Si no manda nada, el código sigue de largo para no trabar el video.
                mensaje_entrante = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                datos_recibidos = json.loads(mensaje_entrante)
                
                # Si el mensaje es telemetría, actualizamos la variable
                if datos_recibidos.get("tipo") == "telemetria_hardware":
                    temp_cpu_pi = datos_recibidos.get("cpu_pi", 0.0)
            except asyncio.TimeoutError:
                pass # Todo normal, no hay mensajes en esta fracción de segundo
            except Exception as e:
                pass # Por si llega un mensaje mal formado
            # ----------------------------------------

            ret, frame = cap.read()
            if not ret:
                break
                
            resultados = model(frame, conf=0.5, classes=[0], verbose=False)
            frame_dibujado = resultados[0].plot()

            # --- LÓGICA DE INTELIGENCIA ÉTICA ---
            if len(resultados[0].boxes) > 0:
                caja = resultados[0].boxes[0]
                x1, y1, x2, y2 = map(int, caja.xyxy[0])
                
                # 1. CÁLCULO DE MOVIMIENTO
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                
                if prev_cx != 0 and prev_cy != 0:
                    distancia = math.sqrt((cx - prev_cx)**2 + (cy - prev_cy)**2)
                    nuevo_hz = min(20, max(1, int(distancia / 4)))
                    parpadeo_hz = int((parpadeo_hz * 0.7) + (nuevo_hz * 0.3))
                    
                    if parpadeo_hz < 3:
                        nivel_movimiento = "Bajo"
                    elif parpadeo_hz < 10:
                        nivel_movimiento = "Medio"
                    else:
                        nivel_movimiento = "Alto"
                
                prev_cx, prev_cy = cx, cy

                # 2. EXTRACCIÓN DE COLOR
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
                if parpadeo_hz == 1:
                    nivel_movimiento = "Nulo"
                prev_cx, prev_cy = 0, 0

            # --- FIN LÓGICA DE INTELIGENCIA ---

            # Codificamos la imagen para mandarla a React
            _, buffer = cv2.imencode('.jpg', frame_dibujado, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_base64 = base64.b64encode(buffer).decode('utf-8')

            # Empaquetamos todo
            datos = {
                "color": color_hex,
                "movimiento": nivel_movimiento,
                "parpadeo": parpadeo_hz,
                "cpu": temp_cpu_pi, # <--- AHORA ENVIAMOS LA TEMPERATURA REAL DE LA PI A REACT
                "video": frame_base64
            }

            await websocket.send(json.dumps(datos))
            await asyncio.sleep(0.05) 
            
    except websockets.exceptions.ConnectionClosed:
        print("Cliente desconectado.")
    finally:
        cap.release()

async def main():
    # CAMBIO IMPORTANTE: Al usar "0.0.0.0" abrimos el servidor a tu red Wi-Fi
    async with websockets.serve(enviar_telemetria, "0.0.0.0", 8765):
        print("Servidor de IA iniciado en ws://0.0.0.0:8765")
        print("Esperando conexión de React (Local) y de Raspberry Pi (Wi-Fi)...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())