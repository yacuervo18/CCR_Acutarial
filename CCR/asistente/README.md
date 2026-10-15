# Asistente de CCR

El asistente es un módulo independiente con respuesta simulada. En esta fase no
se conecta a Copilot Studio, Teams, Power Automate ni a servicios externos.

## Cambiar el icono

Reemplace `../assets/asistente/Giru_logo.webp` por otro archivo con el mismo nombre,
o edite `icono_ruta` en `config.py`. Se admiten PNG, JPG/JPEG, SVG y WEBP.
Si el archivo falta o no se puede leer, el botón utiliza `icono_respaldo`.

## Cambiar apariencia y saludo

Edite `CONFIGURACION` en `config.py`:

- `nombre_asistente`: nombre mostrado en el chat.
- `icono_ruta` / `icono_respaldo`: imagen o emoji de respaldo.
- `tamano_icono_px`: diámetro del botón.
- `color_principal`: color hexadecimal del botón.
- `mensaje_bienvenida`: saludo inicial.
- `posicion`: `derecha` o `izquierda`.
- `ancho_ventana_px` / `alto_ventana_px`: tamaño máximo del panel.

Para desactivar por completo el asistente, cambie `ASISTENTE_ACTIVO` a `False`.

## Conexión futura

La integración futura se realizará en `conexion.py`, reemplazando la respuesta
simulada dentro de `enviar_pregunta()`. La decisión entre iframe y Direct Line
queda pendiente. Los datos de configuración, como endpoint y credenciales,
deberán leerse en el servidor desde `st.secrets`; nunca se deben guardar tokens
en el repositorio ni exponerlos al navegador.

El registro de errores solo guarda tipo, mensaje sanitizado, fecha, origen y
hasta tres ubicaciones de función/línea. No captura ni intercepta errores
globales de CCR.

## Limitación de Streamlit

Los controles de Streamlit provocan una nueva ejecución del script. El panel
conserva su estado de sesión y no desplaza el tablero, pero no es una interfaz
JavaScript sin reruns internos. El botón y el panel utilizan CSS asociado a
contenedores con clave; esos selectores pueden requerir revisión al actualizar
Streamlit.
