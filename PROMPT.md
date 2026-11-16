# Hand Figure: réplica nativa en Python

## Qué quiero

Quiero replicar una demo que vi en un video: una figura geométrica de neón flota sobre mi mano en la imagen de la webcam, cambia de forma según cuántos dedos levanto, y con la otra mano le cambio el tamaño.

La demo original corre en el navegador (en el video se ve una pestaña "Hand Figure" en `127.0.0.1:5173`, o sea un servidor de desarrollo web). **El único cambio que quiero es ese: que sea una aplicación nativa de escritorio en Python, sin navegador, sin servidor local y sin webview**, para no gastar más CPU, GPU y RAM de lo necesario. Todo lo demás debe verse y comportarse igual que en el video.

Empieza en un repositorio vacío. Si existe `referencia/vayunara.mp4`, es el video original (27 s, 30 fps): extrae fotogramas con ffmpeg y míralos antes de decidir detalles visuales; vale más que esta descripción.

## Lo que se ve en el video

Esta sección sale de analizar el video fotograma por fotograma. Los valores numéricos son estimaciones medidas sobre los fotogramas; trátalos como punto de partida y déjalos ajustables.

### Escena

- La webcam ocupa toda la ventana (16:9), con aspecto oscuro y frío: luminancia media muy baja y viñeta en las esquinas, de modo que el neón resalta.
- Encima se dibuja una sola figura de alambre (solo aristas, sin caras rellenas) con brillo de neón.
- Sobre cada mano detectada hay un esqueleto muy tenue: líneas finas claras de 1 px entre los 21 puntos de la mano, casi imperceptible.
- Abajo a la izquierda, un texto de estado diminuto. En el centro, un aviso cuando no hay manos.

### Mano principal: elige la figura

El número de dedos levantados de la mano principal define la figura. La regla es un prisma cuya base tiene tantos lados como dedos, con los casos pequeños degenerados:

| Dedos | Figura | Color aproximado |
|---|---|---|
| 0 (puño) | Anillo (círculo) | Blanco azulado `#DCEBFF` |
| 1 | Segmento de línea | Cian `#5CE6E0` |
| 2 | Cuadrilátero plano (cuadrado) | Verde menta `#55E6A5` |
| 3 | Prisma triangular (6 vértices, 9 aristas) | Amarillo `#F2E94E` |
| 4 | Cubo (8 vértices, 12 aristas) | Naranja `#FF9A4D` |
| 5 | Prisma pentagonal (10 vértices, 15 aristas) | Rosa magenta `#FF5FD0` |

Los tonos están medidos del video (matices cerca de 205°, 175°, 153°, 58°, 26° y 319°), pero la compresión lava la saturación, así que los hex son mi reconstrucción.

### Segunda mano: escala

- Si aparece una segunda mano, controla el tamaño de la figura. Con la mano cerrada o los dedos juntos la escala baja hasta ×0.35 (ese mínimo se repite varias veces, parece un tope). Con pulgar e índice bien separados o la mano abierta sube hasta alrededor de ×3.1.
- Lo más coherente con el video es: escala proporcional a la distancia entre la punta del pulgar y la punta del índice, normalizada por el tamaño de la mano para que no dependa de la distancia a la cámara.
- Cuando la segunda mano sale del cuadro, **la escala se queda en el último valor**; no vuelve a un valor por defecto.
- Tamaño de referencia: a ×1.0 la figura mide cerca del 18 % del ancho de la imagen; a ×0.35 cerca del 6 %; a ×3.1 llega a la mitad del ancho y puede salirse del cuadro.

### Cuál mano es la principal

- La principal es la que lleva más tiempo en cuadro. Una mano nueva entra como segunda.
- Si la principal se pierde y queda otra, esa otra pasa a ser la principal y la figura vuela hacia ella dejando una estela larga.
- No uses la etiqueta izquierda/derecha del modelo para esto: en el video los roles se intercambian entre ambas manos según el orden de aparición. Mantén la identidad entre fotogramas emparejando por cercanía.

### Posición y rotación

