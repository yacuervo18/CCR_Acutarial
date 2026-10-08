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

## Fase 2 propuesta

Primero conectar Índices y monedas con Rentabilidades; después usar esos
insumos en F394 y en las reservas. Las dependencias deberían derivar
`Bloqueado` y `Crítico` desde resultados persistidos, no desde banderas
manuales. La integración Power Automate puede consumir el JSON documentado;
la programación requiere un job externo o la programación dentro del flujo,
no un scheduler en Streamlit.
