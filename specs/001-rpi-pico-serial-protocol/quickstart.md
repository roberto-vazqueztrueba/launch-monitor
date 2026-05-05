# Quickstart: Protocolo de Comunicación Serie RPi ↔ Pico

**Feature**: `001-rpi-pico-serial-protocol`
**Date**: 2026-05-05

---

## Prerrequisitos

**RPi (host)**:
```bash
pip install pyserial
```

**Pico (firmware)**:
- MicroPython 1.22+ instalado en la Raspberry Pi Pico
- `collections.deque` disponible en stdlib de MicroPython RP2

---

## Verificar que el Pico es visible en la RPi

```bash
ls /dev/ttyACM*
# Debe mostrar /dev/ttyACM0 (u otro número)
```

---

## Estructura de archivos a crear

```
host/
└── communication/
    ├── channel.py      # SerialChannel
    ├── dispatcher.py   # EventDispatcher
    └── messages.py     # Dataclasses de mensajes

pico/
└── communication/
    ├── channel.py      # UartChannel (envío)
    └── event_queue.py  # Cola FIFO
```

---

## Uso básico — RPi (host)

```python
from host.communication.channel import SerialChannel
from host.communication.dispatcher import EventDispatcher

dispatcher = EventDispatcher()
channel = SerialChannel(port="/dev/ttyACM0", dispatcher=dispatcher)

# Suscribirse a un tipo de evento
@dispatcher.on("t0_detected")
def handle_t0(msg):
    print(f"t0 detectado! confianza={msg['payload']['confidence']}")

# Iniciar canal (no bloqueante)
channel.start()

# Enviar comando al Pico
channel.send({"type": "led_set", "payload": {"led_id": "status", "state": "on"}})
```

---

## Uso básico — Pico (firmware MicroPython)

```python
from communication.channel import UartChannel
from communication.event_queue import EventQueue

queue = EventQueue(maxlen=20)
channel = UartChannel(queue=queue)

# Emitir evento t0
queue.push({
    "type": "t0_detected",
    "payload": {"confidence": 0.95}
})
channel.flush()  # Envía todos los mensajes pendientes al host
```

---

## Probar el canal manualmente

Desde la RPi, usando `minicom` o `screen`:
```bash
screen /dev/ttyACM0 115200
```
Si el Pico está enviando heartbeats, deberías ver líneas JSON cada 2 segundos:
```json
{"type":"heartbeat","version":"1.0.0","timestamp_ms":2000,"payload":{"uptime_ms":2000,"queue_size":0}}
```

---

## Test unitario del canal en el host

```python
# tests/unit/test_channel.py
from unittest.mock import MagicMock, patch
import json

def test_dispatcher_calls_handler_on_valid_message():
    from host.communication.dispatcher import EventDispatcher
    dispatcher = EventDispatcher()
    received = []
    dispatcher.on("t0_detected")(lambda msg: received.append(msg))

    raw = json.dumps({
        "type": "t0_detected",
        "version": "1.0.0",
        "timestamp_ms": 1000,
        "payload": {"confidence": 0.9}
    }).encode() + b"\n"

    dispatcher.dispatch(raw)
    assert len(received) == 1
    assert received[0]["payload"]["confidence"] == 0.9
```

Ejecutar:
```bash
cd host
pytest tests/unit/
```

---

## Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| No aparece `/dev/ttyACM0` | Pico no detectado | Comprobar cable USB; reiniciar Pico |
| `Permission denied /dev/ttyACM0` | Usuario no en grupo `dialout` | `sudo usermod -a -G dialout $USER` + re-login |
| Sin mensajes del Pico | Firmware no iniciado | Verificar que `main.py` del Pico ejecuta el canal |
| JSON malformado en logs | Bug en firmware Pico | Revisar `json.dumps()` en el Pico; comprobar encoding UTF-8 |
| Latencia > 50 ms en `t0` | Cola del Pico llena | Reducir frecuencia de `sensor_ambient`; aumentar prioridad de `t0` |
