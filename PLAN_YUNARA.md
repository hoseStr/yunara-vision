# Plan: las cuentas de Yunara alrededor del cuello

Proyecto construido sobre la base de Hand Figure (`PLAN.md`). Se conserva lo que ya funcionaba: cámara
sin retraso, detección asíncrona, bucle de dibujo con reloj propio a 45 fps y valores en `config.py`.
Lo que aquí dice "medido" se ejecutó de verdad en esta máquina (Ryzen 5 5600X, Windows 11).

## Referencias

En `referencia/` están `yunara.png`, `yunara_2.png` y `yunara_bailando.gif` (25 fotogramas de 220×144,
2.5 s).

- Las armas son **6 cuentas esféricas de bronce** con relieves oscuros y tachuelas, de tamaño parecido a
  la cabeza.
- En `yunara.png` forman un anillo inclinado alrededor del cuerpo: se ven 5 y la sexta queda tapada.
  Las de atrás están más arriba y se ven más chicas que las de delante.
- En el baile flotan despacio en arco detrás de la cabeza, cada una con un **aura violeta tenue**.

Pedido: las cuentas giran alrededor del cuello. Primero esferas básicas, después un modelo 3D realista.

## Etapas

### Etapa 1. Esferas alrededor del cuello (hecha)

- `deteccion.py`: base común de los detectores. La imagen se reduce a 640×360 una sola vez y va a los
  dos. Se corrigió además que una respuesta tardía del detector lo marcara como libre con un envío
  pendiente.
- `cuerpo.py`: `PoseLandmarker` lite con silueta. El cuello está entre el centro de los hombros y la
  boca (45 % hacia la boca); la escala es el ancho de hombros y la inclinación sigue la línea de los
  hombros. Si los hombros salen del cuadro, se estiman con las orejas.
- `cuentas.py`: anillo de 6 cuentas con giro, flote, inclinación de 22° y perspectiva. Todas las
  medidas van en anchos de hombros, así el anillo crece y se encoge con la distancia a la cámara.
  Aparecen y se desvanecen con la persona.
- `render.py`: esferas de bronce iluminadas con aura violeta. Las cuentas que pasan detrás del cuello
  las tapa la silueta de la persona.
- Se quitó la figura de alambre, la estela y el halo. `figuras.py` quedó sin usar, para borrarlo en el
  commit. La detección de manos sigue activa para la etapa de gestos.

Medido:

| Medida | Valor |
|---|---|
| Pose lite, con silueta (video de referencia) | 12.1 ms de media; el modelo full, 17.1 ms |
| Pose lite en la app con la cámara real | 13 a 16 ms |
| Dibujo de las cuentas (video de referencia) | 0.83 ms de media, p95 1.1 ms |
| Ritmo de dibujo con cámara real | 45 fps, peor intervalo 22.7 ms |
| CPU del proceso | 83 a 120 % de un núcleo (antes 60 a 100 %) |

La primera versión del dibujo mezclaba en float con numpy y costaba 5.1 ms. Ahora mezcla en uint8 con
OpenCV y reduce una esfera maestra en vez de calcular cada tamaño.

### Etapa 2. Modelo 3D de las cuentas en GPU (hecha)

Mirando de cerca las cuentas de `yunara.png`: bronce pálido, tachuelas de acero gris que sobresalen del
contorno con un collar de bronce, líneas grabadas y medialunas anchas color carbón (dos o tres por lado).

- `modelo_cuenta.py`: la cuenta se genera en código sobre una esfera geodésica de 40962 vértices. El
  relieve es desplazamiento real: 12 tachuelas en los vértices de un icosaedro, collar, línea grabada y
  una medialuna por cada par de tachuelas opuestas, medida desde su propia tachuela para que no se corte.
  Cada vértice lleva su material (oscuro, acero). Se genera en 0.1 s al arrancar.
- `render_gpu.py`: moderngl con contexto sin ventana. Las 6 cuentas van en una sola llamada instanciada,
  con 4 muestras por píxel. Luz metálica con reflejo de Fresnel, luz principal cálida, relleno frío y
  reflejo de un entorno simple; las medialunas son pintura mate. El aura es un cuadrado de frente a la
  cámara que se suma. La oclusión ahora es por píxel: la silueta se sube como textura y tapa cada punto
  según su profundidad, así una cuenta medio detrás queda medio tapada.
