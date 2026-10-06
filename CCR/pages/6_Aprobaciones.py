"""
Aprobaciones - CCR
Gestión de aprobaciones con tres estados: Técnico, Aprobación, SOX.
"""
import streamlit as st
from datetime import date
from src.ui.theme import inject_css, ICONS, status_dot, badge, list_card
from src.alerts.scheduler import ejecutar_scheduler
from src.services.aprobaciones_service import (
    get_aprobaciones_cierre, get_aprobacion_by_id, crear_aprobacion, 
    actualizar_aprobacion, puede_completar_reserva
)
from src.services.procesos_service import get_cierre_actual
from src.services.config_service import get_estados_activos, get_usuarios_activos
from src.services.bitacoras_service import registrar_bitacora


st.set_page_config(page_title="Aprobaciones - CCR", layout="wide")
inject_css()
ejecutar_scheduler()

cierre = get_cierre_actual()
if not cierre:
    st.warning("No hay cierre activo.")
    st.stop()

st.markdown(f"""
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
    <div style="display: flex; align-items: center; gap: 12px;">
        <span class="material-symbols-outlined" style="font-size: 28px; color: #185FA5;">{ICONS['aprobacion']}</span>
        <h1 style="margin: 0; font-size: 24px; font-weight: 500;">Aprobaciones</h1>
    </div>
    <div style="font-size: 13px; color: #5F5E5A;">Cierre: {cierre.nombre}</div>
</div>
""", unsafe_allow_html=True)

# Filtros
col_f1, col_f2 = st.columns([2, 2])
with col_f1:
    filtro_estado = st.selectbox("Estado general", ["Todas", "Pendientes", "Completadas"], key="ap_filtro_estado")
with col_f2:
    usuarios = get_usuarios_activos()
    filtro_resp = st.selectbox("Responsable", ["Todos"] + [u["nombre"] for u in usuarios], key="ap_filtro_resp")

aprobaciones = get_aprobaciones_cierre(cierre.id)

if filtro_estado == "Pendientes":
    aprobaciones = [a for a in aprobaciones if not a["completada_totalmente"]]
elif filtro_estado == "Completadas":
    aprobaciones = [a for a in aprobaciones if a["completada_totalmente"]]
if filtro_resp != "Todos":
    aprobaciones = [a for a in aprobaciones if a.get("responsable_nombre") == filtro_resp]

if not aprobaciones:
    st.info("No hay aprobaciones.")
