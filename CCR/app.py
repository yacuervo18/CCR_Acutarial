import streamlit as st
from datetime import date, datetime

from src.phase1.config import PROCESOS, proceso_por_codigo
from src.phase1.domain import EstadoProceso
from src.phase1.notifications import Notification, NotificationService, validar_destinatarios
from src.phase1.repository import Repository
from src.phase1.service import ProcessService

st.set_page_config(page_title="CCR · Centro de Control Actuarial", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")


@st.cache_resource
def get_repository() -> Repository:
    return Repository()


repo = get_repository()
service = ProcessService(repo)
period_default = datetime.now().strftime("%Y-%m")
repo.ensure_period(period_default)
periods = repo.periods()

st.markdown("""<style>
.block-container {padding-top: 1rem; max-width: 1500px;}
.ccr-sticky {position: sticky; top: 0; z-index: 999; background: #ffffff; padding: .65rem 0 .8rem; border-bottom: 1px solid #e6e8eb;}
.ccr-bar {height: 13px; display: flex; border-radius: 8px; overflow: hidden; background: #eef0f2;}
.ccr-segment {height: 100%;}
.ccr-card {border: 1px solid #e6e8eb; border-radius: 12px; padding: 1rem; background: white; margin-bottom: 1rem;}
.ccr-kpi {border: 1px solid #e6e8eb; border-radius: 10px; padding: .8rem; background: #fff;}
.ccr-kpi-label {font-size: .78rem; color: #667085;}
.ccr-kpi-value {font-size: 1.65rem; font-weight: 700; color: #17202a;}
.ccr-muted {color: #667085; font-size: .9rem;}
.ccr-row {padding: .45rem 0; border-bottom: 1px solid #f0f1f2;}
</style>""", unsafe_allow_html=True)


def render_progress(period: str) -> None:
    data = service.dashboard(period)
    summaries = data["summaries"]
    colors = {
        EstadoProceso.COMPLETADO: "#639922",
        EstadoProceso.EN_PROCESO: "#EF9F27",
        EstadoProceso.VENCIDO: "#E24B4A",
        EstadoProceso.BLOQUEADO: "#888780",
    }
    counts = {state: sum(s.estado == state for s in summaries) for state in colors}
    total = len(summaries)
    parts = "".join(f'<span class="ccr-segment" style="width:{counts[state] / total * 100:.2f}%;background:{color}"></span>' for state, color in colors.items())
    legend = " · ".join(f"{state.value}: {counts[state]}" for state in colors)
    st.markdown(f'<div class="ccr-sticky"><b>Avance alcanzado · {data["avance"]}%</b><div class="ccr-bar">{parts}</div><div class="ccr-muted">{legend}</div></div>', unsafe_allow_html=True)


def render_dashboard(period: str) -> None:
    data = service.dashboard(period)
    st.title("Tablero")
    st.caption(f"Resumen de procesos · periodo {period}")
    labels = (("Tareas pendientes", "pending"), ("Tareas vencidas", "overdue"), ("Procesos bloqueados", "blocked"), ("Procesos críticos", "critical"), ("SOX pendientes", "sox"), ("Aprobaciones pendientes", "approvals"))
    cols = st.columns(6)
    for col, (label, key) in zip(cols, labels):
        with col:
            st.markdown(f'<div class="ccr-kpi"><div class="ccr-kpi-label">{label}</div><div class="ccr-kpi-value">{data["kpis"][key]}</div></div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        st.subheader("Estado de procesos")
        for summary in data["summaries"]:
            st.markdown(f'<div class="ccr-row"><b>{summary.proceso.icono} {summary.proceso.nombre}</b><br><span style="color:{summary.proceso.color}">{summary.estado.value}</span> · {summary.completadas}/{summary.total} subtareas</div>', unsafe_allow_html=True)
    with right:
        st.subheader("Panel de alertas")
        if not data["alerts"]:
            st.success("No hay alertas derivadas del estado actual.")
        for alert in data["alerts"]:
            st.warning(f"**{alert.titulo}** · {alert.descripcion}")
    a, b, c = st.columns(3)
    with a:
        st.subheader("Pendientes de hoy")
        st.info("Las tareas no completadas del periodo activo.")
    with b:
        st.subheader("Próximos masivos")
        st.info("Sin scheduler en esta fase.")
    with c:
        st.subheader("Próximos vencimientos")
        st.info("Se muestran al configurar programación.")


def render_process(period: str, code: str, readonly: bool = False) -> None:
    process = proceso_por_codigo(code)
    summary = next(s for s in service.dashboard(period)["summaries"] if s.proceso.codigo == code)
    st.title(f"{process.icono} {process.nombre}")
    st.caption(f"Periodo {period} · {summary.estado.value} · {summary.completadas}/{summary.total} tareas")
    if readonly:
        st.warning("Periodo histórico: consulta de solo lectura.")
    st.info(process.descripcion)
    with st.expander("Qué hay que hacer", expanded=True):
        st.write(process.descripcion)
    with st.expander("Cómo se hace", expanded=True):
        for index, step in enumerate(process.guia, 1):
            st.write(f"{index}. {step}")
    st.subheader("Tareas")
    for task in process.tareas:
        current = task.completada
        value = st.checkbox(f"{task.nombre}{' · SOX' if task.sox else ''}{' · requiere aprobación' if task.requiere_aprobacion else ''}", value=current, key=f"{period}:{code}:{task.id}", disabled=readonly)
        if value != current:
            repo.set_task(period, code, task.id, value)
            st.rerun()
    st.subheader("Programación y notificaciones")
    saved = repo.schedule(period, code)
    with st.form(f"schedule-{period}-{code}"):
        scheduled_at = st.datetime_input("Fecha y hora", value=datetime.fromisoformat(saved["scheduled_at"]) if saved else datetime.now())
        recipients = st.text_input("Destinatarios (correos separados por coma)", value=saved["recipients"] if saved else "")
        channels = st.multiselect("Canales", ["Teams", "Correo"], default=saved["channels"].split(",") if saved else ["Teams"])
        if st.form_submit_button("Guardar programación", disabled=readonly):
            try:
                emails = validar_destinatarios(recipients)
                if not channels:
                    raise ValueError("Seleccione al menos un canal.")
                repo.save_schedule(period, code, scheduled_at.isoformat(), ", ".join(emails), ", ".join(channels))
                NotificationService(repo).schedule(Notification(code, period, "programacion", f"Notificación programada para {process.nombre}", emails, ", ".join(channels), scheduled_at.isoformat()))
                st.success("Programación guardada y registrada en historial simulado.")
            except ValueError as error:
                st.error(str(error))
    history = repo.notification_history(period, code)
    if history:
        with st.expander("Historial simulado"):
            for event in history:
                st.write(f"{event['created_at']} · {event['payload']}")


with st.sidebar:
    st.title("CCR")
    selected_period = st.selectbox("Periodo", periods or [period_default], index=0)
    selected = st.radio("Navegación", ["TABLERO"] + [p.nombre.upper() for p in PROCESOS], index=0)
    st.caption("Los periodos anteriores se consultan en modo lectura recomendado.")

render_progress(selected_period)
if selected == "TABLERO":
    render_dashboard(selected_period)
else:
    render_process(selected_period, next(p.codigo for p in PROCESOS if p.nombre.upper() == selected), readonly=selected_period != period_default)