"""Detección de manos con MediaPipe HandLandmarker, sin bloquear el bucle de dibujo."""
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

import config

# Pares de puntos (de los 21 de la mano) unidos por una línea del esqueleto.
CONEXIONES = tuple((c.start, c.end) for c in vision.HandLandmarksConnections.HAND_CONNECTIONS)

# Si un envío no recibe respuesta en este tiempo, se da por perdido y se envía otro.
_ESPERA_MAX = 0.5


class Detector:
    """Envía fotogramas al detector y guarda el último resultado.

    La detección tarda unos 20 ms, así que corre en el hilo de MediaPipe (modo LIVE_STREAM) y el
    bucle principal solo lee `manos`: una tupla con un arreglo (21, 3) por mano, en coordenadas
    normalizadas de 0 a 1 respecto a la imagen enviada.
    """

    def __init__(self):
        if not config.MODELO.exists():
            raise FileNotFoundError(f"Falta el modelo de manos: {config.MODELO}")
        opciones = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(config.MODELO)),
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=config.MANOS_MAX,
            min_hand_detection_confidence=config.CONFIANZA_DETECCION,
            min_hand_presence_confidence=config.CONFIANZA_PRESENCIA,
            min_tracking_confidence=config.CONFIANZA_SEGUIMIENTO,
            result_callback=self._al_resultado,
        )
        self._detector = vision.HandLandmarker.create_from_options(opciones)
        forma = (config.DETECCION_ALTO, config.DETECCION_ANCHO, 3)
        self._reducido = np.empty(forma, np.uint8)
        self._rgb = np.empty(forma, np.uint8)
        self._enviado = 0.0  # instante del envío en curso; 0 si el detector está libre
        self._marca = 0
        self.manos = ()
        self.ms = 0.0  # tiempo de envío a resultado, suavizado
        self.resultados = 0

    def enviar(self, imagen_bgr):
        """Manda la imagen a detectar si el detector está libre; si no, no hace nada."""
        ahora = time.perf_counter()
        if self._enviado and ahora - self._enviado < _ESPERA_MAX:
            return
        cv2.resize(imagen_bgr, (config.DETECCION_ANCHO, config.DETECCION_ALTO),
                   dst=self._reducido, interpolation=cv2.INTER_LINEAR)
        cv2.cvtColor(self._reducido, cv2.COLOR_BGR2RGB, dst=self._rgb)
        self._marca = max(self._marca + 1, int(ahora * 1000))  # milisegundos, siempre creciente
        self._enviado = ahora
        # mp.Image copia los datos, así que el búfer se puede reutilizar en el siguiente envío.
        self._detector.detect_async(mp.Image(image_format=mp.ImageFormat.SRGB, data=self._rgb), self._marca)

    def _al_resultado(self, resultado, _imagen, _marca):
        # Se ejecuta en el hilo de MediaPipe, también cuando no hay manos.
        ms = (time.perf_counter() - self._enviado) * 1000
        self.manos = tuple(np.array([(p.x, p.y, p.z) for p in mano], np.float32)
                           for mano in resultado.hand_landmarks)
        self.ms = ms if not self.ms else self.ms + (ms - self.ms) * 0.1
        self.resultados += 1
        self._enviado = 0.0

    def cerrar(self):
        self._detector.close()
