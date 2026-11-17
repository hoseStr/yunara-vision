"""Composición de la imagen: cámara atenuada, esqueleto, figura con estela y halo, y textos."""
from collections import deque

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config
from manos import CONEXIONES

_CONEXIONES = np.array(CONEXIONES)
_REDUCCION = 4  # el halo se calcula a 1/4 de resolución


def _mapa_ganancia(ancho, alto):
    """Ganancia por píxel y canal (0 a 255): brillo, tinte frío y viñeta, calculados una sola vez."""
    y, x = np.mgrid[0:alto, 0:ancho].astype(np.float32)
    dx = (x + 0.5) / ancho * 2 - 1
    dy = (y + 0.5) / alto * 2 - 1
    r = np.hypot(dx, dy) / np.sqrt(2)  # 0 en el centro, 1 en las esquinas
    t = np.clip((r - config.VINETA_INICIO) / (1 - config.VINETA_INICIO), 0, 1)
    ganancia = config.BRILLO * (1 - config.VINETA_FUERZA * t * t * (3 - 2 * t))
    mapa = ganancia[..., None] * np.array(config.TINTE, np.float32) * 255
    return np.clip(np.rint(mapa), 0, 255).astype(np.uint8)


def _trazos(segmentos):
    """Convierte los segmentos (n, 2, 2) en píxeles en polilíneas con 4 bits de fracción.

    Los segmentos que se tocan se unen en una sola polilínea, que OpenCV dibuja más rápido que
    segmentos sueltos, y se descartan los de menos de medio píxel (las uniones de las figuras planas
    miden cero).
    """
    p = np.rint(segmentos * 16).astype(np.int32)  # 4 bits de fracción: el giro lento no salta de píxel en píxel
    p = p[np.abs(p[:, 1] - p[:, 0]).max(axis=1) > 8]
    if not len(p):
        return []
    cortes = np.flatnonzero((p[1:, 0] != p[:-1, 1]).any(axis=1)) + 1
    return [np.concatenate((g[:, 0], g[-1:, 1])) for g in np.split(p, cortes)]


def _pasos_hasta_apagar(factor):
    """Dibujos que tarda un píxel a 255 en llegar a 0 con el decaimiento de la estela."""
    v, pasos = np.full((1, 1), 255, np.uint8), 0
    while v[0, 0]:
        v = cv2.addWeighted(v, factor, v, 0, -1)
        pasos += 1
    return pasos


