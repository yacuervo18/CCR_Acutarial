# Guía de Integración CCR ↔ Microsoft Teams vía Power Automate

## Resumen
El CCR genera alertas locales y, si está configurado, las envía a Microsoft Teams mediante un flujo de Power Automate que recibe un webhook HTTP POST con JSON.

---

## 1. Crear el flujo en Power Automate

### Paso a paso:

1. **Entrar a Power Automate** (make.powerautomate.com)
2. **Crear > Flujo en la nube instantáneo**
3. **Nombre**: "CCR - Notificaciones Teams"
4. **Desencadenador**: *Cuando se recibe una solicitud de webhook de Teams* (o *When an HTTP request is received*)
   - **Esquema JSON del cuerpo de la solicitud** (pegar esto):

```json
{
  "type": "object",
  "properties": {
    "schema_version": { "type": "string" },
    "event_id": { "type": "string" },
    "tipo": { "type": "string" },
    "severidad": { "type": "string" },
    "titulo": { "type": "string" },
    "mensaje": { "type": "string" },
    "proceso": { "type": "string" },
    "periodo": { "type": "string" },
    "responsable": { "type": "string" },
    "responsable_email": { "type": "string" },
    "fecha_limite": { "type": "string" },
    "enlace_app": { "type": "string" },
    "generado_en": { "type": "string" },
    "card": { "type": "object" }
  },
  "required": ["schema_version", "event_id", "tipo", "severidad", "titulo", "mensaje"]
}
```

5. **Guardar** → Se genera la **URL HTTP POST** (copiarla)

---

## 2. Publicar en Teams (Acción)

### Opción A: Publicar en un canal (recomendado)
1. **Nuevo paso** > *Publicar un mensaje en un chat o canal* (Microsoft Teams)
2. **Publicar como**: Flujo (bot)
3. **Equipo**: Seleccionar equipo
4. **Canal**: Seleccionar canal
5. **Mensaje**: Usar contenido dinámico:
   - **Título**: `titulo`
   - **Texto**: `mensaje`
   - O usar **Adaptive Card** (ver abajo)

### Opción B: Publicar en chat privado (mención @usuario)
1. **Nuevo paso** > *Publicar un mensaje en un chat* (Microsoft Teams)
2. **Destinatario**: Usar `responsable_email` del JSON
3. **Mensaje**: Combinar `titulo` + `mensaje`

---

## 3. Adaptive Card (Opcional, recomendado)

Si en CCR está activada la opción "Incluir Adaptive Card", el payload trae un campo `card` listo para usar.

En Power Automate:
1. **Nuevo paso** > *Publicar una tarjeta adaptable* (Microsoft Teams) - *Preview*
2. **Equipo/Canal**: Seleccionar
3. **Tarjeta adaptable**: Seleccionar *Especificar valor personalizado* > `card` (del contenido dinámico)

---

## 4. Configurar en CCR

1. Ir a **Configuración > Teams**
2. ✅ **Enviar notificaciones a Teams**
3. **URL del flujo**: Pegar la URL HTTP POST copiada en paso 1
4. ☑ **Incluir Adaptive Card** (si usa tarjetas)
5. **Guardar**
6. Probar con botón **Enviar mensaje de prueba**

---

## 5. Contrato del Payload (v1.0)

```json
{
  "schema_version": "1.0",
  "event_id": "abc123...",
  "tipo": "proceso_bloqueado | vencido | sox_pendiente | aprobacion_pendiente | masivo_proximo | fecha_proxima | resumen_diario",
  "severidad": "Info | Aviso | Critica",
  "titulo": "Proceso bloqueado: Correcciones ARL",
  "mensaje": "El proceso 'Correcciones ARL' está bloqueado: Dependencia pendiente: F394.",
  "proceso": "Correcciones ARL",
  "periodo": "2026-10",
  "responsable": "Carlos López",
  "responsable_email": "carlos@empresa.com",
  "fecha_limite": "2026-10-15",
  "enlace_app": "http://localhost:8501/Procesos",
  "generado_en": "2026-10-05T08:30:00",
  "card": { ... }  // opcional
}
```

**Tipos de alerta (`tipo`):**
- `proceso_bloqueado`: Dependencias no cumplidas
- `vencido`: Fecha límite pasada sin completar
- `fecha_proxima`: Próximo a vencer (7, 3, 1 días)
- `sox_pendiente`: Control SOX sin completar
- `aprobacion_pendiente`: Aprobación con estados abiertos
- `masivo_proximo`: Proceso masivo programado
- `resumen_diario`: Resumen consolidado (modo resumen)

**Severidades:**
- `Critica`: Requiere acción inmediata (rojo en Teams)
- `Aviso`: Atención pronto (ámbar)
- `Info`: Informativo (azul)

---

## 6. Reglas de Envío

| Regla | Descripción |
|-------|-------------|
| **Desactivado por defecto** | Solo envía si se activa en Configuración |
| **Deduplicación** | Misma `clave_unica` = un solo envío; reenvía si cambia severidad |
| **Reintentos** | Máx 3 (1, 5, 15 min) al abrir la app |
| **Horario silencioso** | Configurable (ej. 19:00-07:00) |
| **Límite/hora** | Configurable (default 10) |
| **Modos** | Individual, Resumen diario, o Ambos |
| **Filtros** | Por tipo y severidad mínima |

---

## 7. Solución de Problemas

| Síntoma | Causa | Solución |
|---------|-------|----------|
| "Error de red" | Sin internet / firewall | Verificar salida a `*.logic.azure.com` |
| "HTTP 401/403" | URL inválida / expirada | Regenerar URL en Power Automate |
| "HTTP 400" | JSON inválido | Verificar esquema en desencadenador |
| No llega a Teams | Flujo desactivado | Activar flujo en Power Automate |
| Llega duplicado | Reintentos | CCR deduplica por `clave_unica`; revisar cola en Configuración > Teams |

---

## 8. Bitácora Técnica

Todos los envíos se registran en `data/ccr.log` (sin exponer la URL completa):

```
2026-10-05T08:30:00.123 | TEAMS_SEND_OK | event_id=abc123 tipo=vencido severidad=Critica
2026-10-05T08:35:00.456 | TEAMS_SEND_ERROR | event_id=def456 error=Timeout (10s)
```

---

## 9. Seguridad

- La URL del webhook se almacena encriptada en configuración (base de datos local)
- En logs y UI se muestra enmascarada: `••••••••••••••••••••••••••••••••`
- No hay servidores intermedios; comunicación directa CCR → Power Automate
- Solo salida HTTPS; no requiere puertos de entrada

---

## 10. Pruebas Rápidas

1. En CCR: Configuración > Teams > **Enviar mensaje de prueba**
2. Verificar en Teams: llega mensaje "✅ Prueba de conexión CCR → Teams"
3. Crear un proceso con fecha límite ayer → refrescar Dashboard → debe aparecer alerta "Vencido" en Teams
4. Ver cola en Configuración > Teams > **Cola de salida**

---

*Documento generado automáticamente por CCR v1.0*