"""
Dashboard Ejecutivo - CCR
Versión con HTML/CSS grid puro (sin st.metric, st.progress, st.columns, st.dataframe, st.table).
Primero muestra datos de ejemplo para validación visual.
"""
import streamlit as st
import html
from datetime import date, datetime
from src.ui.theme import inject_css, svg_icon, COLORS
from src.alerts.scheduler import ejecutar_scheduler
from src.services.procesos_service import get_cierre_actual, calcular_avance_cierre
from src.services.alertas_service import get_alertas_activas_para_toast
from src.services.procesos_masivos_service import get_procesos_masivos_proximos
from src.services.config_service import get_config


# Configuración de página
st.set_page_config(page_title="Dashboard - CCR", layout="wide")

# Inyectar CSS
inject_css()

# Ejecutar scheduler
ejecutar_scheduler()

# Obtener cierre actual
cierre = get_cierre_actual()

# ============================================================
# DATOS DE EJEMPLO (para validación visual)
# ============================================================
# Avance: 38% (5 completados / 13 total)
avance_pct = 38

# KPIs
kpis = [
    ("Tareas pendientes", "14", ""),
    ("Tareas vencidas", "2", "rojo"),
    ("Procesos bloqueados", "1", ""),
    ("Procesos críticos", "3", "ambar"),
    ("SOX pendientes", "4", ""),
    ("Aprobaciones pendientes", "2", ""),
]

# Procesos (orden: vencidos, bloqueados, en proceso, pendientes, completados)
procesos_ejemplo = [
    {"nombre": "Índices y Monedas", "estado": "vencido", "detalle": "Vencido 2 d", "color": "#E24B4A"},
    {"nombre": "Correcciones ARL", "estado": "bloqueado", "detalle": "Dependencia pendiente", "color": "#888780"},
    {"nombre": "F394", "estado": "en_proceso", "detalle": "4/8 subtareas", "color": "#EF9F27"},
    {"nombre": "Reserva Matemática Ley 100", "estado": "en_proceso", "detalle": "2/5 subtareas", "color": "#EF9F27"},
    {"nombre": "Reserva Salario Mínimo", "estado": "pendiente_aprobacion", "detalle": "Pend. aprobación", "color": "#185FA5"},
    {"nombre": "Rentabilidades", "estado": "completado", "detalle": "8/8 subtareas", "color": "#639922"},
]

# Alertas
alertas_ejemplo = [
    {"icono": "lock", "titulo": "Proceso bloqueado", "detalle": "Correcciones ARL: esperando confirmación de Carlos", "color": "#888780"},
    {"icono": "clock_alert", "titulo": "Vencido", "detalle": "Índices y Monedas, límite 3 oct", "color": "#E24B4A"},
    {"icono": "file_check", "titulo": "Control SOX pendiente", "detalle": "Conciliación RM Ley 100, vence mañana", "color": "#BA7517"},
    {"icono": "calendar", "titulo": "Proceso masivo próximo", "detalle": "17615 Reporte Mensual RM F394, en 3 días", "color": "#185FA5"},
]

# Pendientes de hoy
hoy_ejemplo = [
    {"icono": "sun", "titulo": "Programar ramo 087", "derecha": "10:00"},
    {"icono": "sun", "titulo": "Revisar ejecución F394", "derecha": "15:00"},
]

# Próximos masivos
masivos_ejemplo = [
    {"icono": "calendar", "titulo": "17615 · Ramo 087", "derecha": "8 oct"},
    {"icono": "calendar", "titulo": "17616 · Ramo 088", "derecha": "9 oct"},
]

# Próximos vencimientos
vencimientos_ejemplo = [
    {"icono": "flag", "titulo": "Reporte Superintendencia", "derecha": "12 oct"},
    {"icono": "flag", "titulo": "Carga SAP", "derecha": "14 oct"},
]


