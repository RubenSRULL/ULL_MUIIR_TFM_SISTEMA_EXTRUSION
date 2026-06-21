# ==========================
# ===== Importaciones ======
# ==========================
import os
import time
import threading
from queue import Queue, Empty
import serial


# ==========================
# ===== Clase UART_COM =====
# ==========================
class UART_COM:
    def __init__(self, port="/dev/ttyUSB0", baudrate=115200, modo_simulado=False):
        """
        Descripción: Clase para manejar la comunicación UART con un dispositivo externo. Permite enviar y recibir mensajes a través de un puerto serie, y también puede operar en modo simulado para pruebas sin hardware.
        Parámetros:
            port (str): Nombre del puerto serie (por defecto "/dev/ttyUSB0").
            baudrate (int): Velocidad de transmisión en baudios (por defecto 115200).
            modo_simulado (bool): Si es True, la clase operará en modo simulado, generando respuestas ficticias en lugar de comunicarse con un dispositivo real.
        Retorna:
            None
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_port = None
        self.modo_simulado = modo_simulado
        self.queue = Queue()
        self._running = False
        self._thread = None

        self._estado_simulado = 1

        if self.modo_simulado:
            print("UART en modo SIMULADO")
            return

        if serial is None:
            print("pyserial no disponible. UART en modo SIMULADO")
            self.modo_simulado = True
            return

        if not os.path.exists(port):
            print(f"Puerto UART {port} no encontrado. UART en modo SIMULADO")
            self.modo_simulado = True
            return

        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
            )
            print(f"UART inicializado en {port} a {baudrate} baudios")
        except Exception as e:
            print(f"Error al inicializar UART: {e}. UART en modo SIMULADO")
            self.modo_simulado = True

    # -- Inicia el hilo de recepción de mensajes UART --
    def iniciar_recepcion(self):
        """
        Descripción: Inicia un hilo en segundo plano que se encarga de recibir mensajes desde el puerto UART. Los mensajes recibidos se almacenan en una cola para su posterior procesamiento.
        Parámetros:
            None
        Retorna:
            None
        """
        if self._running:
            return

        if self.serial_port is None and not self.modo_simulado:
            print("No se puede iniciar recepción: UART no disponible")
            return

        self._running = True
        self._thread = threading.Thread(target=self._recepcion_loop, daemon=True)
        self._thread.start()

    # -- Bucle de recepción de mensajes UART --
    def _recepcion_loop(self):
        """
        Descripción: Bucle que se ejecuta en un hilo separado para recibir mensajes desde el puerto UART. Lee líneas de texto desde el puerto serie, las decodifica y las coloca en una cola para su procesamiento. Si la clase está en modo simulado, simplemente espera sin hacer nada.
        Parámetros:
            None
        Retorna:
            None
        """
        while self._running:
            if self.modo_simulado or self.serial_port is None:
                time.sleep(0.1)
                continue

            try:
                linea = self.serial_port.readline()
                if linea:
                    texto = linea.decode("utf-8", errors="ignore").strip()
                    if texto:
                        self.queue.put(texto)
            except Exception as e:
                print(f"Error recibiendo UART: {e}")
                time.sleep(0.1)

    # -- Obtiene un mensaje de la cola de recepción --
    def get_mensaje(self, timeout=1.0):
        """
        Descripción: Intenta obtener un mensaje de la cola de recepción de mensajes UART. Si no hay mensajes disponibles dentro del tiempo de espera especificado, devuelve None.
        Parámetros:
            timeout (float): Tiempo máximo en segundos para esperar un mensaje antes de devolver None (por defecto 1.0).
        Retorna:
            str o None: El mensaje recibido como cadena de texto, o None si no se recibió ningún mensaje dentro del tiempo de espera.
        """
        try:
            return self.queue.get(timeout=timeout)
        except Empty:
            return None

    # -- Envía un mensaje a través del puerto UART --
    def enviar_mensaje(self, data_str):
        """
        Descripción: Envía un mensaje de texto a través del puerto UART. Si la clase está en modo simulado, imprime el mensaje en la consola y genera una respuesta simulada. Si ocurre un error al enviar el mensaje, se captura la excepción y se devuelve False.
        Parámetros:
            data_str (str): El mensaje de texto a enviar. Se agregará un salto de línea al final si no está presente.
        Retorna:
            bool: True si el mensaje se envió correctamente (o se simuló), False si hubo un error al enviar el mensaje.
        """
        if self.modo_simulado:
            print(f"[UART SIM] TX: {data_str}")
            self._simular_respuesta(data_str.strip())
            return True

        if self.serial_port is None:
            print("Error: UART no disponible")
            return False

        try:
            if not data_str.endswith("\n"):
                data_str += "\n"
            self.serial_port.write(data_str.encode("utf-8"))
            self.serial_port.flush()
            return True
        except Exception as e:
            print(f"Error enviando UART: {e}")
            return False

    # -- Simula una respuesta para pruebas sin hardware --
    def _simular_respuesta(self, comando):
        """
        Descripción: Genera respuestas simuladas para ciertos comandos cuando la clase está en modo simulado. Esto permite probar la lógica de la aplicación sin necesidad de un dispositivo UART real.
        Parámetros:
            comando (str): El comando recibido que se desea simular.
        Retorna:
            None
        """
        if comando == "STATE?":
            self.queue.put(f"OK:STATE={self._estado_simulado};ALARM=0x00000000")
            return

        cambios = {
            "AUTO": 2,
            "RESET_AUTO": 1,
            "MANUAL": 6,
            "PREHEAT": 3,
            "START": 5,
            "STOP": 1,
            "HEATER_OFF": 6,
            "STOP_INT": 6,
            "STOP_EXT": 6,
        }

        if comando in cambios:
            self._estado_simulado = cambios[comando]

        if comando.startswith("SET_TEMP:") or comando.startswith("SET_INT_RPM:") or comando.startswith("SET_EXT_RPM:"):
            self.queue.put("OK")
        elif comando.startswith("DIAM:"):
            pass
        else:
            self.queue.put("OK")

    # -- Detiene el hilo de recepción de mensajes UART --
    def detener_recepcion(self):
        """
        Descripción: Detiene el hilo de recepción de mensajes UART y espera a que termine. Si el hilo no está en ejecución, no hace nada.
        Parámetros:
            None
        Retorna:
            None
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    # -- Cierra el puerto UART y detiene la recepción --
    def cerrar(self):
        """
        Descripción: Cierra el puerto UART y detiene la recepción de mensajes. Si el puerto UART está abierto, se cierra y se libera. También detiene el hilo de recepción si está en ejecución.
        Parámetros:
            None
        Retorna:
            None
        """
        self.detener_recepcion()
        if self.serial_port is not None:
            self.serial_port.close()
            self.serial_port = None