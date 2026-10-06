"""
Procesos Masivos - CCR
Carga CSV, gestión de procesos masivos.
"""
import streamlit as st
import pandas as pd
from datetime import date
from src.ui.theme import inject_css, ICONS, status_dot, badge, priority_badge, list_card
from src.alerts.scheduler import ejecutar_scheduler
from src.services.procesos_masivos_service import (
    get_procesos_masivos, crear_proceso_masivo, actualizar_proceso_masivo,
    importar_csv_procesos_masivos, get_plantilla_csv
)
from src.services.config_service import get_estados_activos


st.set_page_config(page_title="Procesos Masivos - CCR", layout="wide")
inject_css()
ejecutar_scheduler()

st.markdown(f"""
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
    <div style="display: flex; align-items: center; gap: 12px;">
        <span class="material-symbols-outlined" style="font-size: 28px; color: #185FA5;">{ICONS['masivo']}</span>
        <h1 style="margin: 0; font-size: 24px; font-weight: 500;">Procesos Masivos</h1>
    </div>
</div>
""", unsafe_allow_html=True)

# Tabs
tab_lista, tab_carga, tab_nuevo = st.tabs(["Lista", "Cargar CSV", "Nuevo proceso"])

# --- TAB LISTA ---
with tab_lista:
    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
    with col_f1:
        filtro_estado = st.selectbox("Estado", ["Todos"] + [e["nombre"] for e in get_estados_activos()], key="pm_filtro_estado")
    with col_f2:
        filtro_ramo = st.text_input("Ramo", placeholder="Filtrar por ramo...", key="pm_filtro_ramo")
    with col_f3:
        hoy = date.today().isoformat()
        filtro_fecha = st.date_input("Fecha desde", value=None, key="pm_filtro_fecha")
    
    procesos = get_procesos_masivos(
        fecha_desde=filtro_fecha.isoformat() if filtro_fecha else None,
        estado_codigo=None if filtro_estado == "Todos" else next((e["codigo"] for e in get_estados_activos() if e["nombre"] == filtro_estado), None),
        ramo=filtro_ramo or None
    )
    
    if not procesos:
        st.info("No hay procesos masivos.")
    else:
        for pm in procesos:
            cols = st.columns([1, 3, 1, 1, 1, 1, 1])
            with cols[0]:
                st.markdown(status_dot(pm["estado_codigo"]), unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"**{pm['codigo']}** - {pm['nombre']}")
            with cols[2]:
                st.caption(date.fromisoformat(pm["fecha_ejecucion"]).strftime("%d/%m/%Y"))
            with cols[3]:
                st.caption(pm["hora"] or "—")
            with cols[4]:
                st.caption(pm["ramo"] or "—")
            with cols[5]:
                st.markdown(badge(pm["estado_nombre"], pm["estado_codigo"]), unsafe_allow_html=True)
            with cols[6]:
                if st.button(":material/edit:", key=f"pm_edit_{pm['id']}", help="Editar"):
                    st.session_state[f"pm_edit_{pm['id']}"] = True
                    st.rerun()
            
            # Formulario de edición inline
            if st.session_state.get(f"pm_edit_{pm['id']}"):
                with st.form(f"pm_form_{pm['id']}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        nuevo_estado = st.selectbox("Estado", [e["nombre"] for e in get_estados_activos()], 
                                                   index=[e["nombre"] for e in get_estados_activos()].index(pm["estado_nombre"]))
                    with c2:
                        nueva_hora = st.text_input("Hora", value=pm["hora"] or "")
                    with c3:
                        nuevo_ramo = st.text_input("Ramo", value=pm["ramo"] or "")
                    obs = st.text_area("Observaciones", value=pm["observaciones"] or "")
                    
                    if st.form_submit_button("Guardar"):
                        estado_cod = next(e["codigo"] for e in get_estados_activos() if e["nombre"] == nuevo_estado)
                        actualizar_proceso_masivo(pm["id"], estado_id=estado_cod, hora=nueva_hora or None, ramo=nuevo_ramo or None, observaciones=obs)
                        st.session_state[f"pm_edit_{pm['id']}"] = False
                        st.success("Actualizado")
                        st.rerun()

# --- TAB CARGA CSV ---
with tab_carga:
    st.markdown("### Cargar procesos masivos desde CSV")
    
    # Descargar plantilla
    st.download_button(
        ":material/download: Descargar plantilla CSV",
        data=get_plantilla_csv(),
        file_name="plantilla_procesos_masivos.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    st.markdown("**Formato esperado:** `codigo,nombre,fecha_ejecucion,hora,ramo,estado,observaciones`")
    st.caption("Fecha en formato YYYY-MM-DD. Hora en formato HH:MM (opcional).")
    
    archivo = st.file_uploader("Seleccionar archivo CSV", type=["csv"], key="pm_csv_upload")
    
    if archivo:
        # Vista previa
        try:
            df = pd.read_csv(archivo)
            st.markdown("**Vista previa:**")
            st.dataframe(df.head(10), use_container_width=True)
            
            if st.button(":material/upload: Confirmar carga", type="primary", use_container_width=True):
                # Guardar temporal y procesar
                import tempfile
                with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as f:
                    f.write(archivo.getvalue())
                    temp_path = f.name
                
                resultado = importar_csv_procesos_masivos(temp_path)
                
                if resultado["exito"]:
                    st.success(f"Carga completada: {resultado['insertados']} insertados, {resultado['errores']} errores")
                    if resultado["detalles"]:
                        with st.expander("Detalles de errores"):
                            for d in resultado["detalles"]:
                                st.caption(d)
                else:
                    st.error(resultado["error"])
                
                # Limpiar temp
                import os
                os.unlink(temp_path)
        except Exception as e:
            st.error(f"Error leyendo CSV: {e}")

# --- TAB NUEVO ---
with tab_nuevo:
    st.markdown("### Crear proceso masivo manual")
    
    with st.form("pm_nuevo_form"):
        c1, c2 = st.columns(2)
        with c1:
            codigo = st.text_input("Código *", placeholder="Ej: 17615")
            nombre = st.text_input("Nombre *", placeholder="Ej: Reporte Mensual F394")
            fecha = st.date_input("Fecha ejecución *", value=date.today())
        with c2:
            hora = st.text_input("Hora", placeholder="HH:MM (opcional)")
            ramo = st.text_input("Ramo", placeholder="Ej: 087 (opcional)")
            estado = st.selectbox("Estado", [e["nombre"] for e in get_estados_activos()])
        observaciones = st.text_area("Observaciones")
        
        if st.form_submit_button("Crear", type="primary"):
            if not codigo or not nombre:
                st.error("Código y nombre son obligatorios")
            else:
                estado_cod = next(e["codigo"] for e in get_estados_activos() if e["nombre"] == estado)
                ok, msg = crear_proceso_masivo(
                    codigo, nombre, fecha.isoformat(), 
                    hora or None, ramo or None, estado_cod, observaciones
                )
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)