# ============================================================
# CONSTRUIR HTML COMPLETO
# ============================================================
def build_dashboard_html():
    """Construye todo el HTML del dashboard como un solo string."""
    
    # --- 1. ENCABEZADO ---
    hoy_str = datetime.now().strftime("%A %d de %B").capitalize()
    cierre_nombre = html.escape(cierre.nombre) if cierre else "Sin cierre"
    
    header = f"""
<div class="ccr-header">
<div class="ccr-header-left">
{svg_icon('shield_check', 24, COLORS['acento'])}
<div class="ccr-header-title">Centro de Control de Reservas y Cierres Actuariales</div>
<div class="ccr-header-subtitle">Cierre: {html.escape(cierre_nombre.lower())} · Hoy: {html.escape(hoy_str)}</div>
</div>
<div class="ccr-header-right">
{svg_icon('bell', 20, COLORS['texto_secundario'])}
<span class="ccr-alert-pill">5 alertas</span>
</div>
</div>
"""
    
    # --- 2. AVANCE DEL CIERRE ---
    legend_items = [
        ("verde", "Completado", 5),
        ("ambar", "En proceso", 3),
        ("rojo", "Vencido", 1),
        ("gris", "Bloqueado", 1),
    ]
    
    legend_html = "".join([
        f'<div class="ccr-legend-item"><span class="ccr-status-dot ccr-status-dot--{c}"></span>{l} {n}</div>'
        for c, l, n in legend_items
    ])
    
    segments_html = "".join([
        f'<div class="ccr-progress-segment ccr-progress-segment--{c}" style="width: {p}%"></div>'
        for c, p in [("verde", 38), ("ambar", 23), ("rojo", 8), ("gris", 8)]
    ])
    
    avance = f"""
<div class="ccr-card">
<div class="ccr-card-header">
<span class="ccr-card-title">Avance alcanzado</span>
<span class="ccr-card-value">{avance_pct}%</span>
</div>
<div class="ccr-progress-stacked">
{segments_html}
</div>
<div class="ccr-progress-legend">
{legend_html}
</div>
</div>
"""
    
    # --- 3. INDICADORES ---
    kpi_html = ""
    for label, value, variante in kpis:
        color_class = ""
        if variante == "rojo":
            color_class = ' style="color: #A32D2D"'
        elif variante == "ambar":
            color_class = ' style="color: #854F0B"'
        kpi_html += f"""
<div class="ccr-kpi">
<div class="ccr-kpi-label">{html.escape(label)}</div>
<div class="ccr-kpi-value"{color_class}>{html.escape(value)}</div>
</div>
"""
    
    # --- 4. PROCESOS ---
    proc_rows = ""
    for p in procesos_ejemplo:
        estado_color = p["color"]
        estado_label = p["estado"].replace("_", " ").title()
        proc_rows += f"""
<div class="ccr-process-row">
<span class="ccr-status-dot" style="background: {estado_color}"></span>
<span class="ccr-process-name">{html.escape(p['nombre'])}</span>
<span class="ccr-process-state" style="color: {estado_color}">{html.escape(estado_label)} · {html.escape(p['detalle'])}</span>
</div>
"""
    
    procesos_card = f"""
<div class="ccr-card">
<div class="ccr-card-header">
{svg_icon('shield', 16, COLORS['acento'])}
<span class="ccr-card-title">Estado de procesos</span>
</div>
{proc_rows}
</div>
"""
    
    # --- 4. ALERTAS ---
    alert_rows = ""
    for a in alertas_ejemplo:
        alert_rows += f"""
<div class="ccr-alert-row">
{svg_icon(a['icono'], 16, a['color'])}
<div class="ccr-alert-content">
<div class="ccr-alert-title">{html.escape(a['titulo'])}</div>
<div class="ccr-alert-detail">{html.escape(a['detalle'])}</div>
</div>
</div>
"""
    
    alertas_card = f"""
<div class="ccr-card">
<div class="ccr-card-header">
{svg_icon('bell', 16, COLORS['acento'])}
<span class="ccr-card-title">Panel de alertas</span>
</div>
{alert_rows}
</div>
"""
    
    # --- 5. TARJETAS PEQUEÑAS ---
    def build_small_card(title, icon_name, rows_data, icon_color=COLORS['acento']):
        rows = ""
        for r in rows_data:
            rows += f"""
<div class="ccr-small-row">
{svg_icon(r['icono'], 16, icon_color)}
<span class="ccr-small-title">{html.escape(r['titulo'])}</span>
<span class="ccr-small-right">{html.escape(r['derecha'])}</span>
</div>
"""
        return f"""
<div class="ccr-card">
<div class="ccr-card-header">
{svg_icon(icon_name, 16, COLORS['acento'])}
<span class="ccr-card-title">{html.escape(title)}</span>
</div>
{rows}
</div>
"""
    
    hoy_card = build_small_card("Pendientes de hoy", "sun", hoy_ejemplo, COLORS['sem_ambar'])
    masivos_card = build_small_card("Próximos masivos", "calendar", masivos_ejemplo, COLORS['acento'])
    venc_card = build_small_card("Próximos vencimientos", "flag", vencimientos_ejemplo, COLORS['sem_rojo'])
    
    # --- ARMAR TODO ---
    return f"""
{header}
{avance}
<div class="ccr-grid-6">
{kpi_html}
</div>
<div class="ccr-grid-2">
{procesos_card}
{alertas_card}
</div>
<div class="ccr-grid-3">
{hoy_card}
{masivos_card}
{venc_card}
</div>
"""


