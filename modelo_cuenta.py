"""Modelo 3D de una cuenta de Yunara, generado en código.

Como en las referencias: esfera de bronce pálido con 12 tachuelas de acero que sobresalen, cada una
con un collar de bronce y una línea grabada alrededor, y medialunas oscuras que se curvan junto a la
mitad de las tachuelas. Se construye sobre una esfera geodésica fina y el relieve es desplazamiento
real de los vértices, así la luz lo marca.
"""
import math

import numpy as np

import config


def _normalizar(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _icosaedro():
    t = (1 + math.sqrt(5)) / 2
    v = np.array([(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
                  (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)], np.float64)
    f = np.array([(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4),
                  (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8),
                  (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)], np.int64)
    return _normalizar(v), f


def _icosfera(niveles):
    """Esfera geodésica: cada nivel parte cada triángulo en cuatro."""
    v, f = _icosaedro()
    for _ in range(niveles):
        a, b, c = f[:, 0], f[:, 1], f[:, 2]
        aristas = np.sort(np.stack((np.stack((a, b), 1), np.stack((b, c), 1), np.stack((c, a), 1)), 1)
                          .reshape(-1, 2), axis=1)
        unicas, inversa = np.unique(aristas, axis=0, return_inverse=True)
        medios = _normalizar(v[unicas[:, 0]] + v[unicas[:, 1]])
        ab, bc, ca = (len(v) + inversa.reshape(-1, 3)).T
        v = np.vstack((v, medios))
        f = np.concatenate((np.stack((a, ab, ca), 1), np.stack((b, bc, ab), 1),
                            np.stack((c, ca, bc), 1), np.stack((ab, bc, ca), 1)))
    return v, f


def _bulto(x, centro, medio_ancho):
    """Perfil suave de 1 en el centro a 0 a medio_ancho de distancia."""
    return np.clip(1 - ((x - centro) / medio_ancho) ** 2, 0, 1)


def _marco(centros):
    """Dos tangentes por centro, para medir ángulos alrededor de cada tachuela."""
    referencia = np.where(np.abs(centros[:, 1:2]) < 0.9, (0.0, 1.0, 0.0), (1.0, 0.0, 0.0))
    t1 = _normalizar(np.cross(centros, referencia))
    return t1, np.cross(centros, t1)


def _una_por_par(centros):
    """Índices de una tachuela de cada par de opuestas (el icosaedro las trae de a pares)."""
    elegidas = []
    for i, c in enumerate(centros):
        if all(c @ centros[j] > -0.99 for j in elegidas):
            elegidas.append(i)
    return elegidas


def _relieve(n):
    """Desplazamiento radial y material (oscuro, tachuela) de cada dirección unitaria n."""
    centros, _ = _icosaedro()  # 12 tachuelas repartidas por igual
    cosenos = n @ centros.T
    theta = np.arccos(np.clip(cosenos.max(axis=1), -1, 1))  # distancia a la tachuela más cercana

    radio, linea, collar_ancho = config.TACHUELA_RADIO, config.LINEA_ANCHO, config.COLLAR_ANCHO
    domo = np.where(theta < radio, np.sqrt(np.clip(1 - (theta / radio) ** 2, 0, 1)), 0.0)
    collar = _bulto(theta, radio + collar_ancho, collar_ancho)
    borde_collar = radio + 2 * collar_ancho
    grabado = _bulto(theta, borde_collar + 2 * linea, linea)

    # Medialunas: bandas que se curvan alrededor de una tachuela, gruesas en el medio y finas en las
    # puntas. Una por cada par de tachuelas opuestas, así se ven dos o tres por lado como en las
    # referencias. Cada una se mide desde su propia tachuela para que no quede cortada donde empieza
    # la zona de otra.
    medialuna = np.zeros(len(n))
    t1, t2 = _marco(centros)
    fases = np.random.default_rng(7).uniform(0, 2 * math.pi, len(centros))
    for k in _una_por_par(centros):
        theta_k = np.arccos(np.clip(cosenos[:, k], -1, 1))
        phi = (np.arctan2(n @ t2[k], n @ t1[k]) + fases[k]) % (2 * math.pi)
        vuelta = phi / (2 * math.pi)
        recorrido = vuelta / config.MEDIALUNA_LARGO
        grosor = config.MEDIALUNA_ANCHO * np.sin(math.pi * np.clip(recorrido, 0, 1)) ** 0.7
        curva = borde_collar + config.MEDIALUNA_SEPARACION + config.MEDIALUNA_APERTURA * vuelta
        banda = np.clip((grosor - np.abs(theta_k - curva)) / (0.4 * linea), 0, 1) * (recorrido < 1)
        medialuna = np.maximum(medialuna, banda)
    medialuna *= np.clip((theta - borde_collar - 2 * linea) / (2 * linea), 0, 1)  # no pisa tachuelas

    oscuro = np.maximum(medialuna, 0.6 * grabado)
    altura = (config.TACHUELA_ALTURA * domo + config.COLLAR_ALTURA * collar
              - config.LINEA_PROFUNDIDAD * grabado - config.MEDIALUNA_PROFUNDIDAD * medialuna)
    tachuela = np.clip((radio - theta) / (0.2 * radio), 0, 1)
    return altura, oscuro, tachuela


def construir():
    """Malla de la cuenta con radio base 1.

    Devuelve (vertices, indices): vertices es (n, 8) en float32 con posición, normal y material
    (oscuro, tachuela), e indices es (m, 3) en uint32.
    """
    n, caras = _icosfera(config.CUENTA_SUBDIVISIONES)
    altura, oscuro, tachuela = _relieve(n)
    posiciones = n * (1 + altura)[:, None]

    # Normales del relieve: suma de las normales de las caras que tocan cada vértice, pesadas por área.
    a, b, c = (posiciones[caras[:, k]] for k in range(3))
    normales_cara = np.cross(b - a, c - a)
    normales = np.zeros_like(posiciones)
    for k in range(3):
        np.add.at(normales, caras[:, k], normales_cara)
    if (normales * posiciones).sum() < 0:  # que apunten hacia fuera, sea cual sea el orden de las caras
        normales = -normales
    normales = _normalizar(normales)

    vertices = np.hstack((posiciones, normales, oscuro[:, None], tachuela[:, None])).astype(np.float32)
    return vertices, caras.astype(np.uint32)
