# Data Model: Protocolo de Comunicación Serie RPi ↔ Pico

**Feature**: `001-rpi-pico-serial-protocol`
**Date**: 2026-05-05

---

## Entidades

### Message (mensaje base)

Toda unidad de comunicación en el canal. Transmitida como JSON + `\n`.

| Campo          | Tipo    | Requerido | Descripción |
|----------------|---------|-----------|-------------|
| `type`         | string  | ✅        | Identificador del tipo de mensaje (ver catálogo) |
| `version`      | string  | ✅        | Versión semver del protocolo (e.g. `"1.0.0"`) |
| `timestamp_ms` | integer | ✅        | Milisegundos desde boot del Pico (monotónico) |
| `payload`      | object  | ✅        | Datos específicos del tipo de mensaje |

**Invariantes**:
- `type` DEBE ser una cadena no vacía del catálogo conocido
- `version` DEBE tener formato `MAJOR.MINOR.PATCH`
- `timestamp_ms` DEBE ser ≥ 0
- `payload` DEBE ser un objeto JSON (nunca null, nunca array)

---

### Payloads de mensajes Pico → RPi

#### `t0_detected`
```json
{
  "type": "t0_detected",
  "version": "1.0.0",
  "timestamp_ms": 45231,
  "payload": {
    "confidence": 0.92
  }
}
```
| Campo           | Tipo  | Descripción |
|-----------------|-------|-------------|
| `confidence`    | float | Confianza de la detección [0.0–1.0] |

---

#### `sensor_ambient`
```json
{
  "type": "sensor_ambient",
  "version": "1.0.0",
  "timestamp_ms": 45400,
  "payload": {
    "temperature_c": 21.3,
    "pressure_hpa": 1013.2,
    "humidity_pct": 58.1
  }
}
```
| Campo             | Tipo  | Descripción |
|-------------------|-------|-------------|
| `temperature_c`   | float | Temperatura en grados Celsius |
| `pressure_hpa`    | float | Presión en hPa |
| `humidity_pct`    | float | Humedad relativa en % |

---

#### `sensor_imu`
```json
{
  "type": "sensor_imu",
  "version": "1.0.0",
  "timestamp_ms": 45410,
  "payload": {
    "pitch_deg": -2.1,
    "roll_deg": 0.3
  }
}
```
| Campo        | Tipo  | Descripción |
|--------------|-------|-------------|
| `pitch_deg`  | float | Inclinación frontal-trasero en grados |
| `roll_deg`   | float | Inclinación lateral en grados |

---

#### `input_button`
```json
{
  "type": "input_button",
  "version": "1.0.0",
  "timestamp_ms": 46001,
  "payload": {
    "button_id": "BAD_SHOT",
    "action": "press"
  }
}
```
| Campo       | Tipo   | Valores permitidos |
|-------------|--------|--------------------|
| `button_id` | string | `BAD_SHOT`, `SAVE_SESSION`, `CALIBRATE`, `RESET_SESSION` |
| `action`    | string | `press`, `long_press` |

---

#### `input_encoder`
```json
{
  "type": "input_encoder",
  "version": "1.0.0",
  "timestamp_ms": 46050,
  "payload": {
    "action": "rotate",
    "direction": "cw",
    "steps": 2
  }
}
```
| Campo       | Tipo    | Valores permitidos |
|-------------|---------|-------------------|
| `action`    | string  | `rotate`, `click`, `long_press` |
| `direction` | string  | `cw`, `ccw` (solo cuando `action == "rotate"`) |
| `steps`     | integer | Número de pasos (solo cuando `action == "rotate"`) |

---

#### `input_nfc`
```json
{
  "type": "input_nfc",
  "version": "1.0.0",
  "timestamp_ms": 46200,
  "payload": {
    "uid": "04:A3:2B:C1"
  }
}
```
| Campo  | Tipo   | Descripción |
|--------|--------|-------------|
| `uid`  | string | UID del tag NFC en formato hex con separador `:` |

---

#### `heartbeat`
```json
{
  "type": "heartbeat",
  "version": "1.0.0",
  "timestamp_ms": 48000,
  "payload": {
    "uptime_ms": 48000,
    "queue_size": 0
  }
}
```
| Campo        | Tipo    | Descripción |
|--------------|---------|-------------|
| `uptime_ms`  | integer | Milisegundos desde boot del Pico |
| `queue_size` | integer | Mensajes actualmente en cola de envío |

---

### Payloads de mensajes RPi → Pico

#### `led_set`
```json
{
  "type": "led_set",
  "version": "1.0.0",
  "timestamp_ms": 0,
  "payload": {
    "led_id": "status",
    "state": "on"
  }
}
```
| Campo    | Tipo   | Valores permitidos |
|----------|--------|--------------------|
| `led_id` | string | `status`, `mode`, `error` |
| `state`  | string | `on`, `off`, `blink_slow`, `blink_fast` |

---

#### `buzzer_beep`
```json
{
  "type": "buzzer_beep",
  "version": "1.0.0",
  "timestamp_ms": 0,
  "payload": {
    "pattern": "short"
  }
}
```
| Campo     | Tipo   | Valores permitidos |
|-----------|--------|--------------------|
| `pattern` | string | `short`, `long`, `double`, `error` |

---

#### `state_transition`
```json
{
  "type": "state_transition",
  "version": "1.0.0",
  "timestamp_ms": 0,
  "payload": {
    "new_state": "ARMED"
  }
}
```
| Campo       | Tipo   | Valores permitidos |
|-------------|--------|--------------------|
| `new_state` | string | `BOOTING`, `SELF_TEST`, `WAITING_PROFILE`, `WAITING_CLUB`, `READY`, `ARMED`, `IMPACT_DETECTED`, `PROCESSING`, `RESULTS`, `DIAGNOSTICS`, `ERROR` |

---

#### `heartbeat_ack`
```json
{
  "type": "heartbeat_ack",
  "version": "1.0.0",
  "timestamp_ms": 0,
  "payload": {}
}
```
Sin campos en payload — es una confirmación de que el host sigue activo.

---

#### `heartbeat_request`
```json
{
  "type": "heartbeat_request",
  "version": "1.0.0",
  "timestamp_ms": 0,
  "payload": {}
}
```
Sin campos en payload — solicita al Pico que envíe un `heartbeat` inmediato sin esperar al ciclo
periódico. El Pico DEBE responder con un `heartbeat` en el siguiente ciclo de escritura.

---

## Reglas de validación del canal

1. Un mensaje DEBE descartarse (con log) si:
   - No es JSON válido
   - Falta cualquiera de los campos obligatorios (`type`, `version`, `timestamp_ms`, `payload`)
   - `payload` no es un objeto
2. Un mensaje con `type` desconocido DEBE aceptarse y loguearse en DEBUG, no descartarse (para
   compatibilidad hacia adelante — forward-compatible)
3. Un mensaje con `version` incompatible (MAJOR diferente) DEBE descartarse con log de error
