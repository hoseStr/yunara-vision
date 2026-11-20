"""Cuentas en 3D con la GPU (moderngl), en un búfer fuera de pantalla que luego se mezcla con la cámara.

La GPU dibuja las 6 cuentas como mallas iluminadas, con su aura y tapadas por la silueta donde pasan
detrás del cuello. Solo se lee de vuelta el rectángulo que ocupan, ya premultiplicado por su opacidad,
y `Render.capa` lo mezcla sobre el lienzo en la CPU.

La lectura no espera a la GPU: cada dibujo deja su resultado copiándose a un búfer intermedio y
recoge el del dibujo anterior, que ya está listo. Esperar costaba entre 2 y 6 ms por dibujo dentro del
bucle (la GPU se enfría entre dibujos); a cambio, las cuentas van un dibujo atrasadas (22 ms).
"""
import moderngl
import numpy as np

import config
import modelo_cuenta

# Coordenadas: píxeles respecto al cuello, x a la derecha, y hacia abajo, z hacia el fondo. La
# perspectiva converge en el cuello, igual que en `Cuentas.proyectar`. La fila 0 del búfer es la de
# arriba de la imagen, así se lee sin voltear.
_PROYECCION = """
uniform vec2 u_cuello;
uniform vec2 u_tam;
uniform float u_distancia;

vec4 proyectar(vec3 p) {
    float w = (u_distancia + p.z) / u_distancia;
    vec2 s = u_cuello * w + p.xy;  // (cuello + p.xy / w) * w: lineal en p, interpola bien
    return vec4(s / u_tam * 2.0 - w, p.z / (2.0 * u_distancia), w);
}
"""

_OCLUSION = """
uniform sampler2D u_mascara;
uniform bool u_oclusion;
uniform float u_opacidad;

// Opacidad de un punto a profundidad z: la silueta lo tapa cuanto más detrás del cuello está.
float visible(float z, float transicion) {
    float v = u_opacidad;
    if (u_oclusion) {
        float m = texture(u_mascara, gl_FragCoord.xy / u_tam).r;
        v *= 1.0 - clamp(z / transicion, 0.0, 1.0) * m;
    }
    return v;
}
"""

_CUENTA_VERTICES = "#version 330\n" + _PROYECCION + """
in vec3 en_pos;
in vec3 en_normal;
in vec2 en_material;
in vec3 i_centro;
in vec3 i_x;
in vec3 i_y;
in vec3 i_z;
out vec3 v_pos;
out vec3 v_normal;
out vec2 v_material;

void main() {
    mat3 m = mat3(i_x, i_y, i_z);  // giro propio por el radio en píxeles
    v_pos = i_centro + m * en_pos;
    v_normal = m * en_normal;  // escala uniforme: basta normalizar después
    v_material = en_material;
    gl_Position = proyectar(v_pos);
}
"""

_CUENTA_FRAGMENTOS = "#version 330\n" + _PROYECCION + _OCLUSION + """
in vec3 v_pos;
in vec3 v_normal;
in vec2 v_material;
out vec4 f_color;

uniform float u_radio;
uniform vec3 u_bronce;
uniform vec3 u_tachuela;
uniform vec3 u_oscuro;
uniform vec3 u_luz_dir;
uniform vec3 u_luz_color;
uniform vec3 u_relleno_dir;
uniform vec3 u_relleno_color;
uniform vec3 u_cielo;
uniform vec3 u_suelo;
uniform vec3 u_violeta;
uniform float u_borde;

void main() {
    vec3 n = normalize(v_normal);
    vec3 v = normalize(vec3(0.0, 0.0, -u_distancia) - v_pos);  // hacia la cámara
    float oscuro = v_material.x;
    float tachuela = v_material.y;

    // Metal: el color sale casi todo del reflejo. El acero de las tachuelas está pulido. Las
    // medialunas son como pintura oscura: más luz difusa y un brillo apagado.
    vec3 base = mix(mix(u_bronce, u_tachuela, tachuela), u_oscuro, oscuro);
    float pulido = mix(mix(0.55, 0.9, tachuela), 0.35, oscuro);
    float exponente = mix(6.0, 90.0, pulido);
    float ndv = max(dot(n, v), 0.0);
    vec3 fresnel = base + (1.0 - base) * pow(1.0 - ndv, 5.0) * pulido;

    vec3 color = vec3(0.0);
    vec3 luces[2] = vec3[](normalize(u_luz_dir), normalize(u_relleno_dir));
    vec3 colores[2] = vec3[](u_luz_color, u_relleno_color);
    for (int k = 0; k < 2; k++) {
        vec3 l = luces[k];
        float ndl = max(dot(n, l), 0.0);
        float ndh = max(dot(n, normalize(l + v)), 0.0);
        float especular = pow(ndh, exponente) * (exponente + 8.0) / 25.0;
        color += colores[k] * ndl * (base * mix(0.25, 0.9, oscuro) + fresnel * especular);
    }
    // Reflejo de un entorno simple: claro arriba, oscuro abajo (y crece hacia abajo).
    vec3 r = reflect(-v, n);
    color += mix(u_suelo, u_cielo, clamp(0.5 - 0.5 * r.y, 0.0, 1.0)) * fresnel * (0.35 + 0.65 * pulido);
    color *= 1.0 - 0.25 * oscuro;
    color += u_violeta * u_borde * pow(1.0 - ndv, 3.0);  // reflejo del aura en el contorno

    color = pow(color, vec3(1.0 / 2.2));
    float a = visible(v_pos.z, u_radio);
    f_color = vec4(color.bgr * a, a);  // la CPU trabaja en BGR
}
"""

