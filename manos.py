"""Manos: detección con MediaPipe HandLandmarker, identidad, conteo de dedos y gestos."""
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

import config
from deteccion import DetectorAsincrono

# Pares de puntos (de los 21 de la mano) unidos por una línea del esqueleto.
CONEXIONES = tuple((c.start, c.end) for c in vision.HandLandmarksConnections.HAND_CONNECTIONS)


class DetectorManos(DetectorAsincrono):
    """`resultado` trae una tupla con un arreglo (21, 3) por mano, en coordenadas normalizadas de 0
    a 1 respecto a la imagen enviada."""

    VACIO = ()

    def _crear(self, al_resultado):
        if not config.MODELO_MANOS.exists():
            raise FileNotFoundError(f"Falta el modelo de manos: {config.MODELO_MANOS}")
        opciones = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(config.MODELO_MANOS)),
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=config.MANOS_MAX,
            min_hand_detection_confidence=config.CONFIANZA_DETECCION,
            min_hand_presence_confidence=config.CONFIANZA_PRESENCIA,
            min_tracking_confidence=config.CONFIANZA_SEGUIMIENTO,
            result_callback=al_resultado,
        )
        return vision.HandLandmarker.create_from_options(opciones)

    def _extraer(self, resultado):
        return tuple(np.array([(p.x, p.y, p.z) for p in mano], np.float32)
                     for mano in resultado.hand_landmarks)


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


class Mano:
    """Una mano seguida entre detecciones, con sus dedos y sus gestos.

    `pinza`: pulgar e índice juntos, con histéresis para que no parpadee en el umbral.
    `abierta`: detecciones seguidas con los cinco dedos levantados y sin pinza.
    """

    def __init__(self, identidad, puntos, aspecto):
        self.id = identidad
        self.perdida = 0  # detecciones seguidas sin verla
        self._aspecto = aspecto
        self._candidato, self._racha = None, 0
        self.pinza = False
        self.abierta = 0
        self._colocar(puntos)
        self.dedos = contar_dedos(self.plano)
        self._gestos()

    def _colocar(self, puntos):
        self.puntos = puntos  # (21, 3) normalizados a la imagen
        # Mismos puntos con x e y en la misma unidad (anchos de imagen), para medir distancias.
        self.plano = puntos[:, :2] * (1.0, self._aspecto)
        self.centro = self.plano[list(_PALMA)].mean(axis=0)
        self.tamano = _dist(self.plano, _MUNECA, _NUDILLO_MEDIO)

    @property
    def palma(self):
        """Centro de la palma, normalizado a la imagen (x e y de 0 a 1)."""
        return self.puntos[list(_PALMA), :2].mean(axis=0)

    @property
    def punto_pinza(self):
        """Punto medio entre las puntas del pulgar y el índice, normalizado a la imagen."""
        return (self.puntos[_PULGAR_PUNTA, :2] + self.puntos[_INDICE_PUNTA, :2]) / 2

    def _gestos(self):
        apertura = _dist(self.plano, _PULGAR_PUNTA, _INDICE_PUNTA) / (self.tamano or 1e-6)
        self.pinza = apertura < (config.PINZA_ABRE if self.pinza else config.PINZA_CIERRA)
        self.abierta = self.abierta + 1 if self.dedos == 5 and not self.pinza else 0

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
        self._gestos()


class Seguidor:
    """Mantiene la identidad de las manos entre detecciones, emparejándolas por cercanía.

    `actualizar` se llama una vez por resultado del detector. No se usa la etiqueta izquierda/derecha
    del modelo. Una mano que deja de verse se conserva unas detecciones (`perdida` > 0) para que un
    parpadeo del detector no suelte lo que tenía agarrado.
    """

    def __init__(self, aspecto):
        self._aspecto = aspecto  # alto / ancho de la imagen
        self.manos = []
        self._siguiente_id = 1

    @property
    def visibles(self):
        return [m for m in self.manos if m.perdida == 0]

    def actualizar(self, detecciones):
        centros = [(d[list(_PALMA), :2] * (1.0, self._aspecto)).mean(axis=0) for d in detecciones]
        # Empareja cada mano conocida con la detección más cercana, empezando por los pares más próximos.
        pares = sorted((float(np.hypot(*(m.centro - c))), i, j)
                       for i, m in enumerate(self.manos) for j, c in enumerate(centros))
        mano_de, usadas = {}, set()
        for distancia, i, j in pares:
            if distancia <= config.SEGUIMIENTO_DISTANCIA_MAX and i not in mano_de and j not in usadas:
                mano_de[i] = j
                usadas.add(j)

        for i, mano in enumerate(self.manos):
            if i in mano_de:
                mano.actualizar(detecciones[mano_de[i]])
            else:
                mano.perdida += 1
        self.manos = [m for m in self.manos if m.perdida <= config.MANO_PERDIDA_TOLERANCIA]
        for j, puntos in enumerate(detecciones):  # las detecciones sin pareja son manos nuevas
            if j not in usadas:
                self.manos.append(Mano(self._siguiente_id, puntos, self._aspecto))
                self._siguiente_id += 1
