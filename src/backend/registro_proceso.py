import csv
import os
import time
import threading
from datetime import datetime


class RegistroProceso:
    """
    Guarda datos del proceso en CSV.

    Crea dos archivos por ejecución:
      - telemetria_YYYYMMDD_HHMMSS.csv
      - eventos_YYYYMMDD_HHMMSS.csv

    telemetria:
      datos periódicos de la máquina, cámara y enrolladora.

    eventos:
      botones pulsados, cambios de vista, comandos enviados, calibración, parada, etc.
    """

    def __init__(self, carpeta="logs", periodo_telemetria=0.1):
        self.carpeta = carpeta
        self.periodo_telemetria = periodo_telemetria
        self._ultimo_guardado_telemetria = 0.0
        self._lock = threading.Lock()

        os.makedirs(self.carpeta, exist_ok=True)

        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.ruta_telemetria = os.path.join(self.carpeta, f"telemetria_{marca}.csv")
        self.ruta_eventos = os.path.join(self.carpeta, f"eventos_{marca}.csv")

        self.columnas_telemetria = [
            "timestamp",
            "tiempo_s",
            "diametro_camara_mm",
            "diametro_telemetria_mm",
            "temp",
            "target",
            "heater",
            "rpm_int",
            "rpm_ext",
            "state",
            "alarm",
            "winder_state",
            "winder_alarm",
            "factor_mm_por_pixel",
            "x_laser",
            "ancho_roi",
        ]

        self.columnas_eventos = [
            "timestamp",
            "tiempo_s",
            "tipo",
            "origen",
            "comando",
            "exito",
            "respuesta",
            "detalle",
        ]

        self._t0 = time.time()

        self._crear_csv(self.ruta_telemetria, self.columnas_telemetria)
        self._crear_csv(self.ruta_eventos, self.columnas_eventos)

    def _crear_csv(self, ruta, columnas):
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columnas)
            writer.writeheader()

    def _timestamp(self):
        return datetime.now().isoformat(timespec="milliseconds")

    def _tiempo_s(self):
        return round(time.time() - self._t0, 3)

    def guardar_telemetria(self, diametro_camara_mm, telemetria, camara=None):
        """
        Guarda una muestra periódica de telemetría.

        diametro_camara_mm:
            diámetro medido por cámara. Puede ser None.

        telemetria:
            diccionario de ControlUC.telemetria.
        """

        ahora = time.time()

        if ahora - self._ultimo_guardado_telemetria < self.periodo_telemetria:
            return

        self._ultimo_guardado_telemetria = ahora

        fila = {
            "timestamp": self._timestamp(),
            "tiempo_s": self._tiempo_s(),
            "diametro_camara_mm": diametro_camara_mm,
            "diametro_telemetria_mm": telemetria.get("diam"),
            "temp": telemetria.get("temp"),
            "target": telemetria.get("target"),
            "heater": telemetria.get("heater"),
            "rpm_int": telemetria.get("rpm_int"),
            "rpm_ext": telemetria.get("rpm_ext"),
            "state": telemetria.get("state"),
            "alarm": telemetria.get("alarm"),
            "winder_state": telemetria.get("winder_state"),
            "winder_alarm": telemetria.get("winder_alarm"),
            "factor_mm_por_pixel": getattr(camara, "factor_mm_por_pixel", None),
            "x_laser": getattr(camara, "x_laser", None),
            "ancho_roi": getattr(camara, "ancho_roi", None),
        }

        self._escribir_fila(self.ruta_telemetria, self.columnas_telemetria, fila)

    def guardar_evento(self, tipo, origen="", comando="", exito="", respuesta="", detalle=""):
        """
        Guarda eventos puntuales: botones, comandos, cambios de vista, calibración, parada, etc.
        """

        fila = {
            "timestamp": self._timestamp(),
            "tiempo_s": self._tiempo_s(),
            "tipo": tipo,
            "origen": origen,
            "comando": comando,
            "exito": exito,
            "respuesta": respuesta,
            "detalle": detalle,
        }

        self._escribir_fila(self.ruta_eventos, self.columnas_eventos, fila)

    def _escribir_fila(self, ruta, columnas, fila):
        with self._lock:
            try:
                with open(ruta, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=columnas)
                    writer.writerow(fila)
            except Exception as e:
                print(f"Error guardando registro en {ruta}: {e}")
