import asyncio
import websockets
import json
import cv2
import numpy as np
import base64
from ultralytics import YOLO

print("Cargando modelo YOLOv8...")
model = YOLO('yolov8n.pt') 

# Variables globales de estado
parpadeo_hz = 1
nivel_movimiento = "Nulo"
color_hex = "#A855F7"
temp_cpu_pi = 0.0
prev_gray = None  # Guardará el fotograma anterior en blanco y negro

clientes_conectados = set()

async def servidor_ia(websocket):
    global parpadeo_hz, nivel_movimiento, color_hex, temp_cpu_pi, prev_gray
    
    clientes_conectados.add(websocket)
    print(f"Nuevo cliente conectado. Total en la red: {len(clientes_conectados)}")
    
    try:
        async for mensaje in websocket:
            datos = json.loads(mensaje)
            
            if datos.get("tipo") == "telemetria_pi":
                temp_cpu_pi = datos.get("cpu_pi", 0.0)
                frame_b64 = datos.get("video")
                
                if frame_b64:
                    # 1. Decodificar la imagen de la CloudBerry
                    img_bytes = base64.b64decode(frame_b64)
                    np_arr = np.frombuffer(img_bytes, np.uint8)
                    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                    # Preprocesar la imagen para detección de movimiento (Gris y desenfoque)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.GaussianBlur(gray, (21, 21), 0)

                    # 2. Correr la IA para detectar personas
                    resultados = model(frame, conf=0.5, classes=[0], verbose=False)
                    frame_dibujado = resultados[0].plot()

                    # 3. LÓGICA AVANZADA DE MOVIMIENTO (Solo si hay una persona y un fotograma previo)
                    if len(resultados[0].boxes) > 0 and prev_gray is not None:
                        # Calcular la diferencia absoluta entre el fotograma actual y el anterior
                        diferencia_marcos = cv2.absdiff(prev_gray, gray)
                        # Resaltar solo los cambios grandes (elimina el ruido de la cámara)
                        _, umbral = cv2.threshold(diferencia_marcos, 25, 255, cv2.THRESH_BINARY)
                        
                        # Contar cuántos píxeles se movieron
                        pixeles_movidos = cv2.countNonZero(umbral)
                        porcentaje_cambio = (pixeles_movidos / gray.size) * 100

                        # Mapear el porcentaje de cambio directamente a Hz (Rango sensible de 0.2% a 6%)
                        nuevo_hz = min(20, max(1, int(porcentaje_cambio * 3.5)))
                        # Suavizado para que los Hz no salten bruscamente
                        parpadeo_hz = int((parpadeo_hz * 0.5) + (nuevo_hz * 0.5))
                        
                        # Clasificar la intensidad del movimiento
                        if porcentaje_cambio < 0.3: nivel_movimiento = "Nulo"
                        elif porcentaje_cambio < 1.5: nivel_movimiento = "Bajo"
                        elif porcentaje_cambio < 4.0: nivel_movimiento = "Medio"
                        else: nivel_movimiento = "Alto"

                        # --- EXTRAER COLOR DE LA PERSONA DETECTADA ---
                        caja = resultados[0].boxes[0]
                        x1, y1, x2, y2 = map(int, caja.xyxy[0])
                        h_img, w_img, _ = frame.shape
                        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w_img, x2), min(h_img, y2)
                        
                        if x2 > x1 and y2 > y1:
                            recorte = frame[y1:y2, x1:x2]
                            color_promedio_bgr = cv2.resize(recorte, (1, 1))[0][0]
                            b, g, r = map(int, color_promedio_bgr)
                            color_hex = f"#{r:02X}{g:02X}{b:02X}"
                    else:
                        # Si no hay nadie, el movimiento baja gradualmente a cero
                        parpadeo_hz = max(1, int(parpadeo_hz * 0.7))
                        if parpadeo_hz == 1: nivel_movimiento = "Nulo"

                    # Guardar el fotograma actual como el "anterior" para la próxima vuelta
                    prev_gray = gray

                    # 4. Comprimir y mandar al Dashboard y a la Pi
                    _, buffer = cv2.imencode('.jpg', frame_dibujado, [cv2.IMWRITE_JPEG_QUALITY, 60])
                    frame_procesado_b64 = base64.b64encode(buffer).decode('utf-8')

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
        if websocket in clientes_conectados:
            clientes_conectados.remove(websocket)
        print("Un cliente se ha desconectado.")

async def main():
    async with websockets.serve(servidor_ia, "0.0.0.0", 8765):
        print("Servidor Cerebro (Modo Avanzado) iniciado en ws://0.0.0.0:8765")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())