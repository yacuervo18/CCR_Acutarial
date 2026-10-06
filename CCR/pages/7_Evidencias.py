"""
Evidencias - CCR
Gestión de archivos y enlaces como evidencias.
"""
import streamlit as st
from datetime import date
from src.ui.theme import inject_css, ICONS, status_dot, badge, list_card
from src.alerts.scheduler import ejecutar_scheduler
from src.services.evidencias_service import (
    get_evidencias_filtros, get_evidencias_entidad, guardar_archivo_evidencia,
    registrar_enlace_evidencia, eliminar_evidencia, get_ruta_absoluta_evidencia
)
from src.services.config_service import get_tipos_evidencia_activos, get_usuarios_activos
from src.services.procesos_service import get_cierre_actual, get_procesos_cierre


st.set_page_config(page_title="Evidencias - CCR", layout="wide")
inject_css()
ejecutar_scheduler()

cierre = get_cierre_actual()
if not cierre:
    st.warning("No hay cierre activo.")
    st.stop()

st.markdown(f"""
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
    <div style="display: flex; align-items: center; gap: 12px;">
        <span class="material-symbols-outlined" style="font-size: 28px; color: #185FA5;">{ICONS['evidencia']}</span>
        <h1 style="margin: 0; font-size: 24px; font-weight: 500;">Evidencias</h1>
    </div>
    <div style="font-size: 13px; color: #5F5E5A;">Cierre: {cierre.nombre}</div>
</div>
""", unsafe_allow_html=True)

# Tabs
tab_lista, tab_subir, tab_enlace = st.tabs(["Lista", "Subir archivo", "Registrar enlace"])

