import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, X } from 'lucide-react'

const steps = [
  { target: '[data-tour="floorplan"]', title: 'Empieza por un plano', body: 'Selecciona un piso. Rumbo incluye una Clínica Santa María de ejemplo con geometría, nodos, puntos, conexiones y QR ya configurados para que puedas inspeccionarlos.' },
  { target: '[data-tour="scale"]', title: 'Calibrar convierte píxeles en metros', body: 'Marca dos puntos cuya distancia real conozcas y escribe los metros. Desde ese momento el mapa tiene una escala física y Medir puede trabajar en metros.' },
  { target: '[data-tour="measure"]', title: 'Medir valida el plano', body: 'Mide cualquier segmento después de calibrar. Sirve para comprobar pasillos, separaciones y que la escala del plano sea coherente.' },
  { target: '[data-tour="wall"]', title: 'Pared describe la geometría', body: 'Traza límites físicos del edificio. Una pared no es una ruta: sirve para estructurar el espacio y más adelante permitirá generar la representación 3D.' },
  { target: '[data-tour="node"]', title: 'Nodo es un punto del recorrido', body: 'Coloca nodos sobre zonas transitables y en lugares donde el usuario puede girar, entrar, salir o tomar una decisión. Son los vértices del grafo.' },
  { target: '[data-tour="poi"]', title: 'Punto es un destino', body: 'Un Punto de Interés (POI) es algo que el usuario busca, como Recepción o Consultorio 101. Se asocia a un nodo para que Rumbo sepa cómo llegar.' },
  { target: '[data-tour="edge"]', title: 'Conexión crea el camino', body: 'Haz clic en dos nodos para indicar que se puede transitar entre ellos. Las conexiones son las aristas que usa el algoritmo para calcular rutas.' },
  { target: '[data-tour="connector"]', title: 'Entre pisos une dos mapas', body: 'Un ascensor, escalera o rampa conecta un nodo del piso actual con un nodo de otro piso. Así el grafo puede calcular recorridos multi-piso.' },
  { target: '[data-tour="qr"]', title: 'QR fija la ubicación del usuario', body: 'Asocia un QR físico a un nodo. Al escanearlo, la app sabrá exactamente en qué punto del mapa se encuentra el usuario sin necesitar BLE en el MVP.' },
  { target: '[data-tour="navigation"]', title: 'Navegación usa todo lo anterior', body: 'El módulo Navegación toma nodos, conexiones, POIs y conectores verticales para calcular la ruta más corta y visualizarla sobre el plano.' },
]

export function ModelingTutorial({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [index, setIndex] = useState(0)
  const step = steps[index]
  const [rect, setRect] = useState<DOMRect | null>(null)
  useEffect(() => { if (open) setIndex(0) }, [open])
  useEffect(() => {
    if (!open) return
    const target = document.querySelector<HTMLElement>(step.target)
    if (!target) { setRect(null); return }
    target.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' })
    target.classList.add('tour-highlight')
    const update = () => setRect(target.getBoundingClientRect())
    update(); window.addEventListener('resize', update); window.addEventListener('scroll', update, true)
    return () => { target.classList.remove('tour-highlight'); window.removeEventListener('resize', update); window.removeEventListener('scroll', update, true) }
  }, [open, step])
  const style = useMemo(() => {
    if (!rect) return { top: 110, left: Math.max(24, window.innerWidth / 2 - 180) }
    const width = 360
    const left = Math.min(Math.max(18, rect.left), window.innerWidth - width - 18)
    const below = rect.bottom + 14
    const top = below + 230 < window.innerHeight ? below : Math.max(18, rect.top - 230)
    return { top, left }
  }, [rect])
  if (!open) return null
  const finish = () => { localStorage.setItem('rumbo:modeling-tour-seen', '1'); onClose() }
  return (
    <div className="tour-layer" aria-live="polite">
      <button className="tour-dismiss-area" aria-label="Cerrar tutorial" onClick={finish} />
      <section className="tour-card" style={style}>
        <div className="tour-card-top"><span>{index + 1} de {steps.length}</span><button className="tour-close" onClick={finish} aria-label="Cerrar"><X size={17} /></button></div>
        <h3>{step.title}</h3><p>{step.body}</p>
        <div className="tour-progress" aria-hidden="true">{steps.map((_, i) => <span key={i} className={i <= index ? 'done' : ''} />)}</div>
        <div className="tour-actions">
          <button className="button" disabled={index === 0} onClick={() => setIndex((value) => value - 1)}><ArrowLeft size={15}/> Anterior</button>
          {index === steps.length - 1 ? <button className="button primary" onClick={finish}><Check size={15}/> Listo</button> : <button className="button primary" onClick={() => setIndex((value) => value + 1)}>Siguiente <ArrowRight size={15}/></button>}
        </div>
      </section>
    </div>
  )
}
