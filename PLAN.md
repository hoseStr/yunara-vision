# Plan de trabajo: Hand Figure nativo en Python

Plan derivado de `PROMPT.md`, del video `referencia/vayunara.mp4` y de mediciones hechas en esta máquina
(Ryzen 5 5600X, 16 GB, Windows 11) el 2026-11-16. Lo que aquí dice "medido" o "comprobado" se ejecutó de verdad;
lo demás es propuesta.

## 1. Lo comprobado antes de escribir código

### Entorno y dependencias

| Paquete | Versión instalada | Nota |
|---|---|---|
| Python | 3.12.10 | En `.venv`. También hay 3.10, 3.13 y 3.14 en el equipo. |
| mediapipe | 1.2.3 | Wheel `py3-none-win_amd64`. |
| opencv-contrib-python | 5.0.0.93 | Lo instala mediapipe como dependencia. |
| numpy | 2.5.5 | Lo instala mediapipe. |
| pillow | 13.0.0 | Solo para el texto. |

- **No hay que instalar `opencv-python`.** mediapipe exige `opencv-contrib-python`, y ambos paquetes
  proveen el mismo módulo `cv2`; instalar los dos los pisa entre sí. `requirements.txt` lleva solo
  `mediapipe` y `pillow`.
- mediapipe arrastra además `matplotlib` y `sounddevice`. No los importamos, así que solo cuestan disco.
- `cv2.freetype` no viene en este build, lo que confirma Pillow para el texto.

### API de MediaPipe

- `mp.solutions` **no existe** en 1.2.3 (`hasattr(mp, "solutions")` da `False`). Solo está la API de Tasks:
  `mediapipe.tasks.python.vision.HandLandmarker`.
- Modos: `IMAGE` → `detect`, `VIDEO` → `detect_for_video(img, ts_ms)`, `LIVE_STREAM` → `detect_async(img, ts_ms)`
  con `result_callback`. Las marcas de tiempo van en milisegundos y deben crecer siempre.
- Opciones: `num_hands` (por defecto 1, hay que poner 2) y tres umbrales de confianza en 0.5.
- **Solo hay un modelo de manos publicado**: `hand_landmarker.task`, float16, 7.8 MB. No existe la variante
  "ligera" que pide el PROMPT (las rutas float32 e int8 dan 404). Queda en `modelos/hand_landmarker.task`.
- Las conexiones del esqueleto están en `vision.HandLandmarksConnections`.

### Rendimiento medido

Detección sobre los 817 fotogramas del video a 640×360, dos manos, CPU:

| Modo | Media | p95 | Máximo |
|---|---|---|---|
| `VIDEO` (con seguimiento) | 20.7 ms | 29.4 ms | 37.6 ms |
| `IMAGE` (sin seguimiento) | 24.7 ms | 31.3 ms | 39.4 ms |

Operaciones de render a 1280×720:

| Operación | ms |
|---|---|
| Espejo (`cv2.flip`) | 0.10 |
| Atenuación + viñeta (un `cv2.multiply` con mapa de ganancia precalculado) | 0.61 |
| Decaimiento de estela con `cv2.convertScaleAbs` | 0.41 |
| Decaimiento de estela con `cv2.multiply` por escalar | 2.25 |
| 15 aristas con antialias, grosor 3 | 0.24 |
| Halo: reducir a 1/4 + desenfoque + reescalar | 1.90 |
| Dos sumas aditivas | 0.18 |

Conclusiones:

- El render completo cuesta unos 3.5 ms. **La CPU alcanza de sobra; no hace falta capa de GPU.**
- La detección es el costo dominante. En serie con el render daría 35 a 38 fps con caídas bajo 30 en los
  picos, y en un portátil más lento no llegaría. Por eso la detección va desacoplada del bucle de dibujo
  (ver sección 2).
- Para el decaimiento se usa `convertScaleAbs`, cinco veces más rápido que `multiply`.

### Cámara

