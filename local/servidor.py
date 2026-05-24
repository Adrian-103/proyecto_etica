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
color_hex = "#A855F7"  # Inicia morado por defecto

async def enviar_telemetria(websocket):
    global prev_cx, prev_cy, parpadeo_hz, nivel_movimiento, color_hex
    
    print("¡Dashboard conectado!")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: No se pudo abrir la cámara.")
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            resultados = model(frame, conf=0.5, classes=[0], verbose=False)
            frame_dibujado = resultados[0].plot()

            # --- LÓGICA DE INTELIGENCIA ÉTICA ---
            if len(resultados[0].boxes) > 0:
                # Tomamos los datos de la primera persona que detecte
                caja = resultados[0].boxes[0]
                # Coordenadas de la caja (x1, y1: esquina superior izq | x2, y2: esquina inferior der)
                x1, y1, x2, y2 = map(int, caja.xyxy[0])
                
                # 1. CÁLCULO DE MOVIMIENTO (Centroide)
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                
                if prev_cx != 0 and prev_cy != 0:
                    # Teorema de Pitágoras para sacar la distancia que se movió en píxeles
                    distancia = math.sqrt((cx - prev_cx)**2 + (cy - prev_cy)**2)
                    
                    # Convertimos la distancia a Hz (de 1 a 20)
                    nuevo_hz = min(20, max(1, int(distancia / 4)))
                    # Filtro de suavizado: 70% del valor anterior + 30% del nuevo (evita saltos bruscos)
                    parpadeo_hz = int((parpadeo_hz * 0.7) + (nuevo_hz * 0.3))
                    
                    # Asignar texto según los Hz
                    if parpadeo_hz < 3:
                        nivel_movimiento = "Bajo"
                    elif parpadeo_hz < 10:
                        nivel_movimiento = "Medio"
                    else:
                        nivel_movimiento = "Alto"
                
                # Guardamos la posición actual para el siguiente fotograma
                prev_cx, prev_cy = cx, cy

                # 2. EXTRACCIÓN DE COLOR
                # Aseguramos que el recorte no se salga de los límites de la pantalla
                h_img, w_img, _ = frame.shape
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w_img, x2), min(h_img, y2)
                
                if x2 > x1 and y2 > y1:
                    # Recortamos la imagen original solo donde está la persona
                    recorte = frame[y1:y2, x1:x2]
                    # Truco de OpenCV: Reducir la imagen a 1x1 píxel promedia todos sus colores al instante
                    color_promedio_bgr = cv2.resize(recorte, (1, 1))[0][0]
                    # OpenCV usa BGR, lo pasamos a RGB
                    b, g, r = map(int, color_promedio_bgr)
                    # Lo convertimos a código Hexadecimal (#RRGGBB) para React
                    color_hex = f"#{r:02X}{g:02X}{b:02X}"

            else:
                # Si no hay nadie en pantalla, bajamos el movimiento poco a poco hasta 1 Hz
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
                # La temperatura sí sigue siendo dummy, porque esa forzosamente viene del hardware de la Pi
                "cpu": 45.5, 
                "video": frame_base64
            }

            await websocket.send(json.dumps(datos))
            await asyncio.sleep(0.05) 
            
    except websockets.exceptions.ConnectionClosed:
        print("Dashboard desconectado.")
    finally:
        cap.release()

async def main():
    async with websockets.serve(enviar_telemetria, "localhost", 8765):
        print("Servidor de IA iniciado en ws://localhost:8765")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())