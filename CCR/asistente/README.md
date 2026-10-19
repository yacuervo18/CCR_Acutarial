# Asistente de CCR

El asistente es un módulo independiente con dos proveedores: Copilot Studio por
Direct Line y Gemini para consultas documentales sobre un repositorio privado de
GitHub. Las credenciales se leen en el servidor y nunca se envían al navegador.
Las llamadas a Direct Line, GitHub y Gemini validan HTTPS con los certificados
de confianza del sistema operativo; no desactivan la verificación TLS.

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

## Usar Giru en CCR

1. Abre Giru con el botón flotante de la esquina inferior derecha.
2. Escribe la consulta junto al icono de envío y pulsa **Enter** o el icono.
3. Pulsa **Agente** para elegir **Copilot Studio** o **Giru**.

El compositor permanece visible en la parte inferior del panel. La selección se
conserva después de enviar una pregunta y cada proveedor mantiene su conversación.
Junto al selector aparece el agente elegido. En la interfaz, **Giru** es el nombre
visible del proveedor Gemini. La pregunta aparece en el historial mientras Giru
procesa la respuesta.

## Solicitudes de procesos desde Giru

Con **Giru** seleccionado, las órdenes explícitas de Rentabilidades e Índices y
monedas se relacionan con los mismos identificadores de operación que usan los
paneles de esas pantallas. Giru muestra qué entendió y pide confirmación. En la
fase actual no hay manejadores operativos registrados: confirmar informa que la
acción sigue pendiente y no inicia scraping, copia de contenido, envío de correo
ni cambios en OSIRIS o archivos. Las órdenes con **Copilot Studio** continúan por
su ruta conversacional actual y no se interceptan como operaciones locales.

## Configurar Copilot Studio por Direct Line

1. En la configuración de seguridad del canal web de Copilot Studio, usa uno
   de los secretos disponibles. No lo compartas por chat ni lo guardes en un
   archivo versionado.
2. Crea `CCR/.streamlit/secrets.toml` a partir de
   `CCR/.streamlit/secrets.toml.example`.
3. Completa `direct_line_base_url` con el URI base global o regional que
   corresponda al agente, y `direct_line_secret` con el secreto elegido.
   Consulta la [referencia oficial de Direct Line](https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-direct-line-3-0-api-reference?view=azure-bot-service-4.0)
   para identificar el URI base correcto.
4. Reinicia Streamlit. La aplicación inicia la conversación y conserva su
   token en `st.session_state`; el secreto solo se usa desde el servidor.
5. Después de comprobar la conexión, habilita **Requerir acceso protegido**
   en Copilot Studio. Microsoft indica que el cambio puede tardar hasta dos
   horas en aplicarse; mientras tanto, conserva el acceso anterior.

El botón **Limpiar** también descarta la conversación remota. Si la configuración
falta o Direct Line falla, Giru muestra un mensaje explícito y no simula una
respuesta exitosa.

## Configurar Gemini y el repositorio privado de GitHub

1. Mantén `CCR/.streamlit/secrets.toml` fuera del repositorio. Su ruta ya está
   excluida en `.gitignore`; no compartas ni pegues sus valores en el chat.
2. Agrega a ese archivo las secciones `[github_knowledge]` y `[gemini]` del
   ejemplo. No reemplaces la configuración existente de Copilot Studio.
3. En `github_knowledge`, usa el repositorio, rama y carpeta de documentos
   configurados. `read_token` debe tener acceso de solo lectura al contenido de
   ese repositorio. En `gemini`, configura la clave de API y un modelo habilitado
   para tu proyecto.
4. Giru consulta únicamente archivos `.txt`, `.md` y `.markdown` en el servidor,
   busca fragmentos relacionados y envía a Gemini la pregunta y esos fragmentos.
   El token de GitHub no se envía a Gemini. Las respuestas muestran botones con
   enlaces a las fuentes consultadas.
5. Mientras no haya documentos de texto en el repositorio, Gemini no recibe la
   pregunta y Giru informa que aún no hay documentos disponibles.

La búsqueda inicial es léxica por términos y encabezados; no es una garantía de
que todo resultado sea correcto. Se probará con preguntas y fuentes esperadas
cuando se carguen los manuales. Los documentos del repositorio se leen en memoria
del servidor y no se guardan como copias locales.

Las conversaciones de Copilot Studio y Gemini se mantienen separadas. El selector
no hace cambios automáticos de proveedor. Si Direct Line devuelve
`IntegratedAuthenticationNotSupportedInChannel`, Giru muestra el mensaje de
permisos acordado; no reenvía esa consulta a Gemini.

Al pulsar **Preguntar sobre el último error**, se envía solo el resumen técnico
sanitizado del error. No se envía automáticamente contexto de negocio de CCR.

El registro de errores solo guarda tipo, mensaje sanitizado, fecha, origen y
hasta tres ubicaciones de función/línea. No captura ni intercepta errores
globales de CCR.

## Limitación de Streamlit

Los controles de Streamlit provocan una nueva ejecución del script. El panel
conserva su estado de sesión y no desplaza el tablero, pero no es una interfaz
JavaScript sin reruns internos. El botón y el panel utilizan CSS asociado a
contenedores con clave; esos selectores pueden requerir revisión al actualizar
Streamlit.
