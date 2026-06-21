# ==========================
# ===== Importaciones ======
# ==========================
import time
import threading
from picamera2 import Picamera2
import cv2
import numpy as np


# ===========================
# ===== Clase CAMARA_HQ =====
# ===========================
class CAMARA_HQ:
    """
    Descripción: Clase para manejar la cámara HQ de Raspberry Pi, capturando imágenes, midiendo diámetros y generando frames JPEG para transmisión web. Incluye un modo simulado si la cámara no está disponible.
    Atributos:
        factor_mm_por_pixel (float): Factor de conversión de mm a píxel.
        x_laser (int): Posición del láser en el eje X.
        ancho_roi (int): Ancho del área de interés (ROI).
        web_fps (int): Fotogramas por segundo para la transmisión web.
        web_width (int): Ancho de la imagen web.
        web_height (int): Altura de la imagen web.
        jpeg_quality (int): Calidad del JPEG para la transmisión web.
        verbose (bool): Indica si se deben imprimir mensajes de depuración.
    Métodos:
        generate_frames(): Genera frames JPEG para transmisión web.
    """

    def __init__(
        self,
        factor_mm_por_pixel=1.00,
        x_laser=640,
        ancho_roi=80,
        web_fps=15,
        web_width=640,
        web_height=360,
        jpeg_quality=50,
        verbose=False,
    ):
        """
        Descripción: Inicializa la clase CAMARA_HQ, configurando la cámara, los parámetros de medición y los hilos de captura, medición y transmisión web.
        Parametros:
            factor_mm_por_pixel (float): Factor de conversión de mm a píxel.
            x_laser (int): Posición del láser en el eje X.
            ancho_roi (int): Ancho del área de interés (ROI).
            web_fps (int): Fotogramas por segundo para la transmisión web.
            web_width (int): Ancho de la imagen web.
            web_height (int): Altura de la imagen web.
            jpeg_quality (int): Calidad del JPEG para la transmisión web.
            verbose (bool): Indica si se deben imprimir mensajes de depuración.
        Retorna:
            None
        """
        self.factor_mm_por_pixel = factor_mm_por_pixel
        self.x_laser = x_laser
        self.ancho_roi = ancho_roi

        self.frame_actual = None
        self.diametro_mm = None
        self.diametro_y1 = None
        self.diametro_y2 = None
        self.jpeg_actual = None
        self.running = True

        self.lock_frame = threading.Lock()
        self.lock_diametro = threading.Lock()
        self.lock_jpeg = threading.Lock()

        self.web_fps = web_fps
        self.web_width = web_width
        self.web_height = web_height
        self.jpeg_quality = jpeg_quality

        self.verbose = verbose
        self._ultimo_print = 0
        self.print_interval = 0.20

        self.picam2 = None
        self.modo_simulado = False
        self.estado_medicion = "Arrancando cámara"

        try:
            self.picam2 = Picamera2()

            config = {
                "main": {"size": (1280, 720), "format": "RGB888"},
                "controls": {
                    "AeEnable": True,
                    "AwbEnable": True,
                    "Brightness": 0.0,
                    "Contrast": 1.0,
                    "Sharpness": 1.0,
                    "Saturation": 1.0,
                },
            }
            self.__configurar(config)

            self.picam2.start()
            time.sleep(2)

            self.hilo_captura = threading.Thread(target=self.__capture_loop, daemon=True)
            self.hilo_medicion = threading.Thread(target=self.__diameter_loop, daemon=True)
            self.hilo_web = threading.Thread(target=self.__web_encoder_loop, daemon=True)

            self.hilo_captura.start()
            self.hilo_medicion.start()
            self.hilo_web.start()

            self.estado_medicion = "Cámara iniciada"
            print("Cámara iniciada correctamente")

        except Exception as e:
            print("Camara no conectada")
            print(e)
            self.modo_simulado = True
            self.estado_medicion = "Cámara simulada por error de inicio"
            self._iniciar_simulacion()

    # -- Inicia el modo de simulación de la cámara --
    def _iniciar_simulacion(self):
        """
        Descripción: Inicia el modo de simulación de la cámara, generando un flujo de imágenes simuladas y un diámetro fijo para pruebas.
        Parámetros:
            None
        Retorna:
            None
        """
        threading.Thread(target=self.__simulacion_loop, daemon=True).start()

    # -- Bucle de simulación que genera un flujo de imágenes simuladas y un diámetro fijo --
    def __simulacion_loop(self):
        while self.running:
            with self.lock_diametro:
                self.diametro_mm = 1.75
                self.diametro_y1 = None
                self.diametro_y2 = None
                self.estado_medicion = "Simulación: 1.75 mm"

            if cv2 is not None and np is not None:
                frame = np.zeros((self.web_height, self.web_width, 3), dtype=np.uint8)
                cv2.putText(frame, "CAMARA SIMULADA", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                cv2.putText(frame, "Diametro: 1.75 mm", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
                if ok:
                    with self.lock_jpeg:
                        self.jpeg_actual = buffer.tobytes()

            time.sleep(1.0 / max(self.web_fps, 1))

    # -- Configura la cámara con los parámetros especificados --
    def __configurar(self, config):
        video_config = self.picam2.create_video_configuration(
            main=config["main"],
            controls=config["controls"],
        )
        self.picam2.configure(video_config)

    # -- Bucle de captura de frames desde la cámara --
    def __capture_loop(self):
        while self.running:
            try:
                frame = self.picam2.capture_array()
                with self.lock_frame:
                    self.frame_actual = frame
            except Exception as e:
                print("Error capturando frame:", e)
                with self.lock_diametro:
                    self.estado_medicion = f"Error capturando frame: {e}"
                time.sleep(0.01)

    # -- Bucle de cálculo del diámetro --
    def __diameter_loop(self):
        while self.running:
            with self.lock_frame:
                if self.frame_actual is None:
                    roi = None
                else:
                    _, w, _ = self.frame_actual.shape

                    x_laser = int(max(0, min(w - 1, self.x_laser)))
                    ancho_roi = int(max(5, min(w, self.ancho_roi)))

                    x1 = x_laser - ancho_roi // 2
                    x2 = x_laser + ancho_roi // 2

                    x1 = max(0, x1)
                    x2 = min(w, x2)

                    if x2 <= x1:
                        roi = None
                    else:
                        roi = self.frame_actual[:, x1:x2].copy()

            if roi is None:
                with self.lock_diametro:
                    self.diametro_mm = None
                    self.diametro_y1 = None
                    self.diametro_y2 = None
                    self.estado_medicion = "ROI no válida o sin frame"
                time.sleep(0.001)
                continue

            resultado = self.__calculate_diameter_from_roi(roi)

            if resultado is not None:
                diametro, y_inicio, y_fin = resultado

                with self.lock_diametro:
                    self.diametro_mm = diametro
                    self.diametro_y1 = y_inicio
                    self.diametro_y2 = y_fin
                    self.estado_medicion = f"OK: {diametro:.3f} mm"

                self.__send_diameter(diametro)
            else:
                with self.lock_diametro:
                    self.diametro_mm = None
                    self.diametro_y1 = None
                    self.diametro_y2 = None
                    self.estado_medicion = "Sin rojo detectado en ROI"

            time.sleep(0.001)

    # -- Bucle de codificación para la transmisión web --
    def __web_encoder_loop(self):
        intervalo = 1.0 / max(self.web_fps, 1)

        while self.running:
            inicio = time.perf_counter()

            with self.lock_frame:
                frame = self.frame_actual
                if frame is not None:
                    frame_web = frame.copy()
                else:
                    frame_web = None

            if frame_web is None:
                time.sleep(0.01)
                continue

            frame_web = cv2.resize(
                frame_web,
                (self.web_width, self.web_height),
                interpolation=cv2.INTER_AREA,
            )

            with self.lock_diametro:
                diametro = self.diametro_mm
                diametro_y1 = self.diametro_y1
                diametro_y2 = self.diametro_y2
                estado = self.estado_medicion

            escala_x = self.web_width / 1280
            escala_y = self.web_height / 720
            x_laser_web = int(self.x_laser * escala_x)
            ancho_roi_web = max(2, int(self.ancho_roi * escala_x))
            x1_web = x_laser_web - ancho_roi_web // 2
            x2_web = x_laser_web + ancho_roi_web // 2

            x1_web = max(0, x1_web)
            x2_web = min(self.web_width - 1, x2_web)

            cv2.rectangle(frame_web, (x1_web, 0), (x2_web, frame_web.shape[0] - 1), (0, 255, 255), 1)

            if diametro is not None:
                if diametro_y1 is not None and diametro_y2 is not None:
                    y1_diam_web = int(diametro_y1 * escala_y)
                    y2_diam_web = int(diametro_y2 * escala_y)

                    cv2.line(frame_web, (x_laser_web, y1_diam_web), (x_laser_web, y2_diam_web), (0, 255, 0), 4)
                    cv2.line(frame_web, (x1_web, y1_diam_web), (x2_web, y1_diam_web), (255, 0, 255), 2)
                    cv2.line(frame_web, (x1_web, y2_diam_web), (x2_web, y2_diam_web), (255, 0, 255), 2)

                cv2.putText(frame_web, f"Diametro: {diametro:.2f} mm", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            else:
                cv2.putText(frame_web, "Sin medida", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            cv2.putText(frame_web, estado[:60], (20, self.web_height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

            ok, buffer = cv2.imencode(".jpg", frame_web, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])

            if ok:
                with self.lock_jpeg:
                    self.jpeg_actual = buffer.tobytes()

            pausa = intervalo - (time.perf_counter() - inicio)
            if pausa > 0:
                time.sleep(pausa)

    # -- Genera frames JPEG para transmisión web --
    def generate_frames(self):
        while True:
            with self.lock_jpeg:
                jpeg = self.jpeg_actual

            if jpeg is None:
                time.sleep(0.01)
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                jpeg +
                b"\r\n"
            )

            time.sleep(1.0 / max(self.web_fps, 1))

    # -- Calcula el diámetro a partir del ROI --
    def __calculate_diameter_from_roi(self, roi, medir_rojo=True):
        """
        Medición original, sin HSV ni cambios de umbral.
        """
        if roi is None or roi.size == 0:
            return None

        r = roi[:, :, 2].astype(np.int16)
        g = roi[:, :, 1].astype(np.int16)
        b = roi[:, :, 0].astype(np.int16)

        mascara_rojo = ((r > 120) & (r > g + 40) & (r > b + 40))

        suma_rojo = mascara_rojo.sum(axis=1)

        umbral_rojo_fila = 2
        filas_con_rojo = suma_rojo >= umbral_rojo_fila

        if medir_rojo:
            filas_a_medir = filas_con_rojo
        else:
            filas_a_medir = ~filas_con_rojo

        mejor_inicio = None
        mejor_fin = None
        inicio_actual = None

        for i, fila_valida in enumerate(filas_a_medir):
            if fila_valida:
                if inicio_actual is None:
                    inicio_actual = i
            else:
                if inicio_actual is not None:
                    fin_actual = i - 1

                    if (mejor_inicio is None or (fin_actual - inicio_actual) > (mejor_fin - mejor_inicio)):
                        mejor_inicio = inicio_actual
                        mejor_fin = fin_actual

                    inicio_actual = None

        if inicio_actual is not None:
            fin_actual = len(filas_a_medir) - 1

            if (mejor_inicio is None or (fin_actual - inicio_actual) > (mejor_fin - mejor_inicio)):
                mejor_inicio = inicio_actual
                mejor_fin = fin_actual

        if mejor_inicio is None:
            return None

        diametro_pixeles = mejor_fin - mejor_inicio + 1

        if diametro_pixeles < 5:
            return None

        diametro_mm = diametro_pixeles * self.factor_mm_por_pixel

        return diametro_mm, mejor_inicio, mejor_fin

    # -- Envía el diámetro medido a la salida estándar si está habilitado verbose --
    def __send_diameter(self, diametro_mm):
        if not self.verbose:
            return

        ahora = time.time()
        if ahora - self._ultimo_print >= self.print_interval:
            print(f"Diametro: {diametro_mm:.2f} mm")
            self._ultimo_print = ahora

    # -- Detiene la captura de la cámara y los hilos asociados --
    def stop(self):
        self.running = False
        time.sleep(0.1)

        try:
            if self.picam2 is not None:
                self.picam2.stop()
        except Exception:
            pass