- Hay una "USB Camera" y el permiso de cámara de Windows está en "Permitir".
- El modo por defecto es 640×480 a 30 fps, así que pedir 1280×720 y leer lo que realmente entrega es
  obligatorio.
- **Media Foundation (MSMF)** entrega 1280×720 a 30 fps si los parámetros se pasan al abrir. **DirectShow**
  se queda en 10 fps (YUY2) o 14 fps (MJPG), así que en Windows se usa MSMF.
- Con `OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0` la cámara abre en 1.7 s en vez de 6.8 s.
- De esos 30 fps, **solo unos 24 son fotogramas distintos**: 28 de 149 eran copias exactas del anterior, y
  los intervalos de entrega van de 12 a 66 ms. Es un límite de la cámara, no de la aplicación.
- Si otra aplicación tiene la cámara tomada, abre pero no entrega fotogramas (error `0xC00D3704`).

### Lo que muestra el video

- El archivo es una grabación de pantalla vertical de 720×1280; la demo ocupa una franja de 720×403. Todas las
  medidas en píxeles tienen una precisión de más o menos 1 px sobre 720 de ancho.
- Texto de estado leído con zoom: `ведущая рука: 3 · вторая рука: масштаб ×0.40 · 31 fps`, y solo `45 fps`
  sin manos. El texto cambia a saltos, unas 3 o 4 veces por segundo, no en cada fotograma.
- Luminancia media de la escena 27/255, centro 50, esquinas entre 7 y 20: imagen muy oscura con viñeta fuerte.
- El conteo de dedos por distancias a la muñeca (punta contra nudillo medio con margen 1.10; pulgar medido
  contra la base del meñique) coincidió con el número que muestra el video en todos los tramos comparados
  (1, 2, 3, 4 y 5 dedos).
- El esqueleto va algo retrasado respecto a la mano cuando esta se mueve rápido (fotogramas 0 y 320), lo que
  encaja con una detección asíncrona.
- La estela son copias separadas y nítidas de las aristas, coherente con el búfer con decaimiento.

### La escala no sigue la pinza

Leí la escala del texto de estado en 47 fotogramas y la comparé con medidas de la segunda mano:

| Medida de la segunda mano | Correlación con la escala |
|---|---|
| Pinza pulgar–índice / tamaño de mano | −0.16 |
| Punta del dedo medio a muñeca / tamaño de mano | +0.87 |
| Extensión media de los cuatro dedos | +0.68 |
| Dedos levantados | +0.59 |

Ejemplo: en el fotograma 420 el pulgar y el índice están bien separados en "L" y la escala marca ×0.37, el
mínimo; con la mano abierta y la pinza a la mitad marca entre ×1.6 y ×2.0. **La escala sigue qué tan abierta
está la mano, no la pinza.** Aun así queda variación sin explicar (la misma pose en "L" marca entre ×0.40 y
×1.25), así que la fórmula final se calibra en la etapa 3 contra esas 47 lecturas.

## 2. Decisiones de diseño

1. **Detección desacoplada.** `HandLandmarker` en modo `LIVE_STREAM`: el bucle envía el último fotograma con
   `detect_async` y sigue dibujando; el resultado llega por callback y se guarda como "últimas manos". Si en
   la etapa 1 el callback da problemas, la alternativa es un hilo propio con `detect_for_video`.
2. **Hilos:** captura (conserva solo el último fotograma), detección (interno de MediaPipe) y principal
   (render y ventana). Un solo proceso y una sola ventana `cv2.imshow`.
   **El dibujo lleva su propio reloj** (`FPS_OBJETIVO`, 45 por defecto como en el video) y usa el último
   fotograma disponible; así el giro y la estela no heredan el ritmo irregular de la cámara. A la detección
   solo se envían fotogramas nuevos.
3. **Backend de cámara por sistema:** MSMF en Windows, AVFoundation en macOS, V4L2 en Linux, con `CAP_ANY`
   como respaldo. Se pide 1280×720 y se registra lo que entrega; si entrega otra cosa, se reescala al tamaño
   de ventana.
