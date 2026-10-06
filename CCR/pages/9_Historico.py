"""
Histórico - CCR
Consulta de cierres anteriores (solo lectura).
"""
import streamlit as st
from datetime import date
from src.ui.theme import inject_css, ICONS, status_dot, badge, list_card
from src.alerts.scheduler import ejecutar_scheduler
from src.database.db_manager import execute_query, execute_one
from src.services.procesos_service import get_cierre_by_id, get_procesos_cierre
from src.services.sox_service import get_controles_sox_cierre
from src.services.aprobaciones_service import get_aprobaciones_cierre
from src.services.bitacoras_service import get_bitacoras_global
from src.services.evidencias_service import get_evidencias_filtros


st.set_page_config(page_title="Histórico - CCR", layout="wide")
inject_css()
ejecutar_scheduler()

st.markdown(f"""
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
    <div style="display: flex; align-items: center; gap: 12px;">
        <span class="material-symbols-outlined" style="font-size: 28px; color: #185FA5;">{ICONS['historico']}</span>
        <h1 style="margin: 0; font-size: 24px; font-weight: 500;">Histórico de Cierres</h1>
    </div>
</div>
""", unsafe_allow_html=True)

# Selector de año/mes
cierres = execute_query("SELECT * FROM cierres ORDER BY año DESC, mes DESC")

if not cierres:
    st.info("No hay cierres históricos.")
    st.stop()

cierre_opciones = {f"{c['año']}-{c['mes']:02d} - {c['nombre']}": c['id'] for c in cierres}
cierre_seleccionado = st.selectbox(
    "Seleccionar cierre",
    options=list(cierre_opciones.keys()),
    key="historico_cierre_select"
)

if not cierre_seleccionado:
    st.stop()

cierre_id = cierre_opciones[cierre_seleccionado]
cierre = get_cierre_by_id(cierre_id)

st.markdown(f"""
<div class="ccr-card">
    <div class="ccr-card-header">
        <h3 class="ccr-card-title">{cierre.nombre}</h3>
        <span class="ccr-badge ccr-badge--azul">{cierre.estado}</span>
    </div>
    <div style="font-size: 13px; color: #5F5E5A;">
        Creado: {cierre.creado_en.strftime('%d/%m/%Y %H:%M') if cierre.creado_en else '—'} 
        {f'| Cerrado: {cierre.cerrado_en.strftime("%d/%m/%Y %H:%M")}' if cierre.cerrado_en else ''}
    </div>
</div>
""", unsafe_allow_html=True)

# Tabs para cada sección
tab_procesos, tab_sox, tab_aprob, tab_evid, tab_bit, tab_export = st.tabs([
    "Procesos", "Controles SOX", "Aprobaciones", "Evidencias", "Bitácora", "Exportar"
])

# --- PROCESOS ---
with tab_procesos:
    procesos = get_procesos_cierre(cierre_id)
    
    if not procesos:
        st.info("Sin procesos en este cierre.")
    else:
        for p in procesos:
            cols = st.columns([1, 3, 1, 1, 1, 1])
            with cols[0]:
                st.markdown(status_dot(p["estado_codigo"]), unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"**{p['nombre']}**")
            with cols[2]:
                st.caption(f"Resp: {p.get('responsable_nombre', '—')}")
            with cols[3]:
                if p["fecha_limite"]:
                    st.caption(date.fromisoformat(p["fecha_limite"]).strftime("%d/%m/%Y"))
            with cols[4]:
                st.markdown(badge(p["estado_nombre"], p["estado_codigo"]), unsafe_allow_html=True)
            with cols[5]:
                st.caption(f"{p['subtareas_completadas']}/{p['total_subtareas']}")

