"""
Sistema de diseño CCR - Colores, CSS y helpers HTML reutilizables.
Un único bloque CSS inyectado via inject_css().
"""
import streamlit as st
import html


# ============================================================
# PALETA DE COLORES
# ============================================================
COLORS = {
    # Semáforo (único uso de color fuerte)
    "sem_verde": "#639922",      # Completado
    "sem_ambar": "#EF9F27",      # En proceso
    "sem_rojo": "#E24B4A",       # Vencido
    "sem_gris": "#888780",       # Bloqueado
    
    # Acento
    "acento": "#185FA5",         # Enlaces, ítem activo, iconos
    
    # Fondos
    "fondo_pagina": "#FAF9F7",   # Off-white cálido
    "fondo_tarjeta": "#FFFFFF",
    "fondo_metrica": "#F5F5F3",
    "fondo_secundario": "#F5F5F3",
    
    # Bordes
    "borde": "rgba(0,0,0,0.12)",
    
    # Texto
    "texto_primario": "#2C2C2A",
    "texto_secundario": "#5F5E5A",
    
    # Alertas
    "alerta_rojo_fondo": "#FCEBEB",
    "alerta_rojo_texto": "#791F1F",
    "alerta_ambar_fondo": "#FAEEDA",
    "alerta_ambar_texto": "#633806",
    "alerta_azul_fondo": "#E6F1FB",
    "alerta_azul_texto": "#0C447C",
    
    # Píldoras de prioridad
    "prio_baja": "#639922",
    "prio_media": "#185FA5",
    "prio_alta": "#EF9F27",
    "prio_critica": "#E24B4A",
}


