# Autor: Rubén Sahuquillo Redondo

# Descripción:
# - Este módulo implementa la clase CAN_COM para manejar la comunicación CAN en un entorno de impresión 3D.
#   Permite enviar y recibir mensajes CAN, y puede operar en modo simulado si la interfaz CAN no está disponible.

# Flujo del programa:
# 1. Se inicializa la clase CAN_COM, intentando conectar a la interfaz CAN especificada. Si no se encuentra,
#   puede entrar en modo simulado.
# 2. La clase tiene un método para iniciar la recepción de mensajes CAN en un hilo separado, y otro para detenerla.
# 3. Los mensajes recibidos se almacenan en una cola, y se pueden obtener mediante el método get_mensaje.
# 4. Para enviar mensajes, se utiliza el método enviar_mensaje, que acepta un ID de arbitraje y una cadena de datos.
#   Si está en modo simulado, simplemente imprime el mensaje en la consola.
# 5. La clase maneja errores de conexión y envío, y proporciona información sobre el estado de la comunicación CAN.


#------------------#
#---- Módulos -----#
#------------------#
import can
from queue import Queue, Empty
import threading
import time
import subprocess


# ---------------------- #
#---- Clase CAN_COM ---- #
# ---------------------- #
class CAN_COM:
    def __init__(self, channel='can0', interface='socketcan', modo_simulado=True):
        """
        Descripción:
            Inicializa la comunicación CAN. Si la interfaz no está disponible, puede entrar en modo simulado.
        Parámetros:
            channel (str): Nombre de la interfaz CAN (por defecto 'can0').
            interface (str): Tipo de interfaz CAN (por defecto 'socketcan').
            modo_simulado (bool): Si True, activa el modo simulado si la interfaz no está disponible (por defecto True).
        Retorno:
            None
        """
        # Inicialización de variables
        self.channel = channel
        self.interface = interface
        self.bus = None
        self._running = False
        self.queue = Queue()
        self._thread = None
        self.modo_simulado = False

        # Si modo_simulado es True, no intentamos conectar a la interfaz CAN y activamos el modo simulado directamente.
        if modo_simulado:
            print(f"Modo simulado activado. No se intentará conectar a {channel}.")
            self.modo_simulado = True
            return
        # Si modo_simulado es False, intentamos conectar a la interfaz CAN. Si no se encuentra, activamos el modo simulado.
        else:
            if self._existe_interfaz_can(channel):
                print(f"Interfaz {channel} encontrada. Intentando activar CAN...")
                self.__activate_can(channel, bitrate=500000)

                try:
                    self.bus = can.interface.Bus(channel=channel, interface=interface)
                    print(f"CAN inicializado correctamente en {channel}")

                except Exception as e:
                    print(f"Error al inicializar CAN: {e}")
                    self.modo_simulado = True
                    print(f"CAN en modo SIMULADO.")
                    return

            else:
                print(f"Interfaz {channel} no encontrada. CAN desactivado.")
                self.modo_simulado = True
                print(f"CAN en modo SIMULADO.")
                return

            return


    # Método para activar la interfaz CAN
    def __activate_can(self, channel, bitrate=500000):
        """
        Descripción:
            Activa la interfaz CAN utilizando comandos del sistema. Primero baja la interfaz, luego la sube con el tipo CAN
            y la velocidad especificada.
        Parámetros:
            channel (str): Nombre de la interfaz CAN a activar.
            bitrate (int): Velocidad de transmisión en bits por segundo (por defecto 500000).
        Retorno:
            subprocess.CompletedProcess: El resultado de la ejecución del comando para activar la interfaz CAN.
        """
        resultado = subprocess.run(["sudo", "ip", "link", "set", channel, "down"])
        
        if resultado.returncode == 0:
            resultado = subprocess.run(["sudo", "ip", "link", "set", channel, "up", "type", "can", "bitrate", str(bitrate)])
        
        return resultado     


    # Método privado para verificar si la interfaz CAN existe
    def _existe_interfaz_can(self, channel):
        """
        Descripción:
            Verifica si la interfaz CAN especificada existe en el sistema.
        Parámetros:
            channel (str): Nombre de la interfaz CAN a verificar.
        Retorno:
            bool: True si la interfaz existe, False en caso contrario.
        """
        # Utiliza el comando 'ip link show' para verificar la existencia de la interfaz CAN.
        resultado = subprocess.run(["ip", "link", "show", channel],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        # Si el comando se ejecuta correctamente (returncode 0), la interfaz existe. Si no, no existe.
        return resultado.returncode == 0


    # Método para recibir mensajes CAN en un hilo separado
    def recepcion_mensajes(self):
        """
        Descripción:
            Método que se ejecuta en un hilo separado para recibir mensajes CAN de forma continua.
        Parámetros:
            None
        Retorno:
            None
        """
        # El hilo se ejecuta mientras self._running sea True
        while self._running:
            # Si modo simulado está activado, no intentamos recibir mensajes CAN reales
            if self.modo_simulado:
                time.sleep(0.1)
                continue

            # Si la interfaz CAN no está disponible, saltar iteración
            if self.bus is None:
                time.sleep(0.1)
                continue

            # Intenta recibir un mensaje CAN con un timeout de 1 segundo
            try:
                msg = self.bus.recv(timeout=1)
                # Si se recibe un mensaje, decodificar los datos y almacenarlos en la cola junto con el ID de arbitraje
                if msg:
                    texto = msg.data.decode('utf-8', errors='ignore')
                    self.queue.put((msg.arbitration_id, texto))

            except Exception as e:
                print(f"Error recibiendo mensaje CAN: {e}")


    # Método para obtener mensajes recibidos
    def get_mensaje(self, timeout=1):
        """
        Descripción:
            Obtiene un mensaje recibido de la cola de mensajes.
        Parámetros:
            timeout (float): Tiempo máximo de espera para obtener un mensaje.
        Retorno:
            tuple: Una tupla con el ID de arbitraje y el texto del mensaje, o None si no hay mensajes disponibles.
        """
        # Intentar obtener un mensaje de la cola con el timeout especificado. Si no hay mensajes, devuelve None.
        try:
            return self.queue.get(timeout=timeout)
        except Empty:
            return None


    # Método para enviar mensajes CAN
    def enviar_mensaje(self, arbitration_id, data_str):
        """
        Descripción:
            Envía un mensaje por la red CAN.
        Parámetros:
            arbitration_id (int): ID de arbitraje del mensaje.
            data_str (str): Datos del mensaje como cadena de texto.
        Retorno:
            bool: True si el mensaje se envió correctamente, False en caso contrario.
        """
        # Si modo simulado está activado, simplemente imprime el mensaje en la consola y lo agrega a la cola como si se hubiera enviado correctamente.
        if self.modo_simulado:
            print(f"[CAN SIMULADO] ID: {hex(arbitration_id)} DATA: {data_str}")
            self.queue.put((arbitration_id, "OK"))
            return True

        # Si la interfaz CAN no está disponible, no se puede enviar el mensaje. Imprime un error y devuelve False.
        if self.bus is None:
            print("Error: CAN no disponible")
            return False

        # Intenta enviar el mensaje CAN
        try:
            # Codifica la cadena de datos a bytes, asegurándose de que no exceda los 8 bytes permitidos por el estándar CAN.
            data_bytes = data_str.encode('utf-8')[:8]
            # Crea un mensaje CAN con el ID de arbitraje, los datos codificados
            msg = can.Message(arbitration_id=arbitration_id, data=data_bytes, is_extended_id=False)
            # Envía el mensaje por la interfaz CAN
            self.bus.send(msg)
            return True

        except Exception as e:
            print(f"Error enviando mensaje CAN: {e}")
            return False


    # Métodos para iniciar y detener la recepción de mensajes
    def iniciar_recepcion(self):
        """
        Descripción:
            Inicia la recepción de mensajes CAN en un hilo separado. Si ya está en ejecución, no hace nada.
        Parámetros:
            None
        Retorno:
            None
        """
        # Si ya se está ejecutando la recepción, no hacer nada
        if self._running:
            return

        # Si la interfaz CAN no está disponible y no estamos en modo simulado, no se puede iniciar la recepción. Imprime un error y devuelve.
        if self.bus is None and not self.modo_simulado:
            print("No se puede iniciar recepción: CAN no disponible")
            return

        # Inicia el hilo de recepción de mensajes CAN
        self._running = True
        self._thread = threading.Thread(target=self.recepcion_mensajes,daemon=True)
        self._thread.start()


    # Método para detener la recepción de mensajes
    def detener_recepcion(self):
        """
        Descripción:
            Detiene la recepción de mensajes CAN y espera a que el hilo termine.
        Parámetros:
            None
        Retorno:
            None
        """
        # Detiene el hilo de recepción de mensajes CAN estableciendo self._running a False y esperando a que el hilo termine.
        self._running = False
        # Si el hilo de recepción está activo, esperar a que termine antes de continuar.
        if self._thread:
            self._thread.join()
            self._thread = None