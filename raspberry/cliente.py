import asyncio
import websockets
import json
import cv2
import base64

# --- CONFIGURACIÓN ---
IP_DE_TU_PC = "10.42.0.203" # <- PON TU IP DE OULUNSALO AQUÍ
PUERTO = 8765

def leer_temperatura_cpu():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read()) / 1000.0
        return round(temp, 1)
    except Exception as e:
        return 0.0

async def nodo_terminal():
    url = f"ws://{IP_DE_TU_PC}:{PUERTO}"
    print(f"Conectando al Cerebro en {url}...")
    
    # Abrimos la cámara de la Raspberry Pi
    cap = cv2.VideoCapture(0)
    # Bajamos la resolución a 640x480 para no saturar el Wi-Fi
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("Error: No se detectó ninguna cámara en la Raspberry Pi.")
        return

    try:
        async with websockets.connect(url) as websocket:
            print("¡Conectado exitosamente!")
            
            while True:
                # 1. Tomar la foto
                ret, frame = cap.read()
                if not ret:
                    continue
                
                # 2. Comprimirla para envío rápido por red
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                
                # 3. Enviar todo al Cerebro
                paquete_salida = {
                    "tipo": "telemetria_pi",
                    "cpu_pi": leer_temperatura_cpu(),
                    "video": frame_base64
                }
                await websocket.send(json.dumps(paquete_salida))
                
                # 4. Recibir las órdenes mágicas procesadas por la IA
                try:
                    mensaje_ia = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    datos_ia = json.loads(mensaje_ia)
                    
                    color = datos_ia.get("color")
                    hz = datos_ia.get("parpadeo")
                    
                    print(f"[IA DICE] Color: {color} | Parpadeo: {hz} Hz")
                    
                except asyncio.TimeoutError:
                    pass
                
                # Pequeña pausa para mantener la fluidez de red a ~20 FPS
                await asyncio.sleep(0.05)

    except Exception as e:
        print(f"Error de conexión: {e}")
    finally:
        cap.release()

if __name__ == "__main__":
    asyncio.run(nodo_terminal())