# ============================================================
# CSS GLOBAL
# ============================================================
CSS_GLOBAL = f"""
<style>
/* ============================================================
   RESET Y BASE
   ============================================================ */
.block-container {{
    max-width: 1200px !important;
    padding-top: 0.5rem !important;
    padding-bottom: 2rem !important;
    margin: 0 auto !important;
}}

/* Ocultar elementos de Streamlit */
#MainMenu {{ visibility: hidden !important; }}
footer {{ visibility: hidden !important; }}
header {{ visibility: hidden !important; }}
.stDeployButton {{ display: none !important; }}

/* Tipografía global */
html, body, .stApp {{
    font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif !important;
    color: {COLORS["texto_primario"]} !important;
    background-color: {COLORS["fondo_pagina"]} !important;
    font-size: 14px !important;
    line-height: 1.5 !important;
    font-weight: 400 !important;
}}

/* Títulos */
h1, h2, h3, h4, h5, h6 {{
    font-weight: 500 !important;
    color: {COLORS["texto_primario"]} !important;
    margin-top: 0.5rem !important;
    margin-bottom: 0.5rem !important;
    text-transform: none !important;
}}
h1 {{ font-size: 24px !important; }}
h2 {{ font-size: 20px !important; }}
h3 {{ font-size: 18px !important; }}
h4 {{ font-size: 16px !important; }}

/* Texto auxiliar */
small, .texto-auxiliar {{
    font-size: 12px !important;
    color: {COLORS["texto_secundario"]} !important;
    font-weight: 400 !important;
}}

/* ============================================================
   TARJETAS BASE
   ============================================================ */
.ccr-card {{
    background: {COLORS["fondo_tarjeta"]};
    border: 0.5px solid {COLORS["borde"]};
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 12px;
}}

.ccr-card-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
}}

.ccr-card-title {{
    font-size: 16px;
    font-weight: 500;
    color: {COLORS["texto_primario"]};
    margin: 0;
}}

.ccr-card-subtitle {{
    font-size: 12px;
    color: {COLORS["texto_secundario"]};
    font-weight: 400;
    margin: 0;
}}

/* ============================================================
   SEMÁFORO - PUNTOS DE ESTADO
   ============================================================ */
.ccr-status-dot {{
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 8px;
    flex-shrink: 0;
}}
.ccr-status-dot--verde {{ background: {COLORS["sem_verde"]}; }}
.ccr-status-dot--ambar {{ background: {COLORS["sem_ambar"]}; }}
.ccr-status-dot--rojo {{ background: {COLORS["sem_rojo"]}; }}
.ccr-status-dot--gris {{ background: {COLORS["sem_gris"]}; }}

/* ============================================================
   PÍLDORAS (BADGES)
   ============================================================ */
.ccr-badge {{
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
    white-space: nowrap;
}}
.ccr-badge--verde {{
    background: {COLORS["sem_verde"]}20;
    color: {COLORS["sem_verde"]};
}}
.ccr-badge--ambar {{
    background: {COLORS["sem_ambar"]}20;
    color: {COLORS["sem_ambar"]};
}}
.ccr-badge--rojo {{
    background: {COLORS["sem_rojo"]}20;
    color: {COLORS["sem_rojo"]};
}}
.ccr-badge--gris {{
    background: {COLORS["sem_gris"]}20;
    color: {COLORS["sem_gris"]};
}}
.ccr-badge--azul {{
    background: {COLORS["acento"]}20;
    color: {COLORS["acento"]};
}}

/* Prioridades */
.ccr-prio-baja {{ background: {COLORS["prio_baja"]}20; color: {COLORS["prio_baja"]}; }}
.ccr-prio-media {{ background: {COLORS["prio_media"]}20; color: {COLORS["prio_media"]}; }}
.ccr-prio-alta {{ background: {COLORS["prio_alta"]}20; color: {COLORS["prio_alta"]}; }}
.ccr-prio-critica {{ background: {COLORS["prio_critica"]}20; color: {COLORS["prio_critica"]}; }}

/* ============================================================
   BARRA APILADA (PROGRESO)
   ============================================================ */
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
.ccr-progress-segment--verde {{ background: {COLORS["sem_verde"]}; }}
.ccr-progress-segment--ambar {{ background: {COLORS["sem_ambar"]}; }}
.ccr-progress-segment--rojo {{ background: {COLORS["sem_rojo"]}; }}
.ccr-progress-segment--gris {{ background: {COLORS["sem_gris"]}; }}

.ccr-progress-legend {{
    display: flex;
    gap: 16px;
    font-size: 14px;
    color: {COLORS["texto_secundario"]};
    margin-top: 4px;
    flex-wrap: wrap;
}}
.ccr-legend-item {{
    display: flex;
    align-items: center;
    gap: 6px;
}}

/* ============================================================
   FILAS DE LISTA
   ============================================================ */
.ccr-list-row {{
    display: flex;
    align-items: center;
    padding: 8px 0;
    border-top: 0.5px solid {COLORS["borde"]};
    gap: 12px;
}}
.ccr-list-row:first-child {{
    border-top: none;
}}

/* ============================================================
   ALERTAS / FILAS DE ALERTA
   ============================================================ */
.ccr-alert-row {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 8px;
    margin-bottom: 8px;
    font-size: 13px;
}}
.ccr-alert-row--rojo {{
    background: {COLORS["alerta_rojo_fondo"]};
    color: {COLORS["alerta_rojo_texto"]};
}}
.ccr-alert-row--ambar {{
    background: {COLORS["alerta_ambar_fondo"]};
    color: {COLORS["alerta_ambar_texto"]};
}}
.ccr-alert-row--azul {{
    background: {COLORS["alerta_azul_fondo"]};
    color: {COLORS["alerta_azul_texto"]};
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
    margin-bottom: 2px;
}}
.ccr-alert-detail {{
    font-size: 12px;
    opacity: 0.9;
}}

/* ============================================================
   KPI CARD (para dashboard)
   ============================================================ */
.ccr-kpi-card {{
    background: {COLORS["fondo_metrica"]};
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
    min-height: 80px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}}
.ccr-kpi-label {{
    font-size: 12px;
    color: {COLORS["texto_secundario"]};
    font-weight: 400;
    margin-bottom: 4px;
    text-transform: none;
}}
.ccr-kpi-value {{
    font-size: 22px;
    font-weight: 500;
    color: {COLORS["texto_primario"]};
    line-height: 1.2;
}}
.ccr-kpi-value--rojo {{ color: {COLORS["sem_rojo"]}; }}
.ccr-kpi-value--ambar {{ color: {COLORS["sem_ambar"]}; }}

/* ============================================================
   TABLAS
   ============================================================ */
.stDataFrame {{
    border: 0.5px solid {COLORS["borde"]} !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}}
.stDataFrame thead th {{
    background: {COLORS["fondo_secundario"]} !important;
    color: {COLORS["texto_primario"]} !important;
    font-weight: 500 !important;
    font-size: 12px !important;
    padding: 8px 12px !important;
    border-bottom: 1px solid {COLORS["borde"]} !important;
}}
.stDataFrame tbody td {{
    font-size: 13px !important;
    padding: 8px 12px !important;
    border-bottom: 0.5px solid {COLORS["borde"]} !important;
}}
.stDataFrame tbody tr:last-child td {{
    border-bottom: none !important;
}}
.stDataFrame tbody tr:hover td {{
    background: {COLORS["fondo_secundario"]} !important;
}}

/* ============================================================
   FORMULARIOS
   ============================================================ */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div,
.stDateInput > div > div > input,
.stNumberInput > div > div > input {{
    border: 0.5px solid {COLORS["borde"]} !important;
    border-radius: 6px !important;
    background: {COLORS["fondo_tarjeta"]} !important;
    color: {COLORS["texto_primario"]} !important;
    font-size: 13px !important;
}}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus,
.stSelectbox > div > div > div:focus-within {{
    border-color: {COLORS["acento"]} !important;
    box-shadow: 0 0 0 2px {COLORS["acento"]}20 !important;
}}

/* Botones */
.stButton > button {{
    border-radius: 6px !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    padding: 6px 16px !important;
    border: 0.5px solid {COLORS["borde"]} !important;
    background: {COLORS["fondo_tarjeta"]} !important;
    color: {COLORS["texto_primario"]} !important;
    transition: all 0.15s ease !important;
}}
.stButton > button:hover {{
    background: {COLORS["fondo_secundario"]} !important;
    border-color: {COLORS["acento"]} !important;
}}
.stButton > button[kind="primary"] {{
    background: {COLORS["acento"]} !important;
    border-color: {COLORS["acento"]} !important;
    color: white !important;
}}
.stButton > button[kind="primary"]:hover {{
    background: #145085 !important;
    border-color: #145085 !important;
}}

/* ============================================================
   EXPANDERS
   ============================================================ */
.streamlit-expanderHeader {{
    background: {COLORS["fondo_tarjeta"]} !important;
    border: 0.5px solid {COLORS["borde"]} !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    color: {COLORS["texto_primario"]} !important;
}}
.streamlit-expanderContent {{
    border: 0.5px solid {COLORS["borde"]} !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px !important;
    padding: 12px !important;
}}

/* ============================================================
   TABS
   ============================================================ */
.stTabs [data-baseweb="tab-list"] {{
    gap: 4px !important;
    background: transparent !important;
}}
.stTabs [data-baseweb="tab"] {{
    background: {COLORS["fondo_tarjeta"]} !important;
    border: 0.5px solid {COLORS["borde"]} !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 8px 16px !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    color: {COLORS["texto_secundario"]} !important;
}}
.stTabs [aria-selected="true"] {{
    background: {COLORS["fondo_pagina"]} !important;
    border-bottom-color: {COLORS["fondo_pagina"]} !important;
    color: {COLORS["acento"]} !important;
}}

/* ============================================================
   SIDEBAR
   ============================================================ */
section[data-testid="stSidebar"] {{
    background: {COLORS["fondo_pagina"]} !important;
    border-right: 0.5px solid {COLORS["borde"]} !important;
}}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stTextInput label,
section[data-testid="stSidebar"] .stDateInput label {{
    font-size: 12px !important;
    color: {COLORS["texto_secundario"]} !important;
    font-weight: 500 !important;
    text-transform: none !important;
}}

/* ============================================================
   TOAST PERSONALIZADO
   ============================================================ */
.stToast {{
    border-radius: 8px !important;
    padding: 12px 16px !important;
    font-size: 13px !important;
}}

/* ============================================================
   COLUMNAS RESPONSIVE
   ============================================================ */
@media (max-width: 1200px) {{
    .block-container {{
        max-width: 100% !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }}
}}
@media (max-width: 768px) {{
    .ccr-kpi-card {{
        min-height: 70px;
        padding: 10px 12px;
    }}
    .ccr-kpi-value {{
        font-size: 18px;
    }}
}}
</style>
"""


