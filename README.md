# Yunara

Las cuentas de Yunara (League of Legends) giran alrededor de tu cuello en la imagen de la webcam.
Es una aplicación nativa de escritorio en Python: una sola ventana, sin navegador ni servidor.
Proyecto de fans para uso personal.

- Seis cuentas de bronce con aura violeta forman un anillo inclinado que gira alrededor del cuello.
- El anillo sigue tu posición, tu distancia a la cámara y la inclinación de los hombros.
- Las cuentas que pasan por detrás quedan tapadas por tu silueta.

Por ahora las cuentas son esferas; el modelo 3D y el control con las manos vienen después
(ver `PLAN_YUNARA.md`).

## Instalación

Probado con Python 3.12 en Windows 11.

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

En macOS o Linux, el entorno se activa con `source .venv/bin/activate`.

No instales `opencv-python` aparte: `mediapipe` ya trae `opencv-contrib-python`, que provee el mismo
módulo `cv2`, y los dos paquetes se pisan entre sí. Los modelos de manos y de cuerpo vienen en
`modelos/`, así que no hace falta red para ejecutarlo.

## Ejecución

```
python main.py
python main.py --camara 1 --resolucion 1920x1080
```

Se sale con `q`, `Esc` o cerrando la ventana. Una vez por segundo la consola muestra los fps de
dibujo, los fotogramas por segundo que entrega la cámara, el tiempo de cada detector, si encuentra el
cuello y el uso de CPU.

## Ajustes

Todos los valores ajustables están en `config.py`, agrupados por tema:

| Sección | Qué controla |
|---|---|
| Ventana y cámara | Resolución, índice de cámara, espejo, ritmo de dibujo (`FPS_OBJETIVO`) |
| Detección | Modelos, resolución de detección y umbrales de confianza |
| Cuerpo y cuello | Dónde se coloca el cuello entre hombros y boca, y la oclusión |
| Cuentas | Número, radio del anillo, tamaño, inclinación, giro, flote y suavizado |
| Aspecto de las cuentas | Color del bronce, luz, brillo y aura violeta |
| Escena | Brillo de la cámara, tinte frío y viñeta |
| Textos | Cadenas, fuentes, tamaños y colores |

Las medidas del anillo van en anchos de hombros, así que no dependen de la distancia a la cámara.

## Rendimiento

Medido el 2026-11-19 con la cámara real a 1280×720, en un Ryzen 5 5600X (6 núcleos, 12 hilos) con
16 GB y Windows 11:

| Medida | Valor |
|---|---|
| Ritmo de dibujo | 45 fps estables, peor intervalo 22.7 ms (ideal 22.2) |
| Detección de cuerpo | Entre 13 y 16 ms por fotograma, en un hilo aparte |
| Detección de manos | Entre 12 y 15 ms por fotograma, en un hilo aparte |
| Dibujo de las cuentas | Menos de 1 ms por fotograma |
| CPU | Entre 83 y 120 % de un núcleo (de 12 hilos disponibles) |

## Archivos

| Archivo | Contenido |
|---|---|
| `main.py` | Bucle principal con reloj propio, teclado y medición |
| `camara.py` | Captura en un hilo aparte que conserva solo el último fotograma |
| `deteccion.py` | Base de los detectores de MediaPipe: envío asíncrono y reducción compartida |
| `cuerpo.py` | Detección del cuerpo, posición del cuello y silueta |
| `cuentas.py` | Anillo de cuentas: giro, flote, inclinación y perspectiva |
| `manos.py` | Detección de manos, identidad, roles y conteo de dedos (para los gestos) |
| `render.py` | Cámara atenuada, esqueleto de las manos, cuentas con aura y oclusión, textos |
| `config.py` | Todos los valores ajustables |
| `PLAN_YUNARA.md` | Plan, mediciones y decisiones de este proyecto |
| `PLAN.md` | Mediciones y decisiones del proyecto base (Hand Figure) |
