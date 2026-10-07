"""
Configuración - CCR
Administración completa desde interfaz: usuarios, procesos, alertas, Teams, respaldos.
"""
import streamlit as st
from datetime import date
from src.ui.theme import inject_css, ICONS, badge, list_card
from src.alerts.scheduler import ejecutar_scheduler
from src.database.db_manager import execute_query, execute_one, execute_insert, execute_update, backup, get_db_version, set_db_version
from src.services.config_service import get_config, set_config, get_all_config, get_usuarios_activos, get_estados_activos, get_prioridades_activas, get_tipos_evidencia_activos
from src.services.procesos_service import get_cierre_actual
from src.alerts.power_automate import enviar_mensaje_prueba, log_tecnico
from pathlib import Path
import shutil


st.set_page_config(page_title="Configuración - CCR", layout="wide")
inject_css()
ejecutar_scheduler()

cierre = get_cierre_actual()

st.markdown(f"""
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
    <div style="display: flex; align-items: center; gap: 12px;">
        <span class="material-symbols-outlined" style="font-size: 28px; color: #185FA5;">{ICONS['config']}</span>
        <h1 style="margin: 0; font-size: 24px; font-weight: 500;">Configuración</h1>
    </div>
    <div style="font-size: 13px; color: #5F5E5A;">Cierre: {cierre.nombre if cierre else 'Sin cierre'}</div>
</div>
""", unsafe_allow_html=True)

# Tabs principales
tab_general, tab_usuarios, tab_procesos, tab_catalogos, tab_alertas, tab_teams, tab_respaldos = st.tabs([
    "General", "Usuarios", "Procesos (Plantillas)", "Catálogos", "Alertas", "Teams", "Respaldos"
])

# --- TAB GENERAL ---
with tab_general:
    st.markdown("### Configuración General")
    
    with st.form("config_general_form"):
        c1, c2 = st.columns(2)
        with c1:
            app_url = st.text_input("URL base de la app", value=get_config("app_url_base", "http://localhost:8501"))
            usuario_actual = st.text_input("Usuario actual por defecto", value=get_config("usuario_actual", "Usuario Actual"))
        with c2:
            evidencias_max = st.number_input("Tamaño máx. evidencias (MB)", min_value=1, max_value=100, value=int(get_config("evidencias_tamaño_max_mb", "20")))
        
        if st.form_submit_button("Guardar", type="primary"):
            set_config("app_url_base", app_url, "URL base para enlaces en notificaciones")
            set_config("usuario_actual", usuario_actual, "Usuario por defecto para bitácoras")
            set_config("evidencias_tamaño_max_mb", str(evidencias_max), "Límite de tamaño para archivos de evidencia")
            st.success("Configuración general guardada.")
            st.rerun()

# --- TAB USUARIOS ---
with tab_usuarios:
    st.markdown("### Usuarios / Responsables")
    
    usuarios = get_usuarios_activos()
    
    for u in usuarios:
        cols = st.columns([3, 3, 1, 1])
        with cols[0]:
            st.markdown(f"**{u['nombre']}**")
        with cols[1]:
            st.caption(u['email'] or "Sin email")
        with cols[2]:
            if st.button(":material/edit:", key=f"usr_edit_{u['id']}"):
                st.session_state[f"usr_edit_{u['id']}"] = True
                st.rerun()
        with cols[3]:
            if st.button(":material/delete:", key=f"usr_del_{u['id']}"):
                execute_update("UPDATE usuarios SET activo = 0 WHERE id = ?", (u['id'],))
                st.rerun()
        
        if st.session_state.get(f"usr_edit_{u['id']}"):
            with st.form(f"usr_form_{u['id']}"):
                nuevo_nombre = st.text_input("Nombre", value=u['nombre'])
                nuevo_email = st.text_input("Email", value=u['email'] or "")
                if st.form_submit_button("Guardar"):
                    execute_update("UPDATE usuarios SET nombre = ?, email = ? WHERE id = ?", (nuevo_nombre, nuevo_email, u['id']))
                    st.session_state[f"usr_edit_{u['id']}"] = False
                    st.success("Actualizado")
                    st.rerun()
    
    st.markdown("---")
    with st.form("usr_nuevo_form"):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre *")
        with c2:
            email = st.text_input("Email")
        if st.form_submit_button("Crear usuario", type="primary"):
            if nombre:
                execute_insert("INSERT INTO usuarios (nombre, email) VALUES (?, ?)", (nombre, email or None))
                st.success("Usuario creado.")
                st.rerun()
            else:
                st.error("Nombre es obligatorio")

