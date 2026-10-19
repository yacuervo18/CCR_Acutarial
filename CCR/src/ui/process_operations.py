"""Shared confirmation flow for process actions and Giru requests."""

from uuid import uuid4

import streamlit as st

from src.phase1.process_operation_contract import (
    PROCESS_OPERATION_BY_ID,
    OperationResult,
    ejecutar_operacion_confirmada,
)

_PENDING_OPERATION_KEY = "ccr_pending_process_operation"
_LAST_OPERATION_NOTICE_KEY = "ccr_last_process_operation_notice"

PROCESS_OPERATION_PANELS = {
    "rentabilidades": (
        "Acciones de Rentabilidades",
        (
            "rentabilidades.actualizar",
            "rentabilidades.copiar",
        ),
    ),
    "indices": (
        "Acciones de Índices y monedas",
        (
            "indices.extraer",
            "indices.actualizar_osiris",
            "indices.actualizar_archivos",
        ),
    ),
}


def get_pending_process_operation() -> dict | None:
    pending = st.session_state.get(_PENDING_OPERATION_KEY)
    return pending if isinstance(pending, dict) else None


def request_process_operation(
    identifier: str,
    origin: str,
    period: str | None,
) -> dict | None:
    operation = PROCESS_OPERATION_BY_ID.get(identifier)
    if operation is None:
        raise ValueError("La operación solicitada no está registrada.")
    if origin not in {"process", "giru"}:
        raise ValueError("El origen de la solicitud no está admitido.")
    if not period:
        raise ValueError("La solicitud debe asociarse a un periodo.")
    if not operation.requestable:
        return None

    pending = get_pending_process_operation()
    if pending and pending.get("status") == "awaiting_confirmation":
        return None

    request = {
        "request_id": uuid4().hex,
        "operation_id": identifier,
        "origin": origin,
        "period": period,
        "status": "awaiting_confirmation",
    }
    st.session_state[_PENDING_OPERATION_KEY] = request
    st.session_state.pop(_LAST_OPERATION_NOTICE_KEY, None)
    return request


def resolve_process_operation_request(
    request_id: str,
    confirm: bool,
) -> OperationResult:
    pending = get_pending_process_operation()
    if (
        pending is None
        or pending.get("request_id") != request_id
        or pending.get("status") != "awaiting_confirmation"
    ):
        raise ValueError("La solicitud ya no está pendiente de confirmación.")

    operation_id = pending["operation_id"]
    operation = PROCESS_OPERATION_BY_ID[operation_id]
    if confirm:
        result = ejecutar_operacion_confirmada(operation_id, pending["period"])
    else:
        result = OperationResult(
            "cancelled",
            f"Solicitud de «{operation.label}» cancelada; no se ejecutó ninguna acción.",
        )

    st.session_state.pop(_PENDING_OPERATION_KEY, None)
    st.session_state[_LAST_OPERATION_NOTICE_KEY] = {
        "operation_id": operation_id,
        "origin": pending["origin"],
        "status": result.status,
        "message": result.message,
    }
    return result


def _render_operation_notice(origin: str) -> None:
    notice = st.session_state.get(_LAST_OPERATION_NOTICE_KEY)
    if not isinstance(notice, dict) or notice.get("origin") != origin:
        return

    st.info(notice["message"])
    if st.button("Cerrar aviso", key=f"close-process-operation-notice-{origin}"):
        st.session_state.pop(_LAST_OPERATION_NOTICE_KEY, None)
        st.rerun()


def render_operation_confirmation(
    origin: str,
    current_period: str | None,
    readonly: bool = False,
) -> OperationResult | None:
    pending = get_pending_process_operation()
    if (
        pending is None
        or pending.get("origin") != origin
        or pending.get("status") != "awaiting_confirmation"
    ):
        return None

    operation = PROCESS_OPERATION_BY_ID[pending["operation_id"]]
    period_matches = pending["period"] == current_period
    confirmation_blocked = readonly or not period_matches or not operation.requestable
    if not period_matches:
        st.warning(
            f"Esta solicitud corresponde al periodo {pending['period']}. "
            "Selecciona ese periodo antes de confirmar."
        )
    st.warning(
        f"Solicitud: {operation.label}. {operation.confirmation_prompt}"
    )
    accept, reject = st.columns(2)
    with accept:
        confirm = st.button(
            "Confirmar solicitud",
            key=f"confirm-process-operation-{pending['request_id']}",
            disabled=confirmation_blocked,
            use_container_width=True,
        )
    with reject:
        cancel = st.button(
            "Cancelar",
            key=f"cancel-process-operation-{pending['request_id']}",
            use_container_width=True,
        )

    if confirm:
        return resolve_process_operation_request(pending["request_id"], True)
    if cancel:
        return resolve_process_operation_request(pending["request_id"], False)
    return None


def render_process_operation_workflow(
    current_process_code: str | None,
    current_period: str,
    readonly: bool,
) -> None:
    pending = get_pending_process_operation()
    if pending and pending.get("origin") == "process":
        operation = PROCESS_OPERATION_BY_ID[pending["operation_id"]]
        if operation.process_code != current_process_code:
            st.subheader("Confirmación pendiente")
            result = render_operation_confirmation(
                "process",
                current_period,
                readonly,
            )
            if result is not None:
                st.info(result.message)
                st.rerun()
                return
            _render_operation_notice("process")
            return

    notice = st.session_state.get(_LAST_OPERATION_NOTICE_KEY)
    if isinstance(notice, dict) and notice.get("origin") == "process":
        operation = PROCESS_OPERATION_BY_ID[notice["operation_id"]]
        if operation.process_code == current_process_code:
            return
    _render_operation_notice("process")


def render_process_operations(
    code: str,
    readonly: bool,
    period: str,
) -> bool:
    panel = PROCESS_OPERATION_PANELS.get(code)
    if panel is None:
        return False

    title, operation_ids = panel
    st.markdown(
        '<div class="ccr-process-extension">'
        f'<div class="ccr-process-extension-title">{title}</div>'
        '<div class="ccr-process-extension-copy">'
        "Las solicitudes requieren confirmación. Las operaciones se habilitarán "
        "cuando su implementación esté lista."
        "</div></div>",
        unsafe_allow_html=True,
    )
    pending = get_pending_process_operation()
    has_pending = bool(
        pending and pending.get("status") == "awaiting_confirmation"
    )
    with st.container(key=f"process-operations-{code}"):
        for identifier in operation_ids:
            operation = PROCESS_OPERATION_BY_ID[identifier]
            st.button(
                operation.label,
                key=f"{code}-{identifier.replace('.', '-')}",
                use_container_width=True,
                disabled=readonly or has_pending or not operation.requestable,
                help=(
                    "Los periodos históricos son de solo lectura."
                    if readonly
                    else operation.confirmation_prompt
                    if operation.requestable
                    else operation.unavailable_message
                ),
                on_click=request_process_operation,
                args=(identifier, "process", period),
            )

    pending = get_pending_process_operation()
    if pending and pending.get("origin") == "process":
        result = render_operation_confirmation(
            "process",
            period,
            readonly,
        )
        if result is not None:
            st.info(result.message)
            st.rerun()
        else:
            _render_operation_notice("process")
    else:
        _render_operation_notice("process")
    return True
