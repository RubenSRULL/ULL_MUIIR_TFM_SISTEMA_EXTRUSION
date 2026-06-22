# ==========================
# ===== Importaciones ======
# ==========================
from datetime import datetime

from dash import Dash, html, dcc, Output, Input, State, ctx, no_update
from flask import Response

from gpiozero import LED

from src.backend.CAMARA_HQ import CAMARA_HQ
from src.backend.comandos_uc import (AUTO_STATES, STOPPABLE_STATES, FASES_AUTOMATICAS,
                                     MACHINE_IDLE_AUTO, MACHINE_AUTO_PREHEAT,  MACHINE_AUTO_PREHEAT, MACHINE_AUTO_EXTRUDING,
                                     MACHINE_IDLE, MACHINE_MANUAL_CONTROL, MACHINE_STOPPING, WINDER_RUNNING, WINDER_ALARM,
                                     ControlUC, fase_desde_estado, nombre_estado, nombre_estado_winder,)
from src.backend.graficos import figura_lineas
from src.backend.UART_COM import UART_COM
from src.backend.registro_proceso import RegistroProceso
from src.backend.svg_fsm import svg_extrusora_activa, svg_winder_activa


# ==========================
# ====== Instancias ========
# ==========================

# -- Instancia de la aplicación Dash --
app = Dash(__name__, suppress_callback_exceptions=True)
# -- Instancia del servidor Flask  --
server = app.server
# -- Instancia de la cámara --
camara = CAMARA_HQ(verbose=False)
# -- Instancia de la comunicación UART con la UC --
uart = UART_COM(port="/dev/ttyUSB0", baudrate=115200, modo_simulado=False)
uart.iniciar_recepcion()
# -- Instancia del controlador de la UC --
uc = ControlUC(uart)
# -- Instancia del LED de control del láser --
laser = LED(4, initial_value=False)
# -- Instancia del registro de telemetría y eventos --
registro = RegistroProceso(carpeta="logs", periodo_telemetria=0.1)


# ============================
# ==== Variables globales ====
# ============================

MAX_PUNTOS = 150
tiempos = []
diametros = []
temperaturas = []
temperaturas_objetivo = []
velocidades_extrusora = []
velocidades_enrolladora = []


# =============================
# === Funciones auxiliares ====
# =============================

# --- Función para generar un log con timestamp ---
def log(texto):
    """
    Descripción: Genera un log con timestamp para mostrar en la interfaz de usuario.
    Parametros:
        texto (str): Texto del log a mostrar.
    Retorna:
        html.P: Elemento HTML con el log formateado.
    """
    return html.P(f"[{datetime.now().strftime('%H:%M:%S')}] > {texto}")

# --- Función para generar un indicador LED ---
def led(nombre, encendido):
    """
    Descripción: Genera un indicador LED con un nombre y estado.
    Parametros:
        nombre (str): Nombre del indicador.
        encendido (bool): Estado del indicador (True = encendido, False = apagado).
    Retorna:
        list: Lista de elementos HTML que representan el indicador LED.
    """
    return [html.Label(nombre), html.Div(className="led-on" if encendido else "led-off")]

# -- Función para generar estilos de visibilidad según la vista activa ---
def estilos_vista(vista):
    """
    Descripción: Genera estilos de visibilidad para las secciones de la interfaz según la vista activa.
    Parametros:
        vista (str): Vista activa ("monitoreo", "automatico", "manual", "estados").
    Retorna:
        tuple: Tupla con estilos de visibilidad para cada sección.
    """
    visible = {"display": "block"}
    oculto = {"display": "none"}
    return (
        visible if vista == "monitoreo" else oculto,
        visible if vista == "automatico" else oculto,
        visible if vista == "manual" else oculto,
        visible if vista == "estados" else oculto,
    )

# -- Función para generar los indicadores de fases automáticas ---
def indicadores_fases(fase_activa):
    """
    Descripción: Genera los indicadores visuales de las fases automáticas del proceso.
    Parametros:
        fase_activa (int): Índice de la fase activa (0 a 4).
    Retorna:
        list: Lista de elementos HTML que representan los indicadores de fases automáticas.
    """
    salida = []
    for i, fase in enumerate(FASES_AUTOMATICAS):
        clase_fase = "fase_auto"
        clase_label = "label_fase_auto"
        if i < fase_activa:
            clase_fase += " fase_auto_completada"
        if i == fase_activa:
            clase_fase += " fase_auto_activa"
            clase_label += " label_fase_auto_activa"

        salida.append(
            html.Div(
                [html.Div(str(i + 1), className=clase_fase), html.Label(fase["titulo"], className=clase_label)],
                className="fila_fase_auto",
            )
        )
    return salida

