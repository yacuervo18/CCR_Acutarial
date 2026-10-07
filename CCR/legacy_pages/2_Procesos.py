"""
Gestión de Procesos - CCR
Lista de procesos con filtros, detalle con subtareas, dependencias y bitácora.
"""
import streamlit as st
from datetime import date
from src.ui.theme import inject_css, status_dot, badge, priority_badge, list_card, ICONS
from src.alerts.scheduler import ejecutar_scheduler
from src.services.procesos_service import (
    get_cierre_actual, get_procesos_cierre, get_proceso_by_id, 
    get_subtareas_proceso, get_dependencias_proceso, get_estados, get_prioridades,
    actualizar_proceso, actualizar_subtarea, completar_subtarea,
    agregar_dependencia, detectar_ciclo_dependencias
)
from src.services.bitacoras_service import get_bitacoras_proceso, registrar_bitacora
from src.services.config_service import get_config, get_usuarios_activos


# Configuración
st.set_page_config(page_title="Procesos - CCR", layout="wide")
inject_css()
ejecutar_scheduler()

cierre = get_cierre_actual()
if not cierre:
    st.warning("No hay cierre activo. Vaya al Dashboard para crear uno.")
    st.stop()

# ============================================================
# HEADER
# ============================================================
st.markdown(f"""
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
    <div style="display: flex; align-items: center; gap: 12px;">
        <span class="material-symbols-outlined" style="font-size: 28px; color: #185FA5;">{ICONS['proceso']}</span>
        <h1 style="margin: 0; font-size: 24px; font-weight: 500;">Gestión de Procesos</h1>
    </div>
    <div style="font-size: 13px; color: #5F5E5A;">Cierre: {cierre.nombre}</div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# FILTROS
# ============================================================
estados = get_estados()
prioridades = get_prioridades()
usuarios = get_usuarios_activos()

col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 1])
with col_f1:
    filtro_estado = st.selectbox(
        "Estado", ["Todos"] + [e.nombre for e in estados],
        format_func=lambda x: x, key="filtro_estado_procesos"
    )
with col_f2:
    filtro_prioridad = st.selectbox(
        "Prioridad", ["Todas"] + [p.nombre for p in prioridades],
        key="filtro_prioridad_procesos"
    )
with col_f3:
    filtro_responsable = st.selectbox(
        "Responsable", ["Todos"] + [u["nombre"] for u in usuarios],
        key="filtro_responsable_procesos"
    )
with col_f4:
    if st.button(":material/refresh: Refrescar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ============================================================
# OBTENER PROCESOS FILTRADOS
# ============================================================
procesos = get_procesos_cierre(cierre.id)

# Aplicar filtros
if filtro_estado != "Todos":
    procesos = [p for p in procesos if p["estado_nombre"] == filtro_estado]
if filtro_prioridad != "Todas":
    procesos = [p for p in procesos if p["prioridad_nombre"] == filtro_prioridad]
if filtro_responsable != "Todos":
    procesos = [p for p in procesos if p.get("responsable_nombre") == filtro_responsable]

# ============================================================
# LISTA DE PROCESOS
# ============================================================
if not procesos:
    st.info("No hay procesos que coincidan con los filtros.")
else:
    # Encabezados de tabla
    st.markdown("""
    <div class="ccr-list-row" style="font-weight: 500; color: #5F5E5A; border-top: none; background: #F5F5F3; border-radius: 8px 8px 0 0; padding: 10px 0;">
        <div style="width: 40px;"></div>
        <div style="flex: 2;">Proceso</div>
        <div style="flex: 1;">Responsable</div>
        <div style="flex: 1;">Fecha límite</div>
        <div style="flex: 1;">Prioridad</div>
        <div style="flex: 1;">Estado</div>
        <div style="flex: 1;">Avance</div>
    </div>
    """, unsafe_allow_html=True)
    
    for i, proc in enumerate(procesos):
        # Determinar clase de fila
        row_class = "ccr-list-row"
        if proc["bloqueado"]:
            row_class += " ccr-list-row--hover"
        
        # Avance subtareas
        total = proc["total_subtareas"]
        completadas = proc["subtareas_completadas"]
        avance_txt = f"{completadas}/{total}" if total > 0 else "—"
        avance_pct = f"{round(completadas/total*100)}%" if total > 0 else ""
        
        # Fecha límite formateada
        fecha_lim = proc["fecha_limite"]
        if fecha_lim:
            try:
                fecha_fmt = date.fromisoformat(fecha_lim).strftime("%d/%m/%Y")
                # Marcar en rojo si vencida
                hoy = date.today()
                if date.fromisoformat(fecha_lim) < hoy and proc["estado_codigo"] not in ("completado", "cancelado"):
                    fecha_fmt = f'<span style="color: #E24B4A; font-weight: 500;">{fecha_fmt} ⚠</span>'
            except:
                fecha_fmt = fecha_lim
        else:
            fecha_fmt = "—"
        
        # Estado con punto
        estado_html = f'{status_dot(proc["estado_codigo"])} {proc["estado_nombre"]}'
        if proc["bloqueado"]:
            estado_html += f' <span class="ccr-badge ccr-badge--gris" title="{proc["motivo_bloqueo"]}">Bloqueado</span>'
        
        st.markdown(f"""
        <div class="{row_class}" style="cursor: pointer;" onclick="window.parent.postMessage({{type: 'streamlit:setComponentValue', key: 'proceso_seleccionado', value: {proc['id']}}}, '*')">
            <div style="width: 40px; text-align: center;">{proc['orden']}</div>
            <div style="flex: 2; font-weight: 500;">{proc['nombre']}</div>
            <div style="flex: 1;">{proc.get('responsable_nombre', '—')}</div>
            <div style="flex: 1;">{fecha_fmt}</div>
            <div style="flex: 1;">{priority_badge(proc['prioridad_codigo'])}</div>
            <div style="flex: 1;">{estado_html}</div>
            <div style="flex: 1; font-size: 12px; color: #5F5E5A;">{avance_txt} {avance_pct}</div>
        </div>
        """, unsafe_allow_html=True)

# ============================================================
# DETALLE DE PROCESO SELECCIONADO
# ============================================================
st.markdown("---")

# Selector de proceso para detalle
proceso_opciones = {f"{p['orden']}. {p['nombre']}": p['id'] for p in get_procesos_cierre(cierre.id)}
proceso_seleccionado_nombre = st.selectbox(
    "Seleccionar proceso para ver detalle",
    options=[""] + list(proceso_opciones.keys()),
    key="selector_proceso_detalle"
)

if proceso_seleccionado_nombre:
    proceso_id = proceso_opciones[proceso_seleccionado_nombre]
    proc = get_proceso_by_id(proceso_id)
    
    if proc:
        st.markdown(f"""
        <div class="ccr-card">
            <div class="ccr-card-header">
                <h3 class="ccr-card-title">{proc['nombre']}</h3>
                <div style="display: flex; gap: 8px; align-items: center;">
                    {priority_badge(proc['prioridad_codigo'])}
                    {status_dot(proc['estado_codigo'])} <strong>{proc['estado_nombre']}</strong>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-top: 12px; font-size: 13px;">
                <div><strong>Responsable:</strong> {proc.get('responsable_nombre', '—')}</div>
                <div><strong>Fecha planeada:</strong> {date.fromisoformat(proc['fecha_planeada']).strftime('%d/%m/%Y') if proc['fecha_planeada'] else '—'}</div>
                <div><strong>Fecha límite:</strong> {date.fromisoformat(proc['fecha_limite']).strftime('%d/%m/%Y') if proc['fecha_limite'] else '—'}</div>
                <div><strong>Prioridad:</strong> {proc['prioridad_nombre']}</div>
            </div>
            {f'<div style="margin-top: 12px; padding: 8px; background: #F5F5F3; border-radius: 6px; font-size: 13px;"><strong>Observaciones:</strong> {proc["observaciones"]}</div>' if proc.get('observaciones') else ''}
        </div>
        """, unsafe_allow_html=True)
        
        if proc["bloqueado"]:
            st.markdown(f"""
            <div class="ccr-alert-row ccr-alert-row--ambar" style="margin-top: 12px;">
                <span class="material-symbols-outlined ccr-alert-icon">block</span>
                <div class="ccr-alert-content">
                    <div class="ccr-alert-title">Proceso bloqueado</div>
                    <div class="ccr-alert-detail">{proc['motivo_bloqueo']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Tabs para Subtareas, Dependencias, Bitácora
        tab_sub, tab_dep, tab_bit = st.tabs(["Subtareas", "Dependencias", "Bitácora"])
        
        # --- SUBTAREAS ---
        with tab_sub:
            subtareas = get_subtareas_proceso(proceso_id)
            
            if not subtareas:
                st.info("Este proceso no tiene subtareas definidas.")
            else:
                for st_row in subtareas:
                    cols = st.columns([1, 4, 2, 2, 1])
                    
                    # Checkbox completada
                    with cols[0]:
                        checked = st.checkbox(
                            "", value=bool(st_row["completada"]), 
                            key=f"sub_completada_{st_row['id']}",
                            label_visibility="collapsed"
                        )
                        if checked != bool(st_row["completada"]):
                            if checked:
                                completar_subtarea(st_row["id"], "")
                            else:
                                actualizar_subtarea(st_row["id"], completada=0, fecha_ejecucion=None)
                            st.rerun()
                    
                    # Nombre y descripción
                    with cols[1]:
                        estilo = "text-decoration: line-through; color: #888780;" if st_row["completada"] else ""
                        st.markdown(f"""
                        <div style="{estilo}">
                            <strong>{st_row['nombre']}</strong>
                            {f'<br><small style="color: #5F5E5A;">{st_row["descripcion"]}</small>' if st_row.get('descripcion') else ''}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Fecha ejecución
                    with cols[2]:
                        fecha_ejec = st_row["fecha_ejecucion"]
                        if fecha_ejec:
                            st.caption(f"Ejecutada: {date.fromisoformat(fecha_ejec).strftime('%d/%m/%Y')}")
                        else:
                            nueva_fecha = st.date_input(
                                "Fecha", value=None, key=f"sub_fecha_{st_row['id']}",
                                label_visibility="collapsed"
                            )
                            if nueva_fecha:
                                actualizar_subtarea(st_row["id"], fecha_ejecucion=nueva_fecha.isoformat())
                                st.rerun()
                    
                    # Observaciones
                    with cols[3]:
                        obs = st.text_input(
                            "Obs.", value=st_row.get("observaciones", "") or "",
                            key=f"sub_obs_{st_row['id']}", label_visibility="collapsed",
                            placeholder="Observaciones..."
                        )
                        if obs != (st_row.get("observaciones") or ""):
                            actualizar_subtarea(st_row["id"], observaciones=obs)
                    
                    # Evidencias (placeholder)
                    with cols[4]:
                        if st.button(":material/attach_file:", key=f"sub_ev_{st_row['id']}", help="Evidencias"):
                            st.info("Evidencias - pendiente implementar")
        
        # --- DEPENDENCIAS ---
        with tab_dep:
            st.markdown("**Predecesoras (este proceso depende de):**")
            deps = get_dependencias_proceso(proceso_id)
            
            if not deps:
                st.caption("Sin dependencias configuradas.")
            else:
                for dep in deps:
                    estado_dep = dep["predecesora_estado_codigo"]
                    cols = st.columns([1, 4, 2, 1])
                    with cols[0]:
                        st.markdown(status_dot(estado_dep), unsafe_allow_html=True)
                    with cols[1]:
                        st.markdown(f"**{dep['predecesora_nombre']}**")
                    with cols[2]:
                        st.caption(f"Estado: {estado_dep.replace('_', ' ').title()}")
                    with cols[3]:
                        if st.button(":material/delete:", key=f"del_dep_{dep['predecesora_id']}", help="Eliminar dependencia"):
                            from src.database.db_manager import execute_update
                            execute_update(
                                "DELETE FROM dependencias WHERE proceso_id = ? AND predecesora_id = ?",
                                (proceso_id, dep["predecesora_id"])
                            )
                            st.rerun()
            
            st.markdown("---")
            st.markdown("**Agregar dependencia:**")
            # Procesos disponibles como predecesoras (excluir este y sus descendientes)
            disponibles = [p for p in get_procesos_cierre(cierre.id) if p["id"] != proceso_id]
            dep_opciones = {f"{p['orden']}. {p['nombre']}": p['id'] for p in disponibles}
            
            col_d1, col_d2 = st.columns([3, 1])
            with col_d1:
                nueva_dep_nombre = st.selectbox("Proceso predecesor", options=[""] + list(dep_opciones.keys()), key="nueva_dep_select")
            with col_d2:
                if st.button("Agregar", key="btn_agregar_dep", use_container_width=True):
                    if nueva_dep_nombre:
                        nueva_dep_id = dep_opciones[nueva_dep_nombre]
                        if detectar_ciclo_dependencias(proceso_id, nueva_dep_id):
                            st.error("Esta dependencia crearía un ciclo.")
                        else:
                            ok, msg = agregar_dependencia(proceso_id, nueva_dep_id)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)
        
        # --- BITÁCORA ---
        with tab_bit:
            bitacoras = get_bitacoras_proceso(proceso_id)
            
            if not bitacoras:
                st.caption("Sin entradas en bitácora.")
            else:
                for b in bitacoras:
                    fecha_fmt = datetime.fromisoformat(b["fecha"]).strftime("%d/%m/%Y %H:%M") if b["fecha"] else ""
                    st.markdown(f"""
                    <div class="ccr-list-row">
                        <span class="material-symbols-outlined" style="color: #5F5E5A;">{ICONS['bitacora']}</span>
                        <div style="flex: 1;">
                            <div style="font-weight: 500;">{b['comentario']}</div>
                            <div style="font-size: 11px; color: #888780;">{b['usuario']} · {fecha_fmt}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Agregar entrada
            st.markdown("---")
            nuevo_comentario = st.text_area("Nueva entrada", key="nueva_bitacora", placeholder="Registrar actividad...")
            if st.button("Guardar en bitácora", key="btn_guardar_bitacora"):
                if nuevo_comentario.strip():
                    registrar_bitacora(
                        get_config("usuario_actual", "Usuario Actual"),
                        proceso_id=proceso_id,
                        comentario=nuevo_comentario.strip()
                    )
                    st.success("Registrado.")
                    st.rerun()

# Import datetime for bitácora
from datetime import datetime