# ============================================================
# FUNCIONES PÚBLICAS
# ============================================================

def inject_css():
    """Inyecta el CSS global en la app. Llamar una vez por página."""
    st.markdown(CSS_GLOBAL, unsafe_allow_html=True)


def status_dot(estado_codigo: str) -> str:
    """
    Retorna HTML para un punto de semáforo según código de estado.
    Códigos: 'completado', 'en_proceso', 'vencido', 'bloqueado', 'pendiente', 'pendiente_aprobacion', 'cancelado'
    """
    mapping = {
        "completado": "verde",
        "en_proceso": "ambar",
        "vencido": "rojo",
        "bloqueado": "gris",
        "pendiente": "gris",
        "pendiente_aprobacion": "ambar",
        "cancelado": "gris",
    }
    cls = mapping.get(estado_codigo, "gris")
    return f'<span class="ccr-status-dot ccr-status-dot--{cls}"></span>'


def badge(texto: str, variante: str = "gris") -> str:
    """
    Retorna HTML para una píldora (badge).
    Variantes: verde, ambar, rojo, gris, azul
    """
    return f'<span class="ccr-badge ccr-badge--{variante}">{html.escape(texto)}</span>'


def priority_badge(prioridad_codigo: str) -> str:
    """
    Retorna HTML para una píldora de prioridad.
    Códigos: baja, media, alta, critica
    """
    return f'<span class="ccr-badge ccr-prio-{prioridad_codigo}">{html.escape(prioridad_codigo.capitalize())}</span>'


