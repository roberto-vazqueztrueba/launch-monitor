# Research: Protocolo de Comunicación Serie RPi ↔ Pico

**Feature**: `001-rpi-pico-serial-protocol`
**Date**: 2026-05-05
**Status**: ✅ Completo — sin NEEDS CLARIFICATION pendientes

---

## 1. Lectura no bloqueante en el host (pyserial, Python 3.11)

**Decision**: `threading.Thread` dedicado con `serial.readline()` bloqueante + `queue.Queue` para
transferir mensajes al hilo principal.

**Rationale**: Un hilo de lectura llama a `ser.readline(timeout=1)` que se bloquea hasta recibir
`\n`. USB CDC entrega el carácter en ~1 ms, muy por debajo del presupuesto de 50 ms para
`t0_detected`. Los resultados se encolan en `queue.Queue` para consumo asíncrono. `pyserial`
incluye `serial.threaded.ReaderThread + LineReader` que encapsula este patrón con despacho
limpio por protocolo.

**Alternatives considered**:
- `asyncio` + `pyserial-asyncio`: viable pero introduce jitter de scheduling del event loop sin
  ventaja real para un único puerto serie.
- `select()`: funciona en POSIX vía `serial.fileno()`, pero requiere buffering manual de líneas.
  Sin ventaja de latencia.

---

## 2. Envío desde el Pico (MicroPython RP2040)

**Decision**: `sys.stdout.write(json.dumps(data) + '\n')` — o equivalentemente `print(json.dumps(data))`.

**Rationale**: En MicroPython el puerto USB CDC está ligado a `sys.stdout`. `print()` escribe en
él y añade `\n`, exactamente lo que `readline()` del host espera. La llamada es no bloqueante en
la práctica: el stack USB tiene su propio TX FIFO y `write()` retorna tras encolar el dato.
`machine.UART` dirige pines GPIO físicos (GP0/GP1), **no** el cable USB — usarlo requeriría un
adaptador USB-UART adicional en la RPi.

**Alternatives considered**:
- `machine.UART(0, ...)`: Dirige UART físico (GPIO), no USB. Requiere hardware extra. Descartado.
- No existe ningún id de `machine.UART` que mapee al USB CDC en MicroPython RP2.

---

## 3. Dispositivo en el host y baud rate

**Decision**: El Pico con MicroPython aparece como `/dev/ttyACM0` (USB CDC ACM). El baud rate
configurado en `serial.Serial(baudrate=...)` es irrelevante para el throughput real.

**Rationale**: USB Full Speed proporciona ~1.2 MB/s independientemente del valor de baud rate.
El campo baud rate se envía al dispositivo vía mensaje de control CDC pero no afecta al
comportamiento. Usar `115200` es convencional y suficiente para documentación.

**Alternatives considered**:
- UART físico + adaptador USB-UART: genera `/dev/ttyUSB0`, crea dependencia de hardware
  adicional innecesaria cuando el cable USB ya existe.

---

## 4. Cola de eventos en el Pico (RAM RP2040)

**Decision**: `collections.deque((), 20)` — cola FIFO con maxlen=20.

**Rationale**: 20 mensajes × ~100 bytes = ~2,500 bytes de datos. Cada `str` en MicroPython añade
~16 bytes de cabecera → total ~3 KB. Con ~200 KB de heap disponibles en RP2040 esto es <2% de
la RAM. `deque` ofrece `append`/`popleft` O(1) y semántica clara de cola con límite de tamaño.

**Alternatives considered**:
- `list`: `popleft` equivalente es O(n) por el shift. Irrelevante a 20 elementos, pero `deque`
  es más correcto semánticamente.
- Ring buffer de `bytearray`: ahorra ~1 KB pero requiere serialización manual. No justificado.

---

## 5. Reconexión automática tras desconexión USB

**Decision**: Bucle de reintento con captura de `serial.SerialException` y sleep de 0.5 s entre
intentos de reapertura.

**Rationale**: Al desconectar el Pico, `readline()` lanza `SerialException`. El manejador cierra
el puerto, espera 0.5 s y reintenta `serial.Serial(port, ...)` en bucle hasta que el dispositivo
vuelva a estar disponible (el kernel re-enumera el nodo en ~500 ms tras el replug). La
reconexión se completa en < 1.5 s en condiciones normales, cumpliendo SC-002 (< 3 s).

```python
def run_reader(port: str, q: queue.Queue):
    while True:
        try:
            with serial.Serial(port, timeout=1) as ser:
                while True:
                    line = ser.readline()
                    if line:
                        q.put(line)
        except serial.SerialException:
            time.sleep(0.5)
        except Exception:
            time.sleep(1)
```

**Alternatives considered**:
- `inotify`/`pyinotify` sobre `/dev/`: más reactivo pero añade dependencia y complejidad.
  El polling a 500 ms es < 0.1% de CPU.
- `serial.tools.list_ports` polling: útil para logging diagnóstico, no necesario para el bucle
  de reconexión.

---

## Resumen de decisiones técnicas

| Tema | Decisión |
|------|----------|
| Transporte físico | USB CDC ACM (`/dev/ttyACM0`), baud rate nominal 115200 |
| Framing de mensajes | Newline-delimited JSON (`\n` como delimitador) |
| Lectura en host | `threading.Thread` + `serial.readline()` + `queue.Queue` |
| Envío desde Pico | `sys.stdout.write(json.dumps(data) + '\n')` |
| Cola en Pico | `collections.deque((), 20)` (~3 KB RAM) |
| Reconexión | Retry loop con `SerialException` + 0.5 s backoff |
| Baud rate | 115200 (convencional; sin efecto en USB CDC) |

## NEEDS CLARIFICATION resueltos

Ninguno — todos los aspectos técnicos tienen decisión confirmada. La especificación estaba
completa y no requirió investigación adicional para resolver ambigüedades.
