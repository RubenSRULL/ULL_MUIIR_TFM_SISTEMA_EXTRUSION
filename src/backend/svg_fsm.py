# * Este fichero ha sido elaborado con ayuda de IA

from pathlib import Path


# --------------------------------------------------
# Mapeo de estados Python -> nodos draw.io del SVG
# --------------------------------------------------
# Si en draw.io cambias etiquetas/nodos, solo hay que actualizar estos IDs.
#
# EXTRUDER_FSM.svg:
#   BOOT       -> 5h7ZzsJRKUr04c_QEV-G-1
#   STOP       -> 5h7ZzsJRKUr04c_QEV-G-3
#   ALARM      -> 5h7ZzsJRKUr04c_QEV-G-4
#   MANUAL     -> 5h7ZzsJRKUr04c_QEV-G-5
#   IDLE_AUTO  -> 5h7ZzsJRKUr04c_QEV-G-6
#   PREHEAT    -> 5h7ZzsJRKUr04c_QEV-G-7
#   EXTRUDING  -> 5h7ZzsJRKUr04c_QEV-G-8
#
# WINDER_FSM.svg:
#   BOOT       -> ddRSOA4oobAeFci0r3gr-3
#   STOP       -> ddRSOA4oobAeFci0r3gr-8
#   ALARM      -> ddRSOA4oobAeFci0r3gr-11
#   HOME       -> ddRSOA4oobAeFci0r3gr-18
#   RUNNING    -> ddRSOA4oobAeFci0r3gr-25


EXTRUDER_CELL_IDS = {
    0: "5h7ZzsJRKUr04c_QEV-G-1",  # MACHINE_BOOT -> BOOT
    1: "5h7ZzsJRKUr04c_QEV-G-3",  # MACHINE_IDLE -> STOP
    2: "5h7ZzsJRKUr04c_QEV-G-6",  # MACHINE_AUTO_INIT -> IDLE_AUTO
    3: "5h7ZzsJRKUr04c_QEV-G-7",  # MACHINE_AUTO_PREHEAT -> PREHEAT
    4: "5h7ZzsJRKUr04c_QEV-G-6",  # MACHINE_AUTO_READY -> IDLE_AUTO
    5: "5h7ZzsJRKUr04c_QEV-G-8",  # MACHINE_AUTO_EXTRUDING -> EXTRUDING
    6: "5h7ZzsJRKUr04c_QEV-G-5",  # MACHINE_MANUAL_CONTROL -> MANUAL
    7: "5h7ZzsJRKUr04c_QEV-G-3",  # MACHINE_STOPPING -> STOP
    8: "5h7ZzsJRKUr04c_QEV-G-4",  # MACHINE_ALARM -> ALARM
}


WINDER_CELL_IDS = {
    0: "ddRSOA4oobAeFci0r3gr-3",   # WINDER_OFF -> BOOT
    1: "ddRSOA4oobAeFci0r3gr-8",   # WINDER_IDLE -> STOP
    2: "ddRSOA4oobAeFci0r3gr-18",  # WINDER_READY -> HOME
    3: "ddRSOA4oobAeFci0r3gr-25",  # WINDER_RUNNING -> RUNNING
    4: "ddRSOA4oobAeFci0r3gr-8",   # WINDER_STOPPING -> STOP
    5: "ddRSOA4oobAeFci0r3gr-11",  # WINDER_ALARM -> ALARM
}


def _assets_dir():
    # src/backend/svg_fsm.py -> raíz del proyecto -> assets/
    return Path(__file__).resolve().parents[2] / "assets"


def _leer_svg(nombre_archivo):
    ruta = _assets_dir() / nombre_archivo
    try:
        return ruta.read_text(encoding="utf-8")
    except Exception as e:
        return f"""
        <svg xmlns="http://www.w3.org/2000/svg" width="800" height="220">
            <rect width="100%" height="100%" fill="#ffffff"/>
            <text x="20" y="50" font-size="22" fill="red">
                No se pudo cargar {nombre_archivo}
            </text>
            <text x="20" y="90" font-size="14" fill="black">
                {e}
            </text>
        </svg>
        """


def _inyectar_estilo(svg, cell_id):
    if not cell_id:
        return svg

    css = f"""
    <style>
        g[data-cell-id="{cell_id}"] rect {{
            fill: #fff176 !important;
            stroke: #ff9800 !important;
            stroke-width: 4px !important;
            filter: drop-shadow(0px 0px 7px rgba(255, 152, 0, 0.95));
        }}

        g[data-cell-id="{cell_id}"] ellipse {{
            fill: #fff176 !important;
            stroke: #ff9800 !important;
            stroke-width: 4px !important;
            filter: drop-shadow(0px 0px 7px rgba(255, 152, 0, 0.95));
        }}

        g[data-cell-id="{cell_id}"] foreignObject div div div {{
            color: #000000 !important;
            font-weight: 800 !important;
        }}
    </style>
    """

    if "<defs/>" in svg:
        return svg.replace("<defs/>", f"<defs/>{css}", 1)

    pos = svg.find(">")
    if pos != -1:
        return svg[:pos + 1] + css + svg[pos + 1:]

    return css + svg


def svg_extrusora_activa(estado):
    svg = _leer_svg("EXTRUDER_FSM.svg")
    return _inyectar_estilo(svg, EXTRUDER_CELL_IDS.get(estado))


def svg_winder_activa(estado):
    svg = _leer_svg("WINDER_FSM.svg")
    return _inyectar_estilo(svg, WINDER_CELL_IDS.get(estado))
