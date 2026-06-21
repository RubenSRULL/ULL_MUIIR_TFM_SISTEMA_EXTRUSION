# ==========================
# ===== Importaciones ======
# ==========================
import time

# ===================================
# ===== Estados de la Extrusora =====
# ===================================
MACHINE_BOOT = 0
MACHINE_IDLE = 1
MACHINE_AUTO_INIT = 2
MACHINE_AUTO_PREHEAT = 3
MACHINE_AUTO_READY = 4
MACHINE_AUTO_EXTRUDING = 5
MACHINE_MANUAL_CONTROL = 6
MACHINE_STOPPING = 7
MACHINE_ALARM = 8

# =====================================
# ===== Estados de la Enrolladora =====
# =====================================
WINDER_OFF = 0
WINDER_IDLE = 1
WINDER_READY = 2
WINDER_RUNNING = 3
WINDER_STOPPING = 4
WINDER_ALARM = 5

# ==============================================
# ===== Diccionarios de Nombres de Estados =====
# ==============================================
NOMBRES_ESTADOS_STM32 = {
    MACHINE_BOOT: "BOOT",
    MACHINE_IDLE: "IDLE",
    MACHINE_AUTO_INIT: "AUTO_INIT",
    MACHINE_AUTO_PREHEAT: "AUTO_PREHEAT",
    MACHINE_AUTO_READY: "AUTO_READY",
    MACHINE_AUTO_EXTRUDING: "AUTO_EXTRUDING",
    MACHINE_MANUAL_CONTROL: "MANUAL_CONTROL",
    MACHINE_STOPPING: "STOPPING",
    MACHINE_ALARM: "ALARM",
}

NOMBRES_ESTADOS_WINDER = {
    WINDER_OFF: "OFF",
    WINDER_IDLE: "IDLE",
    WINDER_READY: "READY",
    WINDER_RUNNING: "RUNNING",
    WINDER_STOPPING: "STOPPING",
    WINDER_ALARM: "ALARM",
}

# ============================================
# ===== Estados de la Sub FSM Automática =====
# ============================================
AUTO_STATES = {
    MACHINE_AUTO_INIT,
    MACHINE_AUTO_PREHEAT,
    MACHINE_AUTO_READY,
    MACHINE_AUTO_EXTRUDING,
}

# =============================================
# ===== Estados de la Sub FSM Parada/Stop =====
# =============================================
STOPPABLE_STATES = {
    MACHINE_AUTO_PREHEAT,
    MACHINE_AUTO_READY,
    MACHINE_AUTO_EXTRUDING,
    MACHINE_MANUAL_CONTROL,
}

# ============================================
# ===== Fases de la FSM Automática (UI) =====
# ============================================
FASES_AUTOMATICAS = [
    {"titulo": "Configuración", "descripcion": "Configura material, diámetro objetivo y tiempo de proceso."},
    {"titulo": "Precalentamiento", "descripcion": "Envía SET_TEMP y PREHEAT; espera temperatura alcanzada."},
    {"titulo": "Listo", "descripcion": "La máquina está lista para comenzar la extrusión."},
    {"titulo": "Extrusión", "descripcion": "Proceso automático en marcha."},
    {"titulo": "Parada", "descripcion": "Detención ordenada y retorno a IDLE."},
]

