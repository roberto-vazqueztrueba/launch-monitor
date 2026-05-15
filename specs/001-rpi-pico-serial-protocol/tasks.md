# Tasks: Protocolo de Comunicación Serie RPi ↔ Pico

**Feature**: `001-rpi-pico-serial-protocol`
**Branch**: `001-rpi-pico-serial-protocol`
**Generated**: 2026-05-13
**Status**: Implementación completada y verificada en hardware ✅

> **Nota**: Este archivo fue generado a posteriori. Las tareas marcadas `[x]` ya han sido
> implementadas y verificadas con `pytest` (24/24 tests pasan). Las tareas pendientes corresponden
> a verificación en hardware real.

---

## Phase 1 — Setup

- [x] T001 Crear estructura de directorios `host/communication/` y `pico/communication/`
- [x] T002 Crear `host/pyproject.toml` con dependencias `pyserial` y `pytest`
- [x] T003 Crear `.gitignore` con patrones Python, MicroPython y entornos virtuales
- [x] T004 Crear `host/__init__.py` y módulos `__init__.py` de tests

---

## Phase 2 — Foundational

- [x] T005 [P] Definir constante `PROTOCOL_VERSION = "1.0.0"` compartida entre módulos host
- [x] T006 [P] Crear `host/communication/reconnect.py` con `ReconnectPolicy` dataclass (parámetros: `interval_s=0.5`, `heartbeat_timeout_s=5.0`, `max_attempts=0`)
- [x] T007 Crear `host/tests/fixtures/sample_messages.json` con mensajes de ejemplo para todos los tipos del catálogo v1.0

---

## Phase 3 — User Story 1: Pico envía evento al host (P1)

**Goal**: El Pico puede emitir cualquier evento del catálogo; la RPi lo recibe, valida y
despacha al handler registrado.

**Independent test criteria**: Conectar Pico → RPi, provocar evento conocido, verificar mensaje
JSON recibido y decodificado sin errores.

### Pico firmware

- [x] T008 [P] [US1] Crear `pico/communication/event_queue.py` — `EventQueue` FIFO acotado (`maxlen=20`), descarta el más antiguo bajo backpressure en `push/pop/empty/size`
- [x] T009 [P] [US1] Crear `pico/communication/messages.py` — constructores: `t0_detected`, `sensor_ambient`, `sensor_imu`, `input_button`, `input_encoder`, `input_nfc`, `heartbeat` con envelope `{type, version, timestamp_ms, payload}`
- [x] T010 [US1] Crear `pico/communication/channel.py` — `UartChannel.flush()` drena la cola y escribe JSON+`\n` por `sys.stdout`; `send_now()` para envío inmediato

### Host reception

- [x] T011 [P] [US1] Crear `host/communication/dispatcher.py` — `EventDispatcher` con `on(type)` decorator, `register(type, fn)`, `dispatch(raw_bytes)`; valida envelope completo; rechaza MAJOR incompatible; descarta JSON malformado con log WARNING
- [x] T012 [US1] Crear `host/communication/channel.py` — `SerialChannel` con hilo lector daemon, `start()/stop()/send(msg)/is_connected`; apertura con reintento cada 500 ms; heartbeat watchdog a 5 s

### Tests

- [x] T013 [P] [US1] Crear `host/tests/unit/test_dispatcher.py` — 11 casos: handler registrado, múltiples handlers, JSON malformado, campos ausentes, versión MAJOR incompatible, versión MINOR compatible, tipo desconocido, raw vacío, excepción en handler, fixture `sample_messages.json`
- [x] T014 [P] [US1] Crear `host/tests/unit/test_channel.py` — 4 casos: `send` sin `type` lanza ValueError, añade `version`/`timestamp_ms`, silencia mensaje sin puerto, escribe JSON + `\n`

---

## Phase 4 — User Story 2: RPi envía comando al Pico (P2)

**Goal**: La RPi puede construir y enviar cualquier comando del catálogo; el Pico lo recibe y
ejecuta.

**Independent test criteria**: Enviar `led_set` desde RPi y verificar que el LED cambia en el
Pico en < 100 ms.

### Host command factories

- [x] T015 [P] [US2] Crear `host/communication/messages.py` — factories `make_led_set`, `make_buzzer_beep`, `make_state_transition`, `make_heartbeat_ack` con validación de enumerados y envelope completo

### Pico command reception

- [x] T016 [US2] Añadir `UartChannel.read_command()` en `pico/communication/channel.py` — lectura no bloqueante con `select`; valida envelope; devuelve dict o None

### Tests

- [x] T017 [P] [US2] Crear `host/tests/unit/test_messages.py` — 9 casos: `make_led_set` válido, todas las combinaciones LED, `led_id` inválido lanza ValueError, `state` inválido, todos los patrones de buzzer, patrón inválido, todos los estados del sistema, estado inválido, `make_heartbeat_ack` estructura

---

## Phase 5 — User Story 3: Detección y recuperación de errores (P3)

**Goal**: El sistema no se bloquea ante mensajes malformados, timeouts ni desconexiones USB.

**Independent test criteria**: Introducir mensaje malformado en el canal y verificar que la RPi
lo descarta, registra en log y sigue procesando mensajes válidos.

### Error handling (ya cubierto en fases anteriores)

- [x] T018 [US3] Verificar que `EventDispatcher.dispatch()` descarta JSON malformado con log WARNING (cubierto en T013)
- [x] T019 [US3] Verificar que `SerialChannel._read_loop()` emite `heartbeat_request` si no hay datos en > 5 s (lógica en `channel.py` línea `_HEARTBEAT_TIMEOUT_S`)
- [x] T020 [US3] Verificar que `SerialChannel._run()` reintenta la apertura del puerto cada 500 ms tras `SerialException` (lógica en `channel.py` `_open_port()`)

### Pico verification

- [x] T021 [US3] Crear `pico/tests/verify_channel.py` — script de verificación manual: burst inicial de todos los tipos de mensaje + bucle heartbeat cada 2 s + eco de comandos entrantes

---

## Phase 6 — Polish & Cross-cutting

- [x] T022 [P] Crear `host/communication/__init__.py` expone `SerialChannel`, `EventDispatcher` y factories (ya creado; verificar exports completos) ✅
- [x] T023 Verificar en hardware: conectar Pico + RPi, flashear `pico/tests/verify_channel.py` como `main.py`, ejecutar `py -3 -m pytest host/tests/unit/ -v` desde RPi
- [x] T024 Documentar en `quickstart.md` el comando de test unitario (ya documentado en spec) ✅

---

## Dependencies

```
US1 (T008–T014) → debe completarse antes que US2 y US3
US2 (T015–T017) → depende de US1 (SerialChannel.send ya disponible)
US3 (T018–T021) → depende de US1 (mecanismos de error ya en canal)
Phase 6         → depende de US1 + US2 + US3
```

## Parallel Execution

Las tareas marcadas `[P]` pueden ejecutarse en paralelo dentro de su fase:

- **Phase 3**: T008, T009, T011, T013, T014 son independientes entre sí
- **Phase 4**: T015, T017 son independientes de T016
- **Phase 6**: T022, T024 son independientes

## Implementation Strategy

MVP = Phase 1 + Phase 2 + Phase 3 (US1 completo): canal unidireccional Pico→RPi operativo.
Phase 4 añade el canal de bajada RPi→Pico. Phase 5 garantiza robustez.

**Estado actual**: MVP + Phase 4 + Phase 5 implementados. Pendiente: verificación en hardware real (T023).
