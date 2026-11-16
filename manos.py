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
        self.resultado = (0, ())  # (número de resultado, manos); se reemplaza entero en cada detección
        self.ms = 0.0  # tiempo de envío a resultado, suavizado

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
        manos = tuple(np.array([(p.x, p.y, p.z) for p in mano], np.float32)
                      for mano in resultado.hand_landmarks)
        self.resultado = (self.resultado[0] + 1, manos)
        self.ms = ms if not self.ms else self.ms + (ms - self.ms) * 0.1
        self._enviado = 0.0

    def cerrar(self):
        self._detector.close()


# Índices de los 21 puntos de MediaPipe que se usan aquí.
_MUNECA, _NUDILLO_MEDIO, _BASE_MENIQUE = 0, 9, 17
_PULGAR_NUDILLO, _PULGAR_PUNTA, _INDICE_PUNTA = 3, 4, 8
_PUNTAS = (8, 12, 16, 20)  # índice, medio, anular, meñique
_NUDILLOS_MEDIOS = (6, 10, 14, 18)
_PALMA = (0, 5, 9, 13, 17)


def _dist(p, a, b):
    return float(np.hypot(p[a, 0] - p[b, 0], p[a, 1] - p[b, 1]))


def contar_dedos(p):
    """Dedos levantados, de 0 a 5. No depende de la orientación de la mano.

    Un dedo cuenta si su punta está más lejos de la muñeca que su nudillo medio. El pulgar se mide
    contra la base del meñique, porque al doblarse se cruza sobre la palma en vez de acercarse a la
    muñeca.
    """
    n = sum(_dist(p, punta, _MUNECA) > _dist(p, nudillo, _MUNECA) * config.DEDO_MARGEN
            for punta, nudillo in zip(_PUNTAS, _NUDILLOS_MEDIOS))
    n += _dist(p, _PULGAR_PUNTA, _BASE_MENIQUE) > _dist(p, _PULGAR_NUDILLO, _BASE_MENIQUE) * config.PULGAR_MARGEN
    return int(n)


def medida_escala(p):
    """Medida de la segunda mano que gobierna la escala, relativa al tamaño de la mano."""
    tamano = _dist(p, _MUNECA, _NUDILLO_MEDIO) or 1e-6
    if config.ESCALA_MEDIDA == "pinza":
        return _dist(p, _PULGAR_PUNTA, _INDICE_PUNTA) / tamano
    return sum(_dist(p, punta, _MUNECA) for punta in config.ESCALA_DEDOS) / len(config.ESCALA_DEDOS) / tamano


def escala_desde(medida):
    """Lleva la medida a una escala entre ESCALA_MIN y ESCALA_MAX, de forma lineal y con topes."""
    bajo, alto = config.ESCALA_PINZA if config.ESCALA_MEDIDA == "pinza" else config.ESCALA_APERTURA
    t = min(1.0, max(0.0, (medida - bajo) / (alto - bajo)))
    return config.ESCALA_MIN + t * (config.ESCALA_MAX - config.ESCALA_MIN)


class Mano:
    """Una mano seguida entre detecciones."""

    def __init__(self, identidad, puntos, aspecto):
        self.id = identidad
        self.perdida = 0  # detecciones seguidas sin verla
        self._aspecto = aspecto
        self._candidato, self._racha = None, 0
        self._colocar(puntos)
        self.dedos = contar_dedos(self.plano)

    def _colocar(self, puntos):
        self.puntos = puntos  # (21, 3) normalizados a la imagen
        # Mismos puntos con x e y en la misma unidad (anchos de imagen), para medir distancias.
        self.plano = puntos[:, :2] * (1.0, self._aspecto)
        self.centro = self.plano[list(_PALMA)].mean(axis=0)

    def actualizar(self, puntos):
        self._colocar(puntos)
        self.perdida = 0
        # Inercia: el conteo solo cambia tras varias detecciones seguidas con el mismo valor nuevo.
        leido = contar_dedos(self.plano)
        if leido == self.dedos:
            self._candidato, self._racha = None, 0
        elif leido == self._candidato:
            self._racha += 1
            if self._racha >= config.DEDOS_INERCIA:
                self.dedos, self._candidato, self._racha = leido, None, 0
        else:
            self._candidato, self._racha = leido, 1


class Seguidor:
    """Mantiene la identidad de las manos, sus roles y la escala.

    `actualizar` se llama una vez por resultado del detector. Las manos se guardan de la más antigua
    a la más nueva: la primera es la principal y la siguiente es la segunda. No se usa la etiqueta
    izquierda/derecha del modelo.
    """

    def __init__(self, aspecto):
        self._aspecto = aspecto  # alto / ancho de la imagen
        self._manos = []
        self._siguiente_id = 1
        self.escala = config.ESCALA_INICIAL  # se conserva cuando la segunda mano sale

    @property
    def principal(self):
        return self._manos[0] if self._manos else None

    @property
    def segunda(self):
        return self._manos[1] if len(self._manos) > 1 else None

    @property
    def visibles(self):
        return [m for m in self._manos if m.perdida == 0]

    def actualizar(self, detecciones):
        centros = [(d[list(_PALMA), :2] * (1.0, self._aspecto)).mean(axis=0) for d in detecciones]
        # Empareja cada mano conocida con la detección más cercana, empezando por los pares más próximos.
        pares = sorted((float(np.hypot(*(m.centro - c))), i, j)
                       for i, m in enumerate(self._manos) for j, c in enumerate(centros))
        mano_de, usadas = {}, set()
        for distancia, i, j in pares:
            if distancia <= config.SEGUIMIENTO_DISTANCIA_MAX and i not in mano_de and j not in usadas:
                mano_de[i] = j
                usadas.add(j)

        for i, mano in enumerate(self._manos):
            if i in mano_de:
                mano.actualizar(detecciones[mano_de[i]])
            else:
                mano.perdida += 1
        self._manos = [m for m in self._manos if m.perdida <= config.MANO_PERDIDA_TOLERANCIA]
        for j, puntos in enumerate(detecciones):  # las detecciones sin pareja son manos nuevas
            if j not in usadas:
                self._manos.append(Mano(self._siguiente_id, puntos, self._aspecto))
                self._siguiente_id += 1

        segunda = self.segunda
        if segunda is not None and segunda.perdida == 0:
            self.escala = escala_desde(medida_escala(segunda.plano))