def progress_stacked(porcentajes: dict) -> str:
    """
    Retorna HTML para una barra de progreso apilada.
    porcentajes: dict con claves 'verde', 'ambar', 'rojo', 'gris' (valores 0-100)
    """
    segments = []
    for color in ["verde", "ambar", "rojo", "gris"]:
        pct = porcentajes.get(color, 0)
        if pct > 0:
            segments.append(f'<div class="ccr-progress-segment ccr-progress-segment--{color}" style="width: {pct}%"></div>')
        else:
            segments.append(f'<div class="ccr-progress-segment ccr-progress-segment--{color}" style="width: 0%"></div>')
    
    legend_items = []
    labels = {"verde": "Completado", "ambar": "En proceso", "rojo": "Vencido", "gris": "Bloqueado"}
    for color in ["verde", "ambar", "rojo", "gris"]:
        pct = porcentajes.get(color, 0)
        if pct > 0:
            legend_items.append(
                f'<span class="ccr-legend-item">'
                f'<span class="ccr-status-dot ccr-status-dot--{color}"></span>'
                f'{labels[color]} {pct}%'
                f'</span>'
            )
    
    return f'''
    <div class="ccr-progress-stacked">
        {"".join(segments)}
    </div>
    <div class="ccr-progress-legend">
        {"".join(legend_items)}
    </div>
    '''


def kpi_card(label: str, value: str | int, variante: str = "") -> str:
    """
    Retorna HTML para una tarjeta KPI.
    variante: '', 'rojo', 'ambar' (para el color del valor)
    """
    cls = f" ccr-kpi-value--{variante}" if variante else ""
    return f'''
    <div class="ccr-kpi-card">
        <div class="ccr-kpi-label">{html.escape(label)}</div>
        <div class="ccr-kpi-value{cls}">{html.escape(str(value))}</div>
    </div>
    '''


def alert_row(titulo: str, detalle: str, severidad: str = "azul", icono: str = "") -> str:
    """
    Retorna HTML para una fila de alerta.
    severidad: 'rojo', 'ambar', 'azul'
    icono: nombre de material icon (ej. 'warning', 'error', 'info')
    """
    icon_html = f'<span class="ccr-alert-icon material-symbols-outlined">{icono}</span>' if icono else ''
    return f'''
    <div class="ccr-alert-row ccr-alert-row--{severidad}">
        {icon_html}
        <div class="ccr-alert-content">
            <div class="ccr-alert-title">{html.escape(titulo)}</div>
            <div class="ccr-alert-detail">{html.escape(detalle)}</div>
        </div>
    </div>
    '''


