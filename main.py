"""Hand Figure: figura de neón sobre la mano, en una ventana nativa."""
import os

# Sin esto, Media Foundation tarda unos 7 s en abrir la cámara en Windows (medido: 6.8 s frente a
# 1.7 s). Tiene que definirse antes de importar cv2.
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import argparse
import sys
import time

import cv2

import config
from camara import Camara
from figuras import Figura
from manos import Detector, Seguidor
from render import Render


def _argumentos():
    analizador = argparse.ArgumentParser(description="Figura de neón que flota sobre la mano.")
    analizador.add_argument("--camara", type=int, default=config.CAMARA_INDICE, help="índice de la cámara")
    analizador.add_argument("--resolucion", default=f"{config.ANCHO}x{config.ALTO}",
                            help="tamaño de la ventana, por ejemplo 1280x720")
    args = analizador.parse_args()
    try:
        ancho, alto = (int(v) for v in args.resolucion.lower().split("x"))
    except ValueError:
        analizador.error("la resolución debe tener la forma 1280x720")
    return args.camara, ancho, alto


def _estado_provisional(render, seguidor):
    """Rótulos de diagnóstico de la etapa 2; los textos definitivos llegan con la etapa 4."""
    principal, segunda = seguidor.principal, seguidor.segunda
    for mano, rotulo in ((principal, "principal"), (segunda, "segunda")):
        if mano is not None and mano.perdida == 0:
            x, y = mano.puntos[0, 0] * render.ancho, mano.puntos[0, 1] * render.alto
            render.texto_provisional(f"{rotulo} #{mano.id}: {mano.dedos}",
                                     min(max(x - 50, 4), render.ancho - 150), min(y + 22, render.alto - 36))
    if principal is None:
        estado = "sin manos"
    else:
        estado = f"mano principal: {principal.dedos} | segunda mano: "
        estado += "no" if segunda is None else f"escala x{seguidor.escala:.2f}"
    render.texto_provisional(estado, 14, render.alto - 14)


def main():
    indice, ancho, alto = _argumentos()
    detector = Detector()
    try:
        camara = Camara(indice, ancho, alto, config.CAMARA_FPS)
    except RuntimeError as error:
        detector.cerrar()
        sys.exit(str(error))
    print(f"cámara {indice}: {camara.ancho}x{camara.alto} a {camara.fps:.0f} fps ({camara.backend})", flush=True)

    render = Render(ancho, alto)
    seguidor = Seguidor(alto / ancho)
    figura = Figura()
    cv2.namedWindow(config.TITULO, cv2.WINDOW_AUTOSIZE)

    # El dibujo lleva su propio reloj: cada vuelta usa el último fotograma que haya, sea nuevo o no.
    periodo = 1.0 / config.FPS_OBJETIVO
    siguiente = time.perf_counter()
    visto, ultima_senal = 0, siguiente
    deteccion_vista, dibujo_anterior = 0, siguiente
    cuadros, capturas, resultados, peor = 0, 0, 0, 0.0
    reloj, cpu, anterior = siguiente, time.process_time(), siguiente
    try:
        while True:
            fotograma, numero = camara.leer()
            ahora = time.perf_counter()
            render.fondo(fotograma)
            if numero != visto:
                visto, ultima_senal = numero, ahora
                capturas += 1
                detector.enviar(render.lienzo)
            elif ahora - ultima_senal > 3.0:
                print("La cámara dejó de entregar fotogramas.")
                break

            # El seguimiento avanza una vez por resultado del detector, no una vez por dibujo.
            numero_deteccion, detecciones = detector.resultado
            if numero_deteccion != deteccion_vista:
                deteccion_vista = numero_deteccion
                resultados += 1
                seguidor.actualizar(detecciones)

            render.esqueleto(seguidor.visibles)
            figura.avanzar(ahora - dibujo_anterior, seguidor.principal, seguidor.escala, ancho)
            dibujo_anterior = ahora
            if figura.centro is not None:
                render.figura(figura.proyectar(ancho), figura.color)
            _estado_provisional(render, seguidor)
            cv2.imshow(config.TITULO, render.lienzo)

            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (ord("q"), ord("Q"), 27):
                break
            if cv2.getWindowProperty(config.TITULO, cv2.WND_PROP_VISIBLE) < 1:  # ventana cerrada
                break

            # Duerme hasta el siguiente turno; si se atrasó, no intenta recuperar lo perdido.
            siguiente += periodo
            resto = siguiente - time.perf_counter()
            if resto > 0:
                time.sleep(resto)
            elif resto < -periodo:
                siguiente = time.perf_counter()

            ahora = time.perf_counter()
            cuadros += 1
            peor = max(peor, ahora - anterior)
            anterior = ahora
            if ahora - reloj >= 1.0:
                lapso = ahora - reloj
                cpu_ahora = time.process_time()
                print(f"{cuadros / lapso:5.1f} fps (peor intervalo {peor * 1000:4.1f} ms) · "
                      f"cámara {capturas / lapso:4.1f}/s · "
                      f"detección {detector.ms:4.1f} ms ({resultados / lapso:4.1f}/s) · "
                      f"manos {len(seguidor.visibles)} · cpu {(cpu_ahora - cpu) / lapso * 100:3.0f} % de un núcleo",
                      flush=True)
                cuadros, capturas, resultados, peor = 0, 0, 0, 0.0
                reloj, cpu = ahora, cpu_ahora
    except KeyboardInterrupt:
        pass
    finally:
        camara.cerrar()
        detector.cerrar()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
