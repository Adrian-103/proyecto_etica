#!/bin/bash
# 1. Asegurar que el Hotspot esté encendido
sudo nmcli connection up Hotspot

# 2. Esperar 5 segundos a que la red se estabilice
sleep 15

# 3. Moverse a la carpeta del proyecto
#cd /home/birria/proyecto_etica # <- Cambia por tu ruta real

# 4. Activar el entorno virtual de Python
#source venv/bin/activate

# 5. Ejecutar el cliente de la Pi
#python cliente_pi.py
