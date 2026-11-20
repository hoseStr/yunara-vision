"""Cuerpo: detección con MediaPipe PoseLandmarker, posición del cuello y silueta de la persona."""
import math

import cv2
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

import config
from deteccion import DetectorAsincrono

# Índices de los 33 puntos de MediaPipe Pose que se usan aquí.
_OREJA_I, _OREJA_D, _BOCA_I, _BOCA_D, _HOMBRO_I, _HOMBRO_D = 7, 8, 9, 10, 11, 12


class DetectorCuerpo(DetectorAsincrono):
    """`resultado` trae (puntos, máscara) de una persona, o None si no hay nadie.

    `puntos` es un arreglo (33, 4) con x, y, z normalizados y la visibilidad de cada punto.
    `mascara` es la silueta de la persona, (alto, ancho) en uint8 de 0 a 255 al tamaño de detección,
    o None si la oclusión está desactivada.
    """

    VACIO = None

    def _crear(self, al_resultado):
        if not config.MODELO_CUERPO.exists():
            raise FileNotFoundError(f"Falta el modelo de cuerpo: {config.MODELO_CUERPO}")
        opciones = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(config.MODELO_CUERPO)),
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_poses=1,
            min_pose_detection_confidence=config.CONFIANZA_DETECCION,
            min_pose_presence_confidence=config.CONFIANZA_PRESENCIA,
            min_tracking_confidence=config.CONFIANZA_SEGUIMIENTO,
            output_segmentation_masks=config.OCLUSION,
            result_callback=al_resultado,
        )
        return vision.PoseLandmarker.create_from_options(opciones)

    def _extraer(self, resultado):
        if not resultado.pose_landmarks:
            return None
        puntos = np.array([(p.x, p.y, p.z, p.visibility or 0.0) for p in resultado.pose_landmarks[0]],
                          np.float32)
        mascara = None
        if resultado.segmentation_masks:
            # La vista apunta a memoria de MediaPipe que no sobrevive a la llamada; la conversión a
            # uint8 la copia, y se hace aquí, en el hilo de MediaPipe, no en el de dibujo.
            vista = resultado.segmentation_masks[0].numpy_view()
            mascara = cv2.convertScaleAbs(vista.reshape(vista.shape[:2]), alpha=255)
        return puntos, mascara


def _angulo(a, b):
    """Ángulo de la recta a-b respecto a la horizontal, entre -90° y 90° (no depende del orden)."""
    dx, dy = b - a
    if dx < 0:
        dx, dy = -dx, -dy
    return math.atan2(dy, dx)


class Cuerpo:
    """Cuello, tamaño e inclinación de la persona, y su silueta.

    `actualizar` se llama una vez por resultado del detector. Las posiciones van en anchos de imagen
    (x e y en la misma unidad) para que las distancias no dependan de la proporción de la ventana.
    """

    def __init__(self, aspecto):
        self._aspecto = aspecto  # alto / ancho de la imagen
        self._perdido = 0  # detecciones seguidas sin ver a nadie
        self.visible = False
        self.cuello = None  # (x, y) en anchos de imagen
        self.hombros = 0.0  # ancho de hombros, en anchos de imagen
        self.inclinacion = 0.0  # radianes; positiva si el lado derecho de la imagen está más bajo
        self.mascara = None

    def actualizar(self, deteccion):
        if deteccion is None:
            self._perdido += 1
            if self._perdido > config.CUERPO_PERDIDO_TOLERANCIA:
                self.visible, self.mascara = False, None
            return
        self._perdido = 0
        puntos, self.mascara = deteccion
        p = puntos[:, :2] * (1.0, self._aspecto)
        visibilidad = puntos[:, 3]
        boca = (p[_BOCA_I] + p[_BOCA_D]) / 2

        if min(visibilidad[_HOMBRO_I], visibilidad[_HOMBRO_D]) >= config.HOMBROS_VISIBILIDAD_MIN:
            hombro_i, hombro_d = p[_HOMBRO_I], p[_HOMBRO_D]
            centro = (hombro_i + hombro_d) / 2
            self.hombros = float(np.hypot(*(hombro_d - hombro_i)))
            self.inclinacion = _angulo(hombro_i, hombro_d)
            self.cuello = centro + (boca - centro) * config.CUELLO_POSICION
        else:
            # Hombros fuera de cuadro (muy cerca de la cámara): se estiman con las orejas.
            oreja_i, oreja_d = p[_OREJA_I], p[_OREJA_D]
            self.hombros = float(np.hypot(*(oreja_d - oreja_i))) * config.HOMBROS_POR_OREJAS
            self.inclinacion = _angulo(oreja_i, oreja_d)
            abajo = np.array((-math.sin(self.inclinacion), math.cos(self.inclinacion)))
            self.cuello = boca + abajo * self.hombros * config.CUELLO_BAJO_BOCA
        self.visible = True