_AURA_VERTICES = "#version 330\n" + _PROYECCION + """
in vec2 en_esquina;
in vec3 i_centro;
in float i_radio;
out vec2 v_esquina;
out float v_z;
uniform float u_alcance;

void main() {
    // Cuadrado de frente a la cámara, un poco detrás del centro para que la propia cuenta lo tape.
    vec3 c = i_centro + vec3(0.0, 0.0, 0.5 * i_radio);
    vec4 centro = proyectar(c);
    float w = centro.w;
    v_esquina = en_esquina * u_alcance;
    v_z = i_centro.z;
    vec2 s = (u_cuello + c.xy / w + v_esquina * i_radio / w);
    gl_Position = vec4(s / u_tam * 2.0 - 1.0, centro.z / w, 1.0);
}
"""

_AURA_FRAGMENTOS = "#version 330\n" + _PROYECCION + _OCLUSION + """
in vec2 v_esquina;
in float v_z;
out vec4 f_color;
uniform vec3 u_violeta;
uniform float u_intensidad;
uniform float u_ancho;
uniform float u_radio;

void main() {
    float fuera = max(length(v_esquina) - 1.0, 0.0) / u_ancho;
    vec3 aura = u_violeta * u_intensidad * exp(-fuera * fuera);
    f_color = vec4(aura.bgr * visible(v_z, u_radio), 0.0);  // alfa 0: se suma sin tapar
}
"""


def _lineal(hexadecimal):
    h = hexadecimal.lstrip("#")
    return tuple((int(h[k:k + 2], 16) / 255) ** 2.2 for k in (0, 2, 4))


def _hacia_fondo(direccion):
    """Las direcciones de config llevan z hacia la cámara; aquí z va hacia el fondo."""
    x, y, z = direccion
    return x, y, -z


def _srgb(hexadecimal):
    h = hexadecimal.lstrip("#")
    return tuple(int(h[k:k + 2], 16) / 255 for k in (0, 2, 4))


