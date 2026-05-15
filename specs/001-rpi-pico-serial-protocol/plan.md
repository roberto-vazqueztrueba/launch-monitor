# Implementation Plan: Protocolo de Comunicación Serie RPi ↔ Pico

**Branch**: `001-rpi-pico-serial-protocol` | **Date**: 2026-05-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-rpi-pico-serial-protocol/spec.md`

## Summary

Implementar un canal de comunicación serie bidireccional (USB-serial, newline-delimited JSON)
entre la Raspberry Pi (host, Python 3.11+) y la Raspberry Pi Pico (firmware MicroPython). El
canal es la infraestructura fundacional del sistema: sin él, la RPi no puede recibir `t0` del
micrófono ni controlar LEDs/buzzer del Pico.

Decisión técnica clave: **pyserial** en el host (lectura no bloqueante en hilo dedicado) +
**uart nativo de MicroPython** en el Pico con cola de eventos FIFO.

## Technical Context

**Language/Version (RPi host)**: Python 3.11+  
**Language/Version (Pico firmware)**: MicroPython 1.22+ (RP2040)  
**Primary Dependencies (host)**: `pyserial` (lectura serie), stdlib `threading` + `queue`  
**Primary Dependencies (Pico)**: stdlib MicroPython (`sys.stdout` USB CDC, `ujson`, `collections.deque`)  
**Storage**: N/A (este feature no persiste datos; eso corresponde al feature de sesiones)  
**Testing**: `pytest` + `unittest.mock` en el host para simular el canal; scripts de verificación manual en el Pico  
**Target Platform**: Raspberry Pi OS (Linux ARM) + Raspberry Pi Pico (RP2040, MicroPython)  
**Project Type**: biblioteca interna (no CLI, no servicio web) — módulos importables  
**Performance Goals**: latencia `t0_detected` < 50 ms extremo a extremo; throughput ≥ 20 msg/s  
**Constraints**: MicroPython tiene RAM limitada (~200 KB disponibles); cola del Pico ≤ 20 mensajes; sin dependencias externas en el firmware  
**Scale/Scope**: 1 RPi ↔ 1 Pico, canal serie único; carga normal ~5–10 eventos/s durante un golpe

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | ¿Cumple? | Notas |
|-----------|----------|-------|
| I. Precisión y Explicabilidad | ✅ | Los mensajes incluyen `version` y `timestamp_ms`; los malformados se descartan con log |
| II. Modularidad de Sensores | ✅ | El canal no conoce los sensores; cada driver de sensor envía eventos por el canal |
| III. t0 como Evento Central | ✅ | `t0_detected` es un tipo de mensaje de primera clase con latencia garantizada |
| IV. Sistema Orientado a Eventos | ✅ | Diseño event-driven con suscriptores; lectura no bloqueante obligatoria |
| V. Persistencia Fiable | ✅ N/A | Este feature no persiste; garantiza entrega de eventos al feature que sí persiste |
| VI. Test-First | ✅ | Tests unitarios con mock del canal; fixtures de mensajes JSON incluidos en diseño |
| VII. Robustez sobre Perfección | ✅ | Recuperación automática tras desconexión; mensajes malformados no crashean el sistema |

**Veredicto GATE**: ✅ PASA — sin violaciones. Procede a Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-rpi-pico-serial-protocol/
├── plan.md              # Este archivo
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── serial-protocol-v1.md
└── tasks.md             # Phase 2 output (/speckit.tasks - NO creado aquí)
```

### Source Code (repository root)

```text
host/                          # Código Python para Raspberry Pi
├── communication/
│   ├── __init__.py
│   ├── channel.py             # SerialChannel: apertura, lectura no bloqueante, escritura
│   ├── dispatcher.py          # EventDispatcher: suscriptores por tipo de mensaje
│   ├── messages.py            # Dataclasses / TypedDicts para cada tipo de mensaje
│   └── reconnect.py           # Lógica de reconexión automática
└── tests/
    ├── unit/
    │   ├── test_channel.py
    │   ├── test_dispatcher.py
    │   └── test_messages.py
    └── fixtures/
        └── sample_messages.json

pico/                          # Firmware MicroPython para Raspberry Pi Pico
├── communication/
│   ├── channel.py             # UartChannel: envío de mensajes JSON
│   ├── event_queue.py         # Cola FIFO con límite de tamaño
│   └── messages.py            # Constructores de mensajes (ujson)
└── tests/
    └── verify_channel.py      # Script de verificación manual en hardware
```

**Structure Decision**: Dos raíces separadas `host/` y `pico/` para separar claramente el código
Python estándar del firmware MicroPython. Sin monorepo complejo; sin herramientas de build
compartidas en v1.

## Complexity Tracking

Sin violaciones constitucionales — tabla no aplica.

## Constitution Check (post-diseño Phase 1)

*Re-verificación tras generar data-model, contracts y quickstart.*

| Principio | ¿Cumple? | Evidencia en artefactos Phase 1 |
|-----------|----------|---------------------------------|
| I. Precisión y Explicabilidad | ✅ | `data-model.md`: reglas de validación explícitas; mensajes malformados descartados con log |
| II. Modularidad de Sensores | ✅ | `contracts/serial-protocol-v1.md`: el canal no tiene acoplamiento con ningún sensor concreto |
| III. t0 como Evento Central | ✅ | `t0_detected` documentado con payload `confidence` y presupuesto de latencia < 50 ms en el contrato |
| IV. Sistema Orientado a Eventos | ✅ | `quickstart.md`: `dispatcher.on("type")` como interfaz de suscripción; estructura no bloqueante |
| V. Persistencia Fiable | ✅ N/A | El canal entrega eventos; la persistencia es responsabilidad del feature de sesiones |
| VI. Test-First | ✅ | `quickstart.md`: ejemplo de test unitario con mock; estructura `tests/unit/` + `fixtures/` en source layout |
| VII. Robustez sobre Perfección | ✅ | `contracts/serial-protocol-v1.md`: tabla completa de comportamiento ante errores documentada |

**Veredicto post-diseño**: ✅ PASA — diseño consistente con la constitución. Listo para `/speckit.tasks`.