- Las cuentas giran además sobre sí mismas (`CUENTA_GIRO_PROPIO`).
- Si la GPU no arranca, se usa el dibujo en CPU de la etapa 1 (`RENDER_CUENTAS`).

Rendimiento: medido aislado, el dibujo tardaba 1.7 ms, pero dentro del bucle tardaba entre 5 y 10 ms.
Había dos causas:

| Causa | Arreglo | Efecto |
|---|---|---|
| Malla de 163842 vértices | 40962: a tamaño real ya hay menos de un píxel por triángulo | 1.7 → 0.7 ms aislado |
| La CPU esperaba a la GPU para leer, y la GPU se enfría entre dibujos | Lectura asíncrona con dos búferes: cada dibujo recoge el anterior (un dibujo de atraso, 22 ms) | 6.3 → 1.3 ms en el bucle, con la mezcla |

Medido con la cámara real a 1280×720:

| Medida | Valor |
|---|---|
| Ritmo de dibujo | 45 fps, peor intervalo 22.7 ms |
| CPU, GPU frente a CPU, alternando dos veces | 102 y 107 % frente a 100 y 106 % de un núcleo: la GPU no añade carga |
| Memoria | 368 MB (contexto de GPU y modelo de pose incluidos) |

### Etapa 3. Mover las cuentas con las manos (hecha, falta tu revisión)

Gestos, con cualquiera de las dos manos:

| Gesto | Efecto |
|---|---|
| Pinza (pulgar e índice juntos) cerca de una cuenta | La agarra; sigue los dedos con el aura más intensa |
| Soltar la pinza despacio | La cuenta regresa planeando al cuello |
| Soltar la pinza con la mano en movimiento rápido | La lanza: vuela con el impulso, frena y regresa |
| Palma abierta sostenida medio segundo | Las cuentas vuelan a la mano y giran a su alrededor |
| Puño con la mano que las convocó | Regresan al cuello |

- `manos.py`: se quitó la escala con la segunda mano y los roles principal/segunda del proyecto base.
  Cada mano lleva ahora su pinza (con histéresis: se cierra por debajo de 0.35 tamaños de mano y se
  abre por encima de 0.50) y cuántas detecciones seguidas lleva con la palma abierta.
- `cuentas.py`: cada cuenta tiene posición, velocidad y estado (órbita, mano, agarrada, libre,
  regreso). Persigue su objetivo con un resorte de amortiguamiento crítico integrado de forma exacta,
  así llega sin rebotar y sin saltos aunque la mano se detecte a tirones (25 veces por segundo frente
  a 45 dibujos). Cada estado tiene su rigidez: casi pegada a los dedos al agarrarla, más suave al
  regresar. La velocidad al soltar sale del propio resorte, sin estimar la de la mano.
- Las cuentas agarradas o convocadas van un poco por delante del cuello, así no las tapa la silueta.
- La mano que tiene las cuentas convocadas no agarra: al cerrarla en puño también hace pinza.
- La GPU recibe la intensidad del aura de cada cuenta.
- La consola muestra cuántas cuentas hay en cada estado.

Comprobado con una mano simulada (pinza, arrastre, soltar despacio, lanzar, convocar, mover la mano y
puño): todos los cambios de estado ocurren como en la tabla. En la app con la cámara real: 45 fps,
CPU entre 110 y 147 % de un núcleo, y la consola registró cuentas convocadas, agarradas y regresando.

## Pendientes

- Ajustar a ojo el tamaño, la altura y la inclinación del anillo con tu cámara (`config.py`, sección
  "Cuentas"), y el aspecto de la cuenta (secciones "Modelo 3D de la cuenta" y "Aspecto de las cuentas").
- Calibrar los gestos con tu mano: `PINZA_CIERRA`/`PINZA_ABRE` si la pinza no engancha o se suelta
  sola, `CONVOCAR_DETECCIONES` si la palma abierta convoca sin querer al acercar la mano para agarrar,
  y `LANZAR_VELOCIDAD`/`LIBRE_SEGUNDOS` para el lanzamiento.
- Con la oclusión, la silueta llega con un poco de retraso: si te mueves rápido, el borde de una cuenta
  de atrás puede verse un instante sobre la cara.
