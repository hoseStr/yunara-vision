"""Valores ajustables de Yunara. Todo lo que se puede tocar vive aquí."""
from pathlib import Path

# --- Ventana y cámara ---
ANCHO = 1280
ALTO = 720
CAMARA_INDICE = 0
CAMARA_FPS = 30
ESPEJO = True  # vista tipo selfie
TITULO = "Yunara"
FPS_OBJETIVO = 45  # ritmo de dibujo, independiente del ritmo de la cámara
# Los valores "por fotograma" (suavizado) valen para este ritmo; si FPS_OBJETIVO cambia,
# se convierten solos para que el aspecto no cambie.
FPS_REFERENCIA = 45

# --- Detección (manos y cuerpo) ---
MODELO_MANOS = Path(__file__).parent / "modelos" / "hand_landmarker.task"
# "lite" basta para el cuello: 12 ms con silueta frente a 17 ms del "full" (medido en el video).
MODELO_CUERPO = Path(__file__).parent / "modelos" / "pose_landmarker_lite.task"
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

# --- Escala con la segunda mano (del proyecto base; hoy no se usa, se rehace con los gestos) ---
ESCALA_MIN = 0.35
ESCALA_MAX = 3.2
# Tamaño fijo mientras no hay segunda mano: al empezar, al retirarla o si la principal se pierde y la
# otra pasa a serlo. Solo la segunda mano cambia el tamaño.
ESCALA_SIN_SEGUNDA = 0.5
# "apertura": qué tan extendidos están los dedos de ESCALA_DEDOS (lo que mejor encaja con el video).
# "pinza": distancia entre las puntas del pulgar y el índice.
# Las dos medidas se dividen por el tamaño de la mano (muñeca a nudillo del dedo medio).
ESCALA_MEDIDA = "apertura"
ESCALA_DEDOS = (8, 12)  # puntas del índice y del medio
ESCALA_APERTURA = (1.30, 2.00)  # medida que da ESCALA_MIN y medida que da ESCALA_MAX
ESCALA_PINZA = (0.30, 2.00)
# Una lectura que pasa del tope del mapa por más de este factor se descarta y la escala no cambia.
# Solo ocurre con detecciones deformadas (mano cortada por el borde o movida): en el video, el 95 % de
# las lecturas no pasa de 2.02 y todas las que superan 2.2 son de ese tipo.
ESCALA_DESCARTE = 1.12

# --- Cuerpo y cuello ---
CUERPO_PERDIDO_TOLERANCIA = 4  # detecciones seguidas sin ver a nadie antes de darlo por perdido
HOMBROS_VISIBILIDAD_MIN = 0.5  # por debajo, los hombros se estiman con las orejas
CUELLO_POSICION = 0.45  # del centro de los hombros hacia la boca (0 hombros, 1 boca)
HOMBROS_POR_OREJAS = 2.5  # ancho de hombros / distancia entre orejas, para el caso sin hombros
CUELLO_BAJO_BOCA = 0.24  # en anchos de hombros, para el caso sin hombros
# La silueta de la persona tapa las cuentas que pasan por detrás del cuello.
OCLUSION = True

# --- Cuentas ---
# Las medidas van en anchos de hombros, así el anillo crece y se encoge con la distancia a la cámara.
CUENTAS_N = 6
ANILLO_RADIO = 0.75
CUENTA_DIAMETRO = 0.30
ANILLO_INCLINACION = 22  # grados; la parte de atrás sube y la de delante baja
ANILLO_GIRO = 0.8  # rad/s; negativo gira al revés
FLOTE_AMPLITUD = 0.035  # subida y bajada de cada cuenta
FLOTE_HZ = 0.35
PERSPECTIVA_DISTANCIA = 3.0  # cámara virtual; menor = perspectiva más marcada
SUAVIZADO = 0.25  # de posición, tamaño e inclinación, por fotograma a FPS_REFERENCIA
FUNDIDO_SEGUNDOS = 0.3  # aparecer y desvanecerse con la persona

# --- Aspecto de las cuentas (esferas provisionales hasta el modelo 3D) ---
CUENTA_COLOR = "#8E6B40"  # bronce
LUZ_DIRECCION = (-0.45, -0.65, 0.6)  # x derecha, y abajo, z hacia la cámara: luz arriba a la izquierda
LUZ_AMBIENTE = 0.28
LUZ_DIFUSA = 0.95
BRILLO_COLOR = "#FFE8C8"
BRILLO_INTENSIDAD = 0.55
BRILLO_EXPONENTE = 24
AURA_COLOR = "#9A70FF"  # violeta tenue alrededor de cada cuenta
AURA_INTENSIDAD = 0.35
AURA_ANCHO = 0.22  # caída del aura, en radios de cuenta
AURA_ALCANCE = 0.5  # el sprite mide (1 + esto) diámetros: esto en radios a cada lado (a 0.22 de caída ya no se ve)
AURA_BORDE = 0.35  # reflejo violeta en el contorno de la esfera

# --- Escena ---
BRILLO = 0.55  # brillo de la cámara en el centro
TINTE = (1.00, 0.96, 0.88)  # ganancia por canal B, G, R: tinte frío leve
VINETA_INICIO = 0.45  # distancia al centro donde empieza a oscurecer (0 centro, 1 esquina)
VINETA_FUERZA = 0.45  # cuánto se oscurecen las esquinas respecto al centro

# --- Esqueleto de la mano ---
ESQUELETO_COLOR = (230, 240, 235)  # BGR
ESQUELETO_OPACIDAD = 0.35

# --- Textos ---
TEXTO_AVISO = "Ponte frente a la cámara"
TEXTO_ESTADO = "cuello: {cuello} · manos: {manos} · {fps} fps"
TEXTO_SI = "sí"
TEXTO_NO = "no"
# Se prueban en orden; si ninguna está, se usa la fuente incluida en Pillow.
FUENTES = ("segoeui.ttf", "SFNS.ttf", "Helvetica.ttc", "DejaVuSans.ttf", "Arial.ttf")
AVISO_TAMANO = 13  # píxeles a 1280 de ancho
AVISO_COLOR = (255, 255, 255)  # BGR
ESTADO_TAMANO = 12
ESTADO_COLOR = (205, 205, 205)
ESTADO_MARGEN = (14, 13)  # píxeles a 1280 de ancho: desde la izquierda, y desde abajo hasta la línea base
ESTADO_PERIODO = 0.25  # segundos entre actualizaciones de la línea de estado
TEXTO_SOMBRA = 0.6  # opacidad de la sombra oscura que separa el texto del fondo