4. **Escala:** por defecto, extensión de los dedos índice y medio de la segunda mano; la pinza queda como
   fórmula alternativa en `config`.
5. **Transformación entre figuras:** cada figura se describe con 180 segmentos y se interpola segmento a
   segmento con suavizado. Son tres tramos de 60 (base, tapa y uniones), y 60 se divide en partes enteras
   entre 3, 4 y 5 lados.
6. **Estela y halo:** búfer de estela a resolución completa (decaimiento y luego aristas nuevas); el halo sale
   de ese búfer reducido a 1/4, desenfocado y reescalado; ambos se suman a la cámara atenuada.
7. **Texto:** Pillow dibuja cada cadena una vez en un parche pequeño, que se guarda y se mezcla solo en su
   zona. El estado se regenera unas 4 veces por segundo, como en el video.
8. **Modelo:** `modelos/hand_landmarker.task` va versionado en el repositorio para que `python main.py`
   funcione sin red.

## 3. Etapas

Cada etapa termina con una prueba en la cámara, una medición de fps y un commit. Si algo baja de 30 fps, se
optimiza antes de seguir.

### Etapa 0. Base del repositorio (hecha)

`PLAN.md`, `requirements.txt`, `.gitignore`, modelo descargado, entorno verificado.

### Etapa 1. Cámara, detección y esqueleto (hecha, falta tu revisión visual)

- `config.py`: resoluciones, índice de cámara, espejo, ritmo de dibujo, umbrales, esqueleto.
- `camara.py`: hilo de captura con selección de backend, comprobación de la resolución real y tres búferes
  fijos.
- `manos.py`: `HandLandmarker` en `LIVE_STREAM` sobre copia de 640×360.
- `render.py`: recorte a la proporción de la ventana, espejo y esqueleto tenue de 1 px.
- `main.py`: bucle con reloj propio, salida con `q`, `Esc` o cerrando la ventana, argumentos `--camara` y
  `--resolucion`, y una línea de medición por segundo en consola.

Medido con la cámara real a 1280×720:

| Medida | Valor |
|---|---|
| Ritmo de dibujo | 45.0 fps, peor intervalo 22.6 a 23.2 ms (ideal 22.2) |
| Fotogramas de cámara | 30 por segundo nominales, unos 24 distintos |
| Detección | 12 a 14 ms sin manos, 20 a 30 ms con una o dos |
| CPU del proceso | 60 a 90 % de un núcleo sin manos, 115 a 130 % con manos (de 12 núcleos lógicos) |
| Memoria | 205 a 212 MB |

El ritmo de dibujo casi no cambia el consumo (probado a 30, 45 y 60 fps): lo que pesa es la detección.

### Etapa 2. Dedos y roles (hecha, falta tu revisión visual)

- `manos.py`: `Seguidor` mantiene la identidad de cada mano entre detecciones por cercanía de la palma. La
  más antigua es la principal y la siguiente es la segunda; si la principal se pierde, la otra toma su lugar.
  Una mano se da por perdida tras 4 detecciones seguidas sin verla, para que un parpadeo del detector no
  cambie los roles.
- Conteo de dedos con inercia de 4 detecciones iguales seguidas.
- Escala con topes 0.35 y 3.2, que se conserva cuando la segunda mano sale.
- Rótulos provisionales en pantalla (rol, identidad y dedos junto a cada mano, y una línea de estado).

Comprobado contra el video, pasando sus 817 fotogramas por el detector y el seguidor:

| Aspecto | Resultado |
|---|---|
| Roles | Los relevos coinciden con el video: la mano izquierda pasa a principal en el fotograma 316 |
| Segunda mano presente | 56 de 58 lecturas; las otras dos son un adelanto de un cuarto de segundo |
| Dedos de la principal | 48 de 58 lecturas |
| Escala | Correlación 0.91 con la del video, error medio de 0.37 |

De los 10 desajustes de dedos, 5 son adelantos (aquí el cambio se nota antes que en el texto del video) y 5
son un tramo donde el video comprimido muestra el meñique doblado y el original contó 5.