# ============================================================
# INYECTAR CSS ADICIONAL PARA DASHBOARD
# ============================================================
st.markdown(f"""
<style>
/* Ocultar header, menú y footer */
#MainMenu {{ visibility: hidden !important; }}
footer {{ visibility: hidden !important; }}
header {{ visibility: hidden !important; }}
.stDeployButton {{ display: none !important; }}

/* Padding superior reducido */
.block-container {{
    max-width: 1200px !important;
    padding-top: 0.5rem !important;
    padding-bottom: 2rem !important;
    margin: 0 auto !important;
}}

/* Fuente Inter */
html, body, .stApp {{
    font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    background-color: {COLORS['fondo_pagina']} !important;
    color: {COLORS['texto_primario']} !important;
    font-weight: 400 !important;
}}

/* Header */
.ccr-header {{
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
    gap: 16px;
    margin-bottom: 12px;
}}
.ccr-header-left {{
    display: flex;
    align-items: center;
    gap: 12px;
}}
.ccr-header-right {{
    display: flex;
    align-items: center;
    gap: 8px;
    justify-content: flex-end;
}}
.ccr-header-title {{
    font-size: 18px;
    font-weight: 500;
    color: {COLORS['texto_primario']};
    margin: 0;
}}
.ccr-header-subtitle {{
    font-size: 13px;
    color: {COLORS['texto_secundario']};
    margin: 0;
}}
.ccr-alert-pill {{
    background: {COLORS['alerta_rojo_fondo']};
    color: {COLORS['alerta_rojo_texto']};
    font-size: 13px;
    font-weight: 500;
    padding: 2px 10px;
    border-radius: 8px;
}}

/* Tarjeta estándar */
.ccr-card {{
    background: {COLORS['fondo_tarjeta']};
    border: 0.5px solid {COLORS['borde']};
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 12px;
}}

/* Header de tarjeta */
.ccr-card-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}}
.ccr-card-title {{
    font-size: 15px;
    font-weight: 500;
    color: {COLORS['texto_primario']};
    margin: 0;
}}
.ccr-card-value {{
    font-size: 22px;
    font-weight: 500;
    color: {COLORS['texto_primario']};
    margin: 0;
}}

/* KPIs grid */
.ccr-grid-6 {{
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin-bottom: 12px;
}}
.ccr-kpi {{
    background: {COLORS['fondo_metrica']};
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
}}
.ccr-kpi-label {{
    font-size: 14px;
    color: {COLORS['texto_secundario']};
    font-weight: 400;
    margin-bottom: 4px;
}}
.ccr-kpi-value {{
    font-size: 24px;
    font-weight: 500;
    color: {COLORS['texto_primario']};
}}

/* Grid 2 columnas */
.ccr-grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 12px;
}}

/* Grid 3 columnas */
.ccr-grid-3 {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 12px;
}}

/* Barra de progreso */
.ccr-progress-stacked {{
    height: 10px;
    border-radius: 6px;
    background: #F5F5F3;
    overflow: hidden;
    display: flex;
    margin: 8px 0;
}}
.ccr-progress-segment {{
    height: 100%;
    transition: width 0.3s ease;
}}
.ccr-progress-segment--verde {{ background: {COLORS['sem_verde']}; }}
.ccr-progress-segment--ambar {{ background: {COLORS['sem_ambar']}; }}
.ccr-progress-segment--rojo {{ background: {COLORS['sem_rojo']}; }}
.ccr-progress-segment--gris {{ background: {COLORS['sem_gris']}; }}
.ccr-progress-legend {{
    display: flex;
    gap: 16px;
    font-size: 14px;
    color: {COLORS['texto_secundario']};
    flex-wrap: wrap;
}}
.ccr-legend-item {{
    display: flex;
    align-items: center;
    gap: 6px;
}}

/* Status dot */
.ccr-status-dot {{
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}}

/* Filas de proceso */
.ccr-process-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    border-top: 0.5px solid {COLORS['borde']};
    font-size: 15px;
}}
.ccr-process-row:first-child {{
    border-top: none;
}}
.ccr-process-name {{
    flex: 1;
    font-weight: 500;
    color: {COLORS['texto_primario']};
}}
.ccr-process-state {{
    font-size: 13px;
    color: {COLORS['texto_secundario']};
    text-align: right;
}}

/* Filas de alerta */
.ccr-alert-row {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 0;
    border-top: 0.5px solid {COLORS['borde']};
    font-size: 15px;
}}
.ccr-alert-row:first-child {{
    border-top: none;
}}
.ccr-alert-icon {{
    flex-shrink: 0;
    margin-top: 2px;
}}
.ccr-alert-content {{
    flex: 1;
    min-width: 0;
}}
.ccr-alert-title {{
    font-weight: 500;
    color: {COLORS['texto_primario']};
    margin-bottom: 2px;
}}
.ccr-alert-detail {{
    font-size: 13px;
    color: {COLORS['texto_secundario']};
}}

/* Filas pequeñas */
.ccr-small-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    border-top: 0.5px solid {COLORS['borde']};
    font-size: 15px;
}}
.ccr-small-row:first-child {{
    border-top: none;
}}
.ccr-small-title {{
    flex: 1;
    font-weight: 500;
    color: {COLORS['texto_primario']};
}}
.ccr-small-right {{
    font-size: 13px;
    color: {COLORS['texto_secundario']};
    text-align: right;
}}

/* Responsive */
@media (max-width: 1100px) {{
    .ccr-grid-6 {{
        grid-template-columns: repeat(3, 1fr);
    }}
    .ccr-grid-3 {{
        grid-template-columns: 1fr;
    }}
    .ccr-grid-2 {{
        grid-template-columns: 1fr;
    }}
}}
@media (max-width: 768px) {{
    .ccr-grid-6 {{
        grid-template-columns: 1fr;
    }}
}}
</style>
""", unsafe_allow_html=True)

# ============================================================
# RENDERIZAR DASHBOARD
# ============================================================
dashboard_html = build_dashboard_html()
st.markdown(dashboard_html, unsafe_allow_html=True)