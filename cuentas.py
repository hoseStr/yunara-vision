"""Las cuentas de Yunara: giran alrededor del cuello y se pueden mover con las manos.

Cada cuenta tiene posición y velocidad propias y un estado que decide hacia dónde va:

- ORBITA: en su sitio del anillo del cuello.
- MANO: convocada con la palma abierta; gira alrededor de esa mano.
- AGARRADA: sujeta con una pinza; sigue el punto entre el pulgar y el índice.
- LIBRE: lanzada; vuela sola, frenando, hasta que pierde impulso.
- REGRESO: vuelve planeando al anillo del cuello y, al llegar, pasa a ORBITA.

Todas menos LIBRE persiguen su objetivo con un resorte con amortiguamiento crítico: llegan sin
rebotar y sin saltos aunque el objetivo se mueva a tirones (la mano se detecta unas 25 veces por
segundo y se dibuja a 45).

Posiciones en píxeles: x e y en el plano del cuello (x a la derecha, y hacia abajo) y z hacia el
fondo, con 0 en el cuello. La perspectiva converge en el cuello: un punto a profundidad z se ve en
cuello + (xy − cuello) / w, con w = (distancia + z) / distancia.
"""
import math

import numpy as np

import config

ORBITA, MANO, AGARRADA, LIBRE, REGRESO = "órbita", "mano", "agarrada", "libre", "regreso"


def mezcla_por_fotograma(factor, dt):
    """Convierte un suavizado "por fotograma" a FPS_REFERENCIA en el equivalente para un paso dt."""
    return 1.0 - (1.0 - factor) ** (dt * config.FPS_REFERENCIA)


def giro(eje, angulo):
    """Matriz de giro de `angulo` radianes alrededor de `eje` (unitario)."""
    x, y, z = eje
    c, s = math.cos(angulo), math.sin(angulo)
    k = 1 - c
    return np.array(((c + x * x * k, x * y * k - z * s, x * z * k + y * s),
                     (y * x * k + z * s, c + y * y * k, y * z * k - x * s),
                     (z * x * k - y * s, z * y * k + x * s, c + z * z * k)))


