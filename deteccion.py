"""Base común de los detectores de MediaPipe: envío asíncrono que no bloquea el bucle de dibujo."""
import time

import cv2
import mediapipe as mp
import numpy as np

import config

# Si un envío no recibe respuesta en este tiempo, se da por perdido y se envía otro.
_ESPERA_MAX = 0.5


class Preparador:
    """Reduce el fotograma al tamaño de detección una sola vez y lo comparte entre los detectores."""

    def __init__(self):
        forma = (config.DETECCION_ALTO, config.DETECCION_ANCHO, 3)
        self._reducido = np.empty(forma, np.uint8)
        self._rgb = np.empty(forma, np.uint8)

    def preparar(self, imagen_bgr):
        cv2.resize(imagen_bgr, (config.DETECCION_ANCHO, config.DETECCION_ALTO),
                   dst=self._reducido, interpolation=cv2.INTER_LINEAR)
        cv2.cvtColor(self._reducido, cv2.COLOR_BGR2RGB, dst=self._rgb)
        # mp.Image copia los datos, así que los búferes se pueden reutilizar en el siguiente fotograma.
        return mp.Image(image_format=mp.ImageFormat.SRGB, data=self._rgb)


class DetectorAsincrono:
    """Envía imágenes a una tarea de MediaPipe en modo LIVE_STREAM y guarda el último resultado.

    La tarea corre en su propio hilo; el bucle principal solo lee `resultado`, una tupla
    (número de resultado, datos) que se reemplaza entera en cada detección. Cada subclase crea su
    tarea en `_crear`, convierte la salida en `_extraer` y define `VACIO`, los datos sin detección.
    """

    VACIO = None

    def __init__(self):
        self._tarea = self._crear(self._al_resultado)
        self._enviado = 0.0  # instante del envío en curso; 0 si la tarea está libre
        self._marca = 0  # marca de tiempo del último envío, en milisegundos
        self.resultado = (0, self.VACIO)
        self.ms = 0.0  # tiempo de envío a resultado, suavizado

    def _crear(self, al_resultado):
        raise NotImplementedError

    def _extraer(self, resultado):
        raise NotImplementedError

    def enviar(self, imagen):
        """Manda la imagen a detectar si la tarea está libre; si no, no hace nada."""
        ahora = time.perf_counter()
        if self._enviado and ahora - self._enviado < _ESPERA_MAX:
            return
        self._marca = max(self._marca + 1, int(ahora * 1000))  # siempre creciente
        self._enviado = ahora
        self._tarea.detect_async(imagen, self._marca)

    def _al_resultado(self, resultado, _imagen, marca):
        # Se ejecuta en el hilo de MediaPipe, también cuando no hay nada que detectar.
        datos = self._extraer(resultado)
        # Una respuesta tardía a un envío que ya se dio por perdido no libera la tarea.
        if marca == self._marca and self._enviado:
            ms = (time.perf_counter() - self._enviado) * 1000
            self.ms = ms if not self.ms else self.ms + (ms - self.ms) * 0.1
            self._enviado = 0.0
        self.resultado = (self.resultado[0] + 1, datos)

    def cerrar(self):
        self._tarea.close()
