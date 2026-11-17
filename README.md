# Hand Figure

Una figura de neón flota sobre tu mano en la imagen de la webcam. Su forma depende de cuántos dedos
levantas y con la otra mano cambias su tamaño. Es una aplicación nativa de escritorio en Python: una
sola ventana, sin navegador ni servidor.

| Dedos de la mano principal | Figura |
|---|---|
| 0 | Anillo |
| 1 | Segmento |
| 2 | Cuadrado |
| 3 | Prisma triangular |
| 4 | Cubo |
| 5 | Prisma pentagonal |

- La mano principal es la que lleva más tiempo en cuadro. Si sale, la otra toma su lugar.
- La segunda mano controla la escala, de ×0.35 a ×3.2, según cuánto extiende los dedos índice y
  medio. Al retirarla, la escala se queda en su último valor.

## Instalación

Probado con Python 3.12 en Windows 11.

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

En macOS o Linux, el entorno se activa con `source .venv/bin/activate`.

No instales `opencv-python` aparte: `mediapipe` ya trae `opencv-contrib-python`, que provee el mismo
módulo `cv2`, y los dos paquetes se pisan entre sí. El modelo de manos viene en
`modelos/hand_landmarker.task`, así que no hace falta red para ejecutarlo.

## Ejecución

```
python main.py
python main.py --camara 1 --resolucion 1920x1080
```

Se sale con `q`, `Esc` o cerrando la ventana. Una vez por segundo la consola muestra los fps de
dibujo, los fotogramas por segundo que entrega la cámara, el tiempo de detección, las manos visibles
y el uso de CPU.

## Ajustes

Todos los valores ajustables están en `config.py`, agrupados por tema:

| Sección | Qué controla |
|---|---|
| Ventana y cámara | Resolución, índice de cámara, espejo, ritmo de dibujo (`FPS_OBJETIVO`) |
| Detección de manos | Resolución de detección y umbrales de confianza |
| Identidad y roles | Cuánto puede saltar una mano entre detecciones y cuánto tarda en darse por perdida |
| Conteo de dedos | Inercia y márgenes para decidir si un dedo está levantado |
| Escala | Mínimo, máximo, valor inicial, y la medida que la controla (`"apertura"` o `"pinza"`) |
| Figura | Colores, tamaño, separación sobre la palma, perspectiva, giro, transformación y suavizado |
| Brillo y estela | Decaimiento de la estela, tamaño e intensidad del halo, núcleo claro de las aristas |
| Escena | Brillo de la cámara, tinte frío y viñeta |
| Textos | Cadenas, fuentes, tamaños, colores y ritmo de la línea de estado |

Los valores "por fotograma" (suavizado y estela) están pensados para 45 fps y se convierten solos si
cambias `FPS_OBJETIVO`, así que el aspecto no cambia.

## Rendimiento

Medido el 2026-11-16 con la cámara real a 1280×720, en un Ryzen 5 5600X (6 núcleos, 12 hilos) con
16 GB y Windows 11:

| Medida | Valor |
|---|---|
| Ritmo de dibujo | 45 fps estables, peor intervalo entre 22.6 y 24.4 ms (ideal 22.2) |
| Fotogramas de cámara | 30 nominales; entre 20 y 25 distintos por segundo, según la luz |
| Detección de manos | Entre 20 y 25 ms por fotograma con manos, en un hilo aparte |
| CPU | Entre 60 y 100 % de un núcleo con manos y figura (de 12 hilos disponibles) |
| Memoria | Entre 227 y 229 MB |

El dibujo (fondo, esqueleto, figura con estela y halo, y textos) cuesta unos 3 ms por fotograma con la
figura en pantalla. Casi todo el gasto de CPU es la detección de manos.

## Archivos

| Archivo | Contenido |
|---|---|
| `main.py` | Bucle principal con reloj propio, teclado y medición |
| `camara.py` | Captura en un hilo aparte que conserva solo el último fotograma |
| `manos.py` | Detección con MediaPipe, identidad y roles de las manos, dedos y escala |
| `figuras.py` | Geometría de las seis figuras, transformación, giro y posición |
| `render.py` | Cámara atenuada, esqueleto, figura con estela y halo, y textos |
| `config.py` | Todos los valores ajustables |
| `PLAN.md` | Mediciones y decisiones de diseño |