# --- SOX ---
with tab_sox:
    controles = get_controles_sox_cierre(cierre_id)
    
    if not controles:
        st.info("Sin controles SOX en este cierre.")
    else:
        for c in controles:
            estado_calc = c.get("estado_calculado", c["estado_codigo"])
            color = "#E24B4A" if c.get("vencido") else c["estado_color"]
            cols = st.columns([1, 3, 1, 1, 1])
            with cols[0]:
                st.markdown(f'<span class="ccr-status-dot" style="background: {color};"></span>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"**{c['nombre']}**")
            with cols[2]:
                st.caption(f"Resp: {c.get('responsable_nombre', '—')}")
            with cols[3]:
                if c["fecha_ejecucion"]:
                    st.caption(date.fromisoformat(c["fecha_ejecucion"]).strftime("%d/%m/%Y"))
            with cols[4]:
                st.markdown(badge(c["estado_nombre"], estado_calc), unsafe_allow_html=True)

# --- APROBACIONES ---
with tab_aprob:
    aprobaciones = get_aprobaciones_cierre(cierre_id)
    
    if not aprobaciones:
        st.info("Sin aprobaciones en este cierre.")
    else:
        for a in aprobaciones:
            if a["completada_totalmente"]:
                color = "#639922"
                estado = "Completada"
            else:
                color = "#EF9F27"
                estado = "Pendiente"
            
            cols = st.columns([1, 3, 1, 1, 1, 1])
            with cols[0]:
                st.markdown(f'<span class="ccr-status-dot" style="background: {color};"></span>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"**{a['nombre']}**")
            with cols[2]:
                st.markdown(f'<div style="text-align: center;">{status_dot(a["estado_tecnico_codigo"])} Técnico: {a["estado_tecnico_nombre"]}</div>', unsafe_allow_html=True)
            with cols[3]:
                st.markdown(f'<div style="text-align: center;">{status_dot(a["estado_aprobacion_codigo"])} Aprob.: {a["estado_aprobacion_nombre"]}</div>', unsafe_allow_html=True)
            with cols[4]:
                st.markdown(f'<div style="text-align: center;">{status_dot(a["estado_sox_codigo"])} SOX: {a["estado_sox_nombre"]}</div>', unsafe_allow_html=True)
            with cols[5]:
                st.caption(f"Resp: {a.get('responsable_nombre', '—')}")

# --- EVIDENCIAS ---
with tab_evid:
    evidencias = get_evidencias_filtros()
    evidencias_cierre = [e for e in evidencias if e.get("cierre_id") == cierre_id]  # This won't work directly
    
    # Query directo para evidencias del cierre
    evidencias = execute_query("""
        SELECT e.*, te.codigo as tipo_codigo, te.nombre as tipo_nombre
        FROM evidencias e
        JOIN tipos_evidencia te ON e.tipo_evidencia_id = te.id
        WHERE e.activo = 1
        AND (
            (e.entidad_tipo = 'proceso' AND e.entidad_id IN (SELECT id FROM procesos WHERE cierre_id = ?))
            OR (e.entidad_tipo = 'subtarea' AND e.entidad_id IN (SELECT id FROM subtareas WHERE proceso_id IN (SELECT id FROM procesos WHERE cierre_id = ?)))
            OR (e.entidad_tipo = 'control_sox' AND e.entidad_id IN (SELECT id FROM controles_sox WHERE cierre_id = ?))
            OR (e.entidad_tipo = 'aprobacion' AND e.entidad_id IN (SELECT id FROM aprobaciones WHERE cierre_id = ?))
        )
        ORDER BY e.subido_en DESC
    """, (cierre_id, cierre_id, cierre_id, cierre_id))
    
    if not evidencias:
        st.info("Sin evidencias en este cierre.")
    else:
        for e in evidencias:
            cols = st.columns([1, 3, 1, 1, 1, 1])
            with cols[0]:
                icon_map = {"pdf": "picture_as_pdf", "excel": "table_chart", "correo": "mail", "imagen": "image", "captura": "screenshot_monitor", "enlace": "link"}
                icon = icon_map.get(e["tipo_codigo"], "attach_file")
                st.markdown(f'<span class="material-symbols-outlined" style="font-size: 24px; color: #185FA5;">{icon}</span>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"**{e['nombre_original']}**")
                st.caption(f"{e['entidad_tipo']} #{e['entidad_id']}")
            with cols[2]:
                st.caption(f"{(e['tamaño_bytes']/1024):.1f} KB" if e['tamaño_bytes'] > 0 else "Enlace")
            with cols[3]:
                st.caption(e['subido_en'][:16].replace('T', ' '))
            with cols[4]:
                st.markdown(badge(e['tipo_nombre'], e['tipo_codigo']), unsafe_allow_html=True)
            with cols[5]:
                st.caption(e['subido_por'])

# --- BITÁCORA ---
with tab_bit:
    bitacoras = get_bitacoras_global(proceso_id=None)  # Global, filtrar por cierre después
    
    # Filtrar bitácoras relacionadas con este cierre
    bitacoras_cierre = []
    for b in bitacoras:
        if b["proceso_id"]:
            proc = execute_one("SELECT cierre_id FROM procesos WHERE id = ?", (b["proceso_id"],))
            if proc and proc["cierre_id"] == cierre_id:
                bitacoras_cierre.append(b)
        elif b["control_sox_id"]:
            ctrl = execute_one("SELECT cierre_id FROM controles_sox WHERE id = ?", (b["control_sox_id"],))
            if ctrl and ctrl["cierre_id"] == cierre_id:
                bitacoras_cierre.append(b)
        elif b["aprobacion_id"]:
            apr = execute_one("SELECT cierre_id FROM aprobaciones WHERE id = ?", (b["aprobacion_id"],))
            if apr and apr["cierre_id"] == cierre_id:
                bitacoras_cierre.append(b)
    
    if not bitacoras_cierre:
        st.info("Sin entradas en bitácora para este cierre.")
    else:
        for b in bitacoras_cierre[:100]:  # Limitar a 100
            fecha_fmt = ""
            if b["fecha"]:
                try:
                    fecha_fmt = date.fromisoformat(b["fecha"][:10]).strftime("%d/%m/%Y %H:%M")
                except:
                    fecha_fmt = b["fecha"][:16].replace('T', ' ')
            
            st.markdown(f"""
            <div class="ccr-list-row">
                <span class="material-symbols-outlined" style="color: #5F5E5A;">{ICONS['bitacora']}</span>
                <div style="flex: 1;">
                    <div style="font-weight: 500;">{b['comentario']}</div>
                    <div style="font-size: 11px; color: #888780;">{b['usuario']} · {fecha_fmt}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# --- EXPORTAR ---
with tab_export:
    st.markdown("### Exportar resumen del cierre")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button(":material/download: Exportar a CSV", use_container_width=True, type="primary"):
            import pandas as pd
            import io
            
            # Procesos
            procesos = get_procesos_cierre(cierre_id)
            df_procesos = pd.DataFrame([{
                "Proceso": p["nombre"],
                "Estado": p["estado_nombre"],
                "Prioridad": p["prioridad_nombre"],
                "Responsable": p.get("responsable_nombre", ""),
                "Fecha límite": p["fecha_limite"],
                "Subtareas": f"{p['subtareas_completadas']}/{p['total_subtareas']}",
                "Observaciones": p.get("observaciones", "")
            } for p in procesos])
            
            # SOX
            controles = get_controles_sox_cierre(cierre_id)
            df_sox = pd.DataFrame([{
                "Control": c["nombre"],
                "Estado": c["estado_nombre"],
                "Responsable": c.get("responsable_nombre", ""),
                "Fecha ejecución": c["fecha_ejecucion"],
                "Vencido": "Sí" if c.get("vencido") else "No",
                "Observaciones": c.get("observaciones", "")
            } for c in controles])
            
            # Aprobaciones
            aprobaciones = get_aprobaciones_cierre(cierre_id)
            df_aprob = pd.DataFrame([{
                "Aprobación": a["nombre"],
                "Estado Técnico": a["estado_tecnico_nombre"],
                "Estado Aprobación": a["estado_aprobacion_nombre"],
                "Estado SOX": a["estado_sox_nombre"],
                "Completada": "Sí" if a["completada_totalmente"] else "No",
                "Responsable": a.get("responsable_nombre", "")
            } for a in aprobaciones])
            
            # Crear Excel con múltiples hojas
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_procesos.to_excel(writer, sheet_name='Procesos', index=False)
                df_sox.to_excel(writer, sheet_name='SOX', index=False)
                df_aprob.to_excel(writer, sheet_name='Aprobaciones', index=False)
            
            st.download_button(
                "Descargar Excel",
                data=output.getvalue(),
                file_name=f"CCR_Historico_{cierre.año}_{cierre.mes:02d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    
    with col2:
        if st.button(":material/download: Exportar CSV (Procesos)", use_container_width=True):
            import pandas as pd
            procesos = get_procesos_cierre(cierre_id)
            df = pd.DataFrame([{
                "Proceso": p["nombre"],
                "Estado": p["estado_nombre"],
                "Prioridad": p["prioridad_nombre"],
                "Responsable": p.get("responsable_nombre", ""),
                "Fecha límite": p["fecha_limite"],
                "Subtareas": f"{p['subtareas_completadas']}/{p['total_subtareas']}",
                "Observaciones": p.get("observaciones", "")
            } for p in procesos])
            
            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
            st.download_button(
                "Descargar CSV",
                data=csv,
                file_name=f"CCR_Procesos_{cierre.año}_{cierre.mes:02d}.csv",
                mime="text/csv",
                use_container_width=True
            )