# -- Función para cargar panel de fase automática ---
def panel_fase_automatica():
    """
    Descripción: Genera el panel de controles y descripción para la fase automática del proceso.
    Parametros:
        None
    Retorna:
        html.Div: Elemento HTML que representa el panel de fase automática con controles y descripción.
    """
    return html.Div(
        className="contenedor_fase_auto",
        children=[
            html.H3("Fase 1: Configuración", id="titulo-fase-auto"),
            html.P(FASES_AUTOMATICAS[0]["descripcion"], id="descripcion-fase-auto"),
            html.Div(
                id="controles-fase-0",
                className="controles_fase_auto",
                children=[
                    html.Div([html.Label("Material"), dcc.Dropdown(id="auto-material", options=["PLA", "ABS"], value="PLA", clearable=False)], className="campo_auto"),
                    html.Div([html.Label("Tiempo de proceso (min)"), dcc.Input(id="auto-tiempo", type="number", min=1, step=1, value=10)], className="campo_auto"),
                    html.Div([html.Label("Diámetro objetivo (mm)"), dcc.Input(id="auto-diametro-objetivo", type="number", min=0.1, step=0.01, value=1.75)], className="campo_auto"),
                ],
            ),
            html.Div(
                id="controles-fase-1",
                className="controles_fase_auto",
                style={"display": "none"},
                children=[
                    html.H4("Temperatura del calefactor"),
                    dcc.Slider(
                        id="auto-temperatura",
                        min=100,
                        max=400,
                        step=1,
                        value=200,
                        marks={100: "100°C", 180: "180°C", 220: "220°C", 250: "250°C", 360: "360°C", 400: "400°C"},
                        included=False,
                        tooltip={"placement": "bottom", "always_visible": True},
                    ),
                    html.Div([html.Button("ON", id="auto-aplicar-temperatura", n_clicks=0, className="btn-on"), html.Button("OFF", id="auto-apagar-temperatura", n_clicks=0, className="btn-off")], className="contenedor-botones"),
                ],
            ),
            html.Div(
                id="controles-fase-2",
                className="controles_fase_auto",
                style={"display": "none"},
                children=[
                    html.H4("Guiado del filamento"),
                    html.P("Cuando la FSM esté en PREHEAT y el firmware permita extrusión, pulsa Siguiente."),
                ],
            ),
            html.Div(
                id="controles-fase-3",
                className="controles_fase_auto",
                style={"display": "none"},
                children=[
                    html.H4("Extrusión"),
                    html.Div(id="auto-tiempo-restante", children="Proceso en marcha"),
                ],
            ),
            html.Div(
                id="controles-fase-4",
                className="controles_fase_auto",
                style={"display": "none"},
                children=[
                    html.H4("Finalización del proceso"),
                    dcc.Checklist(
                        id="auto-finalizacion-checklist",
                        options=[
                            {"label": "Apagar calefactor", "value": "calefactor"},
                            {"label": "Detener motores", "value": "motores"},
                            {"label": "Desactivar láser", "value": "laser"},
                        ],
                        value=["calefactor", "motores", "laser"],
                    ),
                    html.Button("Finalizar proceso", id="auto-finalizar-proceso", n_clicks=0, className="btn-off"),
                ],
            ),
        ],
    )

# -- Función para generar estilos de visibilidad de controles según la fase activa ---
def estilos_controles_fase(fase_activa):
    """
    Descripción: Genera estilos de visibilidad para los controles de cada fase automática según la fase activa.
    Parametros:
        fase_activa (int): Índice de la fase activa (0 a 4).
    Retorna:
        list: Lista de diccionarios con estilos de visibilidad para cada fase automática.
    """
    return [{"display": "block"} if i == fase_activa else {"display": "none"} for i in range(len(FASES_AUTOMATICAS))]

