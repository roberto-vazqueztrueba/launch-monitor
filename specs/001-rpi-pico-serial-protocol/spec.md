# Feature Specification: Protocolo de Comunicación Serie RPi ↔ Pico

**Feature Branch**: `001-rpi-pico-serial-protocol`
**Created**: 2026-05-05
**Status**: Implemented
**Input**: Protocolo de comunicación serie entre Raspberry Pi y Raspberry Pi Pico para intercambio de eventos JSON

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Pico envía evento de sensor al host (Priority: P1)

El Pico detecta un evento relevante (p.ej. detección de `t0` por el micrófono, lectura de BME280,
pulsación de botón) y lo comunica a la Raspberry Pi. La RPi recibe el mensaje, lo interpreta
correctamente y lo procesa.

**Why this priority**: Es el flujo más crítico del sistema. Sin este canal operativo, la RPi no
puede iniciar el pipeline de golpe. Todo lo demás depende de que este intercambio funcione.

**Independent Test**: Conectar el Pico a la RPi, provocar un evento conocido (p.ej. pulsar un
botón físico), y verificar que la RPi recibe y decodifica el mensaje JSON correcto sin errores.

**Acceptance Scenarios**:

1. **Given** Pico y RPi conectados por USB-serial, **When** el Pico detecta `t0`, **Then** la RPi recibe dentro de 50 ms un mensaje JSON con tipo `t0_detected` y timestamp válido.
2. **Given** canal activo, **When** el Pico envía una lectura de BME280, **Then** la RPi recibe temperatura, presión y humedad como floats correctamente tipados.
3. **Given** canal activo, **When** el Pico envía una pulsación de botón, **Then** la RPi recibe `input_button` con el identificador correcto del botón.

---

### User Story 2 — RPi envía comando de control al Pico (Priority: P2)

La Raspberry Pi necesita enviar órdenes al Pico: activar un LED, hacer sonar el buzzer, o cambiar
el estado del firmware.

**Why this priority**: El feedback al usuario (LEDs, buzzer) lo gestiona el Pico. Sin este canal
de bajada la RPi no puede confirmar acciones al usuario.

**Independent Test**: Desde la RPi enviar un comando `led_set` con estado ON y verificar que el
LED correspondiente se enciende en el Pico.

**Acceptance Scenarios**:

1. **Given** canal activo, **When** la RPi envía `led_set {id: "status", state: "on"}`, **Then** el Pico enciende el LED de estado en menos de 100 ms.
2. **Given** canal activo, **When** la RPi envía `buzzer_beep {pattern: "short"}`, **Then** el Pico emite el patrón sonoro correspondiente.
3. **Given** canal activo, **When** la RPi envía `state_transition {new_state: "ARMED"}`, **Then** el Pico actualiza su estado interno. *(El ACK explícito queda fuera del alcance de v1.)*

---

### User Story 3 — Detección y recuperación de errores de comunicación (Priority: P3)

El canal serie puede sufrir interrupciones, mensajes corruptos o timeouts. El sistema debe
detectarlo y recuperarse sin bloquear el flujo principal.

**Why this priority**: La robustez es un principio constitucional. Un fallo silencioso en el
canal podría provocar que el pipeline del golpe se inicie con datos inválidos.

**Independent Test**: Introducir un mensaje malformado en el canal y verificar que la RPi lo
descarta, registra el error en el log y sigue procesando mensajes válidos posteriores.

**Acceptance Scenarios**:

1. **Given** canal activo, **When** llega un mensaje JSON malformado, **Then** se descarta, se registra en el log y el sistema no se bloquea.
2. **Given** canal activo, **When** no se recibe ningún mensaje durante más de 5 segundos, **Then** la RPi emite un `heartbeat_request` y espera respuesta del Pico.
3. **Given** pérdida de conexión USB, **When** se reconecta el dispositivo, **Then** ambos nodos restablecen el canal automáticamente y retoman el intercambio.

---

### Edge Cases

