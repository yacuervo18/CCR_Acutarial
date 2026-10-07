import streamlit as st
from datetime import datetime, time
from html import escape
import json
from pathlib import Path

from src.phase1.config import PROCESOS, proceso_por_codigo
from src.phase1.domain import EstadoProceso
from src.phase1.notifications import NotificationService, parse_destinatarios
from src.phase1.repository import Repository
from src.phase1.service import ProcessService

st.set_page_config(page_title="Centro de control y gestión Actuarial", layout="wide", initial_sidebar_state="expanded")


@st.cache_resource
def get_repository() -> Repository:
    return Repository()


repo = get_repository()
service = ProcessService(repo)
period_default = datetime.now().strftime("%Y-%m")
repo.ensure_period(period_default)
periods = repo.periods()

st.markdown("""<style>
.block-container {padding: .65rem 1.5rem 1rem; max-width: 1500px;}
.ccr-dashboard-title {font-size: 1.45rem; font-weight: 650; line-height: 1.2; margin: .35rem 0 .1rem;}
.ccr-dashboard-caption {font-size: .75rem; color: #667085; margin-bottom: .55rem;}
.ccr-dashboard [data-testid="stHorizontalBlock"] {gap: .7rem;}
.ccr-dashboard [data-testid="column"] {padding: 0;}
.ccr-sticky {position: sticky; top: 0; z-index: 999; background: #ffffff; padding: .65rem 0 .8rem; border-bottom: 1px solid #e6e8eb;}
.ccr-bar {height: 13px; display: flex; border-radius: 8px; overflow: hidden; background: #eef0f2;}
.ccr-segment {height: 100%;}
.ccr-muted {color: #667085; font-size: .72rem;}
.ccr-kpi {min-height: 78px; box-sizing: border-box; border: 1px solid #e8e8e6; border-radius: 10px; padding: .55rem .45rem; background: #f8f8f7; text-align: center;}
.ccr-kpi-label {font-size: .71rem; line-height: 1.2; color: #626262; min-height: 1.7em;}
.ccr-kpi-value {font-size: 1.45rem; line-height: 1.25; font-weight: 500; color: #252525; margin-top: .2rem;}
.ccr-kpi-value--danger {color: #c83232;}
.ccr-kpi-value--warning {color: #9b5b00;}
.ccr-panel {border: 1px solid #dededc; border-radius: 12px; padding: .7rem .85rem; background: #fff; min-height: 306px; box-sizing: border-box;}
.ccr-panel-header {font-size: .95rem; font-weight: 600; text-align: right; color: #303030; padding-bottom: .5rem; border-bottom: 1px solid #dededc;}
.ccr-panel-header--left {text-align: left;}
.ccr-process-row {display: flex; align-items: center; gap: .55rem; min-height: 38px; border-bottom: 1px solid #dededc; font-size: .82rem;}
.ccr-process-row:last-child {border-bottom: 0;}
.ccr-status-dot {width: 10px; height: 10px; flex: 0 0 10px; border-radius: 50%;}
.ccr-process-name {flex: 1; color: #373737; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.ccr-process-state {font-size: .75rem; white-space: nowrap;}
.ccr-alert-row {padding: .62rem 0 .62rem .2rem; border-bottom: 1px solid #dededc;}
.ccr-alert-row:last-child {border-bottom: 0;}
.ccr-alert-title {font-size: .84rem; color: #373737; font-weight: 500;}
.ccr-alert-description {font-size: .73rem; color: #747474; margin-top: .18rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.ccr-bottom-panel {border: 1px solid #dededc; border-radius: 12px; padding: .7rem .85rem; background: #fff; min-height: 108px; box-sizing: border-box;}
.ccr-bottom-row {display: flex; justify-content: space-between; gap: .5rem; padding: .52rem 0; border-top: 1px solid #dededc; font-size: .8rem;}
.ccr-bottom-row:first-child {margin-top: .45rem;}
.ccr-bottom-date {color: #686868; white-space: nowrap;}
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


def render_dashboard(period: str, reminders: list) -> None:
    data = service.dashboard(period)
    st.markdown('<div class="ccr-dashboard">', unsafe_allow_html=True)
    st.markdown('<div class="ccr-dashboard-title">Tablero</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ccr-dashboard-caption">Resumen de procesos · periodo {escape(period)}</div>', unsafe_allow_html=True)
    labels = (("Tareas pendientes", "pending"), ("Tareas vencidas", "overdue"), ("Procesos bloqueados", "blocked"), ("Procesos críticos", "critical"), ("SOX pendientes", "sox"), ("Aprobaciones pendientes", "approvals"))
    cols = st.columns(6)
    warning_keys = {"overdue": "ccr-kpi-value--danger", "critical": "ccr-kpi-value--warning"}
    for col, (label, key) in zip(cols, labels):
        with col:
            value_class = warning_keys.get(key, "")
            st.markdown(f'<div class="ccr-kpi"><div class="ccr-kpi-label">{label}</div><div class="ccr-kpi-value {value_class}">{data["kpis"][key]}</div></div>', unsafe_allow_html=True)
    st.markdown('<div style="height:.7rem"></div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        process_rows = []
        for summary in data["summaries"]:
            process_rows.append(
                f'<div class="ccr-process-row"><span class="ccr-status-dot" style="background:{summary.proceso.color}"></span>'
                f'<span class="ccr-process-name">{escape(summary.proceso.nombre)}</span>'
                f'<span class="ccr-process-state" style="color:{summary.proceso.color}">{escape(summary.estado.value)} · {summary.completadas}/{summary.total} subtareas</span></div>'
            )
        st.markdown(f'<div class="ccr-panel"><div class="ccr-panel-header">Estado de procesos</div>{"".join(process_rows)}</div>', unsafe_allow_html=True)
    with right:
        alert_rows = []
        if not data["alerts"]:
            alert_rows.append('<div class="ccr-alert-row"><div class="ccr-alert-title">Sin alertas activas</div><div class="ccr-alert-description">No hay alertas derivadas del estado actual.</div></div>')
        for alert in data["alerts"]:
            alert_rows.append(f'<div class="ccr-alert-row"><div class="ccr-alert-title">{escape(alert.titulo)}</div><div class="ccr-alert-description">{escape(alert.descripcion)}</div></div>')
        for reminder in reminders:
            alert_rows.append(f'<div class="ccr-alert-row"><div class="ccr-alert-title">Recordatorio · {escape(reminder.proceso)}</div><div class="ccr-alert-description">{escape(reminder.mensaje)}</div></div>')
        st.markdown(f'<div class="ccr-panel"><div class="ccr-panel-header">Panel de alertas</div>{"".join(alert_rows)}</div>', unsafe_allow_html=True)
    st.markdown('<div style="height:.7rem"></div>', unsafe_allow_html=True)
    a, b, c = st.columns(3)
    with a:
        st.markdown('<div class="ccr-bottom-panel"><div class="ccr-panel-header">Pendientes de hoy</div><div class="ccr-bottom-row"><span>Revisar tareas del periodo activo</span><span class="ccr-bottom-date">Hoy</span></div></div>', unsafe_allow_html=True)
    with b:
        st.markdown('<div class="ccr-bottom-panel"><div class="ccr-panel-header">Próximos masivos</div><div class="ccr-bottom-row"><span>Sin scheduler en esta fase</span><span class="ccr-bottom-date">—</span></div></div>', unsafe_allow_html=True)
    with c:
        st.markdown('<div class="ccr-bottom-panel"><div class="ccr-panel-header">Próximos vencimientos</div><div class="ccr-bottom-row"><span>Se muestran al configurar programación</span><span class="ccr-bottom-date">—</span></div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


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
    saved = repo.process_schedule(code)
    saved_months = json.loads(saved["months"]) if saved else list(range(1, 13))
    saved_recipients = json.loads(saved["recipients"]) if saved else []
    recipient_text = "\n".join(f"{item['label']} | {item['value']}" for item in saved_recipients)
    with st.form(f"schedule-{period}-{code}"):
        schedule_date = st.date_input("Fecha de inicio", value=datetime.now().date(), disabled=readonly)
        schedule_time = st.time_input("Hora del recordatorio", value=time.fromisoformat(saved["scheduled_time"]) if saved else time(8, 0), disabled=readonly)
        month_mode = st.radio("Aplicación", ["Todos los meses", "Seleccionar meses"], index=0 if saved_months == list(range(1, 13)) else 1, horizontal=True, disabled=readonly)
        month_options = list(range(1, 13))
        months = st.multiselect("Meses en los que se recordará", month_options, default=saved_months, format_func=lambda month: datetime(2000, month, 1).strftime("%B").capitalize(), disabled=readonly) if month_mode == "Seleccionar meses" else month_options
        frequency = st.selectbox("Frecuencia de revisión", [("Al abrir la aplicación", 1440), ("Cada 30 minutos", 30), ("Cada hora", 60), ("Cada 2 horas", 120)], format_func=lambda item: item[0], index=next((i for i, item in enumerate([("Al abrir la aplicación", 1440), ("Cada 30 minutos", 30), ("Cada hora", 60), ("Cada 2 horas", 120)]) if saved and item[1] == saved["interval_minutes"]), 0), disabled=readonly)
        recipients = st.text_area("Destinatarios de Teams (una línea por persona: Nombre | correo o identificador)", value=recipient_text, placeholder="Carlos | carlos@empresa.com", disabled=readonly)
        if st.form_submit_button("Guardar programación", disabled=readonly):
            try:
                if not months:
                    raise ValueError("Seleccione al menos un mes.")
                parsed_recipients = parse_destinatarios(recipients)
                repo.save_process_schedule(code, schedule_date.isoformat(), schedule_time.strftime("%H:%M"), months, frequency[1], parsed_recipients)
                st.success("Programación de Teams guardada correctamente.")
            except ValueError as error:
                st.error(str(error))
    history = repo.notification_history(period, code)
    if history:
        with st.expander("Historial simulado"):
            for event in history:
                st.write(f"{event['created_at']} · {event['payload']}")


with st.sidebar:
    logo_path = Path(__file__).resolve().parents[1] / "LogoSura_sinFondo.png"
    if logo_path.exists():
        st.image(str(logo_path), width=150)
    st.title("Centro de control y gestión Actuarial")
    selected_period = st.selectbox("Periodo", periods or [period_default], index=0)
    selected = st.radio("Navegación", ["TABLERO"] + [p.nombre.upper() for p in PROCESOS], index=0)
    st.caption("Los periodos anteriores se consultan en modo lectura recomendado.")

if "daily_reminders" not in st.session_state or st.session_state.get("daily_reminders_period") != selected_period:
    reminders = service.daily_reminders(selected_period)
    for reminder in reminders:
        NotificationService(repo).send_daily_reminder(reminder)
    st.session_state["daily_reminders"] = reminders
    st.session_state["daily_reminders_period"] = selected_period
else:
    reminders = st.session_state["daily_reminders"]

render_progress(selected_period)
if selected == "TABLERO":
    render_dashboard(selected_period, reminders)
else:
    render_process(selected_period, next(p.codigo for p in PROCESOS if p.nombre.upper() == selected), readonly=selected_period != period_default)