class Cuentas:
    """Estado de las cuentas: el cuello (suavizado) y la posición, velocidad y estado de cada una."""

    def __init__(self):
        n = config.CUENTAS_N
        self.centro = None  # cuello suavizado, en píxeles; None hasta que aparece la primera persona
        self.hombros = 0.0  # ancho de hombros suavizado, en píxeles
        self.inclinacion = 0.0
        self.opacidad = 0.0  # aparecen y se desvanecen con la persona
        self._giro = 0.0
        self._tiempo = 0.0
        self._fases = 2 * math.pi * np.arange(n) / n
        # Cada cuenta gira además sobre sí misma, alrededor de un eje propio.
        ejes = np.random.default_rng(3).normal(size=(n, 3))
        self._ejes = ejes / np.linalg.norm(ejes, axis=1, keepdims=True)

        self.pos = None  # (n, 3); None hasta que aparece la primera persona
        self.vel = np.zeros((n, 3))
        self.estado = [ORBITA] * n
        self._dueno = [None] * n  # id de la mano que la tiene convocada o agarrada
        self._vuelo = np.zeros(n)  # segundos en vuelo libre
        self.brillo = np.ones(n)  # intensidad del aura: más fuerte en las que manejas
        self._convocadora = None  # id de la mano que tiene las cuentas convocadas
        self._pinzas = {}  # id de mano -> si estaba en pinza, para notar cuándo se cierra o se abre

    # --- Geometría ---

    @property
    def radio(self):
        """Radio de una cuenta, en píxeles."""
        return config.CUENTA_DIAMETRO * self.hombros / 2

    @property
    def distancia(self):
        """Distancia de la cámara virtual de la perspectiva, en píxeles."""
        return config.PERSPECTIVA_DISTANCIA * self.hombros

    def _w(self, z):
        return (self.distancia + z) / self.distancia

    def pantalla(self, pos):
        """Puntos (n, 3) llevados a píxeles de pantalla (n, 2)."""
        return self.centro + (pos[:, :2] - self.centro) / self._w(pos[:, 2:3])

    def _desde_pantalla(self, punto, z):
        """Posición a profundidad z que se ve en el punto de pantalla indicado."""
        return np.array((*(self.centro + (np.asarray(punto) - self.centro) * self._w(z)), z))

    def _anillo(self, centro, radio, inclinacion, ladeo):
        """Sitios de las cuentas en un anillo alrededor de `centro` (posición 3D), (n, 3).

        `inclinacion` en grados: la parte de atrás sube y la de delante baja. `ladeo` en radianes,
        en el plano de la imagen.
        """
        angulos = self._giro + self._fases
        x = radio * np.cos(angulos)
        z = radio * np.sin(angulos)
        y = config.FLOTE_AMPLITUD * self.hombros * np.sin(
            2 * math.pi * config.FLOTE_HZ * self._tiempo + 2 * self._fases)
        t = math.radians(inclinacion)
        y, z = y * math.cos(t) - z * math.sin(t), y * math.sin(t) + z * math.cos(t)
        x, y = x * math.cos(ladeo) - y * math.sin(ladeo), x * math.sin(ladeo) + y * math.cos(ladeo)
        return np.asarray(centro) + np.stack((x, y, z), axis=1)

    def _anillo_cuello(self):
        return self._anillo((*self.centro, 0.0), config.ANILLO_RADIO * self.hombros,
                            config.ANILLO_INCLINACION, self.inclinacion)

    # --- Avance ---

    def avanzar(self, dt, cuerpo, manos, ancho, alto):
        """Avanza dt segundos: sigue al cuello, lee los gestos de las manos y mueve las cuentas.

        `manos` son las manos seguidas (`Seguidor.manos`).
        """
        self._giro += config.ANILLO_GIRO * dt
        self._tiempo += dt
        paso = dt / config.FUNDIDO_SEGUNDOS
        self.opacidad = min(1.0, self.opacidad + paso) if cuerpo.visible else max(0.0, self.opacidad - paso)

        if cuerpo.visible:
            cuello = np.asarray(cuerpo.cuello) * ancho
            hombros = cuerpo.hombros * ancho
            if self.centro is None:
                self.centro, self.hombros, self.inclinacion = cuello, hombros, cuerpo.inclinacion
            else:
                mezcla = mezcla_por_fotograma(config.SUAVIZADO, dt)
                self.centro = self.centro + (cuello - self.centro) * mezcla
                self.hombros += (hombros - self.hombros) * mezcla
                self.inclinacion += (cuerpo.inclinacion - self.inclinacion) * mezcla
        if self.centro is None:
            return
        if self.pos is None:
            self.pos = self._anillo_cuello()

        escala = np.array((ancho, alto))
        vivas = {m.id: m for m in manos}
        self._gestos(vivas, escala)
        self._mover(dt, vivas, escala)

    def _gestos(self, vivas, escala):
        # Lo que tenía una mano que ya no está vuelve al cuello.
        for i, dueno in enumerate(self._dueno):
            if dueno is not None and dueno not in vivas:
                self._soltar(i, lanzar=False)
        if self._convocadora not in vivas:
            self._convocadora = None
        self._pinzas = {k: v for k, v in self._pinzas.items() if k in vivas}

        for mano in vivas.values():
            if mano.perdida:  # sin detección nueva no hay gesto nuevo
                continue
            # La mano que tiene las cuentas convocadas no agarra: al cerrarla en puño también hace
            # pinza, y se quedaría con una.
            convocadora = mano.id == self._convocadora
            antes = self._pinzas.get(mano.id, False)
            if mano.pinza and not antes and not convocadora:
                self._agarrar(mano, escala)
            elif not mano.pinza and antes:
                for i, dueno in enumerate(self._dueno):
                    if dueno == mano.id and self.estado[i] == AGARRADA:
                        self._soltar(i, lanzar=True)
            self._pinzas[mano.id] = mano.pinza

            if self._convocadora is None and mano.abierta >= config.CONVOCAR_DETECCIONES:
                self._convocadora = mano.id
                for i, estado in enumerate(self.estado):
                    if estado != AGARRADA:
                        self.estado[i], self._dueno[i] = MANO, mano.id
            elif convocadora and mano.dedos == 0:  # puño: que vuelvan
                self._convocadora = None
                for i, dueno in enumerate(self._dueno):
                    if dueno == mano.id:
                        self._soltar(i, lanzar=False)

    def _agarrar(self, mano, escala):
        punto = mano.punto_pinza * escala
        en_pantalla = self.pantalla(self.pos)
        alcance = config.AGARRAR_ALCANCE * self.radio / self._w(self.pos[:, 2])
        distancias = np.hypot(*(en_pantalla - punto).T)
        libres = [i for i, e in enumerate(self.estado) if e != AGARRADA]
        cerca = [i for i in libres if distancias[i] <= alcance[i]]
        if cerca:
            i = min(cerca, key=lambda k: distancias[k])
            self.estado[i], self._dueno[i] = AGARRADA, mano.id

    def _soltar(self, i, lanzar):
        rapida = np.hypot(*self.vel[i, :2]) > config.LANZAR_VELOCIDAD * self.hombros
        self.estado[i] = LIBRE if lanzar and rapida else REGRESO
        self._dueno[i] = None
        self._vuelo[i] = 0.0

    def _objetivos(self, vivas, escala):
        """Objetivo y rigidez (rad/s) del resorte de cada cuenta. En vuelo libre no hay resorte."""
        objetivos = self._anillo_cuello()
        omegas = np.full(len(objetivos), config.ORBITA_OMEGA)
        delante = config.MANO_PROFUNDIDAD * self.hombros
        anillos = {}
        for i, estado in enumerate(self.estado):
            if estado == REGRESO:
                omegas[i] = config.REGRESO_OMEGA
            elif estado == AGARRADA:
                objetivos[i] = self._desde_pantalla(vivas[self._dueno[i]].punto_pinza * escala, delante)
                omegas[i] = config.AGARRAR_OMEGA
            elif estado == MANO:
                mano = vivas[self._dueno[i]]
                if mano.id not in anillos:
                    centro = self._desde_pantalla(mano.palma * escala, delante)
                    anillos[mano.id] = self._anillo(centro, config.MANO_ANILLO_RADIO * mano.tamano * escala[0],
                                                    config.MANO_INCLINACION, 0.0)
                objetivos[i] = anillos[mano.id][i]
                omegas[i] = config.MANO_OMEGA
        return objetivos, omegas

    def _mover(self, dt, vivas, escala):
        objetivos, omegas = self._objetivos(vivas, escala)
        libres = np.array([e == LIBRE for e in self.estado])

        # Resorte con amortiguamiento crítico, integrado de forma exacta (estable con cualquier dt).
        w = omegas[:, None]
        x = self.pos - objetivos
        y = self.vel + w * x
        e = np.exp(-w * dt)
        pos = objetivos + (x + y * dt) * e
        vel = (self.vel - w * y * dt) * e

        # Vuelo libre: sigue con su impulso y frena con el aire.
        vel_libre = self.vel * math.exp(-config.LIBRE_FRENADO * dt)
        pos_libre = self.pos + vel_libre * dt
        self.pos = np.where(libres[:, None], pos_libre, pos)
        self.vel = np.where(libres[:, None], vel_libre, vel)

        llegada = config.CUENTA_DIAMETRO * self.hombros
        for i, estado in enumerate(self.estado):
            if estado == LIBRE:
                self._vuelo[i] += dt
                lenta = np.hypot(*self.vel[i, :2]) < config.LIBRE_VELOCIDAD_MIN * self.hombros
                if lenta or self._vuelo[i] > config.LIBRE_SEGUNDOS:
                    self.estado[i] = REGRESO
            elif estado == REGRESO and np.linalg.norm(self.pos[i] - objetivos[i]) < llegada:
                self.estado[i] = ORBITA

        objetivo_brillo = np.array([config.BRILLO_MANEJADA if e in (AGARRADA, LIBRE)
                                    else config.BRILLO_CONVOCADA if e == MANO else 1.0 for e in self.estado])
        self.brillo += (objetivo_brillo - self.brillo) * (1 - math.exp(-dt / config.BRILLO_SEGUNDOS))

    # --- Salida para el dibujo ---

    def proyectar(self):
        """Cuentas en pantalla como (x, y, diámetro, oculta), de la más lejana a la más cercana.

        `oculta` va de 0 (delante del cuello, se ve entera) a 1 (detrás, la tapa la silueta). Es lo
        que usa el dibujo en CPU, con esferas planas.
        """
        z = self.pos[:, 2]
        en_pantalla = self.pantalla(self.pos)
        diametro = 2 * self.radio / self._w(z)
        oculta = np.clip(z / self.radio, 0.0, 1.0)  # pasa a tapada mientras cruza el plano del cuello
        return [(*en_pantalla[i], diametro[i], oculta[i]) for i in np.argsort(-z)]

    def escena(self):
        """Lo que necesita el dibujo en GPU: (cuello, centros, ejes, radio, distancia, brillo).

        `cuello` en píxeles de pantalla; `centros` (n, 3) en píxeles respecto al cuello, de la cuenta
        más lejana a la más cercana; `ejes` (n, 3, 3) es el giro propio de cada cuenta multiplicado
        por su radio; `brillo` (n,) es la intensidad del aura de cada una.
        """
        orden = np.argsort(-self.pos[:, 2])
        centros = self.pos[orden] - (*self.centro, 0.0)
        ejes = np.stack([giro(self._ejes[i], self._fases[i] + config.CUENTA_GIRO_PROPIO * self._tiempo)
                         for i in orden]) * self.radio
        return self.centro, centros, ejes, self.radio, self.distancia, self.brillo[orden]
