import asyncio
import websockets
import json
import cv2
import base64
import time
import board
import neopixel
from picamera2 import Picamera2  # <--- El nuevo motor oficial de la Pi 5

# --- CONFIGURACIÓN ---
IP_DE_TU_PC = "10.42.0.203" # <- Tu IP de Oulunsalo
PUERTO = 8765

# --- CONFIGURACIÓN DE LEDs ---
NUM_PIXELS = 160
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
    
    # --- INICIALIZACIÓN DE PICAMERA2 (PI 5) ---
    print("Iniciando Picamera2...")
    picam = Picamera2()
    
    # Configuramos el formato RGB888 que la Pi 5 ama, a una resolución óptima para la IA
    config = picam.create_preview_configuration(main={"format": "RGB888", "size": (640, 480)})
    picam.configure(config)
    
    print("Arrancando el sensor de la cámara...")
    picam.start()
    time.sleep(1) # Pequeña pausa para estabilizar la exposición
    print("¡Cámara lista y activa!")

    # Variables para controlar el parpadeo sin pausar el video
    estado_led = False
    ultimo_cambio = time.time()
    
    # Valores por defecto para los LEDs por si tarda en llegar la primera orden
    rgb = (0, 0, 0)
    hz = 1

    try:
        async with websockets.connect(url) as websocket:
            print("¡Conectado exitosamente al servidor de la PC!")
            
            while True:
                # 1. Tomar foto usando el motor nativo de la Pi 5
                frame_rgb = picam.capture_array()
                if frame_rgb is None:
                    continue
                
                # Convertimos el formato de RGB (Pi 5) a BGR (El idioma que habla OpenCV)
                frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                
                # Comprimir a JPG para mandarlo por la red sin saturarla
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                
                # Preparar el paquete con telemetría en tiempo real
                paquete_salida = {
                    "tipo": "telemetria_pi",
                    "cpu_pi": leer_temperatura_cpu(),
                    "video": frame_base64
                }
                await websocket.send(json.dumps(paquete_salida))
                
                # 2. Recibir órdenes y controlar los LEDs
                try:
                    # Le damos 2 segundos de tolerancia a la PC para procesar YOLOv8. 
                    # Si responde antes, el código avanza de inmediato sin esperar los 2 segundos.
                    mensaje_ia = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    datos_ia = json.loads(mensaje_ia)
                    
                    color_hex = datos_ia.get("color", "#000000")
                    hz = datos_ia.get("parpadeo", 1)
                    
                    print(f"[CloudBerry DICE] Color: {color_hex} | Parpadeo: {hz} Hz")
                    rgb = hex_a_rgb(color_hex)
                    
                except asyncio.TimeoutError:
                    # Si la PC se tarda un poco, imprimimos aviso pero NO detenemos el envío de video
                    print("⚠️ Esperando respuesta de la IA (Timeout temporal)...")
                except Exception as e:
                    print(f"Error al procesar mensaje del servidor: {e}")
                
                # 3. Lógica de parpadeo (Cronómetro no bloqueante)
                # Se ejecuta en cada ciclo del bucle usando los últimos valores estables recibidos
                tiempo_actual = time.time()
                periodo = 1.0 / hz
                mitad_periodo = periodo / 2.0
                
                if (tiempo_actual - ultimo_cambio) >= mitad_periodo:
                    estado_led = not estado_led
                    ultimo_cambio = tiempo_actual
                    
                    if estado_led and rgb != (0,0,0):
                        pixels.fill(rgb)
                    else:
                        pixels.fill((0, 0, 0)) # Apagado
                    
                    pixels.show()
                
    except Exception as e:
        print(f"Error de conexión: {e}")
    finally:
        # APAGADO SEGURO DE HARDWARE
        print("\nCerrando de forma segura...")
        picam.stop() # Apaga el sensor de la cámara flex
        pixels.fill((0, 0, 0)) # Apaga la tira de LEDs por seguridad
        pixels.show()

if __name__ == "__main__":
    asyncio.run(nodo_terminal())