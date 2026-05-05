# Contrato: Protocolo Serie RPi ↔ Pico v1.0

**Feature**: `001-rpi-pico-serial-protocol`
**Versión del protocolo**: `1.0.0`
**Date**: 2026-05-05

---

## Transporte

| Parámetro | Valor |
|-----------|-------|
| Interfaz física | USB (cable Pico → RPi) |
| Tipo de dispositivo | USB CDC ACM |
| Device node en RPi | `/dev/ttyACM0` (puede variar; configurable) |
| Baud rate nominal | `115200` (sin efecto en USB CDC; convencional) |
| Framing | Newline-delimited JSON — cada mensaje termina en `\n` |
| Encoding | UTF-8 |
| Dirección | Full-duplex bidireccional |

---

## Estructura de mensaje (envelope)

```
{"type": "<TYPE>", "version": "1.0.0", "timestamp_ms": <INT>, "payload": {…}}\n
```

Todos los campos del envelope son **obligatorios**. Un mensaje sin cualquiera de ellos es inválido.

---

## Catálogo de mensajes

### Pico → RPi (eventos)

| `type`           | Descripción | `payload` requerido |
|------------------|-------------|---------------------|
| `t0_detected`    | Impacto detectado por micrófono | `confidence: float` |
| `sensor_ambient` | Lectura BME280 | `temperature_c`, `pressure_hpa`, `humidity_pct: float` |
| `sensor_imu`     | Lectura IMU (inclinación) | `pitch_deg`, `roll_deg: float` |
| `input_button`   | Pulsación de botón | `button_id: str`, `action: str` |
| `input_encoder`  | Acción del encoder | `action: str`, `direction?: str`, `steps?: int` |
| `input_nfc`      | Lectura de tag NFC | `uid: str` |
| `heartbeat`      | Señal de vida | `uptime_ms: int`, `queue_size: int` |

### RPi → Pico (comandos)

| `type`              | Descripción | `payload` requerido |
|---------------------|-------------|---------------------|
| `led_set`           | Control de LED | `led_id: str`, `state: str` |
| `buzzer_beep`       | Activar buzzer | `pattern: str` |
| `state_transition`  | Notificar estado del sistema | `new_state: str` |
| `heartbeat_ack`     | Confirmar heartbeat recibido | `{}` (vacío) |

---

## Reglas de compatibilidad

1. **MAJOR**: cambios incompatibles (campos obligatorios eliminados o renombrados, tipos cambiados).
   El receptor DEBE descartar mensajes con MAJOR diferente al propio.
2. **MINOR**: nuevos campos opcionales o nuevos tipos de mensaje. El receptor DEBE ignorar campos
   desconocidos.
3. **PATCH**: correcciones sin cambio de schema.

---

## Contrato de latencia

| Evento | Presupuesto | Medición |
|--------|------------|----------|
| `t0_detected` Pico → RPi recibido | < 50 ms | extremo a extremo |
| Comando RPi → Pico ejecutado | < 100 ms | desde envío hasta efecto físico |
| Reconexión tras desconexión USB | < 3 s | desde replug hasta primer mensaje recibido |

---

## Contrato de comportamiento ante errores

| Situación | Comportamiento del receptor |
|-----------|----------------------------|
| JSON malformado | Descartar + log WARNING. No lanzar excepción. |
| Campo obligatorio ausente | Descartar + log WARNING. |
| `type` desconocido | Aceptar + log DEBUG (forward-compatible). |
| MAJOR incompatible | Descartar + log ERROR. |
| Canal silencioso > 5 s (RPi) | Emitir `heartbeat_request` y registrar alerta. |
| Desconexión USB | Reintentar apertura cada 500 ms hasta reconexión. |

---

## Valores enumerados

### `button_id`
`BAD_SHOT` · `SAVE_SESSION` · `CALIBRATE` · `RESET_SESSION`

### `input_button.action`
`press` · `long_press`

### `input_encoder.action`
`rotate` · `click` · `long_press`

### `input_encoder.direction` (solo cuando `action == "rotate"`)
`cw` · `ccw`

### `led_id`
`status` · `mode` · `error`

### `led_set.state`
`on` · `off` · `blink_slow` · `blink_fast`

### `buzzer_beep.pattern`
`short` · `long` · `double` · `error`

### `state_transition.new_state`
`BOOTING` · `SELF_TEST` · `WAITING_PROFILE` · `WAITING_CLUB` · `READY` · `ARMED` ·
`IMPACT_DETECTED` · `PROCESSING` · `RESULTS` · `DIAGNOSTICS` · `ERROR`
