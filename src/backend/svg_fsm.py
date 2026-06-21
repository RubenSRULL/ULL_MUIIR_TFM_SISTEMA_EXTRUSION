# * Este fichero ha sido elaborado con ayuda de IA

from pathlib import Path


# ==========================================================
# Mapeo directo de state_id Simulink -> nodos draw.io del SVG
# ==========================================================
#
# EXTRUDER_FSM_Y.state_id:
#   0 BOOT       -> BOOT
#   1 STOP       -> STOP
#   2 IDLE_AUTO  -> IDLE_AUTO
#   3 PREHEAT    -> PREHEAT
#   4 EXTRUDING  -> EXTRUDING
#   5 MANUAL     -> MANUAL
#   6 ALARM      -> ALARM
#
# WINDER_FSM_Y.state_id:
#   0 BOOT       -> BOOT
#   1 STOP       -> STOP
#   2 HOME       -> HOME
#   3 RUNNING    -> RUNNING
#   4 ALARM      -> ALARM
# ==========================================================

EXTRUDER_CELL_IDS = {
    0: "5h7ZzsJRKUr04c_QEV-G-1",  # BOOT
    1: "5h7ZzsJRKUr04c_QEV-G-3",  # STOP
    2: "5h7ZzsJRKUr04c_QEV-G-6",  # IDLE_AUTO
    3: "5h7ZzsJRKUr04c_QEV-G-7",  # PREHEAT
    4: "5h7ZzsJRKUr04c_QEV-G-8",  # EXTRUDING
    5: "5h7ZzsJRKUr04c_QEV-G-5",  # MANUAL
    6: "5h7ZzsJRKUr04c_QEV-G-4",  # ALARM
}


WINDER_CELL_IDS = {
    0: "ddRSOA4oobAeFci0r3gr-3",   # BOOT
    1: "ddRSOA4oobAeFci0r3gr-8",   # STOP
    2: "ddRSOA4oobAeFci0r3gr-18",  # HOME
    3: "ddRSOA4oobAeFci0r3gr-25",  # RUNNING
    4: "ddRSOA4oobAeFci0r3gr-11",  # ALARM
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
