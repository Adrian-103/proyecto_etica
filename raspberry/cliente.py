import asyncio
import websockets
import json
import time

# --- CONFIGURACIÓN ---
# Cambia esto por la IP local de tu computadora (ej. "192.168.1.25")
IP_DE_TU_PC = "TU_IP_AQUI" 
PUERTO = 8765

def leer_temperatura_cpu():
    """Lee la temperatura real del procesador de la Raspberry Pi en Linux"""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = float(f.read()) / 1000.0
        return round(temp, 1)
    except Exception as e:
        return 0.0

async def conectar_al_cerebro():
    url = f"ws://{IP_DE_TU_PC}:{PUERTO}"
    print(f"Intentando conectar al cerebro en {url}...")

    try:
        async with websockets.connect(url) as websocket:
            print("¡Conexión establecida con la PC!")
            
            while True:
                # 1. LEER ÓRDENES: Escuchamos lo que nos manda la PC
                try:
                    # Usamos wait_for para no quedarnos bloqueados esperando eternamente
                    mensaje_pc = await asyncio.wait_for(websocket.recv(), timeout=0.5)
                    datos_ia = json.loads(mensaje_pc)
                    
                    color = datos_ia.get("color")
                    hz = datos_ia.get("parpadeo")
                    
                    # Por ahora solo lo imprimimos, luego aquí pondremos el código de la tira LED
                    print(f"[ÓRDEN RECIBIDA] Color: {color} | Parpadeo: {hz} Hz")
                    
                except asyncio.TimeoutError:
                    pass # Si no hay mensaje nuevo en este medio segundo, no pasa nada
                
                # 2. ENVIAR TELEMETRÍA: Le mandamos la temperatura real a la PC
                temp_real = leer_temperatura_cpu()
                datos_pi = {
                    "tipo": "telemetria_hardware",
                    "cpu_pi": temp_real
                }
                await websocket.send(json.dumps(datos_pi))
                
                await asyncio.sleep(0.1)

    except ConnectionRefusedError:
        print("Error: No se pudo conectar. ¿Está corriendo el servidor en la PC y es la IP correcta?")
    except websockets.exceptions.ConnectionClosed:
        print("Desconectado del cerebro.")

if __name__ == "__main__":
    asyncio.run(conectar_al_cerebro())
