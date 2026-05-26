import { useState, useEffect } from 'react'

function App() {
  const [colorHex, setColorHex] = useState("#A855F7"); 
  const [movimiento, setMovimiento] = useState("Esperando...");
  const [parpadeoHz, setParpadeoHz] = useState(0);
  const [tempCPU, setTempCPU] = useState(0.0);
  const [videoFrame, setVideoFrame] = useState(null);

  useEffect(() => {
    // Nos conectamos al servidor de Python
    const ws = new WebSocket('ws://localhost:8765');

    ws.onopen = () => {
      console.log('Conectado al servidor de telemetría');
    };

    // Cada vez que Python mande un mensaje, actualizamos los datos
    ws.onmessage = (evento) => {
      const datos = JSON.parse(evento.data);
      setColorHex(datos.color);
      setMovimiento(datos.movimiento);
      setParpadeoHz(datos.parpadeo);
      setTempCPU(datos.cpu);
      
      // Si el servidor nos mandó un fotograma, lo guardamos
      if (datos.video) {
        setVideoFrame(datos.video);
      }
    };

    ws.onclose = () => {
      console.log('Desconectado del servidor');
    };

    // Limpiamos la conexión si cerramos la ventana
    return () => ws.close();
  }, []);

  return (
    <div className="min-h-screen p-8 font-mono bg-slate-950 flex flex-col items-center justify-center">
      
      <h1 className="text-4xl font-bold mb-8 text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-cyan-400">
        // TÉRMINAL DE ÉTICA_
      </h1>

      {/* Contenedor Principal Grid */}
      <div className="grid grid-cols-3 gap-6 w-full max-w-6xl">
        
        {/* Panel 1: Video Feed (Ocupa 2 columnas) */}
        <div className="col-span-2 bg-white/5 backdrop-blur-md border border-purple-500/50 rounded-xl p-4 shadow-[0_0_20px_rgba(168,85,247,0.2)]">
          <h2 className="text-purple-400 mb-2 border-b border-purple-500/30 pb-2">{'>>'} YOLO_VISION_STREAM</h2>
          <div className="w-full h-96 bg-black rounded-lg border border-slate-800 flex items-center justify-center overflow-hidden">
             {videoFrame ? (
               <img src={`data:image/jpeg;base64,${videoFrame}`} alt="YOLO Stream" className="w-full h-full object-cover" />
             ) : (
               <span className="text-slate-600 animate-pulse">Esperando señal de video...</span>
             )}
          </div>
        </div>

        {/* Columna Derecha: Telemetría */}
        <div className="flex flex-col gap-6">
          
          {/* Panel 2: Color Predominante */}
          <div className="bg-white/5 backdrop-blur-md border border-cyan-500/50 rounded-xl p-4 shadow-[0_0_20px_rgba(6,182,212,0.2)]">
            <h2 className="text-cyan-400 mb-2 border-b border-cyan-500/30 pb-2">{'>>'} COLOR_DETECTADO</h2>
            <div className="flex items-center gap-4 mt-4">
              <div 
                className="w-16 h-16 rounded-full border-2 border-white/20 shadow-lg"
                style={{ backgroundColor: colorHex }}
              ></div>
              <span className="text-2xl font-bold">{colorHex}</span>
            </div>
          </div>

          {/* Panel 3: Estado de Movimiento */}
          <div className="bg-white/5 backdrop-blur-md border border-emerald-500/50 rounded-xl p-4 shadow-[0_0_20px_rgba(16,185,129,0.2)]">
            <h2 className="text-emerald-400 mb-2 border-b border-emerald-500/30 pb-2">{'>>'} ACTIVIDAD_FÍSICA</h2>
            <div className="mt-4">
              <p className="text-lg">Nivel: <span className="font-bold text-emerald-300">{movimiento}</span></p>
              <p className="text-lg mt-2">Frecuencia LED: <span className="font-bold text-emerald-300">{parpadeoHz} Hz</span></p>
            </div>
          </div>

          {/* Panel 4: Hardware RPi5 */}
          <div className="bg-white/5 backdrop-blur-md border border-rose-500/50 rounded-xl p-4 shadow-[0_0_20px_rgba(244,63,94,0.2)]">
            <h2 className="text-rose-400 mb-2 border-b border-rose-500/30 pb-2">{'>>'} TELEMETRÍA_RPi5</h2>
            <div className="mt-4 flex items-center justify-between">
              <span className="text-lg">Temp CPU:</span>
              <span className={`text-2xl font-bold ${tempCPU > 75 ? 'text-red-500 animate-pulse' : 'text-rose-300'}`}>
                {tempCPU}°C
              </span>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}

export default App