# =========================================
# ===== Clase de Control de la Unidad =====
# =========================================
class ControlUC:
    def __init__(self, uart):
        """
        Descripción: Inicializa la clase ControlUC con una instancia de UART_COM. Configura la telemetría inicial y prepara la lista de respuestas pendientes.
        Parámetros:
            uart (UART_COM): Instancia de la clase UART_COM para la comunicación con la unidad de control.
        Retorna:
            None
        """
        self.uart = uart
        self.respuestas_pendientes = []
        self.telemetria = {
            "state": MACHINE_BOOT,
            "temp": 0.0,
            "target": 0.0,
            "heater": 0.0,
            "rpm_int": 0.0,
            "rpm_ext": 0.0,
            "diam": 0.0,
            "alarm": "0x00000000",
            "winder_state": WINDER_OFF,
            "winder_alarm": 0,
        }

    # -- Verifica si la comunicación con la unidad de control está disponible --
    def disponible(self):
        """
        Descripción: Verifica si la comunicación con la unidad de control está disponible. Esto se determina si la clase UART_COM está en modo simulado o si el puerto serial está abierto.
        Parámetros:
            None
        Retorna:
            bool: True si la comunicación está disponible, False en caso contrario.
        """
        return self.uart.modo_simulado or self.uart.serial_port is not None

    # -- Lee mensajes pendientes de la cola UART y los procesa --
    def leer_pendiente(self):
        """
        Descripción: Lee mensajes pendientes de la cola UART y los procesa. Si hay mensajes disponibles, se procesan hasta que no queden más. Esto permite actualizar la telemetría y manejar las respuestas de la unidad de control.
        Parámetros:
            None
        Retorna:
            None
        """
        while True:
            linea = self.uart.get_mensaje(timeout=0.001)
            if linea is None:
                break
            self.procesar_linea(linea)

    # -- Procesa una línea recibida desde la unidad de control --
    def procesar_linea(self, linea):
        """
        Descripción: Procesa una línea de texto recibida desde la unidad de control. Dependiendo del prefijo de la línea, se actualiza la telemetría, se agregan respuestas pendientes o se ignora la línea si no es relevante.
        Parámetros:
            linea (str): Línea de texto recibida desde la unidad de control.
        Retorna:
            None
        """
        if not linea:
            return

        linea = linea.strip()

        if linea.startswith("OK") or linea.startswith("ERR"):
            self.respuestas_pendientes.append(linea)
            return

        if linea.startswith("TEL:"):
            self._procesar_telemetria(linea[4:])
            return

        if linea.startswith("TEMP:"):
            try:
                self.telemetria["temp"] = float(linea.split(":", 1)[1].split()[0])
            except ValueError:
                pass

    # -- Procesa la telemetría recibida desde la unidad de control --
    def _procesar_telemetria(self, texto):
        """
        Descripción: Procesa la telemetría recibida desde la unidad de control. Extrae los valores de estado, temperatura, objetivo, calefactor, RPMs, diámetro y alarmas, y actualiza el diccionario de telemetría correspondiente.
        Parámetros:
            texto (str): Línea de telemetría recibida desde la unidad de control.
        Retorna:
            None
        """
        campos = {}

        for parte in texto.split(";"):
            if "=" in parte:
                clave, valor = parte.split("=", 1)
                campos[clave.strip()] = valor.strip()

        valores_float = {
            "TEMP": "temp",
            "TARGET": "target",
            "HEATER": "heater",
            "RPM_INT": "rpm_int",
            "RPM_EXT": "rpm_ext",
            "DIAM": "diam",
        }

        try:
            if "STATE" in campos:
                self.telemetria["state"] = int(campos["STATE"])

            if "WINDER_STATE" in campos:
                self.telemetria["winder_state"] = int(campos["WINDER_STATE"])

            if "WINDER_ALARM" in campos:
                self.telemetria["winder_alarm"] = int(campos["WINDER_ALARM"])

            for clave_uart, clave_local in valores_float.items():
                if clave_uart in campos:
                    self.telemetria[clave_local] = float(campos[clave_uart])

            if "ALARM" in campos:
                self.telemetria["alarm"] = campos["ALARM"]

        except ValueError:
            pass

    # -- Envía un mensaje a través del puerto UART --
    def enviar(self, comando, timeout=1.0):
        """
        Descripción: Envía un comando a la unidad de control a través del puerto UART y espera una respuesta. Si la comunicación no está disponible o si ocurre un error al enviar el mensaje, se devuelve False. Si se recibe una respuesta, se devuelve True junto con la respuesta.
        Parámetros:
            comando (str): Comando a enviar a la unidad de control.
            timeout (float): Tiempo máximo en segundos para esperar una respuesta.
        Retorna:
            tuple: (bool, str o None) - True si se recibió una respuesta, False si no se recibió respuesta o hubo un error. La segunda parte de la tupla es la respuesta
        """
        if not self.disponible():
            return False, None

        if not self.uart.enviar_mensaje(comando):
            return False, None

        respuesta = self.esperar_respuesta(timeout)
        return respuesta is not None and respuesta.startswith("OK"), respuesta

    # -- Envía un comando sin esperar respuesta --
    def enviar_sin_respuesta(self, comando):
        """
        Descripción: Envía un comando a la unidad de control a través del puerto UART sin esperar una respuesta. Esto es útil para comandos que no requieren confirmación inmediata.
        Parámetros:
            comando (str): Comando a enviar a la unidad de control.
        Retorna:
            bool: True si el comando se envió correctamente, False si hubo un error al enviar el comando o si la comunicación no está disponible.
        """
        if self.disponible():
            return self.uart.enviar_mensaje(comando)
        return False

    # -- Espera una respuesta de la unidad de control dentro de un tiempo límite --
    def esperar_respuesta(self, timeout=1.0):
        """
        Descripción: Espera una respuesta de la unidad de control dentro de un tiempo límite.
        Parámetros:
            timeout (float): Tiempo máximo en segundos para esperar una respuesta.
        Retorna:
            str o None: La respuesta recibida o None si no se recibió respuesta.
        """
        fin = time.time() + timeout

        while time.time() < fin:
            if self.respuestas_pendientes:
                return self.respuestas_pendientes.pop(0)

            linea = self.uart.get_mensaje(timeout=0.05)
            if linea is None:
                continue

            linea = linea.strip()

            if linea.startswith("OK") or linea.startswith("ERR"):
                return linea

            self.procesar_linea(linea)

        return None

    # -- Consulta el estado de la unidad de control y extrae el valor del estado --
    def consultar_estado(self, timeout=1.0):
        """
        Descripción: Consulta el estado de la unidad de control enviando el comando "STATE?" y espera una respuesta. Extrae el valor del estado de la respuesta recibida.
        Parámetros:
            timeout (float): Tiempo máximo en segundos para esperar una respuesta.
        Retorna:

        """
        ok, respuesta = self.enviar("STATE?", timeout=timeout)
        estado = extraer_estado_respuesta(respuesta)
        return ok and estado is not None, estado, respuesta


