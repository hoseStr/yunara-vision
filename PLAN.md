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
- **DirectShow no abre** el dispositivo en esta máquina. **Media Foundation (MSMF) sí abre**, con modo por
  defecto 640×480 a 30 fps, así que pedir 1280×720 y leer lo que realmente entrega es obligatorio.
- **Pendiente:** al pedir fotogramas, MSMF devolvió el error `0xC00D3704` (el dispositivo no pudo iniciar la
  transmisión), que suele aparecer cuando otra aplicación tiene la cámara tomada. No pude medir la
  resolución ni los fps reales. Hay que resolverlo antes de probar la etapa 1.

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
3. **Backend de cámara por sistema:** MSMF en Windows, AVFoundation en macOS, V4L2 en Linux, con `CAP_ANY`
   como respaldo. Se pide 1280×720 y se registra lo que entrega; si entrega otra cosa, se reescala al tamaño
   de ventana.
4. **Escala:** por defecto, apertura de la segunda mano; la pinza queda como fórmula alternativa en `config`.
5. **Transformación entre figuras:** cada figura se remuestrea a 180 segmentos (mínimo común múltiplo de 4, 9,
   12 y 15 aristas, así cada arista se parte en trozos enteros) y se interpola segmento a segmento con
   suavizado. El anillo y el segmento usan los mismos 180.
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

### Etapa 1. Cámara, detección y esqueleto

- `config.py`: resoluciones, índice de cámara, espejo, umbrales, cadenas de texto.
- `camara.py`: hilo de captura con selección de backend y comprobación de la resolución real.
- `manos.py`: `HandLandmarker` en `LIVE_STREAM` sobre copia de 640×360.
- `render.py`: espejo y esqueleto tenue de 1 px.
- `main.py`: bucle, salida con `q` o `Esc`, argumentos de índice de cámara y resolución, fps en consola.
- Prueba: se ve la cámara con el esqueleto sobre cada mano. Se anotan fps de render, ms de detección y
  resolución real de la cámara.

### Etapa 2. Dedos y roles

- Identidad de cada mano entre fotogramas por cercanía; rol principal para la más antigua, segunda para la
  nueva, relevo cuando la principal se pierde.
- Conteo de dedos con inercia de 4 fotogramas.
- Medida de apertura de la segunda mano, escala con topes 0.35 y 3.2, y retención del último valor.
- Prueba: estado provisional en pantalla con dedos, rol y escala; se verifica el relevo de manos.

### Etapa 3. Figuras y transformación

- `figuras.py`: las seis figuras como aristas 3D, remuestreo a 180 segmentos e interpolación.
- Giro autónomo en dos ejes, proyección en perspectiva suave, posición sobre la palma con suavizado
  exponencial, colores interpolados.
- Calibración de la fórmula de escala contra las 47 lecturas del video.
- Prueba: las seis figuras con 0 a 5 dedos, transformación en 0.4 s, escala con la segunda mano.

### Etapa 4. Halo, estela, textos y cierre

- Atenuación fría con viñeta, estela, halo aditivo, aviso sin manos y línea de estado.
- Comportamiento sin manos: la figura se transforma en anillo en su última posición.
- `README.md`: instalación, ejecución, ajuste de `config` y mediciones de fps, CPU y memoria.
- Prueba: comparación lado a lado con fotogramas del video.

## 4. Pendientes y riesgos

- **Cámara ocupada** (error `0xC00D3704`): cerrar lo que la esté usando y repetir la prueba. Bloquea la
  prueba de la etapa 1, no su escritura.
- **Fps de la cámara:** si la cámara entrega 30 fps a 1280×720, ese es el techo real; los 45 fps del video
  dependen de la cámara del autor.
- **Fórmula de escala:** la apertura explica la mayor parte, pero no todo. Se ajusta en la etapa 3.
- **Espejo:** el video no permite confirmarlo; queda activado por defecto y ajustable.
- **Fuente del texto:** se usará una sans del sistema (Segoe UI en Windows) con respaldo en la fuente
  incluida en Pillow; el tamaño se ajusta comparando con el video.
