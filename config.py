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

# --- Identidad y roles de las manos ---
# La mano que lleva más tiempo en cuadro es la principal; la otra es la segunda.
SEGUIMIENTO_DISTANCIA_MAX = 0.30  # fracción del ancho; un salto mayor se toma como otra mano
MANO_PERDIDA_TOLERANCIA = 4  # detecciones seguidas sin verla antes de darla por perdida

# --- Conteo de dedos ---
DEDOS_INERCIA = 4  # detecciones iguales seguidas para aceptar un conteo nuevo
DEDO_MARGEN = 1.10  # punta más lejos de la muñeca que el nudillo medio, por este factor
PULGAR_MARGEN = 1.05  # punta del pulgar más lejos de la base del meñique que su nudillo

# --- Escala con la segunda mano ---
ESCALA_MIN = 0.35
ESCALA_MAX = 3.2
ESCALA_INICIAL = 1.0
# "apertura": qué tan extendidos están los dedos de ESCALA_DEDOS (lo que mejor encaja con el video).
# "pinza": distancia entre las puntas del pulgar y el índice.
# Las dos medidas se dividen por el tamaño de la mano (muñeca a nudillo del dedo medio).
ESCALA_MEDIDA = "apertura"
ESCALA_DEDOS = (8, 12)  # puntas del índice y del medio
ESCALA_APERTURA = (1.30, 2.00)  # medida que da ESCALA_MIN y medida que da ESCALA_MAX
ESCALA_PINZA = (0.30, 2.00)

# --- Esqueleto de la mano ---
ESQUELETO_COLOR = (230, 240, 235)  # BGR
ESQUELETO_OPACIDAD = 0.35