def list_card(titulo: str, filas: list[dict], vacio_texto: str = "Sin datos") -> str:
    """
    Retorna HTML para una tarjeta con lista de filas.
    filas: lista de dicts con claves 'icono', 'titulo', 'detalle', 'derecha' (opcional)
    """
    if not filas:
        return f'''
        <div class="ccr-card">
            <div style="color: {COLORS["texto_secundario"]}; font-size: 13px; padding: 16px; text-align: center;">
                {html.escape(vacio_texto)}
            </div>
        </div>
        '''
    
    rows_html = []
    for i, fila in enumerate(filas):
        icono = fila.get("icono", "")
        icon_html = f'<span class="material-symbols-outlined" style="font-size: 18px; color: {COLORS["texto_secundario"]};">{icono}</span>' if icono else ''
        derecha = fila.get("derecha", "")
        derecha_html = f'<span style="margin-left: auto; color: {COLORS["texto_secundario"]}; font-size: 12px;">{html.escape(derecha)}</span>' if derecha else ''
        
        rows_html.append(f'''
        <div class="ccr-list-row">
            {icon_html}
            <div style="flex: 1; min-width: 0;">
                <div style="font-weight: 500; font-size: 13px;">{html.escape(fila["titulo"])}</div>
                {f'<div style="font-size: 12px; color: {COLORS["texto_secundario"]};">{html.escape(fila["detalle"])}</div>' if fila.get("detalle") else ''}
            </div>
            {derecha_html}
        </div>
        ''')
    
    return f'''
    <div class="ccr-card">
        <div class="ccr-card-header">
            <h4 class="ccr-card-title">{html.escape(titulo)}</h4>
        </div>
        <div>
            {"".join(rows_html)}
        </div>
    </div>
    '''


def empty_state(mensaje: str, accion_texto: str = "", accion_callback: str = "") -> str:
    """
    Retorna HTML para estado vacío con botón de acción opcional.
    """
    btn_html = ""
    if accion_texto and accion_callback:
        btn_html = f'''
        <button onclick="{accion_callback}" 
                style="margin-top: 12px; padding: 8px 16px; background: {COLORS["acento"]}; 
                       color: white; border: none; border-radius: 6px; font-weight: 500; cursor: pointer;">
            {html.escape(accion_texto)}
        </button>
        '''
    
    return f'''
    <div class="ccr-card" style="text-align: center; padding: 32px 16px;">
        <div style="font-size: 14px; color: {COLORS["texto_secundario"]}; margin-bottom: 12px;">
            {html.escape(mensaje)}
        </div>
        {btn_html}
    </div>
    '''


# ============================================================
# ICONOS SVG INLINE (outline, 1.5px stroke, sin relleno)
# ============================================================
def svg_icon(name: str, size: int = 16, color: str = COLORS["acento"]) -> str:
    """Retorna SVG inline para iconos outline."""
    icons = {
        "shield_check": '<path d="M12 1l9 4v6c0 5-3.5 9.5-9 11-5.5-1.5-9-6-9-11V5l9-4z"/><path d="M9 12l2 2 4-4"/>',
        "bell": '<path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v1.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 3H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z"/>',
        "sun": '<path d="M12 4.5V2m0 20v-2.5M4.95 4.95l1.77 1.77M17.66 17.66l1.77 1.77M3 12h2.5m13 0H18M4.95 19.05l1.77-1.77M17.66 6.34l1.77-1.77"/>',
        "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
        "lock": '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
        "clock_alert": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/><circle cx="18" cy="6" r="1"/>',
        "file_check": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8z"/><path d="M10 15l2 2 4-4"/>',
        "flag": '<path d="M4 15V4h2v11M8 4h6l-2 4H8V4zm8 0v11h2V4h-2z"/>',
    }
    
    path = icons.get(name, icons["shield_check"])
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'


# ============================================================
# ICONOS MATERIAL SYMBOLS (compatibilidad)
# ============================================================
ICONS = {
    "escudo": "shield",
    "campana": "notifications",
    "calendario": "calendar_month",
    "proceso": "settings",
    "subtarea": "subtasks",
    "dependencia": "account_tree",
    "sox": "security",
    "bitacora": "history",
    "aprobacion": "verified",
    "evidencia": "attach_file",
    "conocimiento": "menu_book",
    "alerta": "warning",
    "historico": "archive",
    "config": "settings",
    "masivo": "batch_prediction",
    "cronograma": "event",
    "usuario": "person",
    "email": "email",
    "adjunto": "paperclip",
    "check": "check_circle",
    "pendiente": "schedule",
    "bloqueado": "block",
    "vencido": "error",
    "en_proceso": "hourglass_top",
    "completado": "check_circle",
    "cancelado": "cancel",
    "flecha_abajo": "keyboard_arrow_down",
    "flecha_arriba": "keyboard_arrow_up",
    "editar": "edit",
    "eliminar": "delete",
    "mas": "add",
    "buscar": "search",
    "filtro": "filter_list",
    "descargar": "download",
    "subir": "upload",
    "enlace": "link",
    "copiar": "content_copy",
    "actualizar": "refresh",
}