- La figura flota justo encima de la mano principal: centrada horizontalmente sobre la palma y un poco por encima de las puntas de los dedos. Ese desplazamiento es fijo, no crece con la escala, así que una figura grande se superpone a la mano y a la cara.
- Sigue a la mano con suavizado, no pegada rígidamente.
- Gira sola todo el tiempo, en más de un eje y despacio, aunque la mano esté quieta. Proyección en perspectiva suave.

### Transiciones, estela y brillo

- Al cambiar el número de dedos, la figura **se transforma** en la siguiente en unos 0.4 s: los vértices se desplazan y el color se interpola a la vez. No hay corte seco.
- El conteo de dedos tiene algo de inercia: tarda unos fotogramas en reaccionar, lo que evita parpadeos.
- **Estela:** cuando la figura se mueve, gira rápido o cambia de escala, deja copias fantasma de las aristas que se desvanecen (se distinguen entre 6 y 10 ecos). Con la figura quieta casi no se nota. La estela afecta solo a la figura, no a la imagen de la cámara.
- **Brillo:** aristas de unos 3 px (a 1280×720) con núcleo claro y halo difuso del mismo color, sumado de forma aditiva sobre la cámara.

### Textos

- Sin manos: aviso centrado, en blanco y pequeño, un poco por encima del centro. Original en ruso: «Покажите руку в кадр». La línea de estado muestra solo los fps.
- Con manos, línea de estado abajo a la izquierda, en gris claro y muy pequeña. Original: `ведущая рука: N · вторая рука: нет · 45 fps`, y con segunda mano `ведущая рука: N · вторая рука: масштаб ×1.83 · 45 fps`.
- Ponlos en español y deja las cadenas en un solo lugar para poder cambiarlas: «Muestra la mano en cámara», `mano principal: N · segunda mano: no · 45 fps`, `mano principal: N · segunda mano: escala ×1.83 · 45 fps`.

## Restricción central: nativo y liviano

El motivo de todo el proyecto es el consumo de recursos, así que pesa en cada decisión.

- Una sola ventana nativa y un solo proceso. Nada de Electron, webview, servidor HTTP ni dependencias web.
- Dependencias mínimas. Mi propuesta: `opencv-python` para captura, dibujo y ventana, `mediapipe` para las manos, `numpy`, y `Pillow` solo para el texto. Si crees que otra combinación es más liviana, dímelo con el motivo antes de cambiarla.
- Todo en CPU debe alcanzar. No agregues una capa de GPU (moderngl, pyglet, shaders) salvo que midas que no se llega al objetivo sin ella.
- Objetivo: 30 fps o más estables a 1280×720 en un portátil normal. El video original marca entre 30 y 49 fps.

Decisiones que ayudan y que espero ver:

- Correr la detección de manos sobre una copia reducida del fotograma (por ejemplo 640×360) y con el modelo ligero. Los puntos salen normalizados, así que sirven igual para dibujar a resolución completa.
- Captura en un hilo aparte que conserve solo el último fotograma, para no acumular retraso.
- Calcular el halo sobre una capa reducida (1/4 de resolución) y reescalarla, en vez de desenfocar a resolución completa.
- La estela como un búfer que se multiplica por un factor de decaimiento en cada fotograma y luego recibe las aristas actuales.
- Reutilizar búferes; no reservar arreglos grandes en cada fotograma.
- Renderizar cada texto una vez y guardarlo; volver a generarlo solo cuando cambie.

## Trampas que conviene revisar antes de escribir código

- **API de MediaPipe:** verifica qué API está vigente en la versión que se instala y qué versiones de Python soporta. La API actual es la de Tasks (`HandLandmarker`, con su archivo de modelo `.task`); la antigua `mp.solutions.hands` puede no estar disponible. No lo des por sabido, compruébalo.
- **Texto:** `cv2.putText` solo dibuja ASCII. Los símbolos `×` y `·` y las tildes no salen. Por eso propongo Pillow para el texto.
- **Cámara:** el backend y la resolución real dependen del sistema operativo. Detecta el sistema, pide 1280×720 y comprueba qué entrega de verdad la cámara.
- **Conteo de dedos:** que no dependa de la orientación de la mano. Comparar distancias a la muñeca (punta frente a nudillo medio) funciona mejor que comparar coordenadas en Y. El pulgar necesita su propio criterio.

