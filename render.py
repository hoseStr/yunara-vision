"""Composición de la imagen: fondo de cámara y esqueleto de las manos."""
import cv2
import numpy as np

import config
from manos import CONEXIONES

_CONEXIONES = np.array(CONEXIONES)


class Render:
    """Dibuja sobre un único lienzo del tamaño de la ventana, que se reutiliza en cada fotograma."""

    def __init__(self, ancho, alto):
        self.ancho, self.alto = ancho, alto
        self.lienzo = np.empty((alto, ancho, 3), np.uint8)

    def fondo(self, fotograma):
        """Lleva la cámara al lienzo: recorta a la proporción de la ventana, reescala y espeja."""
        h, w = fotograma.shape[:2]
        if (w, h) == (self.ancho, self.alto):
            if config.ESPEJO:
                cv2.flip(fotograma, 1, dst=self.lienzo)
            else:
                np.copyto(self.lienzo, fotograma)
            return
        if w * self.alto > h * self.ancho:  # sobra ancho
            util = h * self.ancho // self.alto
            x0 = (w - util) // 2
            fotograma = fotograma[:, x0:x0 + util]
        else:  # sobra alto
            util = w * self.alto // self.ancho
            y0 = (h - util) // 2
            fotograma = fotograma[y0:y0 + util]
        cv2.resize(fotograma, (self.ancho, self.alto), dst=self.lienzo, interpolation=cv2.INTER_LINEAR)
        if config.ESPEJO:
            cv2.flip(self.lienzo, 1, dst=self.lienzo)

    def texto_provisional(self, texto, x, y):
        """Texto de diagnóstico mientras no existan los textos definitivos (solo ASCII)."""
        cv2.putText(self.lienzo, texto, (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (220, 220, 220), 1, cv2.LINE_AA)

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
