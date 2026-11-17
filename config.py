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
# Los valores "por fotograma" (suavizado, estela) valen para este ritmo; si FPS_OBJETIVO cambia,
# se convierten solos para que el aspecto no cambie.
FPS_REFERENCIA = 45

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

# --- Figura ---
# Color por número de dedos, de 0 a 5: anillo, segmento, cuadrado, prisma triangular, cubo y
# prisma pentagonal.
FIGURA_COLORES = ("#DCEBFF", "#5CE6E0", "#55E6A5", "#F2E94E", "#FF9A4D", "#FF5FD0")
FIGURA_DIAMETRO = 0.18  # diámetro de la base a escala x1.0, como fracción del ancho
FIGURA_ALTURA = 2.4  # separación sobre el centro de la palma, en tamaños de mano (muñeca a nudillo medio)
PRISMA_ALTURA = 0.707  # altura de los prismas respecto al diámetro de la base; 0.707 da un cubo exacto
PERSPECTIVA_DISTANCIA = 1.8  # cámara virtual, en diámetros de figura; menor = perspectiva más marcada
GIRO_VELOCIDAD = (0.6, 0.4)  # rad/s alrededor del eje vertical y del horizontal
TRANSFORMACION_SEGUNDOS = 0.4
SUAVIZADO = 0.25  # de posición y escala, por fotograma a FPS_REFERENCIA
ARISTA_GROSOR = 3  # píxeles a 1280 de ancho

# --- Brillo y estela de la figura ---
# La estela es un búfer que se apaga un poco en cada dibujo y recibe las aristas nuevas; el halo es
# ese mismo búfer desenfocado. Los dos se suman a la cámara.
ESTELA_DECAIMIENTO = 0.82  # por fotograma a FPS_REFERENCIA
HALO_DESENFOQUE = 5  # sigma del desenfoque, en píxeles a 1280 de ancho
HALO_INTENSIDAD = 0.45
NUCLEO_BLANCO = 0.3  # cuánto se acerca al blanco la línea central de cada arista (0 a 1)

# --- Escena ---
BRILLO = 0.55  # brillo de la cámara en el centro
TINTE = (1.00, 0.96, 0.88)  # ganancia por canal B, G, R: tinte frío leve
VINETA_INICIO = 0.45  # distancia al centro donde empieza a oscurecer (0 centro, 1 esquina)
VINETA_FUERZA = 0.45  # cuánto se oscurecen las esquinas respecto al centro

# --- Esqueleto de la mano ---
ESQUELETO_COLOR = (230, 240, 235)  # BGR
ESQUELETO_OPACIDAD = 0.35

# --- Textos ---
TEXTO_AVISO = "Muestra la mano en cámara"
TEXTO_ESTADO = "mano principal: {dedos} · segunda mano: {segunda} · {fps} fps"
TEXTO_SEGUNDA_NO = "no"
TEXTO_SEGUNDA_ESCALA = "escala ×{escala:.2f}"
TEXTO_SOLO_FPS = "{fps} fps"  # estado cuando no hay manos
# Se prueban en orden; si ninguna está, se usa la fuente incluida en Pillow.
FUENTES = ("segoeui.ttf", "SFNS.ttf", "Helvetica.ttc", "DejaVuSans.ttf", "Arial.ttf")
AVISO_TAMANO = 13  # píxeles a 1280 de ancho
AVISO_COLOR = (255, 255, 255)  # BGR
ESTADO_TAMANO = 12
ESTADO_COLOR = (205, 205, 205)
ESTADO_MARGEN = (14, 13)  # píxeles a 1280 de ancho: desde la izquierda, y desde abajo hasta la línea base
ESTADO_PERIODO = 0.25  # segundos entre actualizaciones de la línea de estado
TEXTO_SOMBRA = 0.6  # opacidad de la sombra oscura que separa el texto del fondo