def extraer_estado_respuesta(respuesta):
    if not respuesta or "STATE=" not in respuesta:
        return None

    try:
        return int(respuesta.split("STATE=", 1)[1].split(";", 1)[0])
    except (ValueError, IndexError):
        return None


def extraer_estado_winder_respuesta(respuesta):
    if not respuesta or "WINDER_STATE=" not in respuesta:
        return None

    try:
        return int(respuesta.split("WINDER_STATE=", 1)[1].split(";", 1)[0])
    except (ValueError, IndexError):
        return None


def nombre_estado(estado):
    return NOMBRES_ESTADOS_STM32.get(estado, f"DESCONOCIDO({estado})")


def nombre_estado_winder(estado):
    return NOMBRES_ESTADOS_WINDER.get(estado, f"DESCONOCIDO({estado})")


def fase_desde_estado(estado, fase_actual=0):
    fase_actual = fase_actual or 0

    if estado == MACHINE_AUTO_INIT:
        return 0

    if estado == MACHINE_AUTO_PREHEAT:
        return max(fase_actual, 1)

    if estado == MACHINE_AUTO_READY:
        return max(fase_actual, 2)

    if estado == MACHINE_AUTO_EXTRUDING:
        return max(fase_actual, 3)

    if estado == MACHINE_STOPPING:
        return 4

    return fase_actual