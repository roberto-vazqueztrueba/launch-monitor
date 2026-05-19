# Quickstart: Protocolo de Comunicación Serie RPi ↔ Pico

**Feature**: `001-rpi-pico-serial-protocol`
**Date**: 2026-05-05

---

## Prerrequisitos

**RPi (host)**:
```bash
pip install pyserial pytest
```

**Pico (firmware)**:
- MicroPython 1.22+ instalado en la Raspberry Pi Pico
- `collections.deque` disponible en stdlib de MicroPython RP2

---

## Crear symlink fijo `/dev/pico` (udev)

El número de `/dev/ttyACMx` varía entre reinicios. Creamos un symlink permanente:

```bash
# En la RPi, como root:
cat > /etc/udev/rules.d/99-pico.rules << 'EOF'
SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="0005", SYMLINK+="pico", GROUP="dialout", MODE="0660"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger
```

> **Opción recomendada (más segura)**: `GROUP="dialout", MODE="0660"` — solo los usuarios del
> grupo `dialout` pueden acceder al dispositivo. Añade tu usuario al grupo:
> `sudo usermod -aG dialout $USER` (requiere cerrar sesión y volver a entrar).
>
> **Opción alternativa (más cómoda en desarrollo)**: sustituye por `MODE="0666"` para dar acceso
> a todos los usuarios locales sin necesidad de gestionar grupos. No recomendado en producción
> porque cualquier proceso local puede enviar comandos al firmware.

Después de reconectar el Pico, el dispositivo estará disponible como `/dev/pico`.

## Verificar que el Pico es visible en la RPi

```bash
ls /dev/pico
# O si no tienes la udev rule: ls /dev/ttyACM*
```

---

## Estructura de archivos

```
host/
└── communication/
    ├── __init__.py
    ├── channel.py      # SerialChannel
    ├── dispatcher.py   # EventDispatcher
    ├── messages.py     # Factorías de comandos (make_led_set, etc.)
    └── reconnect.py    # ReconnectPolicy

pico/
├── main.py             # Entry point de producción
└── communication/
    ├── channel.py      # UartChannel (envío + lectura de comandos)
    ├── event_queue.py  # Cola FIFO
    └── messages.py     # Constructores de eventos
```

---

## Uso básico — RPi (host)

```python
from host.communication.channel import SerialChannel
from host.communication.dispatcher import EventDispatcher
from host.communication.messages import make_led_set

dispatcher = EventDispatcher()
channel = SerialChannel(dispatcher=dispatcher)  # port por defecto: /dev/pico

# Suscribirse a un tipo de evento
@dispatcher.on("t0_detected")
def handle_t0(msg):
    print(f"t0 detectado! confianza={msg['payload']['confidence']}")

# Iniciar canal (no bloqueante)
channel.start()

# Enviar comando al Pico usando la factoría de mensajes
channel.send(make_led_set("status", "on"))
```

---

## Uso básico — Pico (firmware MicroPython)

```python
import sys
if "communication" not in sys.path:
    sys.path.append("communication")

from channel import UartChannel
from event_queue import EventQueue
import messages as m

queue = EventQueue(maxlen=20)
channel = UartChannel(queue=queue)

# Emitir evento t0
queue.push(m.t0_detected(confidence=0.95))
channel.flush()  # Envía todos los mensajes pendientes al host
```

---

## Probar el canal manualmente

Desde la RPi, usando `minicom` o `screen`:
```bash
screen /dev/pico 115200
```
Si el Pico está enviando heartbeats, deberías ver líneas JSON cada 2 segundos:
```json
{"type":"heartbeat","version":"1.0.0","timestamp_ms":2000,"payload":{"uptime_ms":2000,"queue_size":0}}
```

---

## Test unitario del canal en el host

El ejemplo muestra cómo testear `SerialChannel.send()` sin puerto físico, mockeando `serial.Serial`:

```python
# tests/unit/test_channel.py
import json
from unittest.mock import MagicMock, patch

def test_send_adds_version_and_timestamp():
    from host.communication.channel import SerialChannel, PROTOCOL_VERSION
    from host.communication.dispatcher import EventDispatcher

    dispatcher = EventDispatcher()
    with patch("serial.Serial"):
        channel = SerialChannel(port="/dev/pico", dispatcher=dispatcher)

    mock_serial = MagicMock()
    mock_serial.is_open = True
    channel._serial = mock_serial

    channel.send({"type": "led_set", "payload": {"led_id": "status", "state": "on"}})

    written = mock_serial.write.call_args[0][0].decode("utf-8").strip()
    msg = json.loads(written)
    assert msg["version"] == PROTOCOL_VERSION
    assert "timestamp_ms" in msg
    assert msg["type"] == "led_set"
```

Para testear el dispatcher directamente, ver `host/tests/unit/test_dispatcher.py`.

Ejecutar todos los tests unitarios desde la raíz del repositorio:
```bash
PYTHONPATH=. python3 -m pytest host/tests/unit/
```

---

## Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| No aparece `/dev/pico` | udev rule no aplicada o Pico no detectado | Reconectar Pico; ejecutar `udevadm trigger` |
| No aparece `/dev/ttyACM0` | Pico no detectado | Comprobar cable USB; reiniciar Pico |
| `Permission denied /dev/pico` | Usuario no en grupo `dialout` | `sudo usermod -a -G dialout $USER` + re-login |
| Sin mensajes del Pico | Firmware no iniciado | Verificar que `main.py` del Pico ejecuta el canal |
| JSON malformado en logs | Bug en firmware Pico | Revisar `json.dumps()` en el Pico; comprobar encoding UTF-8 |
| Latencia > 50 ms en `t0` | Cola del Pico llena | Reducir frecuencia de `sensor_ambient`; aumentar prioridad de `t0` |
