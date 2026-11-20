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

# --- Identidad de las manos ---
SEGUIMIENTO_DISTANCIA_MAX = 0.30  # fracción del ancho; un salto mayor se toma como otra mano
MANO_PERDIDA_TOLERANCIA = 4  # detecciones seguidas sin verla antes de darla por perdida

# --- Conteo de dedos ---
DEDOS_INERCIA = 4  # detecciones iguales seguidas para aceptar un conteo nuevo
DEDO_MARGEN = 1.10  # punta más lejos de la muñeca que el nudillo medio, por este factor
PULGAR_MARGEN = 1.05  # punta del pulgar más lejos de la base del meñique que su nudillo

# --- Gestos ---
# Pinza: distancia entre las puntas del pulgar y el índice dividida por el tamaño de la mano (muñeca a
# nudillo del dedo medio). Se cierra por debajo de PINZA_CIERRA y se abre por encima de PINZA_ABRE.
PINZA_CIERRA = 0.35
PINZA_ABRE = 0.50
AGARRAR_ALCANCE = 1.8  # la pinza agarra una cuenta a menos de esto, en radios de cuenta en pantalla
CONVOCAR_DETECCIONES = 12  # palma abierta sostenida (unas 25 detecciones por segundo: medio segundo)

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

# --- Movimiento de las cuentas ---
# Cada cuenta persigue su objetivo con un resorte sin rebote; la rigidez va en rad/s (más = más rápida;
# llega en unos 4 / rigidez segundos).
ORBITA_OMEGA = 14  # en el anillo del cuello
REGRESO_OMEGA = 5  # volviendo al cuello después de soltarla o lanzarla: planea
MANO_OMEGA = 9  # convocada alrededor de la mano
AGARRAR_OMEGA = 28  # agarrada con la pinza: casi pegada a los dedos
MANO_ANILLO_RADIO = 1.3  # anillo alrededor de la mano, en tamaños de mano (muñeca a nudillo medio)
MANO_INCLINACION = 65  # grados; más que el del cuello para que el anillo se vea bien abierto
MANO_PROFUNDIDAD = -0.35  # en anchos de hombros; negativo = delante del cuello, así no la tapa la silueta
LANZAR_VELOCIDAD = 2.5  # al soltar la pinza más rápido que esto (anchos de hombros por segundo), se lanza
LIBRE_FRENADO = 1.2  # por segundo; cuánto frena en el aire
LIBRE_VELOCIDAD_MIN = 0.4  # anchos de hombros por segundo; más lenta que esto, regresa
LIBRE_SEGUNDOS = 1.2  # vuelo libre máximo antes de regresar
BRILLO_MANEJADA = 2.2  # aura de la cuenta agarrada o lanzada, respecto a la normal
BRILLO_CONVOCADA = 1.5  # aura de las cuentas convocadas
BRILLO_SEGUNDOS = 0.15  # lo que tarda el aura en cambiar

# --- Dibujo de las cuentas ---
# "gpu": modelo 3D iluminado con moderngl. "cpu": esferas planas, sin GPU. Si la GPU no arranca, se
# usa "cpu" y se avisa en la consola.
RENDER_CUENTAS = "gpu"
GPU_MUESTRAS = 4  # muestras por píxel para suavizar los bordes
CUENTA_GIRO_PROPIO = 0.5  # rad/s; cada cuenta gira sobre sí misma alrededor de un eje propio

# --- Modelo 3D de la cuenta (ángulos en radianes, alturas en radios de cuenta) ---
CUENTA_SUBDIVISIONES = 6  # esfera geodésica: 6 da 40962 vértices, menos de un píxel por triángulo a tamaño real
TACHUELA_RADIO = 0.17  # 12 tachuelas de acero repartidas por igual
TACHUELA_ALTURA = 0.12  # sobresalen del contorno, como en las referencias
COLLAR_ANCHO = 0.035  # medio ancho del collar de bronce alrededor de cada tachuela
COLLAR_ALTURA = 0.025
LINEA_ANCHO = 0.012  # medio ancho de la línea grabada alrededor del collar
LINEA_PROFUNDIDAD = 0.012
MEDIALUNA_ANCHO = 0.11  # medio ancho de la medialuna en su parte más gruesa
MEDIALUNA_LARGO = 0.42 # fracción de vuelta que recorre alrededor de su tachuela
MEDIALUNA_SEPARACION = 0.17 # distancia entre el collar y el centro de la medialuna al arrancar
MEDIALUNA_APERTURA = 0.30 # cuánto se aleja de la tachuela por vuelta
MEDIALUNA_PROFUNDIDAD = 0.006

# --- Aspecto de las cuentas ---
CUENTA_COLOR = "#B8A27A"  # bronce pálido
TACHUELA_COLOR = "#A3A89C"  # acero
OSCURO_COLOR = "#4A4548"  # medialunas y grabados, color carbón
LUZ_DIRECCION = (-0.45, -0.65, 0.6)  # x derecha, y abajo, z hacia la cámara: luz arriba a la izquierda
LUZ_COLOR = "#FFF1DC"
RELLENO_DIRECCION = (0.8, 0.3, 0.5)  # luz de relleno, fría, desde la derecha (solo GPU)
RELLENO_COLOR = "#5E5870"
ENTORNO_CIELO = "#B49C80"  # lo que reflejan las cuentas arriba y abajo (solo GPU)
ENTORNO_SUELO = "#1C1619"
# Solo en CPU:
LUZ_AMBIENTE = 0.28
LUZ_DIFUSA = 0.95
BRILLO_COLOR = "#FFE8C8"
BRILLO_INTENSIDAD = 0.55
BRILLO_EXPONENTE = 24
# Aura:
AURA_COLOR = "#9A70FF"  # violeta tenue alrededor de cada cuenta
AURA_INTENSIDAD = 0.35
AURA_ANCHO = 0.22  # caída del aura, en radios de cuenta
AURA_ALCANCE = 0.5  # el aura se dibuja hasta (1 + esto) radios del centro; a 0.22 de caída ya no se ve
AURA_BORDE = 0.15  # reflejo violeta en el contorno de la cuenta

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
