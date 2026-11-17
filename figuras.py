"""Geometría de las seis figuras, transformación entre ellas y su estado en pantalla."""
import math

import numpy as np

import config

# Todas las figuras se describen con la misma cantidad de segmentos para poder interpolar una en
# otra: dos lazos (base y tapa) y las aristas que los unen. 60 por tramo se divide en partes enteras
# entre 3, 4 y 5 lados. En las figuras planas los dos lazos coinciden y las uniones miden cero.
_POR_TRAMO = 60
SEGMENTOS = 3 * _POR_TRAMO

# Lados del contorno según los dedos: 0 es un círculo y 1 un segmento.
_LADOS = (0, 1, 4, 3, 4, 5)


def _contorno(lados, t):
    """Puntos (x, y) del contorno de radio 0.5 en los parámetros t, de 0 a 1."""
    t = np.asarray(t, dtype=np.float64)
    if lados < 3:
        # El segmento es el círculo aplastado: se recorre de ida y vuelta, así el anillo se
        # transforma en él cerrándose.
        angulo = 2 * math.pi * t - math.pi / 2
        x = 0.5 * np.cos(angulo)
        y = 0.5 * np.sin(angulo) if lados == 0 else np.zeros_like(t)
        return np.stack([x, y], axis=-1)
    angulos = 2 * math.pi * np.arange(lados + 1) / lados - math.pi / 2
    vertices = 0.5 * np.stack([np.cos(angulos), np.sin(angulos)], axis=-1)
    recorrido = t * lados
    lado = np.minimum(recorrido.astype(int), lados - 1)
    fraccion = (recorrido - lado)[:, None]
    return vertices[lado] * (1 - fraccion) + vertices[lado + 1] * fraccion


def _construir(dedos):
    """Segmentos 3D de la figura, forma (SEGMENTOS, 2, 3). El diámetro de la base es 1."""
    lados = _LADOS[dedos]
    alto = config.PRISMA_ALTURA if dedos >= 3 else 0.0
    segmentos = np.zeros((SEGMENTOS, 2, 3), np.float32)

    xy = _contorno(lados, np.linspace(0, 1, _POR_TRAMO + 1))
    for k, z in enumerate((-alto / 2, alto / 2)):
        lazo = segmentos[k * _POR_TRAMO:(k + 1) * _POR_TRAMO]
        lazo[:, 0, :2], lazo[:, 1, :2], lazo[:, :, 2] = xy[:-1], xy[1:], z

    uniones = segmentos[2 * _POR_TRAMO:]
    if lados >= 3:
        trozos = _POR_TRAMO // lados  # cada arista lateral se parte en trozos iguales
        uniones[:, :, :2] = np.repeat(_contorno(lados, np.arange(lados) / lados), trozos, axis=0)[:, None]
        cortes = -alto / 2 + alto * np.arange(trozos + 1) / trozos
        uniones[:, 0, 2], uniones[:, 1, 2] = np.tile(cortes[:-1], lados), np.tile(cortes[1:], lados)
    else:
        uniones[:, :, :2] = xy[:-1, None]
    return segmentos


def _bgr(hexadecimal):
    h = hexadecimal.lstrip("#")
    return np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)], np.float32)


FORMAS = tuple(_construir(dedos) for dedos in range(6))
COLORES = tuple(_bgr(c) for c in config.FIGURA_COLORES)


def mezcla_por_fotograma(factor, dt):
    """Convierte un suavizado "por fotograma" a FPS_REFERENCIA en el equivalente para un paso dt."""
    return 1.0 - (1.0 - factor) ** (dt * config.FPS_REFERENCIA)


class Figura:
    """La figura que flota sobre la mano principal: forma, color, posición, escala y giro."""

    def __init__(self):
        self.dedos = 0
        self.segmentos = FORMAS[0].copy()
        self.color = COLORES[0].copy()
        self._origen, self._color_origen, self._avance = self.segmentos, self.color, 1.0
        self.centro = None  # píxeles; None hasta que aparece la primera mano
        self.escala = config.ESCALA_INICIAL
        self._giro = np.zeros(2)

    def avanzar(self, dt, mano, escala, ancho):
        """Avanza dt segundos hacia la mano principal (o None) y la escala indicadas."""
        dedos = mano.dedos if mano is not None else 0  # sin manos vuelve al anillo
        if dedos != self.dedos:
            # La transformación parte de la forma actual, aunque otra estuviera a medias.
            self._origen, self._color_origen = self.segmentos.copy(), self.color.copy()
            self.dedos, self._avance = dedos, 0.0
        if self._avance < 1.0:
            self._avance = min(1.0, self._avance + dt / config.TRANSFORMACION_SEGUNDOS)
            s = self._avance * self._avance * (3 - 2 * self._avance)  # arranque y llegada suaves
            self.segmentos = self._origen + (FORMAS[dedos] - self._origen) * s
            self.color = self._color_origen + (COLORES[dedos] - self._color_origen) * s

        self._giro += np.multiply(config.GIRO_VELOCIDAD, dt)

        mezcla = mezcla_por_fotograma(config.SUAVIZADO, dt)
        if mano is not None:
            # Encima de la palma, a una distancia fija que no crece con la escala.
            objetivo = np.array((mano.centro[0], mano.centro[1] - config.FIGURA_ALTURA * mano.tamano)) * ancho
            self.centro = objetivo if self.centro is None else self.centro + (objetivo - self.centro) * mezcla
        self.escala += (escala - self.escala) * mezcla

    def proyectar(self, ancho):
        """Segmentos en píxeles de pantalla, forma (SEGMENTOS, 2, 2), con perspectiva."""
        a, b = self._giro
        ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
        giro_y = np.array(((ca, 0, sa), (0, 1, 0), (-sa, 0, ca)))
        giro_x = np.array(((1, 0, 0), (0, cb, -sb), (0, sb, cb)))
        puntos = self.segmentos @ (giro_y @ giro_x).T
        cerca = config.PERSPECTIVA_DISTANCIA / (config.PERSPECTIVA_DISTANCIA - puntos[..., 2:3])
        return self.centro + puntos[..., :2] * cerca * (config.FIGURA_DIAMETRO * ancho * self.escala)
