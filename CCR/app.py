"""
CCR - Centro de Control de Reservas y Cierres Actuariales
Aplicación principal Streamlit - Redirige al Dashboard.
"""
import streamlit as st
from src.database.seed import init_db


# Configuración de página
st.set_page_config(
    page_title="CCR - Centro de Control de Reservas y Cierres Actuariales",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inicializar base de datos en primera ejecución
if "db_inicializada" not in st.session_state:
    try:
        init_db()
        st.session_state["db_inicializada"] = True
    except Exception as e:
        st.error(f"Error inicializando base de datos: {e}")
        st.stop()

# Redirigir al Dashboard (página principal)
st.switch_page("pages/1_Dashboard.py")