**Fórmula de la escala.** Se probaron 5184 medidas de la segunda mano. Ninguna reproduce el video con
exactitud; la mejor entre las interpretables es la extensión de los dedos índice y medio (distancia de sus
puntas a la muñeca, dividida por el tamaño de la mano), con correlación 0.91 a 0.94. La pinza da −0.16. El
mapa a escala es lineal entre 1.30 (×0.35) y 2.00 (×3.2), y todo queda ajustable en `config`.

### Etapa 3. Figuras y transformación (hecha, falta tu revisión visual)

- `figuras.py`: las seis figuras como 180 segmentos 3D cada una, repartidos en tres tramos de 60: lazo de la
  base, lazo de la tapa y aristas que los unen. En las figuras planas los dos lazos coinciden y las uniones
  miden cero, así que un prisma se aplana al pasar a cuadrado o anillo, y el anillo se cierra al pasar a
  segmento.
- Transformación de 0.4 s con arranque y llegada suaves, de forma y color a la vez. Si los dedos cambian a
  mitad de camino, parte de la forma que hubiera en ese momento, sin saltos.
- Giro autónomo a 0.6 y 0.4 rad/s, proyección en perspectiva y suavizado de posición y escala que no depende
  del ritmo de dibujo.
- Sin manos, la figura vuelve al anillo y se queda en su última posición. Antes de que aparezca la primera
  mano no se dibuja.
- Las aristas son líneas simples de 3 px; el halo y la estela llegan en la etapa 4.

Calibrado contra el video, localizando la figura original por su color en 264 fotogramas con la mano quieta:

| Parámetro | PROMPT | Medido | Queda en |
|---|---|---|---|
| Separación sobre el centro de la palma | 1.6 tamaños de mano | 2.44 ± 0.13 | 2.4 |
| Diámetro a ×1.0 | 18 % del ancho | 18.8 % (incluye el halo) | 18 % |
| Desfase horizontal respecto a la palma | centrada | 0.000 ± 0.018 anchos | centrada |
| Distancia de la cámara virtual | perspectiva suave | cara lejana al 60–69 % de la cercana | 1.8 diámetros |

La separación es proporcional al tamaño de la mano (variación del 5 %), no una distancia fija en píxeles
(variación del 12 %). El costo por dibujo es de 0.06 ms de cálculo y 0.67 ms de trazado.

### Etapa 4. Halo, estela, textos y cierre

- Atenuación fría con viñeta, estela, halo aditivo, aviso sin manos y línea de estado.
- Comportamiento sin manos: la figura se transforma en anillo en su última posición.
- `README.md`: instalación, ejecución, ajuste de `config` y mediciones de fps, CPU y memoria.
- Prueba: comparación lado a lado con fotogramas del video.

## 4. Pendientes y riesgos

- **Fps de la cámara:** la imagen de fondo se renueva unas 24 veces por segundo aunque la figura se dibuje a
  45. Puede deberse a la exposición automática con poca luz o al ajuste antiparpadeo de la cámara; no se
  controla desde OpenCV.
- **Consumo de la detección:** es casi todo el gasto de CPU. Si hiciera falta bajarlo, la opción es limitar
  cuántas detecciones por segundo se envían; se decide con las mediciones de la etapa 4.
- **Decaimiento de la estela:** el 0.82 por fotograma del PROMPT corresponde a unos 45 fps; se expresará de
  forma que no cambie de aspecto si se cambia `FPS_OBJETIVO`.
- **Fórmula de escala:** la extensión de índice y medio explica la mayor parte, pero no todo; puede que el
  original use otra medida. Si al probarla no se siente como en el video, se cambia en `config`.
- **Espejo:** el video no permite confirmarlo; queda activado por defecto y ajustable.
- **Fuente del texto:** se usará una sans del sistema (Segoe UI en Windows) con respaldo en la fuente
  incluida en Pillow; el tamaño se ajusta comparando con el video.
