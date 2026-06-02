import asyncio
import websockets
import json
import cv2
import base64
import time
import board
import neopixel

# --- CONFIGURACIÓN ---
IP_DE_TU_PC = "10.42.0.203" # <- PON TU IP DE OULUNSALO AQUÍ
PUERTO = 8765

# --- CONFIGURACIÓN DE LEDs ---
NUM_PIXELS = 160
# Usamos brightness=1.0 sabiendo que el hardware lo limita de forma segura
pixels = neopixel.NeoPixel(board.D18, NUM_PIXELS, brightness=1.0, auto_write=False)

def leer_temperatura_cpu():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read()) / 1000.0
        return round(temp, 1)
    except Exception as e:
        return 0.0

def hex_a_rgb(hex_color):
    """Convierte un color '#RRGGBB' a una tupla (R, G, B) para los LEDs"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

async def nodo_terminal():
    url = f"ws://{IP_DE_TU_PC}:{PUERTO}"
    print(f"Conectando al Cerebro en {url}...")
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("Error: No se detectó ninguna cámara en la Raspberry Pi.")
        return

    # Variables para controlar el parpadeo sin pausar el video
    estado_led = False
    ultimo_cambio = time.time()

    try:
        async with websockets.connect(url) as websocket:
            print("¡Conectado exitosamente!")
            
            while True:
                # 1. Tomar y enviar la foto
                ret, frame = cap.read()
                if not ret:
                    continue
                
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                
                paquete_salida = {
                    "tipo": "telemetria_pi",
                    "cpu_pi": leer_temperatura_cpu(),
                    "video": frame_base64
                }
                await websocket.send(json.dumps(paquete_salida))
                
                # 2. Recibir órdenes y controlar los LEDs
                try:
                    # Usamos un timeout súper corto para no trabar la cámara
                    mensaje_ia = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    datos_ia = json.loads(mensaje_ia)
                    
                    color_hex = datos_ia.get("color", "#000000")
                    hz = datos_ia.get("parpadeo", 1)
                    
                    print(f"[CloudBerry DICE] Color: {color_hex} | Parpadeo: {hz} Hz")
                    
                    # Convertir el color para la tira LED
                    rgb = hex_a_rgb(color_hex)
                    
                    # Lógica de parpadeo (Cronómetro no bloqueante)
                    tiempo_actual = time.time()
                    periodo = 1.0 / hz # Cuánto dura un ciclo completo de parpadeo
                    mitad_periodo = periodo / 2.0 # Cuánto tiempo debe estar encendido/apagado
                    
                    if (tiempo_actual - ultimo_cambio) >= mitad_periodo:
                        estado_led = not estado_led # Cambiamos de encendido a apagado o viceversa
                        ultimo_cambio = tiempo_actual
                        
                        if estado_led:
                            pixels.fill(rgb)
                        else:
                            pixels.fill((0, 0, 0)) # Apagado
                        
                        pixels.show()
                    
                except asyncio.TimeoutError:
                    # Si no llega mensaje a tiempo, no hacemos nada y seguimos grabando
                    print("Timeout error")
                except Exception as e:
                    print(f"Error raro al recibir: {e}")
                
    except Exception as e:
        print(f"Error de conexión: {e}")
    finally:
        cap.release()
        # Apagar los LEDs si el programa se cierra
        pixels.fill((0, 0, 0))
        pixels.show()

if __name__ == "__main__":
    asyncio.run(nodo_terminal())