class Render:
    """Dibuja sobre un único lienzo del tamaño de la ventana, que se reutiliza en cada fotograma."""

    def __init__(self, ancho, alto):
        self.ancho, self.alto = ancho, alto
        self._px = ancho / 1280  # las medidas en píxeles de config están pensadas para 1280 de ancho
        self.lienzo = np.empty((alto, ancho, 3), np.uint8)
        self._camara = np.empty_like(self.lienzo)  # cámara recortada y espejada, sin atenuar
        self._fondo = np.empty_like(self.lienzo)  # la misma, atenuada
        self._ganancia = _mapa_ganancia(ancho, alto)

        # Estela: se apaga restando además 1 en cada paso para que los valores bajos lleguen a 0
        # (convertScaleAbs redondea y deja restos de 1 y 2 que no desaparecen nunca).
        self._estela = np.zeros_like(self.lienzo)
        # El halo sale de una segunda estela a 1/4 de resolución donde las aristas se dibujan
        # directamente: reducir la estela grande costaba 1.3 ms por dibujo.
        self._estela_chica = np.zeros((-(-alto // _REDUCCION), -(-ancho // _REDUCCION), 3), np.uint8)
        self._decaimiento = config.ESTELA_DECAIMIENTO ** (config.FPS_REFERENCIA / config.FPS_OBJETIVO)
        # Rectángulos de las últimas aristas dibujadas. Todo lo que hay en la estela está dentro de
        # alguno, así que basta trabajar en su unión en vez de en la imagen entera.
        self._cajas = deque(maxlen=_pasos_hasta_apagar(self._decaimiento) + 1)
        self._grosor = max(1, round(config.ARISTA_GROSOR * self._px))
        self._halo_sigma = config.HALO_DESENFOQUE * self._px / _REDUCCION  # en píxeles de la estela chica

        self._fuentes = {}
        self._parches = {}  # textos ya rasterizados

    # --- Fondo ---

    def camara(self, fotograma):
        """Recibe un fotograma nuevo: lo recorta a la proporción de la ventana, reescala, espeja y
        prepara su versión atenuada. Devuelve la imagen sin atenuar, que es la que va al detector."""
        h, w = fotograma.shape[:2]
        if (w, h) == (self.ancho, self.alto):
            if config.ESPEJO:
                cv2.flip(fotograma, 1, dst=self._camara)
            else:
                np.copyto(self._camara, fotograma)
        else:
            if w * self.alto > h * self.ancho:  # sobra ancho
                util = h * self.ancho // self.alto
                x0 = (w - util) // 2
                fotograma = fotograma[:, x0:x0 + util]
            else:  # sobra alto
                util = w * self.alto // self.ancho
                y0 = (h - util) // 2
                fotograma = fotograma[y0:y0 + util]
            cv2.resize(fotograma, (self.ancho, self.alto), dst=self._camara, interpolation=cv2.INTER_LINEAR)
            if config.ESPEJO:
                cv2.flip(self._camara, 1, dst=self._camara)
        cv2.multiply(self._camara, self._ganancia, dst=self._fondo, scale=1 / 255)
        return self._camara

    def fondo(self):
        """Empieza un dibujo con la cámara atenuada del último fotograma."""
        np.copyto(self.lienzo, self._fondo)

    # --- Esqueleto ---

    def esqueleto(self, manos):
        """Líneas tenues de 1 px entre los 21 puntos de cada mano."""
        limite = np.array((self.ancho, self.alto))
        for mano in manos:
            puntos = (mano.puntos[:, :2] * limite).astype(np.int32)
            x0, y0 = np.maximum(puntos.min(axis=0) - 2, 0)
            x1, y1 = np.minimum(puntos.max(axis=0) + 3, limite)
            if x1 <= x0 or y1 <= y0:
                continue
            # La opacidad se mezcla solo en el rectángulo de la mano, no en toda la imagen.
            zona = self.lienzo[y0:y1, x0:x1]
            capa = zona.copy()
            cv2.polylines(capa, list((puntos - (x0, y0))[_CONEXIONES]), False,
                          config.ESQUELETO_COLOR, 1, cv2.LINE_AA)
            cv2.addWeighted(capa, config.ESQUELETO_OPACIDAD, zona, 1 - config.ESQUELETO_OPACIDAD, 0, dst=zona)

    # --- Figura ---

    def _recorte(self, x0, y0, x1, y1):
        x0, y0 = max(int(x0), 0), max(int(y0), 0)
        x1, y1 = min(int(np.ceil(x1)), self.ancho), min(int(np.ceil(y1)), self.alto)
        return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None

    def figura(self, segmentos, color):
        """Aristas de la figura con estela, halo aditivo y núcleo claro.

        `segmentos` viene en píxeles con forma (n, 2, 2). Se llama en cada dibujo desde que la
        figura existe, porque la estela tiene que seguir apagándose.
        """
        margen = self._grosor + 2
        esquinas = segmentos.reshape(-1, 2)
        self._cajas.append(self._recorte(*(esquinas.min(axis=0) - margen), *(esquinas.max(axis=0) + margen)))
        cajas = [c for c in self._cajas if c is not None]
        if not cajas:
            return
        x0, y0 = min(c[0] for c in cajas), min(c[1] for c in cajas)
        x1, y1 = max(c[2] for c in cajas), max(c[3] for c in cajas)

        trazos = _trazos(segmentos)
        bgr = tuple(float(c) for c in color)

        # Estela: apaga lo anterior y dibuja las aristas actuales en su color.
        estela = self._estela[y0:y1, x0:x1]
        cv2.addWeighted(estela, self._decaimiento, estela, 0, -1, dst=estela)
        # Lo mismo a 1/4 de resolución para el halo.
        q, h, w = _REDUCCION, *self._estela_chica.shape[:2]
        chica = self._estela_chica[y0 // q:-(-y1 // q), x0 // q:-(-x1 // q)]
        cv2.addWeighted(chica, self._decaimiento, chica, 0, -1, dst=chica)
        if trazos:
            cv2.polylines(self._estela, trazos, False, bgr, self._grosor, cv2.LINE_AA, shift=4)
            # Con shift=6 los mismos puntos quedan divididos por 4.
            cv2.polylines(self._estela_chica, trazos, False, bgr, 1, cv2.LINE_AA, shift=6)

        # Halo: la estela chica desenfocada, ampliada y sumada, en una zona con margen para el desenfoque.
        m = int(np.ceil(3 * self._halo_sigma))
        sx0, sy0 = max(x0 // q - m, 0), max(y0 // q - m, 0)
        sx1, sy1 = min(-(-x1 // q) + m, w), min(-(-y1 // q) + m, h)
        halo = cv2.GaussianBlur(self._estela_chica[sy0:sy1, sx0:sx1], (0, 0), self._halo_sigma)
        cv2.convertScaleAbs(halo, dst=halo, alpha=config.HALO_INTENSIDAD)
        halo = cv2.resize(halo, ((sx1 - sx0) * q, (sy1 - sy0) * q), interpolation=cv2.INTER_LINEAR)
        hx1, hy1 = min(sx1 * q, self.ancho), min(sy1 * q, self.alto)
        zona = self.lienzo[sy0 * q:hy1, sx0 * q:hx1]
        cv2.add(zona, halo[:hy1 - sy0 * q, :hx1 - sx0 * q], dst=zona)

        zona = self.lienzo[y0:y1, x0:x1]
        cv2.add(zona, estela, dst=zona)
        if trazos:
            nucleo = tuple(c + (255 - c) * config.NUCLEO_BLANCO for c in bgr)
            cv2.polylines(self.lienzo, trazos, False, nucleo, 1, cv2.LINE_AA, shift=4)

    # --- Textos ---

    def aviso(self, texto):
        """Aviso centrado, para cuando no hay manos."""
        self._texto(texto, config.AVISO_TAMANO, config.AVISO_COLOR, self.ancho / 2, self.alto / 2, "mm")

    def estado(self, texto):
        """Línea de estado abajo a la izquierda."""
        mx, my = config.ESTADO_MARGEN
        self._texto(texto, config.ESTADO_TAMANO, config.ESTADO_COLOR,
                    mx * self._px, self.alto - my * self._px, "ls")

    def _fuente(self, tamano):
        if tamano not in self._fuentes:
            for nombre in config.FUENTES:
                try:
                    self._fuentes[tamano] = ImageFont.truetype(nombre, tamano)
                    break
                except OSError:
                    continue
            else:
                self._fuentes[tamano] = ImageFont.load_default(tamano)
        return self._fuentes[tamano]

    def _parche(self, texto, tamano, color, ancla):
        """Rasteriza el texto una vez con Pillow y lo guarda listo para mezclar.

        Devuelve el desplazamiento respecto al punto de anclaje, el factor que conserva el fondo
        (sombra y letra) y el color ya multiplicado por la opacidad de la letra.
        """
        clave = (texto, tamano, color, ancla)
        if clave not in self._parches:
            if len(self._parches) > 64:  # la línea de estado cambia a menudo; no acumular
                self._parches.clear()
            fuente = self._fuente(max(6, round(tamano * self._px)))
            l, t, r, b = fuente.getbbox(texto, anchor=ancla)
            m = 3  # sitio para la sombra
            tam = (r - l + 2 * m, b - t + 2 * m)
            letra, sombra = Image.new("L", tam), Image.new("L", tam)
            ImageDraw.Draw(letra).text((m - l, m - t), texto, fill=255, font=fuente, anchor=ancla)
            ImageDraw.Draw(sombra).text((m - l + 1, m - t + 1), texto, fill=255, font=fuente, anchor=ancla)
            a = np.asarray(letra, np.float32)[..., None] / 255
            s = np.asarray(sombra.filter(ImageFilter.GaussianBlur(1)), np.float32)[..., None] / 255
            conserva = (1 - s * config.TEXTO_SOMBRA) * (1 - a)
            self._parches[clave] = (l - m, t - m, conserva, a * np.array(color, np.float32) + 0.5)
        return self._parches[clave]

    def _texto(self, texto, tamano, color, x, y, ancla):
        dx, dy, conserva, tinta = self._parche(texto, tamano, color, ancla)
        x0, y0 = round(x) + dx, round(y) + dy
        h, w = conserva.shape[:2]
        caja = self._recorte(x0, y0, x0 + w, y0 + h)
        if caja is None:
            return
        cx0, cy0, cx1, cy1 = caja
        sx, sy = slice(cx0 - x0, cx1 - x0), slice(cy0 - y0, cy1 - y0)
        zona = self.lienzo[cy0:cy1, cx0:cx1]
        zona[:] = zona * conserva[sy, sx] + tinta[sy, sx]