## Estructura sugerida

Módulos pequeños, sin sobrediseño:

- `camara`: hilo de captura.
- `manos`: detección, seguimiento de identidad, roles principal y segunda, conteo de dedos con inercia, medida de la pinza.
- `figuras`: geometría de las seis figuras como aristas en 3D y la transformación entre ellas. Como tienen distinto número de aristas, una opción es remuestrearlas a un número común de segmentos e interpolar.
- `render`: composición de cámara atenuada, esqueleto, figura con halo y estela, y textos.
- `config`: todos los valores ajustables en un solo sitio.
- `main`: bucle principal. Salir con `q` o `Esc`. Argumentos mínimos: índice de cámara y resolución.

## Valores ajustables de partida

| Parámetro | Valor inicial |
|---|---|
| Resolución de ventana | 1280×720 |
| Resolución de detección | 640×360 |
| Manos máximas | 2 |
| Inercia del conteo de dedos | 4 fotogramas iguales seguidos |
| Duración de la transformación | 0.4 s, con suavizado |
| Escala mínima y máxima | 0.35 y 3.2 |
| Escala inicial sin segunda mano | 1.0 |
| Diámetro a ×1.0 | 18 % del ancho |
| Altura de la figura sobre la palma | 1.6 veces el tamaño de la mano (muñeca a nudillo medio) |
| Suavizado de posición y escala | exponencial, factor cercano a 0.25 por fotograma |
| Velocidad de giro | 0.6 y 0.4 rad/s en dos ejes |
| Decaimiento de la estela | 0.82 por fotograma |
| Grosor de arista | 3 px |
| Atenuación de la cámara | 55 % de brillo, tinte frío leve, viñeta |

## Lo que no pude confirmar en el video

Decide con criterio y deja cada punto como opción en `config`:

- Si la imagen está en espejo. Asume que sí, como en cualquier vista tipo selfie.
- Si la oscuridad y el tinte son un efecto de la app o solo la habitación. Impleméntalo como efecto ajustable.
- Si la orientación de la mano influye en el giro. Parece giro autónomo.
- La fórmula exacta de la escala. La distancia entre pulgar e índice es la hipótesis que mejor encaja.
- Qué pasa con la figura sin manos. En el primer fotograma se ve transformándose hacia el anillo en su última posición mientras aparece el aviso; replica eso.
- El texto de estado es muy pequeño y está comprimido; lo leí con seguridad razonable, pero no carácter por carácter.

## Cómo sabré que está bien

- Al ejecutar `python main.py` se abre una ventana nativa con la cámara, sin navegador.
- Las seis figuras aparecen con 0 a 5 dedos, con sus colores, y pasan de una a otra transformándose.
- La segunda mano cambia la escala entre ×0.35 y cerca de ×3.2, y la escala se conserva al retirarla.
- Al retirar la mano principal, la otra toma el control y la figura vuela hacia ella con estela.
- El texto de estado y el aviso sin manos se ven como se describe, con los fps reales.
- 30 fps o más a 1280×720. Mide y anota en el README los fps, el uso de CPU y la memoria en mi máquina.
- README corto: instalación, ejecución y cómo ajustar `config`.

## Forma de trabajar

- Avanza por etapas y prueba cada una en mi cámara antes de seguir: primero cámara y detección con el esqueleto, luego conteo de dedos y roles, luego figuras y transformación, y al final halo, estela y textos.
- Mide el rendimiento después de cada etapa. Si algo baja de 30 fps, optimiza eso antes de añadir más.
- Si un detalle visual no queda claro y existe el video de referencia, revisa los fotogramas en vez de suponer. Si sigue sin estar claro, pregúntame.
- No agregues funciones que no estén aquí (grabación, menús, más gestos, sonido).
