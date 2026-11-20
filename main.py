"""Yunara: sus cuentas giran alrededor de tu cuello, en una ventana nativa."""
import os

# Sin esto, Media Foundation tarda unos 7 s en abrir la cámara en Windows (medido: 6.8 s frente a
# 1.7 s). Tiene que definirse antes de importar cv2.
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import argparse
import sys
import time

import cv2

# OpenCV reparte cada operación entre todos los núcleos, y en zonas pequeñas como las de las cuentas los
# hilos pasan más tiempo esperando que trabajando: medido, 11.4 ms de CPU por dibujo frente a 3.1 con
# un solo hilo, sin diferencia en el tiempo real. La detección de MediaPipe usa sus propios hilos.
cv2.setNumThreads(1)

import config
from camara import Camara
from cuentas import Cuentas
from cuerpo import Cuerpo, DetectorCuerpo
from deteccion import Preparador
from manos import DetectorManos, Seguidor
from render import Render


def _argumentos():
    analizador = argparse.ArgumentParser(description="Las cuentas de Yunara giran alrededor de tu cuello.")
    analizador.add_argument("--camara", type=int, default=config.CAMARA_INDICE, help="índice de la cámara")
    analizador.add_argument("--resolucion", default=f"{config.ANCHO}x{config.ALTO}",
                            help="tamaño de la ventana, por ejemplo 1280x720")
    args = analizador.parse_args()
    try:
        ancho, alto = (int(v) for v in args.resolucion.lower().split("x"))
    except ValueError:
        analizador.error("la resolución debe tener la forma 1280x720")
    return args.camara, ancho, alto


def _texto_estado(cuerpo, seguidor, fps):
    return config.TEXTO_ESTADO.format(cuello=config.TEXTO_SI if cuerpo.visible else config.TEXTO_NO,
                                      manos=len(seguidor.visibles), fps=round(fps))


def main():
    indice, ancho, alto = _argumentos()
    detector_manos = DetectorManos()
    detector_cuerpo = DetectorCuerpo()
    try:
        camara = Camara(indice, ancho, alto, config.CAMARA_FPS)
    except RuntimeError as error:
        detector_manos.cerrar()
        detector_cuerpo.cerrar()
        sys.exit(str(error))
    print(f"cámara {indice}: {camara.ancho}x{camara.alto} a {camara.fps:.0f} fps ({camara.backend})", flush=True)

    render = Render(ancho, alto)
    preparador = Preparador()
    seguidor = Seguidor(alto / ancho)
    cuerpo = Cuerpo(alto / ancho)
    cuentas = Cuentas()
    cv2.namedWindow(config.TITULO, cv2.WINDOW_AUTOSIZE)

    # El dibujo lleva su propio reloj: cada vuelta usa el último fotograma que haya, sea nuevo o no.
    periodo = 1.0 / config.FPS_OBJETIVO
    siguiente = time.perf_counter()
    visto, ultima_senal = 0, siguiente
    manos_vistas, cuerpos_vistos, dibujo_anterior = 0, 0, siguiente
    cuadros, capturas, resultados, peor = 0, 0, 0, 0.0
    reloj, cpu, anterior = siguiente, time.process_time(), siguiente
    intervalo = periodo  # entre dibujos, suavizado: da los fps que se muestran
    estado, siguiente_estado = "", siguiente
    try:
        while True:
            fotograma, numero = camara.leer()
            ahora = time.perf_counter()
            if numero != visto:
                visto, ultima_senal = numero, ahora
                capturas += 1
                # Los detectores reciben la imagen sin atenuar; la atenuación es solo para la vista.
                imagen = preparador.preparar(render.camara(fotograma))
                detector_manos.enviar(imagen)
                detector_cuerpo.enviar(imagen)
            elif ahora - ultima_senal > 3.0:
                print("La cámara dejó de entregar fotogramas.")
                break
            render.fondo()

            # El seguimiento avanza una vez por resultado de cada detector, no una vez por dibujo.
            numero, detecciones = detector_manos.resultado
            if numero != manos_vistas:
                manos_vistas = numero
                resultados += 1
                seguidor.actualizar(detecciones)
            numero, deteccion = detector_cuerpo.resultado
            if numero != cuerpos_vistos:
                cuerpos_vistos = numero
                cuerpo.actualizar(deteccion)

            render.esqueleto(seguidor.visibles)
            cuentas.avanzar(ahora - dibujo_anterior, cuerpo, ancho)
            dibujo_anterior = ahora
            if cuentas.centro is not None:
                render.cuentas(cuentas.proyectar(), cuerpo.mascara, cuentas.opacidad)
            if not cuerpo.visible:
                render.aviso(config.TEXTO_AVISO)
            # Como en el original, el estado cambia a saltos unas 4 veces por segundo.
            if ahora >= siguiente_estado:
                estado, siguiente_estado = _texto_estado(cuerpo, seguidor, 1 / intervalo), ahora + config.ESTADO_PERIODO
            render.estado(estado)
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
            intervalo += (ahora - anterior - intervalo) * 0.05
            anterior = ahora
            if ahora - reloj >= 1.0:
                lapso = ahora - reloj
                cpu_ahora = time.process_time()
                print(f"{cuadros / lapso:5.1f} fps (peor intervalo {peor * 1000:4.1f} ms) · "
                      f"cámara {capturas / lapso:4.1f}/s · "
                      f"manos {detector_manos.ms:4.1f} ms ({resultados / lapso:4.1f}/s) · "
                      f"cuerpo {detector_cuerpo.ms:4.1f} ms (cuello {'sí' if cuerpo.visible else 'no'}) · "
                      f"manos vistas {len(seguidor.visibles)} · cpu {(cpu_ahora - cpu) / lapso * 100:3.0f} % de un núcleo",
                      flush=True)
                cuadros, capturas, resultados, peor = 0, 0, 0, 0.0
                reloj, cpu = ahora, cpu_ahora
    except KeyboardInterrupt:
        pass
    finally:
        camara.cerrar()
        detector_manos.cerrar()
        detector_cuerpo.cerrar()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
