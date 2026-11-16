"""Captura de cámara en un hilo aparte que conserva solo el último fotograma."""
import sys
import threading

import cv2

# En Windows, DirectShow entrega 1280x720 a 10-14 fps con esta clase de cámaras; Media Foundation da 30.
_BACKENDS = {"win32": cv2.CAP_MSMF, "darwin": cv2.CAP_AVFOUNDATION, "linux": cv2.CAP_V4L2}


class Camara:
    """Lee la cámara sin acumular retraso: quien consume siempre recibe el fotograma más reciente.

    La cámara no entrega a ritmo parejo (aquí se midieron intervalos de 12 a 66 ms y fotogramas
    repetidos), así que el consumidor no debe esperar a la cámara para dibujar.
    """

    def __init__(self, indice, ancho, alto, fps):
        self._cap = self._abrir(indice, ancho, alto, fps)
        ok, primero = self._cap.read()
        if not ok:
            self._cap.release()
            raise RuntimeError(
                f"La cámara {indice} abrió pero no entrega fotogramas. ¿La está usando otra aplicación?")

        # Lo que la cámara entrega de verdad, que puede no ser lo pedido.
        self.alto, self.ancho = primero.shape[:2]
        self.fps = self._cap.get(cv2.CAP_PROP_FPS)
        self.backend = self._cap.getBackendName()

        # Tres búferes fijos: uno recibe la captura, otro guarda el último fotograma completo y el
        # tercero es el que tiene el consumidor. Así no se reserva memoria en cada fotograma.
        self._bufs = [primero, primero.copy(), primero.copy()]
        self._ultimo, self._en_uso, self._escribe = 0, 0, 1
        self._n = 1
        self._candado = threading.Lock()
        self._activo = True
        self._hilo = threading.Thread(target=self._capturar, name="camara", daemon=True)
        self._hilo.start()

    @staticmethod
    def _abrir(indice, ancho, alto, fps):
        # Los parámetros van en la apertura: pedirlos después obliga a reconfigurar el dispositivo.
        params = [cv2.CAP_PROP_FRAME_WIDTH, ancho, cv2.CAP_PROP_FRAME_HEIGHT, alto, cv2.CAP_PROP_FPS, fps]
        cap = cv2.VideoCapture(indice, _BACKENDS.get(sys.platform, cv2.CAP_ANY), params)
        if not cap.isOpened():
            # Respaldo: backend automático y propiedades después de abrir.
            cap = cv2.VideoCapture(indice)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)
            cap.set(cv2.CAP_PROP_FPS, fps)
        if not cap.isOpened():
            raise RuntimeError(f"No se pudo abrir la cámara {indice}.")
        return cap

    def _capturar(self):
        fallos = 0
        while self._activo and fallos < 30:
            ok, fotograma = self._cap.read(self._bufs[self._escribe])
            if not ok:
                fallos += 1
                continue
            fallos = 0
            with self._candado:
                self._bufs[self._escribe] = fotograma
                self._ultimo = self._escribe
                self._escribe = 3 - self._ultimo - self._en_uso  # el búfer que no está ocupado
                self._n += 1

    def leer(self):
        """Devuelve (fotograma, número) con el más reciente, sin esperar.

        El número crece con cada fotograma nuevo, así que sirve para saber si cambió. El fotograma
        es válido hasta la siguiente llamada.
        """
        with self._candado:
            self._en_uso = self._ultimo
            return self._bufs[self._en_uso], self._n

    def cerrar(self):
        self._activo = False
        self._hilo.join(timeout=2.0)
        self._cap.release()