else:
    for a in aprobaciones:
        # Determinar color general
        if a["completada_totalmente"]:
            color_general = "#639922"
            estado_general = "Completada"
        else:
            # Verificar cuál estado está pendiente
            pendientes = []
            if a["estado_tecnico_codigo"] != "completado":
                pendientes.append("Técnico")
            if a["estado_aprobacion_codigo"] != "completado":
                pendientes.append("Aprobación")
            if a["estado_sox_codigo"] != "completado":
                pendientes.append("SOX")
            estado_general = f"Pendiente: {', '.join(pendientes)}"
            color_general = "#EF9F27"
        
        cols = st.columns([1, 3, 1, 1, 1, 1, 1])
        with cols[0]:
            st.markdown(f'<span class="ccr-status-dot" style="background: {color_general};"></span>', unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f"**{a['nombre']}**")
            if a.get("proceso_nombre"):
                st.caption(f"Proceso: {a['proceso_nombre']}")
        with cols[2]:
            st.markdown(f'<div style="text-align: center;">{status_dot(a["estado_tecnico_codigo"])} <small>Técnico</small><br><strong>{a["estado_tecnico_nombre"]}</strong></div>', unsafe_allow_html=True)
        with cols[3]:
            st.markdown(f'<div style="text-align: center;">{status_dot(a["estado_aprobacion_codigo"])} <small>Aprobación</small><br><strong>{a["estado_aprobacion_nombre"]}</strong></div>', unsafe_allow_html=True)
        with cols[4]:
            st.markdown(f'<div style="text-align: center;">{status_dot(a["estado_sox_codigo"])} <small>SOX</small><br><strong>{a["estado_sox_nombre"]}</strong></div>', unsafe_allow_html=True)
        with cols[5]:
            st.caption(f"Resp: {a.get('responsable_nombre', '—')}")
            if a["fecha_envio"]:
                st.caption(f"Envío: {date.fromisoformat(a['fecha_envio']).strftime('%d/%m/%Y')}")
        with cols[6]:
            if st.button(":material/edit:", key=f"ap_edit_{a['id']}", help="Editar"):
                st.session_state[f"ap_edit_{a['id']}"] = True
                st.rerun()
        
        if st.session_state.get(f"ap_edit_{a['id']}"):
            with st.form(f"ap_form_{a['id']}"):
                st.markdown("**Estados:**")
                c1, c2, c3 = st.columns(3)
                with c1:
                    tec = st.selectbox("Estado Técnico", [e["nombre"] for e in get_estados_activos()],
                                      index=[e["nombre"] for e in get_estados_activos()].index(a["estado_tecnico_nombre"]))
                with c2:
                    apr = st.selectbox("Estado Aprobación", [e["nombre"] for e in get_estados_activos()],
                                      index=[e["nombre"] for e in get_estados_activos()].index(a["estado_aprobacion_nombre"]))
                with c3:
                    sox = st.selectbox("Estado SOX", [e["nombre"] for e in get_estados_activos()],
                                      index=[e["nombre"] for e in get_estados_activos()].index(a["estado_sox_nombre"]))
                
                c4, c5 = st.columns(2)
                with c4:
                    fecha_envio = st.date_input("Fecha envío", 
                                               value=date.fromisoformat(a["fecha_envio"]) if a["fecha_envio"] else None)
                with c5:
                    fecha_aprob = st.date_input("Fecha aprobación", 
                                               value=date.fromisoformat(a["fecha_aprobacion"]) if a["fecha_aprobacion"] else None)
                
                obs = st.text_area("Observaciones", value=a["observaciones"] or "")
                
                if st.form_submit_button("Guardar"):
                    tec_cod = next(e["codigo"] for e in get_estados_activos() if e["nombre"] == tec)
                    apr_cod = next(e["codigo"] for e in get_estados_activos() if e["nombre"] == apr)
                    sox_cod = next(e["codigo"] for e in get_estados_activos() if e["nombre"] == sox)
                    
                    actualizar_aprobacion(a["id"],
                        estado_tecnico_id=next(e["id"] for e in get_estados_activos() if e["codigo"] == tec_cod),
                        estado_aprobacion_id=next(e["id"] for e in get_estados_activos() if e["codigo"] == apr_cod),
                        estado_sox_id=next(e["id"] for e in get_estados_activos() if e["codigo"] == sox_cod),
                        fecha_envio=fecha_envio.isoformat() if fecha_envio else None,
                        fecha_aprobacion=fecha_aprob.isoformat() if fecha_aprob else None,
                        observaciones=obs
                    )
                    st.session_state[f"ap_edit_{a['id']}"] = False
                    st.success("Actualizado")
                    st.rerun()
                
                # Mostrar si puede completar reserva
                if puede_completar_reserva(a["id"]):
                    st.success("✅ Los tres estados están completados. La reserva puede pasar a Completado.")

# --- NUEVA APROBACIÓN ---
st.markdown("---")
with st.expander("➕ Nueva aprobación", expanded=False):
    with st.form("ap_nuevo_form"):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre *", placeholder="Ej: Aprobación RM Ley 100 - Octubre 2026")
            proceso = st.selectbox("Proceso asociado", [""] + [f"{p['orden']}. {p['nombre']}" for p in get_aprobaciones_cierre(cierre.id)], key="ap_proceso_select")
            responsable = st.selectbox("Responsable", [""] + [u["nombre"] for u in usuarios])
        with c2:
            st.markdown("**Estados iniciales:**")
            tec = st.selectbox("Estado Técnico", [e["nombre"] for e in get_estados_activos()], key="ap_nuevo_tec")
            apr = st.selectbox("Estado Aprobación", [e["nombre"] for e in get_estados_activos()], key="ap_nuevo_apr")
            sox = st.selectbox("Estado SOX", [e["nombre"] for e in get_estados_activos()], key="ap_nuevo_sox")
        observaciones = st.text_area("Observaciones")
        
        if st.form_submit_button("Crear", type="primary"):
            if not nombre:
                st.error("Nombre es obligatorio")
            else:
                proceso_id = None
                if proceso:
                    proceso_id = int(proceso.split(".")[0])
                    # Buscar ID real
                    from src.services.procesos_service import get_procesos_cierre
                    procs = get_procesos_cierre(cierre.id)
                    if proceso_id <= len(procs):
                        proceso_id = procs[proceso_id - 1]["id"]
                
                resp_id = next((u["id"] for u in usuarios if u["nombre"] == responsable), None) if responsable else None
                tec_cod = next(e["codigo"] for e in get_estados_activos() if e["nombre"] == tec)
                apr_cod = next(e["codigo"] for e in get_estados_activos() if e["nombre"] == apr)
                sox_cod = next(e["codigo"] for e in get_estados_activos() if e["nombre"] == sox)
                
                ok, msg = crear_aprobacion(
                    cierre.id, nombre, proceso_id, resp_id,
                    tec_cod, apr_cod, sox_cod, observaciones
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)