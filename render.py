"""Composición de la imagen: cámara atenuada, esqueleto, cuentas con aura y oclusión, y textos."""
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config
from manos import CONEXIONES

_CONEXIONES = np.array(CONEXIONES)
_MAESTRA_DIAMETRO = 256  # diámetro al que se calcula la esfera; se rehace más grande si hace falta


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


def _bgr(hexadecimal):
    h = hexadecimal.lstrip("#")
    return np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)], np.float32)


def _normal(v):
    v = np.asarray(v, np.float32)
    return v / np.linalg.norm(v)


def _lado(diametro):
    """Lado del sprite de una cuenta de ese diámetro, con sitio para el aura."""
    return math.ceil(diametro * (1 + config.AURA_ALCANCE))


def _esfera(diametro):
    """Sprite de una cuenta: esfera de bronce iluminada con su aura violeta, en float32.

    Devuelve (lado, lado, 4): los tres primeros canales son la tinta (BGR) que se suma encima, ya
    multiplicada por la opacidad de la esfera, y el cuarto es esa opacidad. Fuera de la esfera la
    tinta es el aura, que se suma sin tapar el fondo.
    """
    r = diametro / 2
    lado = _lado(diametro)
    y, x = (np.mgrid[0:lado, 0:lado].astype(np.float32) + 0.5 - lado / 2) / r
    d = np.hypot(x, y)
    nz = np.sqrt(np.clip(1 - d * d, 0, 1))
    alfa = np.clip((1 - d) * r + 0.5, 0, 1)[..., None]  # borde suavizado de un píxel

    luz = _normal(config.LUZ_DIRECCION)  # x a la derecha, y hacia abajo, z hacia la cámara
    medio = _normal(luz + (0, 0, 1))
    difusa = np.clip(x * luz[0] + y * luz[1] + nz * luz[2], 0, 1)[..., None]
    brillo = (np.clip(x * medio[0] + y * medio[1] + nz * medio[2], 0, 1) ** config.BRILLO_EXPONENTE)[..., None]
    borde = ((1 - nz) ** 3)[..., None]
    violeta = _bgr(config.AURA_COLOR)
    color = (_bgr(config.CUENTA_COLOR) * (config.LUZ_AMBIENTE + config.LUZ_DIFUSA * difusa)
             + _bgr(config.BRILLO_COLOR) * config.BRILLO_INTENSIDAD * brillo
             + violeta * config.AURA_BORDE * borde)

    fuera = np.maximum(d - 1, 0)[..., None] / config.AURA_ANCHO
    aura = violeta * config.AURA_INTENSIDAD * np.exp(-fuera * fuera)
    return np.concatenate((color * alfa + aura * (1 - alfa), alfa), axis=-1)


class Render:
    """Dibuja sobre un único lienzo del tamaño de la ventana, que se reutiliza en cada fotograma."""

    def __init__(self, ancho, alto):
        self.ancho, self.alto = ancho, alto
        self._px = ancho / 1280  # las medidas en píxeles de config están pensadas para 1280 de ancho
        self.lienzo = np.empty((alto, ancho, 3), np.uint8)
        self._camara = np.empty_like(self.lienzo)  # cámara recortada y espejada, sin atenuar
        self._fondo = np.empty_like(self.lienzo)  # la misma, atenuada
        self._ganancia = _mapa_ganancia(ancho, alto)

        # La esfera se calcula una vez a buen tamaño (costaba 7 ms a 130 px) y cada diámetro sale de
        # reducirla. Los sprites listos se guardan por diámetro en píxeles.
        self._maestra = _esfera(_MAESTRA_DIAMETRO)
        self._esferas = {}

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

    # --- Cuentas ---

    def _recorte(self, x0, y0, x1, y1):
        x0, y0 = max(int(x0), 0), max(int(y0), 0)
        x1, y1 = min(int(np.ceil(x1)), self.ancho), min(int(np.ceil(y1)), self.alto)
        return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None

    def _sprite(self, diametro):
        """(alfa, conserva, tinta) de la cuenta en uint8 de 3 canales, listos para mezclar."""
        clave = max(2, round(diametro))
        if clave not in self._esferas:
            if len(self._esferas) > 256:
                self._esferas.clear()
            if _lado(clave) > self._maestra.shape[0]:
                self._maestra = _esfera(clave)
            lado = _lado(clave)
            reducida = cv2.resize(self._maestra, (lado, lado), interpolation=cv2.INTER_AREA)
            alfa = cv2.convertScaleAbs(reducida[..., 3], alpha=255)
            alfa = cv2.cvtColor(alfa, cv2.COLOR_GRAY2BGR)
            tinta = cv2.convertScaleAbs(np.ascontiguousarray(reducida[..., :3]))
            self._esferas[clave] = (alfa, cv2.bitwise_not(alfa), tinta)
        return self._esferas[clave]

    def _silueta(self, mascara, x0, y0, x1, y1):
        """Trozo de la máscara de silueta (al tamaño de detección) llevado al rectángulo indicado."""
        mh, mw = mascara.shape
        sx, sy = self.ancho / mw, self.alto / mh
        # Lleva el píxel (u, v) de la máscara a (sx·(u + ½) − ½ − x0, ...) del rectángulo.
        m = np.float32([[sx, 0, 0.5 * sx - 0.5 - x0], [0, sy, 0.5 * sy - 0.5 - y0]])
        return cv2.warpAffine(mascara, m, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REPLICATE)

    def cuentas(self, cuentas, mascara, opacidad):
        """Dibuja las cuentas de atrás hacia delante.

        `cuentas` viene de `Cuentas.proyectar`. Donde una cuenta está detrás del cuello, la silueta de
        la persona la tapa. Todo se mezcla en uint8 con OpenCV: con numpy en float costaba 0.75 ms por
        cuenta.
        """
        if opacidad <= 0:
            return
        for x, y, diametro, oculta in cuentas:
            alfa, conserva, tinta = self._sprite(diametro)
            lado = alfa.shape[0]
            x0, y0 = round(x - lado / 2), round(y - lado / 2)
            caja = self._recorte(x0, y0, x0 + lado, y0 + lado)
            if caja is None:
                continue
            cx0, cy0, cx1, cy1 = caja
            sx, sy = slice(cx0 - x0, cx1 - x0), slice(cy0 - y0, cy1 - y0)
            zona = self.lienzo[cy0:cy1, cx0:cx1]
            alfa, conserva, tinta = alfa[sy, sx], conserva[sy, sx], tinta[sy, sx]
            tapada = oculta > 0 and mascara is not None
            if opacidad < 1 or tapada:
                # Visibilidad por píxel, de 0 a 255: la opacidad, menos lo que tapa la silueta.
                if tapada:
                    visible = cv2.convertScaleAbs(self._silueta(mascara, *caja),
                                                  alpha=-opacidad * oculta, beta=255 * opacidad)
                else:
                    visible = np.full(zona.shape[:2], round(255 * opacidad), np.uint8)
                visible = cv2.cvtColor(visible, cv2.COLOR_GRAY2BGR)
                conserva = cv2.bitwise_not(cv2.multiply(alfa, visible, scale=1 / 255))
                tinta = cv2.multiply(tinta, visible, scale=1 / 255)
            cv2.multiply(zona, conserva, dst=zona, scale=1 / 255)
            cv2.add(zona, tinta, dst=zona)

    # --- Textos ---

    def aviso(self, texto):
        """Aviso centrado, para cuando no hay nadie frente a la cámara."""
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