# --- TAB PROCESOS (PLANTILLAS) ---
with tab_procesos:
    st.markdown("### Plantillas de Procesos (definición permanente)")
    
    plantillas = execute_query("""
        SELECT pp.*, pr.codigo as prioridad_codigo, pr.nombre as prioridad_nombre
        FROM procesos_plantilla pp
        LEFT JOIN prioridades pr ON pp.prioridad_id = pr.id
        WHERE pp.activo = 1
        ORDER BY pp.orden
    """)
    
    for pt in plantillas:
        with st.expander(f"{pt['orden']}. {pt['nombre']} (Prioridad: {pt['prioridad_nombre']})", expanded=False):
            # Subtareas
            subtareas = execute_query("SELECT * FROM subtareas_plantilla WHERE proceso_plantilla_id = ? AND activo = 1 ORDER BY orden", (pt['id'],))
            st.markdown("**Subtareas:**")
            for st_row in subtareas:
                st.caption(f"{st_row['orden']}. {st_row['nombre']}")
            
            # Dependencias
            deps = execute_query("""
                SELECT pp2.nombre as predecesora_nombre
                FROM dependencias_plantilla dp
                JOIN procesos_plantilla pp2 ON dp.predecesora_id = pp2.id
                WHERE dp.proceso_plantilla_id = ?
            """, (pt['id'],))
            if deps:
                st.markdown("**Depende de:**")
                for d in deps:
                    st.caption(f"→ {d['predecesora_nombre']}")
            
            # Editar
            if st.button(":material/edit:", key=f"pt_edit_{pt['id']}"):
                st.session_state[f"pt_edit_{pt['id']}"] = True
                st.rerun()
            
            if st.session_state.get(f"pt_edit_{pt['id']}"):
                with st.form(f"pt_form_{pt['id']}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        nuevo_nombre = st.text_input("Nombre", value=pt['nombre'])
                        nueva_desc = st.text_area("Descripción", value=pt['descripcion'] or "")
                    with c2:
                        prioridades = get_prioridades_activas()
                        prioridad_sel = st.selectbox("Prioridad", [p['nombre'] for p in prioridades],
                                                    index=[p['nombre'] for p in prioridades].index(pt['prioridad_nombre']))
                        usuarios = get_usuarios_activos()
                        resp_sel = st.selectbox("Responsable", [""] + [u['nombre'] for u in usuarios],
                                               index=([""] + [u['nombre'] for u in usuarios]).index(pt.get('responsable_nombre', '')) if pt.get('responsable_nombre') else 0)
                    with c3:
                        dias = st.number_input("Días estimados", min_value=1, value=pt['dias_duracion_estimada'])
                        orden = st.number_input("Orden", min_value=0, value=pt['orden'])
                    
                    if st.form_submit_button("Guardar"):
                        prio_id = next(p['id'] for p in prioridades if p['nombre'] == prioridad_sel)
                        resp_id = next((u['id'] for u in usuarios if u['nombre'] == resp_sel), None) if resp_sel else None
                        execute_update(
                            "UPDATE procesos_plantilla SET nombre = ?, descripcion = ?, prioridad_id = ?, responsable_id = ?, dias_duracion_estimada = ?, orden = ? WHERE id = ?",
                            (nuevo_nombre, nueva_desc, prio_id, resp_id, dias, orden, pt['id'])
                        )
                        st.session_state[f"pt_edit_{pt['id']}"] = False
                        st.success("Actualizado")
                        st.rerun()

# --- TAB CATÁLOGOS ---
with tab_catalogos:
    st.markdown("### Catálogos editables")
    
    subtab_estados, subtab_prios, subtab_tipos = st.tabs(["Estados", "Prioridades", "Tipos de evidencia"])
    
    # Estados
    with subtab_estados:
        estados = get_estados_activos()
        for e in estados:
            cols = st.columns([1, 2, 1, 1, 1, 1])
            with cols[0]:
                st.markdown(f'<span class="ccr-status-dot" style="background: {e["color"]};"></span>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"**{e['nombre']}** (`{e['codigo']}`)")
            with cols[2]:
                st.caption(f"Orden: {e['orden']}")
            with cols[3]:
                if st.button(":material/edit:", key=f"est_edit_{e['id']}"):
                    st.session_state[f"est_edit_{e['id']}"] = True
                    st.rerun()
            with cols[4]:
                if st.button(":material/delete:", key=f"est_del_{e['id']}"):
                    execute_update("UPDATE estados SET activo = 0 WHERE id = ?", (e['id'],))
                    st.rerun()
            with cols[5]:
                pass
            
            if st.session_state.get(f"est_edit_{e['id']}"):
                with st.form(f"est_form_{e['id']}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        n_nombre = st.text_input("Nombre", value=e['nombre'])
                        n_codigo = st.text_input("Código", value=e['codigo'])
                    with c2:
                        n_color = st.color_picker("Color", value=e['color'])
                    with c3:
                        n_orden = st.number_input("Orden", value=e['orden'])
                    if st.form_submit_button("Guardar"):
                        execute_update("UPDATE estados SET nombre = ?, codigo = ?, color = ?, orden = ? WHERE id = ?", 
                                     (n_nombre, n_codigo, n_color, n_orden, e['id']))
                        st.session_state[f"est_edit_{e['id']}"] = False
                        st.rerun()
        
        with st.form("est_nuevo_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                n_nombre = st.text_input("Nombre *")
                n_codigo = st.text_input("Código *")
            with c2:
                n_color = st.color_picker("Color *", value="#185FA5")
            with c3:
                n_orden = st.number_input("Orden", value=len(estados)+1)
            if st.form_submit_button("Crear estado", type="primary"):
                if n_nombre and n_codigo:
                    execute_insert("INSERT INTO estados (codigo, nombre, color, orden) VALUES (?, ?, ?, ?)", 
                                 (n_codigo, n_nombre, n_color, n_orden))
                    st.success("Estado creado.")
                    st.rerun()
    
    # Prioridades
    with subtab_prios:
        prios = get_prioridades_activas()
        for p in prios:
            cols = st.columns([1, 2, 1, 1, 1])
            with cols[0]:
                st.markdown(f'<span class="ccr-badge ccr-prio-{p["codigo"]}">{p["nombre"]}</span>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"**{p['nombre']}** (`{p['codigo']}`) - Color: {p['color']}")
            with cols[2]:
                st.caption(f"Orden: {p['orden']}")
            with cols[3]:
                if st.button(":material/edit:", key=f"pri_edit_{p['id']}"):
                    st.session_state[f"pri_edit_{p['id']}"] = True
                    st.rerun()
            with cols[4]:
                if st.button(":material/delete:", key=f"pri_del_{p['id']}"):
                    execute_update("UPDATE prioridades SET activo = 0 WHERE id = ?", (p['id'],))
                    st.rerun()
            
            if st.session_state.get(f"pri_edit_{p['id']}"):
                with st.form(f"pri_form_{p['id']}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        n_nombre = st.text_input("Nombre", value=p['nombre'])
                        n_codigo = st.text_input("Código", value=p['codigo'])
                    with c2:
                        n_color = st.color_picker("Color", value=p['color'])
                    with c3:
                        n_orden = st.number_input("Orden", value=p['orden'])
                    if st.form_submit_button("Guardar"):
                        execute_update("UPDATE prioridades SET nombre = ?, codigo = ?, color = ?, orden = ? WHERE id = ?", 
                                     (n_nombre, n_codigo, n_color, n_orden, p['id']))
                        st.session_state[f"pri_edit_{p['id']}"] = False
                        st.rerun()
        
        with st.form("pri_nuevo_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                n_nombre = st.text_input("Nombre *", key="pri_n_nombre")
                n_codigo = st.text_input("Código *", key="pri_n_codigo")
            with c2:
                n_color = st.color_picker("Color *", value="#185FA5", key="pri_n_color")
            with c3:
                n_orden = st.number_input("Orden", value=len(prios)+1, key="pri_n_orden")
            if st.form_submit_button("Crear prioridad", type="primary"):
                if n_nombre and n_codigo:
                    execute_insert("INSERT INTO prioridades (codigo, nombre, color, orden) VALUES (?, ?, ?, ?)", 
                                 (n_codigo, n_nombre, n_color, n_orden))
                    st.success("Prioridad creada.")
                    st.rerun()
    
    # Tipos de evidencia
    with subtab_tipos:
        tipos = get_tipos_evidencia_activos()
        for t in tipos:
            cols = st.columns([2, 2, 2, 1, 1])
            with cols[0]:
                st.markdown(f"**{t['nombre']}** (`{t['codigo']}`)")
            with cols[1]:
                st.caption(f"Extensiones: {', '.join(t['extensiones_permitidas']) if t['extensiones_permitidas'] else 'N/A (enlace)'}")
            with cols[2]:
                st.caption(f"Máx: {t['tamaño_max_mb']} MB")
            with cols[3]:
                if st.button(":material/edit:", key=f"tev_edit_{t['id']}"):
                    st.session_state[f"tev_edit_{t['id']}"] = True
                    st.rerun()
            with cols[4]:
                if st.button(":material/delete:", key=f"tev_del_{t['id']}"):
                    execute_update("UPDATE tipos_evidencia SET activo = 0 WHERE id = ?", (t['id'],))
                    st.rerun()
            
            if st.session_state.get(f"tev_edit_{t['id']}"):
                with st.form(f"tev_form_{t['id']}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        n_nombre = st.text_input("Nombre", value=t['nombre'])
                        n_codigo = st.text_input("Código", value=t['codigo'])
                    with c2:
                        n_ext = st.text_input("Extensiones (coma separadas)", value=', '.join(t['extensiones_permitidas']) if t['extensiones_permitidas'] else "")
                    with c3:
                        n_max = st.number_input("Máx MB", value=t['tamaño_max_mb'])
                    if st.form_submit_button("Guardar"):
                        import json
                        ext_list = [x.strip() for x in n_ext.split(',') if x.strip()] if n_ext else []
                        execute_update("UPDATE tipos_evidencia SET nombre = ?, codigo = ?, extensiones_permitidas = ?, tamaño_max_mb = ? WHERE id = ?", 
                                     (n_nombre, n_codigo, json.dumps(ext_list), n_max, t['id']))
                        st.session_state[f"tev_edit_{t['id']}"] = False
                        st.rerun()
        
        with st.form("tev_nuevo_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                n_nombre = st.text_input("Nombre *", key="tev_n_nombre")
                n_codigo = st.text_input("Código *", key="tev_n_codigo")
            with c2:
                n_ext = st.text_input("Extensiones (coma separadas)", key="tev_n_ext")
            with c3:
                n_max = st.number_input("Máx MB", value=10, key="tev_n_max")
            if st.form_submit_button("Crear tipo", type="primary"):
                if n_nombre and n_codigo:
                    import json
                    ext_list = [x.strip() for x in n_ext.split(',') if x.strip()] if n_ext else []
                    execute_insert("INSERT INTO tipos_evidencia (codigo, nombre, extensiones_permitidas, tamaño_max_mb) VALUES (?, ?, ?, ?)", 
                                 (n_codigo, n_nombre, json.dumps(ext_list), n_max))
                    st.success("Tipo creado.")
                    st.rerun()

# --- TAB ALERTAS ---
with tab_alertas:
    st.markdown("### Configuración de Alertas")
    
    with st.form("alertas_form"):
        c1, c2 = st.columns(2)
        with c1:
            dias_ant = st.text_input("Días de anticipación (coma separados)", value=get_config("alertas_dias_anticipacion", "7,3,1"))
            horario_inicio = st.text_input("Horario silencioso - Inicio (HH:MM)", value=get_config("alertas_horario_silencioso_inicio", "19:00"))
        with c2:
            horario_fin = st.text_input("Horario silencioso - Fin (HH:MM)", value=get_config("alertas_horario_silencioso_fin", "07:00"))
            limite_hora = st.number_input("Límite mensajes/hora", min_value=1, max_value=100, value=int(get_config("alertas_limite_por_hora", "10")))
        
        modo = st.selectbox("Modo de envío", ["individual", "resumen", "ambos"], 
                           index=["individual", "resumen", "ambos"].index(get_config("alertas_modo", "individual")))
        
        if st.form_submit_button("Guardar", type="primary"):
            set_config("alertas_dias_anticipacion", dias_ant, "Días de anticipación para alertas de vencimiento")
            set_config("alertas_horario_silencioso_inicio", horario_inicio, "Inicio horario silencioso")
            set_config("alertas_horario_silencioso_fin", horario_fin, "Fin horario silencioso")
            set_config("alertas_limite_por_hora", str(limite_hora), "Límite de mensajes por hora")
            set_config("alertas_modo", modo, "Modo de envío: individual, resumen o ambos")
            st.success("Configuración de alertas guardada.")
            st.rerun()

# --- TAB TEAMS ---
with tab_teams:
    st.markdown("### Integración con Microsoft Teams (Power Automate)")
    
    teams_activado = get_config("alertas_teams_activado", "false").lower() == "true"
    teams_url = get_config("alertas_teams_url", "")
    teams_card = get_config("alertas_teams_adaptive_card", "false").lower() == "true"
    
    with st.form("teams_form"):
        activado = st.checkbox("Enviar notificaciones a Teams", value=teams_activado)
        
        url = st.text_input(
            "URL del flujo de Power Automate (Webhook)",
            value=teams_url if not teams_activado else "••••••••••••••••••••••••••••••••",
            type="password" if teams_activado else "default",
            placeholder="https://prod-XX.westus.logic.azure.com/...",
            help="Pegue la URL HTTP POST del disparador 'Cuando se recibe una solicitud de webhook de Teams' o 'When an HTTP request is received'"
        )
        
        adaptive = st.checkbox("Incluir Adaptive Card en el payload", value=teams_card)
        
        if st.form_submit_button("Guardar configuración", type="primary"):
            set_config("alertas_teams_activado", "true" if activado else "false", "Activar envío a Teams")
            if url and not teams_activado:  # Solo actualizar URL si no estaba enmascarada
                set_config("alertas_teams_url", url, "URL del webhook de Power Automate")
            set_config("alertas_teams_adaptive_card", "true" if adaptive else "false", "Incluir Adaptive Card")
            st.success("Configuración de Teams guardada.")
            st.rerun()
    
    st.markdown("---")
    st.markdown("### Prueba de conexión")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        if st.button(":material/send: Enviar mensaje de prueba", type="primary", use_container_width=True, disabled=not teams_activado or not teams_url):
            with st.spinner("Enviando..."):
                ok, error = enviar_mensaje_prueba(teams_url)
                if ok:
                    st.success("✅ Mensaje de prueba enviado correctamente. Revise su Teams.")
                    log_tecnico("TEST_OK: Mensaje de prueba Teams enviado")
                else:
                    st.error(f"❌ Error: {error}")
                    log_tecnico(f"TEST_ERROR: {error}")
    with col2:
        if st.button(":material/visibility: Mostrar URL", use_container_width=True):
            st.code(teams_url, language=None)
    
    st.markdown("---")
    st.markdown("### Cola de salida (eventos_salida)")
    
    from src.services.alertas_service import get_eventos_pendientes, reintentar_evento, descartar_evento
    
    eventos = get_eventos_pendientes(limite=50)
    
    if not eventos:
        st.info("Cola vacía.")
    else:
        for ev in eventos:
            cols = st.columns([1, 2, 1, 1, 2, 1, 1])
            with cols[0]:
                sev_color = {"Critica": "rojo", "Aviso": "ambar", "Info": "azul"}.get(ev["severidad"], "gris")
                st.markdown(badge(ev["severidad"], sev_color), unsafe_allow_html=True)
            with cols[1]:
                st.caption(ev["tipo_alerta"])
            with cols[2]:
                estado_color = {"Pendiente": "ambar", "Enviado": "verde", "Error": "rojo", "Omitido": "gris"}.get(ev["estado"], "gris")
                st.markdown(badge(ev["estado"], estado_color), unsafe_allow_html=True)
            with cols[3]:
                st.caption(f"Intentos: {ev['intentos']}")
            with cols[4]:
                st.caption(ev["creado_en"][:16].replace('T', ' '))
            with cols[5]:
                if ev["estado"] in ("Pendiente", "Error"):
                    if st.button(":material/refresh:", key=f"evt_retry_{ev['id']}", help="Reintentar"):
                        reintentar_evento(ev['id'])
                        st.rerun()
            with cols[6]:
                if ev["estado"] in ("Pendiente", "Error"):
                    if st.button(":material/block:", key=f"evt_discard_{ev['id']}", help="Descartar"):
                        descartar_evento(ev['id'])
                        st.rerun()
            
            if ev["ultimo_error"]:
                st.caption(f"Error: {ev['ultimo_error']}")

# --- TAB RESPALDOS ---
with tab_respaldos:
    st.markdown("### Respaldo y Restauración de Base de Datos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Crear respaldo manual")
        if st.button(":material/backup: Crear respaldo ahora", type="primary", use_container_width=True):
            try:
                timestamp = date.today().strftime("%Y%m%d") + "_" + datetime.now().strftime("%H%M%S")
                backup_path = Path(__file__).parent.parent.parent / "data" / "backups" / f"ccr_backup_{timestamp}.db"
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                
                from src.database.db_manager import get_connection
                conn = get_connection()
                with shutil.open(backup_path, 'wb') as f:
                    pass  # placeholder
                # Usar backup nativo de SQLite
                import sqlite3
                with sqlite3.connect(backup_path) as dest:
                    conn.backup(dest)
                
                st.success(f"Respaldo creado: {backup_path.name}")
                st.caption(f"Ubicación: {backup_path}")
            except Exception as e:
                st.error(f"Error creando respaldo: {e}")
    
    with col2:
        st.markdown("#### Restaurar desde respaldo")
        backups = list(Path(__file__).parent.parent.parent / "data" / "backups").glob("*.db")
        backup_files = sorted([f for f in backups], reverse=True)
        
        if backup_files:
            backup_sel = st.selectbox("Seleccionar respaldo", [f.name for f in backup_files])
            if st.button(":material/restore: Restaurar", type="secondary", use_container_width=True):
                st.warning("⚠️ La restauración reemplazará la base de datos actual. Esta acción no se puede deshacer.")
                if st.checkbox("Confirmo que quiero restaurar"):
                    try:
                        src_path = Path(__file__).parent.parent.parent / "data" / "backups" / backup_sel
                        dest_path = Path(__file__).parent.parent.parent / "data" / "ccr.db"
                        shutil.copy2(src_path, dest_path)
                        st.success("Base de datos restaurada. Reinicie la app.")
                    except Exception as e:
                        st.error(f"Error restaurando: {e}")
        else:
            st.info("No hay respaldos disponibles.")
    
    st.markdown("---")
    st.markdown("#### Información de la base de datos")
    db_path = Path(__file__).parent.parent.parent / "data" / "ccr.db"
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        st.caption(f"Archivo: {db_path}")
        st.caption(f"Tamaño: {size_mb:.2f} MB")
        st.caption(f"Versión esquema: {get_db_version()}")
    
    # Lista de respaldos existentes
    if backup_files:
        st.markdown("#### Respaldos existentes")
        for bf in backup_files[:10]:
            st.caption(f"📄 {bf.name} ({bf.stat().st_size / 1024:.1f} KB)")

from datetime import datetime