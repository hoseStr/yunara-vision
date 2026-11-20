"""Las cuentas de Yunara: un anillo que gira alrededor del cuello, con flote y perspectiva."""
import math

import numpy as np

import config


def mezcla_por_fotograma(factor, dt):
    """Convierte un suavizado "por fotograma" a FPS_REFERENCIA en el equivalente para un paso dt."""
    return 1.0 - (1.0 - factor) ** (dt * config.FPS_REFERENCIA)


class Cuentas:
    """Estado del anillo: dónde está el cuello (suavizado), su tamaño, el giro y la opacidad."""

    def __init__(self):
        self.centro = None  # cuello suavizado, en píxeles; None hasta que aparece la primera persona
        self.hombros = 0.0  # ancho de hombros suavizado, en píxeles
        self.inclinacion = 0.0
        self.opacidad = 0.0  # aparecen y se desvanecen con la persona
        self._giro = 0.0
        self._tiempo = 0.0
        self._fases = 2 * math.pi * np.arange(config.CUENTAS_N) / config.CUENTAS_N

    def avanzar(self, dt, cuerpo, ancho):
        """Avanza dt segundos hacia el cuello indicado (si la persona está visible)."""
        self._giro += config.ANILLO_GIRO * dt
        self._tiempo += dt
        paso = dt / config.FUNDIDO_SEGUNDOS
        self.opacidad = min(1.0, self.opacidad + paso) if cuerpo.visible else max(0.0, self.opacidad - paso)
        if not cuerpo.visible:
            return  # se quedan donde estaban mientras se desvanecen

        cuello = np.asarray(cuerpo.cuello) * ancho
        hombros = cuerpo.hombros * ancho
        if self.centro is None:
            self.centro, self.hombros, self.inclinacion = cuello, hombros, cuerpo.inclinacion
            return
        mezcla = mezcla_por_fotograma(config.SUAVIZADO, dt)
        self.centro = self.centro + (cuello - self.centro) * mezcla
        self.hombros += (hombros - self.hombros) * mezcla
        self.inclinacion += (cuerpo.inclinacion - self.inclinacion) * mezcla

    def proyectar(self):
        """Cuentas en pantalla como (x, y, diámetro, oculta), de la más lejana a la más cercana.

        `oculta` va de 0 (delante del cuello, se ve entera) a 1 (detrás, la tapa la silueta).
        """
        h = self.hombros
        radio = config.ANILLO_RADIO * h
        angulos = self._giro + self._fases
        x = radio * np.cos(angulos)
        z = radio * np.sin(angulos)  # positivo hacia el fondo
        y = config.FLOTE_AMPLITUD * h * np.sin(2 * math.pi * config.FLOTE_HZ * self._tiempo + 2 * self._fases)

        # Anillo inclinado: la parte de atrás sube y la de delante baja, como en las referencias.
        t = math.radians(config.ANILLO_INCLINACION)
        y, z = y * math.cos(t) - z * math.sin(t), y * math.sin(t) + z * math.cos(t)
        # Sigue la inclinación de los hombros.
        r = self.inclinacion
        x, y = x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r)

        distancia = config.PERSPECTIVA_DISTANCIA * h
        cerca = distancia / (distancia + z)
        diametro = config.CUENTA_DIAMETRO * h * cerca
        # Pasa de visible a tapada mientras el centro de la cuenta cruza el plano del cuello.
        oculta = np.clip(z / (config.CUENTA_DIAMETRO * h / 2), 0.0, 1.0)
        orden = np.argsort(-z)
        return [(self.centro[0] + x[i] * cerca[i], self.centro[1] + y[i] * cerca[i], diametro[i], oculta[i])
                for i in orden]