# -- Función para generar la sección de monitoreo ---
def monitoreo():
    """
    Descripción: Genera la sección de monitoreo de la interfaz, incluyendo gráficos de diámetro, temperatura y velocidades, así como el feed de video de la cámara.
    Parametros:
        None
    Retorna:
        html.Div: Elemento HTML que representa la sección de monitoreo con gráficos y feed de video.
    """
    return html.Div(
        className="seccion-monitoreo",
        children=[
            html.Div(
                className="fila_graficos",
                children=[
                    html.Div(
                        className="grafico-panel-diametro",
                        children=[
                            dcc.Graph(
                                id="grafico-diametro",
                                responsive=True,
                                figure=figura_lineas(
                                    "Diámetro en tiempo real",
                                    "Tiempo (s)",
                                    "Diámetro (mm)",
                                    [("Diámetro", [], [])],
                                ),
                                className="grafico grafico-diametro-card",
                            ),
                            html.Div(
                                className="panel-medicion-calibracion",
                                children=[
                                    html.Div(
                                        className="fila-calibracion",
                                        children=[
                                            html.Label("mm/píxel"),
                                            dcc.Input(
                                                id="calibracion-mm-pixel",
                                                type="number",
                                                min=0.0001,
                                                step=0.0001,
                                                value=camara.factor_mm_por_pixel,
                                                debounce=True,
                                            ),
                                            html.Label("X láser"),
                                            dcc.Input(
                                                id="calibracion-x-laser",
                                                type="number",
                                                min=0,
                                                max=1279,
                                                step=1,
                                                value=camara.x_laser,
                                                debounce=True,
                                            ),
                                            html.Label("Ancho ROI"),
                                            dcc.Input(
                                                id="calibracion-ancho-roi",
                                                type="number",
                                                min=5,
                                                max=400,
                                                step=1,
                                                value=camara.ancho_roi,
                                                debounce=True,
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        f"Factor: {camara.factor_mm_por_pixel:.4f} | ROI x={camara.x_laser}, ancho={camara.ancho_roi}",
                                        id="calibracion-estado",
                                        className="calibracion-estado",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Img(id="video-feed", src="/video_feed", className="grafico-img"),
                ],
            ),
            html.Div(
                className="fila_graficos",
                children=[
                    dcc.Graph(id="grafico-temperatura", responsive=True, figure=figura_lineas("Temperatura en tiempo real", "Tiempo (s)", "Temperatura (°C)", [("Temperatura", [], []), ("Objetivo", [], [])]), className="grafico"),
                    dcc.Graph(id="grafico-velocidades", responsive=True, figure=figura_lineas("Velocidades en tiempo real", "Tiempo (s)", "RPM", [("Extrusora", [], []), ("Enrolladora", [], [])]), className="grafico"),
                ],
            ),
        ],
    )

# -- Función para generar la sección de estados ---
def estados():
    """
    Descripción: Genera la sección de estados de la interfaz, mostrando los diagramas de estados de la extrusora y enrolladora en tiempo real.
    Parametros:
        None
    Retorna:
        html.Div: Elemento HTML que representa la sección de estados con diagramas de estados en tiempo real.
    """
    return html.Div(
        className="seccion-estados",
        style={
            "padding": "12px",
            "width": "100%",
            "height": "100%",
            "display": "flex",
            "flexDirection": "column",
            "gap": "12px",
            "boxSizing": "border-box",
        },
        children=[
            html.Iframe(
                id="svg-extrusora-fsm",
                srcDoc=svg_extrusora_activa(0),
                style={
                    "width": "100%",
                    "height": "48vh",
                    "border": "none",
                    "background": "white",
                },
            ),
            html.Iframe(
                id="svg-enrolladora-fsm",
                srcDoc=svg_winder_activa(0),
                style={
                    "width": "100%",
                    "height": "48vh",
                    "border": "none",
                    "background": "white",
                },
            ),
        ],
    )

# -- Función para generar la sección de automático ---
def automatico():
    """
    Descripción: Genera la sección de automático de la interfaz, mostrando los indicadores de fases automáticas y el panel de controles para cada fase.
    Parametros:
        None
    Retorna:
        html.Div: Elemento HTML que representa la sección de automático con indicadores y panel de controles.
    """
    return html.Div(
        className="contenedor_fases",
        children=[
            dcc.Store(id="store-fase-automatica", data=0),
            html.Div(id="indicadores-fases-auto", className="indicadores_fases_auto", children=indicadores_fases(0)),
            html.Div(id="contenedor-fase-auto", children=panel_fase_automatica()),
            html.Div([html.Button("Anterior", id="btn-fase-anterior", n_clicks=0, className="boton_menu", style={"display": "none"}), html.Button("Siguiente", id="btn-fase-siguiente", n_clicks=0, className="boton_menu")], className="navegacion_fases_auto"),
        ],
    )

# - Función para generar la sección de manual ---
def manual():
    """
    Descripción: Genera la sección de manual de la interfaz, mostrando los controles para cada parámetro de la extrusora.
    Parametros:
        None
    Retorna:
        html.Div: Elemento HTML que representa la sección de manual con controles.
    """
    return html.Div(
        className="seccion_manual",
        children=[
            html.Div([html.H3("Temperatura calefactor"), dcc.Slider(id="slider-temperatura", min=100, max=400, value=100, step=1, marks={100: "100°C", 180: "180°C", 220: "220°C", 250: "250°C", 400: "400°C"}, included=False, tooltip={"placement": "bottom", "always_visible": True}), html.Div([html.Button("ON", id="temperatura-on", n_clicks=0, className="btn-on"), html.Button("OFF", id="temperatura-off", n_clicks=0, className="btn-off")], className="contenedor-botones")], className="contenedor_slider_botones"),
            html.Div([html.H3("Velocidad extrusora"), dcc.Slider(id="slider-velocidad-extrusora", min=0, max=10, value=0, step=0.1, marks={i: f"{i}" for i in range(11)}, included=False, tooltip={"placement": "bottom", "always_visible": True}), html.Div([html.Button("ON", id="velocidad-extrusora-on", n_clicks=0, className="btn-on"), html.Button("OFF", id="velocidad-extrusora-off", n_clicks=0, className="btn-off")], className="contenedor-botones")], className="contenedor_slider_botones"),
            html.Div([html.H3("Velocidad enrolladora"), dcc.Slider(id="slider-velocidad-enrolladora", min=0, max=10, value=0, step=0.1, marks={i: f"{i}" for i in range(11)}, included=False, tooltip={"placement": "bottom", "always_visible": True}), html.Div([html.Button("ON", id="velocidad-enrolladora-on", n_clicks=0, className="btn-on"), html.Button("OFF", id="velocidad-enrolladora-off", n_clicks=0, className="btn-off")], className="contenedor-botones")], className="contenedor_slider_botones"),
            html.Div([html.H3("Control láser"), html.Div([html.Button("ON", id="laser-on", n_clicks=0, className="btn-on"), html.Button("OFF", id="laser-off", n_clicks=0, className="btn-off")], className="contenedor-botones")], className="contenedor_slider_botones"),
        ],
    )

# -- Función para generar layout principal de la aplicación ---
app.layout = html.Div(
    className="contenedor_principal",
    children=[
        html.Div(
            className="contenedor_lateral",
            children=[
                html.Div([html.Button("Monitoreo", id="btn-monitoreo", className="boton_menu"), html.Button("Automático", id="btn-automatico", className="boton_menu"), html.Button("Manual", id="btn-manual", className="boton_menu"), html.Button("Estados", id="btn-estados", className="boton_menu")], className="menu"),
                html.Div(
                    [
                        html.Div([html.Label("Diámetro"), html.Span("0.00", id="diametro-display", className="display")], className="label-display-parametros"),
                        html.Div([html.Label("Temperatura"), html.Span("0.00", id="temperatura-display", className="display")], className="label-display-parametros"),
                        html.Div([html.Label("Vel. Extrusión"), html.Span("0.00", id="vel-extrusion-display", className="display")], className="label-display-parametros"),
                        html.Div([html.Label("Vel. Enrolladora"), html.Span("0.00", id="vel-enrolladora-display", className="display")], className="label-display-parametros"),
                        html.Div(
                            className="estados-telemetria-compactos",
                            style={
                                "width": "90%",
                                "color": "white",
                                "fontSize": "11px",
                                "lineHeight": "1.2",
                                "marginTop": "6px",
                                "marginBottom": "6px",
                                "padding": "6px 8px",
                                "borderRadius": "6px",
                                "backgroundColor": "rgba(255,255,255,0.08)",
                            },
                            children=[
                                html.Div(
                                    style={"display": "flex", "justifyContent": "space-between", "gap": "8px"},
                                    children=[
                                        html.Span("Estado extrusora"),
                                        html.Strong("0 - BOOT", id="estado-extrusora-display"),
                                    ],
                                ),
                                html.Div(
                                    style={"display": "flex", "justifyContent": "space-between", "gap": "8px", "marginTop": "3px"},
                                    children=[
                                        html.Span("Estado enrolladora"),
                                        html.Strong("0 - BOOT", id="estado-enrolladora-display"),
                                    ],
                                ),
                            ],
                        ),
                        html.Button("Parada", id="btn-parada", className="boton_parada", style={"marginTop": "10px"}),
                    ],
                    className="parametros",
                ),
                html.Div(
                    [
                        html.Div(id="calefactor-estado", children=led("Calefactor", False), className="estado"),
                        html.Div(id="motor-extrusora-estado", children=led("Motor Extrusora", False), className="estado"),
                        html.Div(id="motor-enrolladora-estado", children=led("Motor Enrolladora", False), className="estado"),
                        html.Div(id="laser-estado", children=led("Láser", False), className="estado"),
                        html.Div(id="camara-estado", children=led("Cámara", not camara.modo_simulado), className="estado"),
                    ],
                    className="estados",
                ),
            ],
        ),
        html.Div(
            className="contenedor_contenido_menu",
            children=[
                html.Div(id="seccion-monitoreo", children=monitoreo(), style={"display": "block"}),
                html.Div(id="seccion-automatico", children=automatico(), style={"display": "none"}),
                html.Div(id="seccion-manual", children=manual(), style={"display": "none"}),
                html.Div(id="seccion-estados", children=estados(), style={"display": "none"}),
                html.Div([log("Sistema iniciado")], id="log-sistema", className="contenedor_log"),
            ],
        ),
        dcc.Store(id="store-vista-activa", data="monitoreo"),
        dcc.Store(id="store-modo-pendiente", data=None),
        dcc.Interval(id="intervalo-monitor", interval=100, n_intervals=0),
        dcc.Interval(id="intervalo-graficos", interval=250, n_intervals=0),
        dcc.Interval(id="intervalo-estados-svg", interval=500, n_intervals=0),
        dcc.Interval(id="intervalo-modo-pendiente", interval=500, n_intervals=0),
    ],
)


# =========================
# ====== Callbacks ========
# =========================

# -- Callback para actualizar los indicadores de monitoreo ---
@app.callback(
    Output("diametro-display", "children"),
    Output("temperatura-display", "children"),
    Output("vel-extrusion-display", "children"),
    Output("vel-enrolladora-display", "children"),
    Output("estado-extrusora-display", "children"),
    Output("estado-enrolladora-display", "children"),
    Output("motor-enrolladora-estado", "children"),
    Input("intervalo-monitor", "n_intervals"),
)
def actualizar_monitorizacion(n):
    """
    Descripción: Callback que se ejecuta periódicamente para actualizar los indicadores de monitoreo en la interfaz de usuario.
    Parametros:
        n (int): Número de intervalos transcurridos desde el inicio del callback.
    Retorna:
        tuple: Valores actualizados para los indicadores de monitoreo.
    """
    uc.leer_pendiente()

    diametro = camara.diametro_mm if camara.diametro_mm is not None else uc.telemetria["diam"]

    if camara.diametro_mm is not None:
        uc.enviar_sin_respuesta(f"DIAM:{diametro:.3f}")

    registro.guardar_telemetria(diametro, uc.telemetria, camara)

    t = n * 0.1
    tiempos.append(t)
    diametros.append(diametro)
    temperaturas.append(uc.telemetria["temp"])
    temperaturas_objetivo.append(uc.telemetria["target"])
    velocidades_extrusora.append(uc.telemetria["rpm_int"])
    velocidades_enrolladora.append(uc.telemetria["rpm_ext"])

    for lista in [tiempos, diametros, temperaturas, temperaturas_objetivo, velocidades_extrusora, velocidades_enrolladora]:
        if len(lista) > MAX_PUNTOS:
            del lista[:-MAX_PUNTOS]

    estado_extrusora = uc.telemetria["state"]
    estado_winder = uc.telemetria["winder_state"]

    texto_estado_extrusora = f"{estado_extrusora} - {nombre_estado(estado_extrusora)}"
    nombre_winder = nombre_estado_winder(estado_winder)
    texto_estado_enrolladora = f"{estado_winder} - {nombre_winder}"

    motor_enrolladora_estado = [
        html.Label(f"Enrolladora: {nombre_winder}"),
        html.Div(className="led-on" if estado_winder == WINDER_RUNNING else "led-off"),
    ]

    return (
        f"{diametro:.2f}",
        f"{uc.telemetria['temp']:.2f}",
        f"{uc.telemetria['rpm_int']:.2f}",
        f"{uc.telemetria['rpm_ext']:.2f}",
        texto_estado_extrusora,
        texto_estado_enrolladora,
        motor_enrolladora_estado,
    )

# -- Callback para actualizar los SVGs de los FSM --
@app.callback(
    Output("svg-extrusora-fsm", "srcDoc"),
    Output("svg-enrolladora-fsm", "srcDoc"),
    Input("intervalo-estados-svg", "n_intervals"),
)
def actualizar_svg_fsm(n):
    """
    Descripción: Callback que se ejecuta periódicamente para actualizar los diagramas de estados (FSM) de la extrusora y enrolladora en la interfaz de usuario.
    Parametros:
        n (int): Número de intervalos transcurridos desde el inicio del callback.
    Retorna:
        tuple: Contenido SVG actualizado para los diagramas de estados de la extrusora y enrolladora.
    """
    return (
        svg_extrusora_activa(uc.telemetria["state"]),
        svg_winder_activa(uc.telemetria["winder_state"]),
    )

# -- Callback para actualizar los gráficos de monitoreo ---
@app.callback(
    Output("grafico-diametro", "figure"),
    Output("grafico-temperatura", "figure"),
    Output("grafico-velocidades", "figure"),
    Input("intervalo-graficos", "n_intervals"),
)
def actualizar_graficos(n):
    """
    Descripción: Callback que se ejecuta periódicamente para actualizar los gráficos de monitoreo (diámetro, temperatura y velocidades) en la interfaz de usuario.
    Parametros:
        n (int): Número de intervalos transcurridos desde el inicio del callback.
    Retorna:
        tuple: Figuras actualizadas para los gráficos de diámetro, temperatura y velocidades.
    """
    return (
        figura_lineas("Diámetro en tiempo real", "Tiempo (s)", "Diámetro (mm)", [("Diámetro", tiempos, diametros)]),
        figura_lineas("Temperatura en tiempo real", "Tiempo (s)", "Temperatura (°C)", [("Temperatura", tiempos, temperaturas), ("Objetivo", tiempos, temperaturas_objetivo)]),
        figura_lineas("Velocidades en tiempo real", "Tiempo (s)", "RPM", [("Extrusora", tiempos, velocidades_extrusora), ("Enrolladora", tiempos, velocidades_enrolladora)]),
    )

# -- Callback para actualizar la calibración de la cámara ---
@app.callback(
    Output("calibracion-estado", "children"),
    Input("calibracion-mm-pixel", "value"),
    Input("calibracion-x-laser", "value"),
    Input("calibracion-ancho-roi", "value"),
    prevent_initial_call=True,
)
def actualizar_calibracion(mm_pixel, x_laser, ancho_roi):
    """
    Descripción: Callback que se ejecuta para actualizar la calibración de la cámara.
    Parametros:
        mm_pixel (float): Factor de conversión de mm a píxel.
        x_laser (int): Posición del láser en el eje X.
        ancho_roi (int): Ancho del área de interés.
    Retorna:
        str: Mensaje con el estado de la calibración.
    """
    if mm_pixel is None or mm_pixel <= 0:
        return "mm/píxel no válido"
    if x_laser is None or x_laser < 0:
        return "X láser no válida"
    if ancho_roi is None or ancho_roi < 5:
        return "Ancho ROI no válido"

    camara.factor_mm_por_pixel = float(mm_pixel)
    camara.x_laser = int(x_laser)
    camara.ancho_roi = int(ancho_roi)

    detalle = f"mm_pixel={camara.factor_mm_por_pixel};x_laser={camara.x_laser};ancho_roi={camara.ancho_roi}"
    registro.guardar_evento("CALIBRACION", "panel_calibracion", detalle=detalle)

    return f"Factor: {camara.factor_mm_por_pixel:.4f} | ROI x={camara.x_laser}, ancho={camara.ancho_roi}"

# -- Callback para actualizar la fase automática ---
@app.callback(
    Output("indicadores-fases-auto", "children"),
    Output("titulo-fase-auto", "children"),
    Output("descripcion-fase-auto", "children"),
    Output("controles-fase-0", "style"),
    Output("controles-fase-1", "style"),
    Output("controles-fase-2", "style"),
    Output("controles-fase-3", "style"),
    Output("controles-fase-4", "style"),
    Output("btn-fase-anterior", "style"),
    Output("btn-fase-siguiente", "style"),
    Input("store-fase-automatica", "data"),
)
def pintar_fase_automatica(fase):
    """
    Descripción: Callback que se ejecuta para actualizar la visualización de la fase automática del proceso, incluyendo los indicadores de fase, título, descripción y estilos de visibilidad de los controles.
    Parametros:
        fase (int): Índice de la fase activa (0 a 4).
    Retorna:
        tuple: Valores actualizados para los indicadores de fase, título, descripción y estilos de visibilidad de los controles.
    """
    fase = max(0, min(fase or 0, len(FASES_AUTOMATICAS) - 1))
    visible_boton = {"display": "inline-block"}
    oculto = {"display": "none"}
    estilos_fases = estilos_controles_fase(fase)

    return (
        indicadores_fases(fase),
        f"Fase {fase + 1}: {FASES_AUTOMATICAS[fase]['titulo']}",
        FASES_AUTOMATICAS[fase]["descripcion"],
        *estilos_fases,
        oculto if fase == 0 else visible_boton,
        oculto if fase == len(FASES_AUTOMATICAS) - 1 else visible_boton,
    )

# -- Callback para manejar las acciones de la fase automática ---
@app.callback(
    Output("store-fase-automatica", "data", allow_duplicate=True),
    Output("log-sistema", "children", allow_duplicate=True),
    Output("calefactor-estado", "children", allow_duplicate=True),
    Output("motor-extrusora-estado", "children", allow_duplicate=True),
    Output("motor-enrolladora-estado", "children", allow_duplicate=True),
    Input("btn-fase-anterior", "n_clicks"),
    Input("btn-fase-siguiente", "n_clicks"),
    Input("auto-aplicar-temperatura", "n_clicks"),
    Input("auto-apagar-temperatura", "n_clicks"),
    Input("auto-finalizar-proceso", "n_clicks"),
    State("auto-temperatura", "value"),
    State("store-fase-automatica", "data"),
    State("log-sistema", "children"),
    prevent_initial_call=True,
)
def acciones_auto(n_ant, n_sig, n_temp_on, n_temp_off, n_fin, temp_objetivo, fase, logs):
    """
    Descripción: Callback que se ejecuta para manejar las acciones de la fase automática del proceso, incluyendo los botones de navegación entre fases, aplicación y apagado de temperatura, y finalización del proceso.
    Parametros:
        n_ant (int): Número de clics en el botón "Anterior".
        n_sig (int): Número de clics en el botón "Siguiente".
        n_temp_on (int): Número de clics en el botón "ON" de temperatura.
        n_temp_off (int): Número de clics en el botón "OFF" de temperatura.
        n_fin (int): Número de clics en el botón "Finalizar proceso".
        temp_objetivo (float): Valor objetivo de temperatura.
        fase (int): Índice de la fase activa (0 a 4).
        logs (list): Lista de logs del sistema.
    Retorna:
        tuple: Valores actualizados para la fase automática, logs del sistema y estados de los indicadores de calefactor, motor extrusora y motor enrolladora.
    """
    logs = logs or []
    fase = fase or 0
    disparador = ctx.triggered_id
    registro.guardar_evento("BOTON_AUTO", disparador, detalle=f"fase={fase}")

    if disparador == "btn-fase-anterior":
        if fase >= 3:
            ok, respuesta = uc.enviar("STOP")
            registro.guardar_evento("COMANDO_AUTO", disparador, comando="STOP", exito=ok, respuesta=respuesta)
            logs.append(log(f"STOP automático: {'OK' if ok else 'rechazado'}. Respuesta: {respuesta}"))
            return (4 if ok else fase), logs, led("Calefactor", False), led("Motor Extrusora", False), led("Motor Enrolladora", False)
        return max(fase - 1, 0), logs, no_update, no_update, no_update

    if disparador == "btn-fase-siguiente":
        if fase == 0:
            logs.append(log("Configuración aceptada. Ajusta temperatura y pulsa ON."))
            return 1, logs, no_update, no_update, no_update
        if fase == 1:
            ok_estado, estado, respuesta = uc.consultar_estado(timeout=0.5)
            if ok_estado and estado in {MACHINE_AUTO_PREHEAT, MACHINE_AUTO_EXTRUDING}:
                logs.append(log(f"FSM en {nombre_estado(estado)}. Puedes pasar a START."))
                return 2 if estado == MACHINE_AUTO_PREHEAT else 3, logs, no_update, no_update, no_update
            logs.append(log(f"Aún no está en PREHEAT. Estado: {respuesta}"))
            return fase, logs, no_update, no_update, no_update
        if fase == 2:
            ok, respuesta = uc.enviar("START")
            registro.guardar_evento("COMANDO_AUTO", disparador, comando="START", exito=ok, respuesta=respuesta)
            logs.append(log(f"START extrusión: {'OK' if ok else 'rechazado'}. Respuesta: {respuesta}"))
            return (3 if ok else fase), logs, no_update, led("Motor Extrusora", ok), led("Motor Enrolladora", ok)
        if fase == 3:
            ok, respuesta = uc.enviar("STOP")
            registro.guardar_evento("COMANDO_AUTO", disparador, comando="STOP", exito=ok, respuesta=respuesta)
            logs.append(log(f"STOP extrusión: {'OK' if ok else 'rechazado'}. Respuesta: {respuesta}"))
            return (4 if ok else fase), logs, led("Calefactor", False), led("Motor Extrusora", False), led("Motor Enrolladora", False)

    if disparador == "auto-aplicar-temperatura":
        ok_temp, resp_temp = uc.enviar(f"SET_TEMP:{temp_objetivo}")
        registro.guardar_evento("COMANDO_AUTO", disparador, comando=f"SET_TEMP:{temp_objetivo}", exito=ok_temp, respuesta=resp_temp)
        ok_preheat, resp_preheat = uc.enviar("PREHEAT") if ok_temp else (False, "PREHEAT no enviado")
        registro.guardar_evento("COMANDO_AUTO", disparador, comando="PREHEAT", exito=ok_preheat, respuesta=resp_preheat)
        ok = ok_temp and ok_preheat
        logs.append(log(f"SET_TEMP + PREHEAT: {'OK' if ok else 'rechazado'}. Respuestas: {resp_temp} / {resp_preheat}"))
        return 1, logs, led("Calefactor", ok), no_update, no_update

    if disparador == "auto-apagar-temperatura":
        ok, respuesta = uc.enviar("STOP")
        registro.guardar_evento("COMANDO_AUTO", disparador, comando="STOP", exito=ok, respuesta=respuesta)
        logs.append(log(f"STOP desde precalentamiento: {'OK' if ok else 'rechazado'}. Respuesta: {respuesta}"))
        return (4 if ok else fase), logs, led("Calefactor", False), no_update, no_update

    if disparador == "auto-finalizar-proceso":
        ok, respuesta = uc.enviar("STOP")
        registro.guardar_evento("COMANDO_AUTO", disparador, comando="STOP", exito=ok, respuesta=respuesta)
        logs.append(log(f"Finalización: {'OK' if ok else 'rechazada'}. Respuesta: {respuesta}"))
        laser.off()
        return (4 if ok else fase), logs, led("Calefactor", False), led("Motor Extrusora", False), led("Motor Enrolladora", False)

    return no_update, no_update, no_update, no_update, no_update

# -- Callback para cambiar de vista y manejar la transición entre modos automático y manual ---
@app.callback(
    Output("seccion-monitoreo", "style"),
    Output("seccion-automatico", "style"),
    Output("seccion-manual", "style"),
    Output("seccion-estados", "style"),
    Output("log-sistema", "children", allow_duplicate=True),
    Output("store-fase-automatica", "data", allow_duplicate=True),
    Output("store-vista-activa", "data"),
    Output("store-modo-pendiente", "data", allow_duplicate=True),
    Input("btn-monitoreo", "n_clicks"),
    Input("btn-automatico", "n_clicks"),
    Input("btn-manual", "n_clicks"),
    Input("btn-estados", "n_clicks"),
    State("store-fase-automatica", "data"),
    State("log-sistema", "children"),
    prevent_initial_call=True,
)
def cambiar_vista(n_mon, n_auto, n_manual, n_estados, fase, logs):
    """
    Descripción: Callback que se ejecuta cuando se presionan los botones de cambio de vista (Monitoreo, Automático, Manual, Estados). Maneja la transición entre modos automático y manual, actualiza los estilos de visibilidad de las secciones y registra los eventos en el log del sistema.
    Parametros:
        n_mon (int): Número de clics en el botón "Monitoreo".
        n_auto (int): Número de clics en el botón "Automático".
        n_manual (int): Número de clics en el botón "Manual".
        n_estados (int): Número de clics en el botón "Estados".
        fase (int): Índice de la fase activa (0 a 4).
        logs (list): Lista de logs del sistema.
    Retorna:
        tuple: Estilos de visibilidad de las secciones, logs del sistema, fase automática actualizada, vista activa y modo pendiente.
    """
    logs = logs or []
    disparador = ctx.triggered_id
    registro.guardar_evento("CAMBIO_VISTA", disparador)

    if disparador == "btn-monitoreo":
        logs.append(log("Vista Monitoreo. FSM sin cambios."))
        estilos = estilos_vista("monitoreo")
        return estilos[0], estilos[1], estilos[2], estilos[3], logs, no_update, "monitoreo", no_update

    if disparador == "btn-estados":
        logs.append(log("Vista Estados. FSM sin cambios."))
        estilos = estilos_vista("estados")
        return estilos[0], estilos[1], estilos[2], estilos[3], logs, no_update, "estados", no_update

    destino = "automatico" if disparador == "btn-automatico" else "manual"
    estilos = estilos_vista(destino)
    ok_estado, estado, respuesta_estado = uc.consultar_estado(timeout=0.5)

    if not ok_estado:
        logs.append(log(f"No se pudo consultar la FSM. Respuesta: {respuesta_estado}"))
        return estilos[0], estilos[1], estilos[2], estilos[3], logs, no_update, destino, no_update

    if destino == "automatico":
        if estado in AUTO_STATES:
            logs.append(log(f"Vista Automático. FSM ya estaba en {nombre_estado(estado)}."))
            return estilos[0], estilos[1], estilos[2], estilos[3], logs, fase_desde_estado(estado, fase), destino, None
        if estado == MACHINE_IDLE:
            ok, respuesta = uc.enviar("AUTO")
            logs.append(log(f"AUTO: {'STOP -> IDLE_AUTO' if ok else 'rechazado'}. Respuesta: {respuesta}"))
            return estilos[0], estilos[1], estilos[2], estilos[3], logs, 0 if ok else no_update, destino, None
        if estado == MACHINE_MANUAL_CONTROL:
            ok, respuesta = uc.enviar("STOP")
            logs.append(log(f"Cambio Manual -> Auto: STOP {'OK' if ok else 'rechazado'}. AUTO queda pendiente. Respuesta: {respuesta}"))
            return estilos[0], estilos[1], estilos[2], estilos[3], logs, no_update, destino, "auto" if ok else None

    if destino == "manual":
        if estado == MACHINE_MANUAL_CONTROL:
            logs.append(log("Vista Manual. FSM ya estaba en MANUAL."))
            return estilos[0], estilos[1], estilos[2], estilos[3], logs, no_update, destino, None
        if estado == MACHINE_IDLE:
            ok, respuesta = uc.enviar("MANUAL")
            logs.append(log(f"MANUAL: {'STOP -> MANUAL' if ok else 'rechazado'}. Respuesta: {respuesta}"))
            return estilos[0], estilos[1], estilos[2], estilos[3], logs, no_update, destino, None
        if estado == MACHINE_IDLE_AUTO:
            ok_reset, resp_reset = uc.enviar("RESET_AUTO")
            ok_manual, resp_manual = uc.enviar("MANUAL") if ok_reset else (False, "MANUAL no enviado")
            logs.append(log(f"IDLE_AUTO -> Manual: RESET_AUTO={resp_reset}, MANUAL={resp_manual}"))
            return estilos[0], estilos[1], estilos[2], estilos[3], logs, no_update, destino, None
        if estado in {MACHINE_AUTO_PREHEAT, MACHINE_AUTO_PREHEAT, MACHINE_AUTO_EXTRUDING}:
            ok, respuesta = uc.enviar("STOP")
            logs.append(log(f"Cambio Auto -> Manual: STOP {'OK' if ok else 'rechazado'}. MANUAL queda pendiente. Respuesta: {respuesta}"))
            return estilos[0], estilos[1], estilos[2], estilos[3], logs, 4 if ok else no_update, destino, "manual" if ok else None

    if estado == MACHINE_STOPPING:
        logs.append(log(f"FSM en STOPPING. {destino.upper()} queda pendiente hasta IDLE."))
        return estilos[0], estilos[1], estilos[2], estilos[3], logs, no_update, destino, "auto" if destino == "automatico" else "manual"

    logs.append(log(f"Cambio de modo bloqueado. Estado actual: {nombre_estado(estado)}"))
    return estilos[0], estilos[1], estilos[2], estilos[3], logs, no_update, destino, no_update

# -- Callback para ejecutar el cambio de modo pendiente cuando la FSM esté en IDLE ---
@app.callback(
    Output("store-modo-pendiente", "data", allow_duplicate=True),
    Output("log-sistema", "children", allow_duplicate=True),
    Output("store-fase-automatica", "data", allow_duplicate=True),
    Input("intervalo-modo-pendiente", "n_intervals"),
    State("store-modo-pendiente", "data"),
    State("log-sistema", "children"),
    prevent_initial_call=True,
)
def ejecutar_modo_pendiente(n, modo_pendiente, logs):
    """
    Descripción: Callback que se ejecuta periódicamente para verificar si hay un modo pendiente (automático o manual) y ejecutarlo cuando la FSM esté en estado IDLE. Actualiza el log del sistema y la fase automática según corresponda.
    Parametros:
        n (int): Número de intervalos transcurridos desde el inicio del callback.
        modo_pendiente (str): Modo pendiente a ejecutar ("auto" o "manual").
        logs (list): Lista de logs del sistema.
    Retorna:
        tuple: Modo pendiente actualizado (None si se ejecutó correctamente), logs del sistema y fase automática actualizada (0 si se ejecutó AUTO, no_update si se ejecutó MANUAL o no se ejecutó).
    """
    if not modo_pendiente:
        return no_update, no_update, no_update

    registro.guardar_evento("MODO_PENDIENTE", "intervalo-modo-pendiente", detalle=f"modo={modo_pendiente}")

    ok_estado, estado, _ = uc.consultar_estado(timeout=0.3)
    if not ok_estado or estado != MACHINE_IDLE:
        return no_update, no_update, no_update

    logs = logs or []
    comando = "AUTO" if modo_pendiente == "auto" else "MANUAL"
    ok, respuesta = uc.enviar(comando)
    logs.append(log(f"Cambio pendiente {comando}: {'OK' if ok else 'rechazado'}. Respuesta: {respuesta}"))
    return None if ok else modo_pendiente, logs, 0 if ok and comando == "AUTO" else no_update

# -- Callback para manejar los controles manuales de temperatura, velocidad y láser ---
@app.callback(
    Output("log-sistema", "children", allow_duplicate=True),
    Output("calefactor-estado", "children", allow_duplicate=True),
    Output("motor-extrusora-estado", "children", allow_duplicate=True),
    Output("motor-enrolladora-estado", "children", allow_duplicate=True),
    Output("laser-estado", "children", allow_duplicate=True),
    Input("temperatura-on", "n_clicks"),
    Input("temperatura-off", "n_clicks"),
    Input("velocidad-extrusora-on", "n_clicks"),
    Input("velocidad-extrusora-off", "n_clicks"),
    Input("velocidad-enrolladora-on", "n_clicks"),
    Input("velocidad-enrolladora-off", "n_clicks"),
    Input("laser-on", "n_clicks"),
    Input("laser-off", "n_clicks"),
    State("slider-temperatura", "value"),
    State("slider-velocidad-extrusora", "value"),
    State("slider-velocidad-enrolladora", "value"),
    State("log-sistema", "children"),
    prevent_initial_call=True,
)
def control_manual(n1, n2, n3, n4, n5, n6, n7, n8, temp, rpm_int, rpm_ext, logs):
    """
    Descripción: Callback que se ejecuta cuando se presionan los botones de control manual (temperatura, velocidad y láser). Envía los comandos correspondientes a la unidad de control, actualiza el log del sistema y los estados de los indicadores de calefactor, motor extrusora, motor enrolladora y láser.
    Parametros:
        n1, n2, n3, n4, n5, n6, n7, n8 (int): Número de clics en los botones de control manual.
        temp (float): Valor de temperatura seleccionado en el slider.
        rpm_int (float): Valor de velocidad de la extrusora seleccionado en el slider.
        rpm_ext (float): Valor de velocidad de la enrolladora seleccionado en el slider.
        logs (list): Lista de logs del sistema.
    Retorna:
        tuple: Logs del sistema actualizados y estados de los indicadores de calefactor, motor extrusora, motor enrolladora y láser.
    """
    logs = logs or []
    disparador = ctx.triggered_id
    registro.guardar_evento(
        "BOTON_MANUAL",
        disparador,
        detalle=f"temp={temp};rpm_int={rpm_int};rpm_ext={rpm_ext}",
    )
    calefactor = motor_int = motor_ext = laser_estado = no_update

    comandos = {
        "temperatura-on": (f"SET_TEMP:{temp}", "Calefactor", True),
        "temperatura-off": ("HEATER_OFF", "Calefactor", False),
        "velocidad-extrusora-on": (f"SET_INT_RPM:{rpm_int}", "Motor Extrusora", True),
        "velocidad-extrusora-off": ("STOP_INT", "Motor Extrusora", False),
        "velocidad-enrolladora-on": (f"SET_EXT_RPM:{rpm_ext}", "Motor Enrolladora", True),
        "velocidad-enrolladora-off": ("STOP_EXT", "Motor Enrolladora", False),
    }

    if disparador in comandos:
        comando, nombre, encendido = comandos[disparador]
        ok, respuesta = uc.enviar(comando)
        registro.guardar_evento("COMANDO_MANUAL", disparador, comando=comando, exito=ok, respuesta=respuesta)
        logs.append(log(f"{comando}: {'OK' if ok else 'error'}. Respuesta: {respuesta}"))
        estado = led(nombre, ok and encendido)
        if "Calefactor" in nombre:
            calefactor = estado
        elif "Extrusora" in nombre:
            motor_int = estado
        else:
            motor_ext = estado

    elif disparador == "laser-on":
        laser.on()
        registro.guardar_evento("GPIO", "laser-on", comando="LASER_ON", exito=True)
        logs.append(log("Láser ON"))
        laser_estado = led("Láser", True)

    elif disparador == "laser-off":
        laser.off()
        registro.guardar_evento("GPIO", "laser-off", comando="LASER_OFF", exito=True)
        logs.append(log("Láser OFF"))
        laser_estado = led("Láser", False)

    else:
        return no_update, no_update, no_update, no_update, no_update

    return logs, calefactor, motor_int, motor_ext, laser_estado

# -- Callback para manejar la parada de emergencia ---
@app.callback(
    Output("log-sistema", "children", allow_duplicate=True),
    Output("calefactor-estado", "children", allow_duplicate=True),
    Output("motor-extrusora-estado", "children", allow_duplicate=True),
    Output("motor-enrolladora-estado", "children", allow_duplicate=True),
    Output("laser-estado", "children", allow_duplicate=True),
    Input("btn-parada", "n_clicks"),
    State("log-sistema", "children"),
    prevent_initial_call=True,
)
def parada_emergencia(n_clicks, logs):
    """
    Descripción: Callback que se ejecuta cuando se presiona el botón de parada de emergencia. Envía el comando STOP a la unidad de control, apaga el láser y actualiza el log del sistema y los estados de los indicadores de calefactor, motor extrusora, motor enrolladora y láser.
    Parametros:
        n_clicks (int): Número de clics en el botón de parada de emergencia.
        logs (list): Lista de logs del sistema.
    Retorna:
        tuple: Logs del sistema actualizados y estados de los indicadores de calefactor, motor extrusora, motor enrolladora y láser.
    """
    if not n_clicks:
        return no_update, no_update, no_update, no_update, no_update

    logs = logs or []
    registro.guardar_evento("BOTON_PARADA", "btn-parada")
    ok, respuesta = uc.enviar("STOP")
    registro.guardar_evento("COMANDO_PARADA", "btn-parada", comando="STOP", exito=ok, respuesta=respuesta)
    laser.off()
    registro.guardar_evento("GPIO", "btn-parada", comando="LASER_OFF", exito=True)
    logs.append(log(f"PARADA: {'STOP enviado' if ok else 'error enviando STOP'}. Respuesta: {respuesta}"))
    return logs, led("Calefactor", False), led("Motor Extrusora", False), led("Motor Enrolladora", False), led("Láser", False)

# =========================
# ====== Video Feed =======
# =========================
@server.route("/video_feed")
def video_feed():
    return Response(camara.generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

# ==============
# ==== Main ====
# ==============
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=8050)