- ¿Qué ocurre si el Pico envía dos eventos simultáneos (p.ej. `t0` y un botón al mismo tiempo)?
- ¿Qué ocurre si el buffer serie se satura por eventos en ráfaga?
- ¿Qué ocurre si el Pico se reinicia mientras la RPi está procesando un mensaje a medias?
- ¿Qué ocurre si la versión de protocolo del Pico no coincide con la de la RPi?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El protocolo DEBE usar mensajes JSON delimitados por newline (`\n`) sobre puerto serie USB.
- **FR-002**: Cada mensaje DEBE incluir los campos: `type` (string), `timestamp_ms` (int, ms desde boot del Pico), `version` (string semver del protocolo), y `payload` (objeto con datos del evento).
- **FR-003**: El canal DEBE soportar comunicación bidireccional: Pico→RPi (eventos de sensor/input) y RPi→Pico (comandos de control).
- **FR-004**: La RPi DEBE procesar mensajes entrantes de forma no bloqueante (nunca parar el hilo principal).
- **FR-005**: El Pico DEBE enviar un mensaje `heartbeat` cada 2 segundos cuando no haya otros eventos, para confirmar que el canal está vivo.
- **FR-006**: La RPi DEBE detectar ausencia de mensajes durante más de 5 segundos, emitir un `heartbeat_request` al Pico y registrar una alerta de canal inactivo.
- **FR-007**: Mensajes JSON malformados o con campos obligatorios ausentes DEBEN descartarse con registro en log; NO DEBEN propagar excepciones.
- **FR-008**: El protocolo DEBE incluir un campo `version` para permitir negociación de versión y compatibilidad futura.
- **FR-009**: La RPi DEBE exponer una interfaz programática (callable) para suscribirse a tipos de evento específicos, sin conocer detalles del canal físico.
- **FR-010**: El Pico DEBE encolar eventos cuando el canal esté temporalmente ocupado, con límite máximo de cola documentado.

### Tipos de mensajes definidos (v1.0)

**Pico → RPi (eventos)**:

| `type`            | Descripción                                      |
|-------------------|--------------------------------------------------|
| `t0_detected`     | Instante de impacto detectado por micrófono      |
| `sensor_ambient`  | Lectura BME280 (temperatura, presión, humedad)   |
| `sensor_imu`      | Lectura IMU (ángulo inclinación del dispositivo) |
| `input_button`    | Pulsación de botón físico                        |
| `input_encoder`   | Giro o click del encoder rotativo                |
| `input_nfc`       | Lectura de tag NFC                               |
| `heartbeat`       | Señal de vida periódica                          |

**RPi → Pico (comandos)**:

| `type`              | Descripción                              |
|---------------------|------------------------------------------|
| `led_set`           | Control de estado de un LED              |
| `buzzer_beep`       | Activar patrón de buzzer                 |
| `state_transition`  | Notificar nuevo estado del sistema       |
| `heartbeat_ack`     | Respuesta a heartbeat del Pico           |
| `heartbeat_request` | Solicitar heartbeat inmediato al Pico    |

### Key Entities

- **Mensaje**: unidad atómica de comunicación. Campos: `type`, `version`, `timestamp_ms`, `payload`.
- **Canal**: abstracción sobre el puerto serie USB. Gestiona apertura, lectura no bloqueante, escritura y reconexión.
- **Suscriptor**: componente de la RPi registrado para recibir mensajes de un tipo específico.
- **Cola de eventos (Pico)**: buffer FIFO en el Pico para eventos pendientes de envío.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El evento `t0_detected` llega a la RPi en menos de 50 ms desde que el Pico lo genera, en el 95% de los casos en condiciones normales.
- **SC-002**: El sistema recupera la comunicación automáticamente tras una desconexión USB en menos de 3 segundos.
- **SC-003**: Ningún mensaje malformado provoca un crash o bloqueo en la RPi ni en el Pico.
- **SC-004**: El canal soporta una tasa de al menos 20 mensajes/segundo sin pérdida en condiciones de golpe normal.
- **SC-005**: Un desarrollador puede añadir soporte para un nuevo tipo de evento sin modificar el código del canal (solo añadir suscriptor).

## Assumptions

- El Pico se comunica con la RPi exclusivamente vía USB (no Wi-Fi, no BLE en v1).
- La velocidad del puerto serie es suficiente para la tasa de mensajes esperada (115200 baud o superior).
- La RPi tiene un único Pico conectado en v1; soporte multi-Pico queda fuera de alcance.
- El Pico tiene suficiente RAM para mantener una cola de eventos de al menos 10 mensajes.
- El protocolo v1.0 es el punto de partida; la negociación de versión se implementa pero no se ejerce en v1.
- El formato JSON (vs. binario) se asume aceptable en términos de rendimiento para la tasa de mensajes esperada.