# --- TAB LISTA ---
with tab_lista:
    col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 2])
    with col_f1:
        tipos = get_tipos_evidencia_activos()
        filtro_tipo = st.selectbox("Tipo", ["Todos"] + [t["nombre"] for t in tipos], key="ev_filtro_tipo")
    with col_f2:
        filtro_entidad = st.selectbox("Entidad", ["Todas", "Proceso", "Subtarea", "Control SOX", "Aprobación"], key="ev_filtro_entidad")
    with col_f3:
        procesos = get_procesos_cierre(cierre.id)
        filtro_proceso = st.selectbox("Proceso", ["Todos"] + [f"{p['orden']}. {p['nombre']}" for p in procesos], key="ev_filtro_proceso")
    with col_f4:
        col_a, col_m = st.columns(2)
        with col_a:
            filtro_año = st.number_input("Año", min_value=2020, max_value=2030, value=date.today().year, key="ev_filtro_año")
        with col_m:
            filtro_mes = st.number_input("Mes", min_value=1, max_value=12, value=date.today().month, key="ev_filtro_mes")
    
    # Construir filtros
    tipo_id = None
    if filtro_tipo != "Todos":
        tipo_id = next(t["id"] for t in tipos if t["nombre"] == filtro_tipo)
    
    entidad_tipo = None
    if filtro_entidad != "Todas":
        entidad_tipo = filtro_entidad.lower().replace(" ", "_")
    
    proceso_id = None
    if filtro_proceso != "Todos":
        idx = int(filtro_proceso.split(".")[0]) - 1
        if 0 <= idx < len(procesos):
            proceso_id = procesos[idx]["id"]
    
    evidencias = get_evidencias_filtros(
        tipo_evidencia_id=tipo_id,
        entidad_tipo=entidad_tipo,
        proceso_id=proceso_id,
        año=filtro_año,
        mes=filtro_mes
    )
    
    if not evidencias:
        st.info("No hay evidencias con los filtros actuales.")
    else:
        for ev in evidencias:
            cols = st.columns([1, 3, 1, 1, 1, 1, 1])
            with cols[0]:
                icon_map = {"pdf": "picture_as_pdf", "excel": "table_chart", "correo": "mail", "imagen": "image", "captura": "screenshot_monitor", "enlace": "link"}
                icon = icon_map.get(ev["tipo_codigo"], "attach_file")
                st.markdown(f'<span class="material-symbols-outlined" style="font-size: 24px; color: #185FA5;">{icon}</span>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"**{ev['nombre_original']}**")
                st.caption(f"{ev['entidad_tipo']} #{ev['entidad_id']} · {ev['subido_por']}")
            with cols[2]:
                st.caption(f"{(ev['tamaño_bytes']/1024):.1f} KB" if ev['tamaño_bytes'] > 0 else "Enlace")
            with cols[3]:
                st.caption(ev['subido_en'][:16].replace('T', ' '))
            with cols[4]:
                st.markdown(badge(ev['tipo_nombre'], ev['tipo_codigo']), unsafe_allow_html=True)
            with cols[5]:
                if ev["es_enlace"]:
                    if st.button(":material/open_in_new:", key=f"ev_open_{ev['id']}", help="Abrir enlace"):
                        st.markdown(f'<script>window.open("{ev["enlace_url"]}", "_blank")</script>', unsafe_allow_html=True)
                else:
                    if st.button(":material/download:", key=f"ev_dl_{ev['id']}", help="Descargar"):
                        ruta = get_ruta_absoluta_evidencia(ev)
                        if ruta.exists():
                            with open(ruta, "rb") as f:
                                st.download_button(
                                    "Descargar", f.read(), file_name=ev["nombre_original"],
                                    key=f"dl_btn_{ev['id']}", use_container_width=True
                                )
                        else:
                            st.error("Archivo no encontrado en disco")
            with cols[6]:
                if st.button(":material/delete:", key=f"ev_del_{ev['id']}", help="Eliminar"):
                    ok, msg = eliminar_evidencia(ev["id"])
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

# --- TAB SUBIR ARCHIVO ---
with tab_subir:
    st.markdown("### Subir archivo como evidencia")
    
    with st.form("ev_subir_form"):
        c1, c2 = st.columns(2)
        with c1:
            entidad_tipo = st.selectbox("Tipo de entidad *", ["Proceso", "Subtarea", "Control SOX", "Aprobación"])
            if entidad_tipo == "Proceso":
                entidad_opciones = {f"{p['orden']}. {p['nombre']}": p['id'] for p in procesos}
                entidad_sel = st.selectbox("Entidad *", options=list(entidad_opciones.keys()))
                entidad_id = entidad_opciones[entidad_sel] if entidad_sel else None
            else:
                st.caption("Selección de subtareas/controles/aprobaciones pendiente")
                entidad_id = st.number_input("ID entidad *", min_value=1, value=1)
            
            tipo_ev = st.selectbox("Tipo de evidencia *", [t["nombre"] for t in tipos])
        with c2:
            archivo = st.file_uploader("Archivo *", type=["pdf", "xlsx", "xls", "csv", "msg", "eml", "png", "jpg", "jpeg", "bmp"])
            descripcion = st.text_area("Descripción")
            subido_por = st.selectbox("Subido por", [u["nombre"] for u in get_usuarios_activos()])
        
        if st.form_submit_button("Subir", type="primary"):
            if not archivo or not entidad_id:
                st.error("Archivo y entidad son obligatorios")
            else:
                tipo_id = next(t["id"] for t in tipos if t["nombre"] == tipo_ev)
                ok, msg, ev = guardar_archivo_evidencia(
                    archivo.getvalue(), archivo.name, tipo_id,
                    entidad_tipo.lower(), entidad_id, subido_por, descripcion
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

# --- TAB REGISTRAR ENLACE ---
with tab_enlace:
    st.markdown("### Registrar enlace o ruta de red como evidencia")
    
    with st.form("ev_enlace_form"):
        c1, c2 = st.columns(2)
        with c1:
            entidad_tipo = st.selectbox("Tipo de entidad *", ["Proceso", "Subtarea", "Control SOX", "Aprobación"], key="ev_enlace_entidad")
            if entidad_tipo == "Proceso":
                entidad_opciones = {f"{p['orden']}. {p['nombre']}": p['id'] for p in procesos}
                entidad_sel = st.selectbox("Entidad *", options=list(entidad_opciones.keys()), key="ev_enlace_entidad_sel")
                entidad_id = entidad_opciones[entidad_sel] if entidad_sel else None
            else:
                entidad_id = st.number_input("ID entidad *", min_value=1, value=1, key="ev_enlace_id")
            
            tipo_ev = st.selectbox("Tipo de evidencia *", [t["nombre"] for t in tipos], key="ev_enlace_tipo")
        with c2:
            url = st.text_input("URL / Ruta de red *", placeholder="https://... o \\\\servidor\\carpeta\\archivo")
            nombre = st.text_input("Nombre para mostrar", placeholder="Opcional, se usa la URL si vacío")
            descripcion = st.text_area("Descripción", key="ev_enlace_desc")
            subido_por = st.selectbox("Registrado por", [u["nombre"] for u in get_usuarios_activos()], key="ev_enlace_user")
        
        if st.form_submit_button("Registrar", type="primary"):
            if not url or not entidad_id:
                st.error("URL y entidad son obligatorios")
            else:
                tipo_id = next(t["id"] for t in tipos if t["nombre"] == tipo_ev)
                ok, msg, ev = registrar_enlace_evidencia(
                    url, tipo_id, entidad_tipo.lower(), entidad_id, subido_por, descripcion, nombre or url
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)