class RenderGPU:
    """Dibuja las cuentas en la GPU y devuelve el rectángulo que ocupan, listo para mezclar."""

    def __init__(self, ancho, alto):
        self.ancho, self.alto = ancho, alto
        self.ctx = moderngl.create_standalone_context()
        self.descripcion = self.ctx.info["GL_RENDERER"]

        vertices, indices = modelo_cuenta.construir()
        self._cuenta = self.ctx.program(vertex_shader=_CUENTA_VERTICES, fragment_shader=_CUENTA_FRAGMENTOS)
        self._aura = self.ctx.program(vertex_shader=_AURA_VERTICES, fragment_shader=_AURA_FRAGMENTOS)
        self._instancias = self.ctx.buffer(reserve=config.CUENTAS_N * 13 * 4, dynamic=True)
        self._vao_cuenta = self.ctx.vertex_array(
            self._cuenta,
            [(self.ctx.buffer(vertices.tobytes()), "3f 3f 2f", "en_pos", "en_normal", "en_material"),
             (self._instancias, "3f 3f 3f 3f 4x/i", "i_centro", "i_x", "i_y", "i_z")],
            index_buffer=self.ctx.buffer(indices.tobytes()), index_element_size=4)
        esquinas = np.array([(-1, -1), (1, -1), (-1, 1), (1, 1)], np.float32)
        self._vao_aura = self.ctx.vertex_array(
            self._aura,
            [(self.ctx.buffer(esquinas.tobytes()), "2f", "en_esquina"),
             (self._instancias, "3f 36x f/i", "i_centro", "i_radio")])

        # Búfer con 4 muestras por píxel para bordes suaves, y otro sin muestras para leerlo.
        tam = (ancho, alto)
        muestras = min(config.GPU_MUESTRAS, self.ctx.max_samples)
        self._fbo_muestras = self.ctx.framebuffer(
            color_attachments=[self.ctx.renderbuffer(tam, 4, samples=muestras)],
            depth_attachment=self.ctx.depth_renderbuffer(tam, samples=muestras))
        self._fbo = self.ctx.framebuffer(color_attachments=[self.ctx.renderbuffer(tam, 4)])
        # Dos búferes de lectura que se turnan, cada uno con el rectángulo que tiene pedido.
        self._lecturas = [self.ctx.buffer(reserve=ancho * alto * 4) for _ in range(2)]
        self._pedidos = [None, None]
        self._turno = 0

        self._mascara = None  # textura de la silueta, al tamaño de detección
        self._mascara_subida = None  # arreglo que tiene la textura, para no subirlo dos veces

        u = {
            "u_tam": tam,
            "u_bronce": _lineal(config.CUENTA_COLOR), "u_tachuela": _lineal(config.TACHUELA_COLOR),
            "u_oscuro": _lineal(config.OSCURO_COLOR),
            "u_luz_dir": _hacia_fondo(config.LUZ_DIRECCION), "u_luz_color": _lineal(config.LUZ_COLOR),
            "u_relleno_dir": _hacia_fondo(config.RELLENO_DIRECCION),
            "u_relleno_color": _lineal(config.RELLENO_COLOR),
            "u_cielo": _lineal(config.ENTORNO_CIELO), "u_suelo": _lineal(config.ENTORNO_SUELO),
            "u_borde": config.AURA_BORDE,
        }
        for nombre, valor in u.items():
            if nombre in self._cuenta:
                self._cuenta[nombre].value = valor
        self._cuenta["u_violeta"].value = _lineal(config.AURA_COLOR)
        for nombre, valor in {"u_tam": tam, "u_violeta": _srgb(config.AURA_COLOR),
                              "u_intensidad": config.AURA_INTENSIDAD, "u_ancho": config.AURA_ANCHO,
                              "u_alcance": 1 + config.AURA_ALCANCE}.items():
            self._aura[nombre].value = valor
        for programa in (self._cuenta, self._aura):
            programa["u_mascara"].value = 0

    def _subir_mascara(self, mascara):
        if mascara is self._mascara_subida:
            return
        alto, ancho = mascara.shape
        if self._mascara is None or self._mascara.size != (ancho, alto):
            self._mascara = self.ctx.texture((ancho, alto), 1, dtype="f1", alignment=1)
            self._mascara.repeat_x = self._mascara.repeat_y = False
        self._mascara.write(np.ascontiguousarray(mascara))
        self._mascara_subida = mascara

    def dibujar(self, escena, mascara, opacidad):
        """Dibuja las cuentas y devuelve el dibujo anterior como (x0, y0, bgra), o None.

        `escena` viene de `Cuentas.escena`. `bgra` es (alto, ancho, 4) en uint8, con los canales en
        orden BGR más la opacidad, y el color ya multiplicado por ella.
        """
        cuello, centros, ejes, radio, distancia = escena
        if opacidad <= 0 or not len(centros):
            self._pedidos = [None, None]  # al volver no se muestra un dibujo viejo
            return None

        # Rectángulo que cubren las cuentas con su aura, en píxeles de pantalla.
        w = (distancia + centros[:, 2]) / distancia
        pantalla = cuello + centros[:, :2] / w[:, None]
        alcance = radio * (1 + config.AURA_ALCANCE + config.TACHUELA_ALTURA) / w[:, None] + 2
        x0, y0 = np.floor((pantalla - alcance).min(axis=0)).astype(int)
        x1, y1 = np.ceil((pantalla + alcance).max(axis=0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, self.ancho), min(y1, self.alto)
        if x1 <= x0 or y1 <= y0:
            self._pedidos = [None, None]
            return None

        datos = np.zeros((len(centros), 13), np.float32)
        datos[:, 0:3] = centros
        datos[:, 3:12] = ejes.transpose(0, 2, 1).reshape(-1, 9)  # columnas de cada matriz
        datos[:, 12] = radio
        self._instancias.write(datos.tobytes())

        oclusion = mascara is not None
        if oclusion:
            self._subir_mascara(mascara)
            self._mascara.use(0)
        for programa in (self._cuenta, self._aura):
            programa["u_cuello"].value = tuple(cuello)
            programa["u_distancia"].value = distancia
            programa["u_oclusion"].value = oclusion
            programa["u_opacidad"].value = opacidad
            programa["u_radio"].value = radio

        self._fbo_muestras.use()
        self._fbo_muestras.clear(0.0, 0.0, 0.0, 0.0, depth=1.0)
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.BLEND)
        self.ctx.blend_func = moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA  # color premultiplicado
        # Las instancias van de la más lejana a la más cercana, para que las transparencias se mezclen bien.
        self._vao_cuenta.render(moderngl.TRIANGLES, instances=len(centros))
        self.ctx.depth_mask = False  # el aura no tapa nada, solo se suma
        self._vao_aura.render(moderngl.TRIANGLE_STRIP, instances=len(centros))
        self.ctx.depth_mask = True
        self.ctx.copy_framebuffer(self._fbo, self._fbo_muestras)

        # Pide la copia de este dibujo sin esperarla y recoge la del anterior.
        rect = (x0, y0, x1 - x0, y1 - y0)
        self._fbo.read_into(self._lecturas[self._turno], viewport=rect, components=4, alignment=1)
        self._pedidos[self._turno] = rect
        self._turno ^= 1
        anterior = self._pedidos[self._turno]
        if anterior is None:
            return None
        x0, y0, ancho, alto = anterior
        datos = self._lecturas[self._turno].read(size=ancho * alto * 4)
        return x0, y0, np.frombuffer(datos, np.uint8).reshape(alto, ancho, 4)

    def cerrar(self):
        self.ctx.release()

