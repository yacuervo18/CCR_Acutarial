import streamlit as st
from datetime import datetime, time
from html import escape
import json
from pathlib import Path
from urllib.parse import urlparse

from src.phase1.config import PROCESOS, proceso_por_codigo
from src.phase1.content import delete_videos, load_process_content, save_uploaded_video
from src.phase1.domain import EstadoProceso
from src.phase1.notifications import NotificationService, parse_destinatarios
from src.phase1.repository import Repository
from src.phase1.service import ProcessService

page_icon_path = Path(__file__).resolve().parents[1] / "Icono_Sura.png"
st.set_page_config(
    page_title="Centro de control y gestión Actuarial",
    page_icon=str(page_icon_path),
    layout="wide",
    initial_sidebar_state="expanded",
)


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
:root {--nav-bg: #0B4F9E; --nav-hover: #1E78D6; --nav-active: #2F8BE6; --nav-text: #FFFFFF; --nav-divider: rgba(255,255,255,.10);}
.stApp [data-testid="stSidebar"] {background: var(--nav-bg);}
.stApp [data-testid="stSidebar"] > div:first-child {background: var(--nav-bg);}
.stApp [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {color: #ffffff;}
.stApp [data-testid="stSidebar"] h1 {color: #ffffff; font-size: 1.05rem; line-height: 1.2;}
.st-key-ccr-nav-container {box-sizing: border-box; width: calc(100% + 2rem) !important; margin: .35rem -1rem 0 !important; padding: 0 !important; overflow: visible;}
.st-key-ccr-nav-container > div {width: 100% !important; max-width: none !important;}
.st-key-ccr-nav-container [data-testid="stButton"] {box-sizing: border-box; width: 100% !important; max-width: none !important; margin: 0; padding: 0; border-top: .5px solid var(--nav-divider);}
.st-key-ccr-nav-container [data-testid="stButton"]:last-child {border-bottom: .5px solid var(--nav-divider);}
.st-key-ccr-nav-container [data-testid^="stBaseButton-"] {box-sizing: border-box; width: 100%; height: 46px; padding: 0 1rem; border: 0; border-radius: 0; color: var(--nav-text); background: var(--nav-bg); text-transform: uppercase; font-size: 13px; font-weight: 500; letter-spacing: .02em; line-height: 1.1; transition: background-color 150ms ease; text-align: left;}
.st-key-ccr-nav-container [data-testid="stButton"] > div {width: 100%;}
.st-key-ccr-nav-container [data-testid="stButton"] button > div {display: flex; width: 100%; justify-content: flex-start; align-items: center;}
.st-key-ccr-nav-container [data-testid="stButton"] button p {width: 100%; text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.st-key-ccr-nav-container [data-testid="stBaseButton-secondary"]:hover {background: var(--nav-hover); color: var(--nav-text);}
.st-key-ccr-nav-container [data-testid="stBaseButton-primary"] {background: var(--nav-active); border-left: 4px solid var(--nav-text); padding-left: calc(1rem - 4px);}
.st-key-ccr-nav-container [data-testid="stBaseButton-primary"]:hover {background: var(--nav-active);}
.st-key-ccr-nav-container [data-testid^="stBaseButton-"]:focus-visible {outline: 2px solid var(--nav-text); outline-offset: -3px;}
.stApp [data-testid="stSidebar"] [data-testid="stButton"] button {font-size: .72rem; padding: .25rem .55rem; min-height: 0; border-color: rgba(255,255,255,.65); color: #07529a; background: #ffffff;}
.stApp [data-testid="stSidebar"] .st-key-ccr-nav-container [data-testid="stButton"] button,
.stApp [data-testid="stSidebar"] .st-key-ccr-nav-container [data-testid="stButton"] button p {box-sizing: border-box; width: 100%; min-height: 46px; margin: 0; padding: 0 1rem; border: 0; border-radius: 0; color: var(--nav-text) !important; background: var(--nav-bg) !important; font-size: 13px; font-weight: 500; letter-spacing: .02em; line-height: 46px; text-align: left; text-transform: uppercase;}
.stApp [data-testid="stSidebar"] .st-key-ccr-nav-container [data-testid="stButton"] button > div {padding: 0; justify-content: flex-start;}
.stApp [data-testid="stSidebar"] .st-key-ccr-nav-container [data-testid="stButton"] button p {padding: 0; text-align: left;}
.stApp [data-testid="stSidebar"] .st-key-ccr-nav-container [data-testid="stButton"] button:hover,
.stApp [data-testid="stSidebar"] .st-key-ccr-nav-container [data-testid="stButton"] button:hover p {color: var(--nav-text) !important; background: var(--nav-hover) !important;}
.stApp [data-testid="stSidebar"] .st-key-ccr-nav-container [data-testid="stBaseButton-primary"] button,
.stApp [data-testid="stSidebar"] .st-key-ccr-nav-container [data-testid="stBaseButton-primary"] button p {background: var(--nav-active) !important; border-left: 4px solid var(--nav-text); padding-left: calc(1rem - 4px);}
.stApp [data-testid="stSidebar"] .st-key-ccr-nav-container [data-testid="stBaseButton-primary"] button:hover,
.stApp [data-testid="stSidebar"] .st-key-ccr-nav-container [data-testid="stBaseButton-primary"] button:hover p {background: var(--nav-active) !important;}
.st-key-ccr-reset-container [data-testid="stButton"] button,
.st-key-ccr-reset-container [data-testid="stButton"] button p {color: #07529a !important; background: #ffffff !important;}
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
.ccr-process-extension {border: 1px solid #dededc; border-radius: 12px; padding: .85rem; background: #f8fafc; min-height: 146px; box-sizing: border-box;}
.ccr-process-extension-title {font-size: .95rem; font-weight: 650; color: #303030; margin-bottom: .35rem;}
.ccr-process-extension-copy {font-size: .78rem; color: #667085; line-height: 1.4; margin-bottom: .75rem;}
.st-key-motor-f394-launcher [data-testid="stLinkButton"] a {background: #f2c94c; border-color: #d9ad1e; color: #3f3200; font-weight: 650;}
.st-key-motor-f394-launcher [data-testid="stLinkButton"] a:hover {background: #e8bb32; border-color: #c79d12; color: #3f3200;}
.ccr-content-card {border: 1px solid #dededc; border-radius: 12px; padding: .8rem; background: #fff; min-height: 150px;}
.ccr-content-card-header {font-size: .95rem; font-weight: 650; color: #303030; margin-bottom: .55rem;}
.ccr-edit-button [data-testid="stButton"] button {min-width: 2rem; width: 2rem; height: 2rem; padding: 0; border: 1px solid #c9c9c7; border-radius: 6px; color: #4b5563; background: #fff;}
.ccr-edit-button [data-testid="stButton"] button:hover {border-color: #185FA5; color: #185FA5; background: #f5f9ff;}
.ccr-important-card {border: 1px solid #f2c5c5; border-radius: 12px; padding: .8rem; background: #fff1f1; color: #b42318; min-height: 84px; box-sizing: border-box;}
.ccr-important-card .ccr-content-card-header {color: #b42318;}
.ccr-important-card .ccr-muted {color: #b42318; opacity: .72;}
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


MOTOR_F394_URL = "http://127.0.0.1:8502"


def render_process_extension(code: str) -> bool:
    if code != "f394":
        return False
    st.markdown(
        '<div class="ccr-process-extension">'
        '<div class="ccr-process-extension-title">Motor F394</div>'
        '<div class="ccr-process-extension-copy">'
        "Accede al Motor F394 para realizar descargas, validaciones y correcciones. "
        "Las tareas de CCR se marcan manualmente al finalizar."
        "</div></div>",
        unsafe_allow_html=True,
    )
    with st.container(key="motor-f394-launcher"):
        st.link_button("Abrir Motor F394", MOTOR_F394_URL, use_container_width=True)
    return True


def render_process_tasks(process, period: str, code: str, readonly: bool) -> None:
    for task in process.tareas:
        current = task.completada
        value = st.checkbox(f"{task.nombre}{' · SOX' if task.sox else ''}{' · requiere aprobación' if task.requiere_aprobacion else ''}", value=current, key=f"{period}:{code}:{task.id}", disabled=readonly)
        if value != current:
            repo.set_task(period, code, task.id, value)
            st.rerun()


def render_task_management(code: str, readonly: bool) -> None:
    edit_key = f"edit-process-tasks-{code}"
    task_header, task_edit = st.columns([1, 0.08], vertical_alignment="center")
    with task_header:
        st.markdown('<div class="ccr-content-card-header">Tareas</div>', unsafe_allow_html=True)
    with task_edit:
        st.markdown('<div class="ccr-edit-button">', unsafe_allow_html=True)
        if st.button("✎", key=f"{edit_key}-button", disabled=readonly, help="Editar tareas del proceso"):
            st.session_state[edit_key] = True
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get(edit_key, False) and not readonly:
        st.caption("Los cambios aplican al catálogo del proceso y actualizan los contadores. Las marcas históricas no se eliminan.")
        task_rows = repo.process_tasks(code)
        task_options = {row["task_id"]: row["name"] for row in task_rows}
        selected_id = st.selectbox(
            "Tarea a editar o quitar",
            options=[None, *task_options],
            format_func=lambda value: "Seleccione una tarea" if value is None else task_options[value],
            key=f"task-selected-{code}",
        )
        if selected_id is not None:
            selected = next(row for row in task_rows if row["task_id"] == selected_id)
            with st.form(f"edit-task-form-{code}"):
                name = st.text_input("Nombre", value=selected["name"])
                sox = st.checkbox("Control SOX", value=bool(selected["sox"]))
                requires_approval = st.checkbox("Requiere aprobación", value=bool(selected["requires_approval"]))
                save, remove = st.columns(2)
                with save:
                    save_task = st.form_submit_button("Guardar cambios")
                with remove:
                    remove_task = st.form_submit_button("Quitar tarea")
                if save_task:
                    try:
                        repo.update_process_task(code, selected_id, name, sox, requires_approval)
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        st.rerun()
                if remove_task:
                    st.session_state[f"confirm-remove-task-{code}"] = selected_id
                    st.rerun()
            if st.session_state.get(f"confirm-remove-task-{code}") == selected_id:
                st.warning(f"Confirme que desea quitar “{selected['name']}”.")
                confirm, cancel = st.columns(2)
                with confirm:
                    if st.button("Confirmar", key=f"confirm-remove-{code}"):
                        repo.deactivate_process_task(code, selected_id)
                        st.session_state.pop(f"confirm-remove-task-{code}", None)
                        st.rerun()
                with cancel:
                    if st.button("Cancelar", key=f"cancel-remove-{code}"):
                        st.session_state.pop(f"confirm-remove-task-{code}", None)
                        st.rerun()
        with st.form(f"add-task-form-{code}"):
            st.markdown("**Agregar tarea**")
            new_name = st.text_input("Nombre de la nueva tarea", key=f"new-task-name-{code}")
            new_sox = st.checkbox("Control SOX", key=f"new-task-sox-{code}")
            new_approval = st.checkbox("Requiere aprobación", key=f"new-task-approval-{code}")
            if st.form_submit_button("Agregar tarea"):
                try:
                    repo.add_process_task(code, new_name, new_sox, new_approval)
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.rerun()
        if st.button("Cerrar edición", key=f"{edit_key}-close"):
            st.session_state[edit_key] = False
            st.rerun()


def render_text_content_card(code: str, content, readonly: bool) -> None:
    edit_key = f"edit-content-text-{code}"
    text_header, text_edit = st.columns([1, 0.08], vertical_alignment="center")
    with text_header:
        st.markdown('<div class="ccr-content-card-header">Qué hay que hacer</div>', unsafe_allow_html=True)
    with text_edit:
        st.markdown('<div class="ccr-edit-button">', unsafe_allow_html=True)
        if st.button("✎", key=f"{edit_key}-button", disabled=readonly, help="Editar texto"):
            st.session_state[edit_key] = True
        st.markdown("</div>", unsafe_allow_html=True)
    if st.session_state.get(edit_key, False) and not readonly:
        with st.form(f"{edit_key}-form"):
            text_value = st.text_area("Texto", value=content.what_to_do, height=120, label_visibility="collapsed")
            save, cancel = st.columns(2)
            with save:
                save_text = st.form_submit_button("Guardar")
            with cancel:
                cancel_text = st.form_submit_button("Cancelar")
            if cancel_text:
                st.session_state[edit_key] = False
                st.rerun()
            if save_text:
                cleaned_text = text_value.strip()
                if not cleaned_text:
                    st.error("El texto de “Qué hay que hacer” no puede estar vacío.")
                else:
                    repo.save_process_content(code, cleaned_text, content.manual_url or "", content.important_note)
                    st.session_state[edit_key] = False
                    st.rerun()
    else:
        st.write(content.what_to_do)

def render_video_content_card(code: str, content, readonly: bool) -> None:
    edit_key = f"edit-content-video-{code}"
    video_header, video_edit = st.columns([1, 0.08], vertical_alignment="center")
    with video_header:
        st.markdown('<div class="ccr-content-card-header">Video explicativo</div>', unsafe_allow_html=True)
    with video_edit:
        st.markdown('<div class="ccr-edit-button">', unsafe_allow_html=True)
        if st.button("✎", key=f"{edit_key}-button", disabled=readonly, help="Administrar video"):
            st.session_state[edit_key] = True
        st.markdown("</div>", unsafe_allow_html=True)
    if content.video_path:
        st.video(str(content.video_path))
    else:
        st.info("Aún no hay un video cargado para este proceso.")
    if st.session_state.get(edit_key, False):
        with st.form(f"{edit_key}-form"):
            uploaded_video = st.file_uploader(
                "Cargar o reemplazar video",
                type=["mp4", "webm", "mov"],
                help="Formatos permitidos: MP4, WebM y MOV. Tamaño máximo: 200 MB.",
            )
            save_video = st.form_submit_button("Guardar video")
            if save_video:
                if uploaded_video is None:
                    st.error("Seleccione un video antes de guardar.")
                else:
                    try:
                        save_uploaded_video(code, uploaded_video)
                    except (OSError, ValueError) as error:
                        st.error(str(error))
                    else:
                        st.session_state[edit_key] = False
                        st.rerun()
        if content.video_path:
            confirm_delete = st.checkbox(
                "Confirmo que deseo eliminar el video de este proceso.",
                key=f"{edit_key}-confirm-delete",
            )
            if st.button("Eliminar video", key=f"{edit_key}-delete", disabled=not confirm_delete):
                try:
                    delete_videos(code)
                except OSError as error:
                    st.error(f"No se pudo eliminar el video: {error}")
                else:
                    st.session_state[edit_key] = False
                    st.rerun()
        if st.button("Cerrar", key=f"{edit_key}-close"):
            st.session_state[edit_key] = False
            st.rerun()

def render_manual_content_card(code: str, content, readonly: bool) -> None:
    edit_key = f"edit-content-manual-{code}"
    manual_header, manual_edit = st.columns([1, 0.08], vertical_alignment="center")
    with manual_header:
        st.markdown('<div class="ccr-content-card-header">Manual sugerido</div>', unsafe_allow_html=True)
    with manual_edit:
        st.markdown('<div class="ccr-edit-button">', unsafe_allow_html=True)
        if st.button("✎", key=f"{edit_key}-button", disabled=readonly, help="Editar manual"):
            st.session_state[edit_key] = True
        st.markdown("</div>", unsafe_allow_html=True)
    if st.session_state.get(edit_key, False) and not readonly:
        with st.form(f"{edit_key}-form"):
            manual_value = st.text_input("Enlace", value=content.manual_url or "", placeholder="https://...", label_visibility="collapsed")
            save, cancel = st.columns(2)
            with save:
                save_manual = st.form_submit_button("Guardar")
            with cancel:
                cancel_manual = st.form_submit_button("Cancelar")
            if cancel_manual:
                st.session_state[edit_key] = False
                st.rerun()
            if save_manual:
                cleaned_url = manual_value.strip()
                if cleaned_url and urlparse(cleaned_url).scheme not in {"http", "https"}:
                    st.error("El enlace del manual debe comenzar por http:// o https://.")
                else:
                    repo.save_process_content(code, content.what_to_do, cleaned_url, content.important_note)
                    st.session_state[edit_key] = False
                    st.rerun()
    elif content.manual_url:
        st.link_button("Ver manual sugerido", content.manual_url, use_container_width=True)
    else:
        st.info("Aún no hay un manual configurado para este proceso.")

def render_important_content_card(code: str, content, readonly: bool) -> None:
    edit_key = f"edit-content-important-{code}"
    header, edit = st.columns([1, 0.08], vertical_alignment="center")
    with header:
        st.markdown('<div class="ccr-content-card-header">Importante</div>', unsafe_allow_html=True)
    with edit:
        st.markdown('<div class="ccr-edit-button">', unsafe_allow_html=True)
        if st.button("✎", key=f"{edit_key}-button", disabled=readonly, help="Editar observación importante"):
            st.session_state[edit_key] = True
        st.markdown("</div>", unsafe_allow_html=True)
    if st.session_state.get(edit_key, False) and not readonly:
        with st.form(f"{edit_key}-form"):
            note_value = st.text_area(
                "Observación importante",
                value=content.important_note,
                height=100,
                placeholder="Escriba una observación importante del proceso.",
                label_visibility="collapsed",
            )
            save, cancel = st.columns(2)
            with save:
                save_note = st.form_submit_button("Guardar")
            with cancel:
                cancel_note = st.form_submit_button("Cancelar")
            if cancel_note:
                st.session_state[edit_key] = False
                st.rerun()
            if save_note:
                repo.save_process_content(code, content.what_to_do, content.manual_url or "", note_value.strip())
                st.session_state[edit_key] = False
                st.rerun()
    elif content.important_note:
        st.markdown(f'<div>{escape(content.important_note).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="ccr-muted">No hay una observación importante configurada.</div>', unsafe_allow_html=True)


def render_process(period: str, code: str, readonly: bool = False) -> None:
    process_definition = proceso_por_codigo(code)
    stored_content = repo.process_content(code)
    stored_content_values = dict(stored_content) if stored_content else None
    summary = next(s for s in service.dashboard(period)["summaries"] if s.proceso.codigo == code)
    process = summary.proceso
    content = load_process_content(code, process_definition.descripcion, stored_content_values)
    st.title(process.nombre)
    st.caption(f"Periodo {period} · {summary.estado.value} · {summary.completadas}/{summary.total} tareas")
    if readonly:
        st.warning("Periodo histórico: consulta de solo lectura.")
    with st.container(key=f"content-card-description-{code}"):
        render_text_content_card(code, content, readonly)
    with st.expander("Cómo se hace", expanded=True):
        video_column, manual_column = st.columns(2, gap="large")
        with video_column:
            with st.container(key=f"content-card-video-{code}"):
                render_video_content_card(code, content, readonly)
        with manual_column:
            with st.container(key=f"content-card-manual-{code}"):
                render_manual_content_card(code, content, readonly)
    with st.container(key=f"content-card-important-full-{code}"):
        render_important_content_card(code, content, readonly)
    if code == "f394":
        tasks_column, extension_column = st.columns([1, 1], gap="large")
        with tasks_column:
            render_task_management(code, readonly)
            render_process_tasks(process, period, code, readonly)
        with extension_column:
            st.subheader("Espacio del proceso")
            render_process_extension(code)
    else:
        render_task_management(code, readonly)
        render_process_tasks(process, period, code, readonly)
    st.subheader("Programación y notificaciones")
    saved = repo.process_schedule(code, period)
    saved_months = json.loads(saved["months"]) if saved else list(range(1, 13))
    saved_recipients = json.loads(saved["recipients"]) if saved else []
    recipient_text = "\n".join(f"{item['label']} | {item['value']}" for item in saved_recipients)
    with st.expander("Configurar programación", expanded=not bool(saved)):
        with st.form(f"schedule-{period}-{code}"):
            scope = st.radio("Aplicar configuración", ["General: todos los meses", f"Excepción: {period}"], horizontal=True, disabled=readonly)
            schedule_date = st.date_input("Fecha de inicio", value=datetime.fromisoformat(saved["start_date"]).date() if saved and saved["start_date"] else datetime.now().date(), disabled=readonly)
            schedule_time = st.time_input("Hora", value=time.fromisoformat(saved["scheduled_time"]) if saved else time(8, 0), disabled=readonly)
            month_mode = st.radio("Meses", ["Todos", "Seleccionar"], index=0 if saved_months == list(range(1, 13)) else 1, horizontal=True, disabled=readonly)
            month_options = list(range(1, 13))
            months = month_options
            if month_mode == "Seleccionar":
                months = st.multiselect("Elegir meses", month_options, default=saved_months, format_func=lambda month: datetime(2000, month, 1).strftime("%b").capitalize(), disabled=readonly)
            frequency_options = [("Al abrir la aplicación", 1440), ("Cada 30 minutos", 30), ("Cada hora", 60), ("Cada 2 horas", 120)]
            frequency = st.selectbox("Frecuencia", frequency_options, format_func=lambda item: item[0], index=next((i for i, item in enumerate(frequency_options) if saved and item[1] == saved["interval_minutes"]), 0), disabled=readonly)
            recipients = st.text_area("Destinatarios Teams (Nombre | correo o identificador)", value=recipient_text, placeholder="Carlos | carlos@empresa.com", height=72, disabled=readonly)
            if st.form_submit_button("Guardar programación", disabled=readonly):
                try:
                    if not months:
                        raise ValueError("Seleccione al menos un mes.")
                    parsed_recipients = parse_destinatarios(recipients)
                    repo.save_process_schedule(code, schedule_date.isoformat(), schedule_time.strftime("%H:%M"), months, frequency[1], parsed_recipients, period if scope.startswith("Excepción") else None)
                    st.success("Programación guardada correctamente.")
                except ValueError as error:
                    st.error(str(error))
    history = repo.notification_history(period, code)
    if history:
        with st.expander("Historial simulado"):
            for event in history:
                st.write(f"{event['created_at']} · {event['payload']}")


nav_items = [
    ("TABLERO", "TABLERO"),
    ("RENTABILIDADES", "RENTABILIDADES"),
    ("ÍNDICES Y MONEDAS", "ÍNDICES Y MONEDAS"),
    ("F394", "F394"),
    ("RESERVA DE SALARIO MÍNIMO", "RESERVA DE SALARIO MÍNIMO"),
    ("RESERVA SINIESTROS AVISADOS (RBNS)", "RSA"),
    ("RM LEY 100", "RM LEY 100"),
    ("RM CONMUTACIÓN", "RM CONMUTACIÓN"),
    ("RM ARL", "RM ARL"),
]
valid_navigation = {item[0] for item in nav_items}


def select_navigation(key: str) -> None:
    st.session_state["selected_navigation"] = key


if "selected_navigation" not in st.session_state:
    legacy_selected = st.query_params.get("nav", "TABLERO")
    st.session_state["selected_navigation"] = legacy_selected if legacy_selected in valid_navigation else "TABLERO"
    if "nav" in st.query_params:
        del st.query_params["nav"]
selected = st.session_state["selected_navigation"]

with st.sidebar:
    logo_path = Path(__file__).resolve().parents[1] / "LogoSura_blanco_transparente.png"
    if logo_path.exists():
        st.image(str(logo_path), width=150)
    st.title("Centro de control y gestión Actuarial")
    selected_period = st.selectbox("Periodo", periods or [period_default], index=0)
    with st.container(key="ccr-nav-container"):
        for key, label in nav_items:
            st.button(
                label,
                key=f"nav-{key}",
                type="primary" if key == selected else "secondary",
                use_container_width=True,
                on_click=select_navigation,
                args=(key,),
            )
    st.caption("Los periodos anteriores se consultan en modo lectura recomendado.")
    st.divider()
    with st.container(key="ccr-reset-container"):
        if st.button("Reiniciar tareas del periodo", use_container_width=True):
            st.session_state["confirm_reset_period"] = selected_period
        if st.session_state.get("confirm_reset_period") == selected_period:
            st.caption(f"Se reiniciarán las tareas de {selected_period}. La programación no cambia.")
            confirm_reset = st.checkbox("Confirmar reinicio", key=f"confirm-reset-{selected_period}")
            if confirm_reset and st.button("Confirmar", key=f"confirm-reset-button-{selected_period}", use_container_width=True):
                repo.reset_tasks(selected_period)
                for process in PROCESOS:
                    for task in process.tareas:
                        st.session_state.pop(f"{selected_period}:{process.codigo}:{task.id}", None)
                st.session_state.pop("confirm_reset_period", None)
                st.session_state.pop(f"confirm-reset-{selected_period}", None)
                st.rerun()

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