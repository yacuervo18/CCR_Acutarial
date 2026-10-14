# CCR_Acutarial

Centro de Control y Gestión Actuarial para el seguimiento mensual de reservas,
rentabilidades y reportes regulatorios.

## Ejecutar

```powershell
cd CCR
.\.venv\Scripts\python.exe -m streamlit run app.py
```

La aplicación usa SQLite en `CCR/data/ccr.db`. En la primera ejecución crea
automáticamente el periodo del mes actual y sus tareas por defecto. Los meses
anteriores se conservan y se consultan en modo lectura recomendado; la fase 1
deja el selector disponible, pero no habilita un cierre irreversible.

## Arquitectura de fase 1

`src/phase1` separa dominio (reglas puras), repositorio SQLite, servicios y
notificaciones simuladas. `app.py` solo compone la navegación y los
componentes de Streamlit. La barra de avance usa `position: sticky`: se
mantiene visible sin superponerse al contenido y se recalcula después de cada
marcado de tarea. Agregar un proceso requiere añadir su configuración en
`src/phase1/config.py`.

Las notificaciones implementan `NotificationChannel`, `PowerAutomateChannel` y
`EmailChannel`, pero solo escriben en el log y en el historial SQLite. El
contrato versionable para el futuro flujo HTTP está en
`CCR/docs/notification_contract.json`. La URL del webhook debe llegar por
`POWER_AUTOMATE_WEBHOOK_URL` (ver `.env.example`); no se hacen llamadas reales
en esta fase.

Cada proceso permite configurar una programación general, que se conserva al
crear nuevos periodos mensuales, con fecha de inicio, hora, todos los meses o
meses específicos, frecuencia de revisión y destinatarios de Teams. También
se puede guardar una excepción para el periodo seleccionado sin modificar la
programación general. El reinicio mensual solo crea las tareas del nuevo
periodo; nunca elimina ni reinicia las fechas programadas. Los
destinatarios se registran como `Nombre | correo o identificador`, por ejemplo
`Carlos | carlos@empresa.com` o `Canal Reservas | canal-reservas`. Al abrir la
aplicación se revisan las programaciones aplicables al mes actual; si quedan
tareas pendientes se genera una alerta interna y un evento simulado para Teams.
La frecuencia evita duplicados si la aplicación se abre varias veces dentro
del intervalo configurado. Al completar todas las tareas, no se generan más
recordatorios para ese proceso.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Fase visual autorizada

CCR y el Motor F394 usan `Icono_Sura.png` como icono de la pestaña del
navegador. La aplicación principal de CCR muestra los nombres de los procesos
sin iconos en el menú lateral y presenta el acceso al Motor F394 con el botón
amarillo definido para esa integración. Estos cambios son exclusivamente
visuales y no alteran la base SQLite, la programación, el estado de las tareas
ni la lógica operativa del Motor F394.

## Fase 2: contenidos en modo lectura

Cada proceso tiene una carpeta de contenido bajo `CCR/content/<codigo>/`.
`que_hay_que_hacer.txt` contiene el texto informativo, `manual_url.txt` puede
contener un enlace de manual, `importante.txt` puede contener una observación
destacada y `media/` contiene el video explicativo del proceso. La ausencia de
un video o manual se muestra como un estado pendiente.

## Fases 3 y 4: video y manual administrables

Los botones de lápiz permiten administrar el contenido sin entrar al código:

- “Qué hay que hacer” y “Importante” se guardan por proceso en la tabla
  independiente `phase1_process_content` de SQLite.
- El manual sugerido acepta únicamente enlaces `http://` o `https://`.
  Guardar el campo vacío elimina el enlace configurado.
- El video permite cargar o reemplazar archivos `.mp4`, `.webm` y `.mov` de
  hasta 200 MB. Se guarda en `CCR/content/<codigo>/media/` con escritura
  atómica y se eliminan las versiones anteriores del mismo proceso.
- Eliminar un video requiere confirmación y elimina el archivo físico de la
  carpeta del proceso.
- Los periodos históricos permanecen en modo de solo lectura.
- Estas funciones no modifican tareas, contadores, programación, notificaciones
  ni el Motor F394.

## Fase 5: tareas administrables

El catálogo de tareas de cada proceso se guarda de forma independiente en la
tabla `phase1_process_tasks`. El lápiz ubicado junto al encabezado “Tareas”
abre el panel de edición del proceso seleccionado. Desde allí se puede:

- agregar una tarea;
- cambiar su nombre y marcarla como SOX o con aprobación requerida;
- quitarla con confirmación.

Quitar una tarea la desactiva del catálogo y conserva las marcas históricas en
`phase1_tasks`; no se borra información de la base. Los contadores del proceso,
las tareas pendientes, el avance global y los indicadores SOX/aprobación se
recalculan usando únicamente las tareas activas. La programación, las
notificaciones, los contenidos y el Motor F394 permanecen independientes.

## Próxima fase propuesta

Primero conectar Índices y monedas con Rentabilidades; después usar esos
insumos en F394 y en las reservas. Las dependencias deberían derivar
`Bloqueado` y `Crítico` desde resultados persistidos, no desde banderas
manuales. La integración Power Automate puede consumir el JSON documentado;
la programación requiere un job externo o la programación dentro del flujo,
no un scheduler en Streamlit.
