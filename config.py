"""Valores ajustables de Hand Figure. Todo lo que se puede tocar vive aquí."""
from pathlib import Path

# --- Ventana y cámara ---
ANCHO = 1280
ALTO = 720
CAMARA_INDICE = 0
CAMARA_FPS = 30
ESPEJO = True  # vista tipo selfie
TITULO = "Hand Figure"
FPS_OBJETIVO = 45  # ritmo de dibujo, independiente del ritmo de la cámara

# --- Detección de manos ---
MODELO = Path(__file__).parent / "modelos" / "hand_landmarker.task"
DETECCION_ANCHO = 640
DETECCION_ALTO = 360
MANOS_MAX = 2
CONFIANZA_DETECCION = 0.5
CONFIANZA_PRESENCIA = 0.5
CONFIANZA_SEGUIMIENTO = 0.5

# --- Esqueleto de la mano ---
ESQUELETO_COLOR = (230, 240, 235)  # BGR
ESQUELETO_OPACIDAD = 0.35
