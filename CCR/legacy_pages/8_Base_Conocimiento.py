"""
Base de Conocimiento - CCR
Gestión de enlaces por proceso (manuales, Teams, SharePoint, videos, etc.)
"""
import streamlit as st
from src.ui.theme import inject_css, ICONS, badge, list_card
from src.alerts.scheduler import ejecutar_scheduler
from src.database.db_manager import execute_query, execute_one, execute_insert, execute_update
from src.services.procesos_service import get_cierre_actual
from src.services.config_service import get_usuarios_activos


st.set_page_config(page_title="Base de Conocimiento - CCR", layout="wide")
inject_css()
ejecutar_scheduler()

cierre = get_cierre_actual()
if not cierre:
    st.warning("No hay cierre activo.")
    st.stop()

st.markdown(f"""
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
    <div style="display: flex; align-items: center; gap: 12px;">
        <span class="material-symbols-outlined" style="font-size: 28px; color: #185FA5;">{ICONS['conocimiento']}</span>
        <h1 style="margin: 0; font-size: 24px; font-weight: 500;">Base de Conocimiento</h1>
    </div>
    <div style="font-size: 13px; color: #5F5E5A;">Cierre: {cierre.nombre}</div>
</div>
""", unsafe_allow_html=True)

# Selector de proceso
procesos = execute_query("""
    SELECT pp.id, pp.nombre, pp.orden
    FROM procesos_plantilla pp
    WHERE pp.activo = 1
    ORDER BY pp.orden
""")

proceso_opciones = {f"{p['orden']}. {p['nombre']}": p['id'] for p in procesos}
proceso_seleccionado = st.selectbox(
    "Seleccionar proceso",
    options=[""] + list(proceso_opciones.keys()),
    key="conocimiento_proceso_select"
)

if not proceso_seleccionado:
    st.info("Seleccione un proceso para ver y gestionar sus enlaces.")
    st.stop()

proceso_id = proceso_opciones[proceso_seleccionado]

# Obtener enlaces existentes
enlaces = execute_query("""
    SELECT * FROM conocimiento
    WHERE proceso_plantilla_id = ? AND activo = 1
    ORDER BY tipo, titulo
""", (proceso_id,))

# Agrupar por tipo
tipos_orden = ["manual", "teams", "sharepoint", "video", "correo", "ruta", "otro"]
tipos_labels = {
    "manual": "📄 Manuales",
    "teams": "💬 Teams",
    "sharepoint": "📁 SharePoint",
    "video": "🎥 Videos",
    "correo": "📧 Correos de referencia",
    "ruta": "📂 Rutas operativas",
    "otro": "📎 Otros"
}

for tipo in tipos_orden:
    enlaces_tipo = [e for e in enlaces if e["tipo"] == tipo]
    label = tipos_labels.get(tipo, tipo.capitalize())
    
    with st.expander(f"{label} ({len(enlaces_tipo)})", expanded=len(enlaces_tipo) > 0):
        if not enlaces_tipo:
            st.caption(f"Sin enlaces de tipo {label.lower()}")
        else:
            for e in enlaces_tipo:
                cols = st.columns([1, 4, 1, 1])
                with cols[0]:
                    icon_map = {"manual": "menu_book", "teams": "chat", "sharepoint": "folder", 
                               "video": "videocam", "correo": "mail", "ruta": "folder_open", "otro": "link"}
                    st.markdown(f'<span class="material-symbols-outlined" style="color: #185FA5;">{icon_map.get(tipo, "link")}</span>', unsafe_allow_html=True)
                with cols[1]:
                    st.markdown(f"**{e['titulo']}**")
                    if e["descripcion"]:
                        st.caption(e["descripcion"])
                    # Mostrar URL/ruta como texto copiable
                    if e["url"].startswith(("http://", "https://")):
                        st.markdown(f'<a href="{e["url"]}" target="_blank" style="color: #185FA5; font-size: 12px;">{e["url"]}</a>', unsafe_allow_html=True)
                    else:
                        st.code(e["url"], language=None)
                with cols[2]:
                    if e["url"].startswith(("http://", "https://")):
                        if st.button(":material/open_in_new:", key=f"kn_open_{e['id']}", help="Abrir en nueva pestaña"):
                            st.markdown(f'<script>window.open("{e["url"]}", "_blank")</script>', unsafe_allow_html=True)
                with cols[3]:
                    if st.button(":material/delete:", key=f"kn_del_{e['id']}", help="Eliminar"):
                        execute_update("UPDATE conocimiento SET activo = 0 WHERE id = ?", (e["id"],))
                        st.rerun()

# --- NUEVO ENLACE ---
st.markdown("---")
with st.expander("➕ Agregar enlace", expanded=False):
    with st.form("conocimiento_nuevo_form"):
        c1, c2 = st.columns(2)
        with c1:
            tipo = st.selectbox("Tipo *", list(tipos_labels.keys()), format_func=lambda x: tipos_labels[x])
            titulo = st.text_input("Título *", placeholder="Ej: Manual de parametrización F394")
        with c2:
            url = st.text_input("URL / Ruta *", placeholder="https://... o \\\\servidor\\carpeta\\archivo")
            descripcion = st.text_area("Descripción")
        
        if st.form_submit_button("Guardar", type="primary"):
            if not titulo or not url:
                st.error("Título y URL son obligatorios")
            else:
                # Validar formato básico
                if not (url.startswith(("http://", "https://", "\\\\", "/", "C:\\", "D:\\"))):
                    st.warning("La URL/ruta no parece válida. Se guardará de todos modos.")
                
                execute_insert(
                    "INSERT INTO conocimiento (proceso_plantilla_id, tipo, titulo, url, descripcion) VALUES (?, ?, ?, ?, ?)",
                    (proceso_id, tipo, titulo, url, descripcion)
                )
                st.success("Enlace guardado.")
                st.rerun()