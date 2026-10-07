"""
Cronograma Operativo - CCR
Vista calendario con streamlit-calendar.
"""
import streamlit as st
from datetime import date, datetime, timedelta
from src.ui.theme import inject_css, ICONS, COLORS
from src.alerts.scheduler import ejecutar_scheduler
from src.services.procesos_service import get_cierre_actual, get_procesos_cierre
from src.services.procesos_masivos_service import get_procesos_masivos
from src.services.sox_service import get_controles_sox_cierre
from src.services.config_service import get_usuarios_activos


st.set_page_config(page_title="Cronograma - CCR", layout="wide")
inject_css()
ejecutar_scheduler()

cierre = get_cierre_actual()
if not cierre:
    st.warning("No hay cierre activo.")
    st.stop()

st.markdown(f"""
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
    <div style="display: flex; align-items: center; gap: 12px;">
        <span class="material-symbols-outlined" style="font-size: 28px; color: #185FA5;">{ICONS['cronograma']}</span>
        <h1 style="margin: 0; font-size: 24px; font-weight: 500;">Cronograma Operativo</h1>
    </div>
    <div style="font-size: 13px; color: #5F5E5A;">Cierre: {cierre.nombre}</div>
</div>
""", unsafe_allow_html=True)

# Filtros
col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
with col_f1:
    vista = st.selectbox("Vista", ["Mensual", "Semanal", "Diaria"], key="cal_vista")
with col_f2:
    usuarios = get_usuarios_activos()
    filtro_usuario = st.selectbox("Responsable", ["Todos"] + [u["nombre"] for u in usuarios], key="cal_usuario")
with col_f3:
    tipos = ["Todos", "Proceso", "Subtarea", "Vencimiento", "Masivo", "SOX"]
    filtro_tipo = st.selectbox("Tipo", tipos, key="cal_tipo")

# Preparar eventos para el calendario
eventos = []

# Procesos
procesos = get_procesos_cierre(cierre.id)
for p in procesos:
    if filtro_usuario != "Todos" and p.get("responsable_nombre") != filtro_usuario:
        continue
    if filtro_tipo != "Todos" and filtro_tipo != "Proceso":
        continue
    
    if p["fecha_limite"]:
        try:
            fecha = date.fromisoformat(p["fecha_limite"])
            eventos.append({
                "title": f"📋 {p['nombre']}",
                "start": fecha.isoformat(),
                "end": (fecha + timedelta(days=1)).isoformat(),
                "color": p["estado_color"],
                "extendedProps": {
                    "tipo": "Proceso",
                    "estado": p["estado_nombre"],
                    "responsable": p.get("responsable_nombre", ""),
                    "detalle": f"Fecha límite: {fecha.strftime('%d/%m/%Y')}"
                }
            })
        except:
            pass

# Procesos masivos
masivos = get_procesos_masivos()
for m in masivos:
    if filtro_usuario != "Todos":
        continue  # Masivos no tienen responsable asignado en este modelo
    if filtro_tipo != "Todos" and filtro_tipo != "Masivo":
        continue
    
    try:
        fecha = date.fromisoformat(m["fecha_ejecucion"])
        eventos.append({
            "title": f"⚙️ {m['codigo']} - {m['nombre']}",
            "start": fecha.isoformat(),
            "end": (fecha + timedelta(days=1)).isoformat(),
            "color": m["estado_color"],
            "extendedProps": {
                "tipo": "Masivo",
                "estado": m["estado_nombre"],
                "ramo": m.get("ramo", ""),
                "detalle": f"Ramo: {m.get('ramo', 'N/A')}"
            }
        })
    except:
        pass

# Controles SOX
controles = get_controles_sox_cierre(cierre.id)
for c in controles:
    if filtro_usuario != "Todos" and c.get("responsable_nombre") != filtro_usuario:
        continue
    if filtro_tipo != "Todos" and filtro_tipo != "SOX":
        continue
    
    if c["fecha_ejecucion"]:
        try:
            fecha = date.fromisoformat(c["fecha_ejecucion"])
            color = "#E24B4A" if c.get("vencido") else c["estado_color"]
            eventos.append({
                "title": f"🔒 {c['nombre']}",
                "start": fecha.isoformat(),
                "end": (fecha + timedelta(days=1)).isoformat(),
                "color": color,
                "extendedProps": {
                    "tipo": "SOX",
                    "estado": c["estado_nombre"],
                    "responsable": c.get("responsable_nombre", ""),
                    "detalle": f"SOX - {c.get('estado_calculado', c['estado_nombre'])}"
                }
            })
        except:
            pass

# Renderizar calendario
try:
    from streamlit_calendar import calendar
    
    calendar_options = {
        "initialView": "dayGridMonth" if vista == "Mensual" else ("timeGridWeek" if vista == "Semanal" else "timeGridDay"),
        "locale": "es",
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay"
        },
        "height": 600,
        "eventClick": "function(info) { alert(info.event.title + ': ' + info.event.extendedProps.detalle); }"
    }
    
    calendar(events=eventos, options=calendar_options, key="calendario_ccr")
    
except ImportError:
    st.error("streamlit-calendar no está instalado. Ejecute: pip install streamlit-calendar")
except Exception as e:
    st.error(f"Error renderizando calendario: {e}")

# Leyenda
st.markdown("---")
st.markdown("**Leyenda:**")
cols = st.columns(6)
leyenda_items = [
    ("📋 Procesos", "#185FA5"),
    ("⚙️ Masivos", "#EF9F27"),
    ("🔒 SOX", "#E24B4A"),
    ("✅ Completado", "#639922"),
    ("⏳ En proceso", "#EF9F27"),
    ("⚠️ Vencido", "#E24B4A"),
]
for i, (label, color) in enumerate(leyenda_items):
    with cols[i]:
        st.markdown(f'<div style="display: flex; align-items: center; gap: 6px;"><span style="width: 12px; height: 12px; border-radius: 3px; background: {color};"></span><small>{label}</small></div>', unsafe_allow_html=True)