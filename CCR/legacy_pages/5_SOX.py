"""
Controles SOX - CCR
Gestión de controles SOX con submódulos.
"""
import streamlit as st
from datetime import date
from src.ui.theme import inject_css, ICONS, status_dot, badge, list_card
from src.alerts.scheduler import ejecutar_scheduler
from src.services.sox_service import (
    get_controles_sox_cierre, crear_control_sox, actualizar_control_sox, get_submodulos_sox
)
from src.services.procesos_service import get_cierre_actual
from src.services.config_service import get_estados_activos, get_usuarios_activos
from src.services.bitacoras_service import get_bitacoras_proceso, registrar_bitacora


st.set_page_config(page_title="Controles SOX - CCR", layout="wide")
inject_css()
ejecutar_scheduler()

cierre = get_cierre_actual()
if not cierre:
    st.warning("No hay cierre activo.")
    st.stop()

st.markdown(f"""
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
    <div style="display: flex; align-items: center; gap: 12px;">
        <span class="material-symbols-outlined" style="font-size: 28px; color: #185FA5;">{ICONS['sox']}</span>
        <h1 style="margin: 0; font-size: 24px; font-weight: 500;">Controles SOX</h1>
    </div>
    <div style="font-size: 13px; color: #5F5E5A;">Cierre: {cierre.nombre}</div>
</div>
""", unsafe_allow_html=True)

# Tabs por submódulo
submodulos = get_submodulos_sox()
tabs = st.tabs(["Todos"] + submodulos)

# --- TAB TODOS ---
with tabs[0]:
    col_f1, col_f2 = st.columns([2, 2])
    with col_f1:
        filtro_estado = st.selectbox("Estado", ["Todos"] + [e["nombre"] for e in get_estados_activos()], key="sox_filtro_estado")
    with col_f2:
        usuarios = get_usuarios_activos()
        filtro_resp = st.selectbox("Responsable", ["Todos"] + [u["nombre"] for u in usuarios], key="sox_filtro_resp")
    
    controles = get_controles_sox_cierre(cierre.id)
    
    if filtro_estado != "Todos":
        controles = [c for c in controles if c["estado_nombre"] == filtro_estado]
    if filtro_resp != "Todos":
        controles = [c for c in controles if c.get("responsable_nombre") == filtro_resp]
    
    if not controles:
        st.info("No hay controles SOX.")
    else:
        for c in controles:
            estado_mostrar = c.get("estado_calculado", c["estado_codigo"])
            color_estado = "#E24B4A" if c.get("vencido") else c["estado_color"]
            
            cols = st.columns([1, 3, 2, 1, 1, 1])
            with cols[0]:
                st.markdown(f'<span class="ccr-status-dot" style="background: {color_estado};"></span>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"**{c['nombre']}**")
                if c.get("descripcion"):
                    st.caption(c["descripcion"])
            with cols[2]:
                st.caption(f"Resp: {c.get('responsable_nombre', '—')}")
                if c["fecha_ejecucion"]:
                    st.caption(f"Fecha: {date.fromisoformat(c['fecha_ejecucion']).strftime('%d/%m/%Y')}")
            with cols[3]:
                st.markdown(badge(c["estado_nombre"], estado_mostrar), unsafe_allow_html=True)
            with cols[4]:
                if c.get("vencido"):
                    st.markdown('<span class="ccr-badge ccr-badge--rojo">VENCIDO</span>', unsafe_allow_html=True)
            with cols[5]:
                if st.button(":material/edit:", key=f"sox_edit_{c['id']}", help="Editar"):
                    st.session_state[f"sox_edit_{c['id']}"] = True
                    st.rerun()
            
            if st.session_state.get(f"sox_edit_{c['id']}"):
                with st.form(f"sox_form_{c['id']}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        nuevo_estado = st.selectbox("Estado", [e["nombre"] for e in get_estados_activos()],
                                                   index=[e["nombre"] for e in get_estados_activos()].index(c["estado_nombre"]))
                    with c2:
                        nueva_fecha = st.date_input("Fecha ejecución", 
                                                   value=date.fromisoformat(c["fecha_ejecucion"]) if c["fecha_ejecucion"] else None)
                    with c3:
                        nuevo_resp = st.selectbox("Responsable", [""] + [u["nombre"] for u in usuarios],
                                                 index=([""] + [u["nombre"] for u in usuarios]).index(c.get("responsable_nombre", "")) if c.get("responsable_nombre") else 0)
                    obs = st.text_area("Observaciones", value=c["observaciones"] or "")
                    
                    if st.form_submit_button("Guardar"):
                        estado_cod = next(e["codigo"] for e in get_estados_activos() if e["nombre"] == nuevo_estado)
                        resp_id = next((u["id"] for u in usuarios if u["nombre"] == nuevo_resp), None) if nuevo_resp else None
                        actualizar_control_sox(c["id"], estado_id=estado_cod, 
                                             fecha_ejecucion=nueva_fecha.isoformat() if nueva_fecha else None,
                                             responsable_id=resp_id, observaciones=obs)
                        st.session_state[f"sox_edit_{c['id']}"] = False
                        st.success("Actualizado")
                        st.rerun()

# --- TABS SUBMÓDULOS ---
for i, submodulo in enumerate(submodulos):
    with tabs[i + 1]:
        st.markdown(f"### {submodulo}")
        st.caption(f"Gestión de {submodulo.lower()} para el cierre {cierre.nombre}")
        
        # Placeholder para cada submódulo
        if submodulo == "Bitácoras SOX":
            st.info("Bitácoras específicas de SOX - Ver bitácora global en Procesos")
        elif submodulo == "Parametrización":
            st.info("Parametrización de modelos - Vincular a procesos correspondientes")
        elif submodulo == "Pantallazos":
            st.info("Capturas de ejecución - Ver módulo Evidencias")
        elif submodulo == "Conciliaciones":
            st.info("Conciliaciones contable-actuarial - Pendiente implementar")
        elif submodulo == "Validaciones":
            st.info("Validaciones de consistencia - Pendiente implementar")
        elif submodulo == "Aprobaciones SOX":
            st.info("Aprobaciones formales SOX - Ver módulo Aprobaciones")

# --- NUEVO CONTROL ---
st.markdown("---")
with st.expander("➕ Nuevo control SOX", expanded=False):
    with st.form("sox_nuevo_form"):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre *", placeholder="Ej: Parametrización RM Ley 100")
            descripcion = st.text_area("Descripción")
            responsable = st.selectbox("Responsable", [""] + [u["nombre"] for u in get_usuarios_activos()])
        with c2:
            fecha = st.date_input("Fecha ejecución", value=None)
            estado = st.selectbox("Estado", [e["nombre"] for e in get_estados_activos()])
            orden = st.number_input("Orden", min_value=0, value=len(get_controles_sox_cierre(cierre.id)) + 1)
        observaciones = st.text_area("Observaciones")
        
        if st.form_submit_button("Crear", type="primary"):
            if not nombre:
                st.error("Nombre es obligatorio")
            else:
                resp_id = next((u["id"] for u in get_usuarios_activos() if u["nombre"] == responsable), None) if responsable else None
                estado_cod = next(e["codigo"] for e in get_estados_activos() if e["nombre"] == estado)
                ok, msg = crear_control_sox(
                    cierre.id, nombre, descripcion, resp_id,
                    fecha.isoformat() if fecha else None, estado_cod, observaciones, orden
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)