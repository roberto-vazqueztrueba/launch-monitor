<!--
SYNC IMPACT REPORT
==================
Version change: 1.2.1 → 1.2.2
Added sections:
  - Propósito del Sistema
  - Clasificación de Datos (MEASURED / CALCULATED / ESTIMATED)
  - t0 como Evento Central
  - Sistema Orientado a Eventos
  - Estados del Sistema
  - Modos de Funcionamiento
  - Pipeline del Golpe
  - Modelo de Datos del Golpe
  - Gestión de Sesiones
  - Física y Balística
  - Spin (sección crítica)
  - UX e Interacción de Usuario
  - Calibración
  - Feedback
  - UI
  - Logging
  - Evolución
  - Regla de Oro
Modified principles:
  - I. Precisión de Medición (reforzado con clasificación de datos y spin)
  - II. Modularidad de Sensores (inventario sin cambios)
  - III. Test-First (ampliado con tipos de test)
  - V. Simplicidad y YAGNI (reforzado con "Robustez sobre Perfección")
Removed sections: N/A
Templates requiring updates:
  - .specify/templates/plan-template.md ✅
  - .specify/templates/spec-template.md ✅
  - .specify/templates/tasks-template.md ✅
Deferred TODOs:
  - Protocolo exacto RPi ↔ Pico: definir en primer feature de comunicación
  - MAX9814: confirmar compatibilidad eléctrica y de señal con Pico antes de implementar integración
  - BNO055 vs MPU6050: confirmar sensor de inclinación final
-->

# Launch Monitor Constitution

## Propósito del Sistema

Construir un sistema de medición de golpeo de bola de golf basado en radar mmWave (IWR6842),
sensores periféricos (micrófono, IMU, ambiente), Raspberry Pi + Raspberry Pi Pico, e interfaz
física (pantalla, encoder, botones, feedback).

El sistema DEBE ser: **Preciso · Robusto · Explicable · Modular · Evolutivo**

## Core Principles

### I. Precisión y Explicabilidad (NON-NEGOTIABLE)

Los datos de sensores DEBEN ser validados antes de ser procesados o almacenados. Toda medición
DEBE incluir metadatos de confianza (calidad de señal, timestamp, fuente del sensor). Los
parámetros calculados DEBEN derivarse de mediciones validadas.

El sistema NO DEBE mostrar datos sin confianza asociada. NO DEBE inventar valores.
**Regla de oro**: Si no puedes explicarlo, no lo muestres.

**Clasificación obligatoria de datos** — todo dato DEBE etiquetarse como una de:
- `MEASURED` — medido directamente por un sensor (radar, micrófono, IMU...)
- `CALCULATED` — derivado de mediciones mediante física directa (smash factor, ángulo de lanzamiento...)
- `ESTIMATED` — inferido con un modelo (spin, trayectoria completa, carry, punto de aterrizaje...)

Nunca mezclar categorías sin etiquetar explícitamente.

**Rationale**: La precisión es la razón de ser del dispositivo. Un golpe mal etiquetado o
mostrado sin confianza destruye la credibilidad del sistema.

### II. Modularidad de Sensores

Cada tipo de sensor DEBE encapsularse en su propio módulo con interfaz estandarizada. Los módulos
de sensor DEBEN ser intercambiables e independientemente testeables. El sistema central NO DEBE
depender de la implementación concreta de ningún sensor.

Inventario de sensores/periféricos (a 2026-05-05):
- **Radar**: Texas Instruments IWR6842BOOST (conectado directo a RPi)
- **Micrófono**: MAX9814 (módulo con AGC integrado, conectado a RPi Pico) — fuente de `t0`
- **Ambiental**: BME280 — temperatura, presión, humedad (RPi Pico)
- **IMU**: MPU6050 / BNO055 — inclinación del dispositivo (RPi Pico) `TODO: confirmar modelo final`
- **NFC**: PN532 (RPi Pico) — selección rápida de perfil
- **UI física**: encoder rotativo + 4 botones + buzzer + LEDs (RPi Pico)
- **Pantalla**: conectada directamente a la RPi

**Rationale**: El hardware evoluciona; la modularidad permite sustituir sensores sin reescribir
el sistema.

### III. t0 como Evento Central (NON-NEGOTIABLE)

`t0` es el instante de impacto bola-palo. Es el ancla temporal de todo procesamiento.

- `t0` DEBE ser detectado por el micrófono (gestionado por el Pico)
- El radar SIEMPRE está activo; `t0` se usa para seleccionar la ventana de datos radar, NO para
  iniciar la captura
- Todo cálculo de velocidad, ángulo y trayectoria DEBE referenciarse respecto a `t0`
- Si `t0` no puede determinarse con confianza suficiente, el golpe DEBE marcarse con baja
  confianza o descartarse

**Rationale**: Sin `t0` fiable no hay ventana radar válida y todos los cálculos posteriores
son incorrectos.

### IV. Sistema Orientado a Eventos

El sistema DEBE funcionar mediante eventos asíncronos. La lógica bloqueante está PROHIBIDA.

Tipos de eventos reconocidos:
- `sensor_event` — dato crudo de sensor
- `input_event` — acción del usuario (encoder, botón, NFC)
- `radar_event` — frame o detección del radar
- `state_transition` — cambio de estado del sistema

Las transiciones de estado DEBEN ser explícitas y trazables.

**Rationale**: El hardware es concurrente por naturaleza; la arquitectura bloqueante provoca
pérdida de eventos y latencia inaceptable.

### V. Persistencia Fiable de Sesiones

Cada sesión de golpeos DEBE persistirse atómicamente (todo o nada). Los datos crudos del sensor
DEBEN guardarse junto con los parámetros calculados para permitir recálculo posterior. El esquema
de base de datos DEBE versionarse; las migraciones DEBEN ser reproducibles.

Un golpe marcado como "bad shot" NO DEBE eliminarse; se guarda con flag `is_bad_shot=true`,
no se usa para métricas, y puede revertirse.

**Rationale**: Las sesiones de entrenamiento tienen valor a largo plazo; la pérdida de datos es
inaceptable.

### VI. Test-First

El desarrollo DEBE seguir Red-Green-Refactor: tests escritos y aprobados → tests fallando →
implementación → tests en verde.

Tipos de tests requeridos:
- **Unitarios**: toda lógica de cálculo de parámetros físicos/balísticos
- **Simulados**: flujos de sesión completa con datos sintéticos
- **Físicos**: validación con hardware real (documentados, no automatizados)

**Rationale**: Los errores en cálculos de física son difíciles de detectar sin tests explícitos.

### VII. Robustez sobre Perfección

El sistema DEBE preferir un resultado consistente y explicable sobre un resultado perfecto
ocasional. Ante incertidumbre, DEBE degradar con gracia: mostrar confianza baja, no fallar.

La complejidad DEBE justificarse con un requisito concreto y activo. Las abstracciones prematuras
están PROHIBIDAS. El código para MicroPython DEBE ser explícito y predecible.

**Rationale**: El sistema opera en entorno real con ruido, vibraciones y variabilidad; la
robustez es una restricción técnica, no una preferencia.

## Separación de Responsabilidades

### Raspberry Pi (host)
- Procesamiento de datos radar (pipeline completo)
- Lógica de negocio y cálculos balísticos
- UI en pantalla
- Persistencia (SQLite)
- Orquestación de flujo de golpe
- Logging

### Raspberry Pi Pico (firmware MicroPython)
- Lectura de todos los sensores periféricos (micrófono, BME280, IMU, NFC)
- Detección de `t0`
- Gestión de input físico (encoder, botones)
- Control de feedback (buzzer, LEDs)
- Generación y envío de eventos al host

## Arquitectura de Hardware

```
┌─────────────────────────────────────────────────────┐
│                  Raspberry Pi (cerebro)             │
│  Python 3.11+  |  SQLite  |  UI en pantalla directa │
│                                                     │
│  ┌──────────────┐    ┌───────────────────────────┐  │
│  │ IWR6842BOOST │    │     Raspberry Pi Pico     │  │
│  │    (radar)   │    │       MicroPython         │  │
│  │  USB/serial  │    │                           │  │
│  └──────────────┘    │  ┌─────────┐ ┌─────────┐  │  │
│                      │  │ MAX9814 │ │ BME280  │  │  │
│                      │  │  (mic)  │ │(ambient)│  │  │
│                      │  └─────────┘ └─────────┘  │  │
│                      │  ┌─────────┐ ┌─────────┐  │  │
│                      │  │MPU6050/ │ │  PN532  │  │  │
│                      │  │ BNO055  │ │  (NFC)  │  │  │
│                      │  └─────────┘ └─────────┘  │  │
│                      │  ┌─────────────────────┐  │  │
│                      │  │ encoder · botones   │  │  │
│                      │  │ buzzer · LEDs       │  │  │
│                      │  └─────────────────────┘  │  │
│                      └───────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Stack y Restricciones de Plataforma

- **Lenguajes**: Python 3.11+ (RPi host), MicroPython (RPi Pico firmware)
- **Base de datos**: SQLite en RPi; esquema migratable con versionado explícito
- **Testing**: `pytest` en RPi; scripts de verificación en MicroPython para el Pico
- **Comunicación RPi ↔ Pico**: protocolo serial sobre USB; mensajes JSON versionados
  `TODO: confirmar protocolo exacto en primer feature de comunicación`
- **Comunicación RPi ↔ Radar**: protocolo TI sobre USB/UART; encapsulado en `sensors/radar.py`
- **Dependencias externas**: DEBEN minimizarse en el firmware Pico; en el host se permiten con
  justificación explícita
- **Formato de datos**: JSON para intercambio RPi↔Pico; estructuras nativas en memoria

## Estados del Sistema

```
BOOTING → SELF_TEST → WAITING_PROFILE → WAITING_CLUB → READY
                                                          ↓
ERROR ←─────────────────────────── ARMED → IMPACT_DETECTED → PROCESSING → RESULTS
                                     ↑                                        │
                                     └────────────────────────────────────────┘
DIAGNOSTICS (accesible desde cualquier estado con permiso)
```

## Modos de Funcionamiento

| Modo            | Trayectoria | Precisión | Estimación |
|-----------------|-------------|-----------|------------|
| `MODE_RANGE`    | Larga       | Alta      | Baja       |
| `MODE_SIMULATOR`| Corta       | Baja      | Alta       |

El modo afecta: radar pipeline, BallisticsEngine, y la confianza reportada de cada parámetro.

## Pipeline del Golpe

1. Usuario selecciona palo (encoder / NFC)
2. Usuario arma sistema (encoder click)
3. Micrófono (Pico) detecta `t0`
4. RPi extrae ventana de frames radar centrada en `t0`
5. Detecta palo y bola en la nube de puntos
6. Calcula velocidades (`MEASURED`)
7. Calcula ángulos de lanzamiento (`MEASURED` / `CALCULATED`)
8. Ejecuta `BallisticsEngine` con densidad de aire del BME280
9. Muestra resultados con confianza
10. Guarda golpe en SQLite

## Modelo de Datos del Golpe

| Campo           | Tipo         | Categoría    |
|-----------------|--------------|--------------|
| `club_speed`    | float (m/s)  | `MEASURED`   |
| `ball_speed`    | float (m/s)  | `MEASURED`   |
| `smash_factor`  | float        | `CALCULATED` |
| `launch_angle`  | float (°)    | `CALCULATED` |
| `apex`          | float (m)    | `CALCULATED` |
| `carry`         | float (m)    | `ESTIMATED`  |
| `landing_spot`  | point (x, y) | `ESTIMATED`  |
| `trajectory`    | list[point]  | `ESTIMATED`  |
| `spin`          | float (rpm)  | `ESTIMATED`  |
| `spin_axis`     | float (°)    | `ESTIMATED`  |
| `mode`          | enum         | —            |
| `confidence`    | float [0,1]  | —            |
| `is_bad_shot`   | bool         | —            |

## Spin (CRÍTICO)

El spin **NO se mide directamente**. Su estimación DEBE etiquetarse como:

- `ESTIMATED_BY_CLUB_MODEL` — estimado a partir del modelo del palo seleccionado
- `ESTIMATED_BY_FIT` — estimado ajustando la trayectoria radar (solo en `MODE_RANGE`)

Presentar spin como `MEASURED` o `CALCULATED` está **PROHIBIDO**.

## Física y Balística

El `BallisticsEngine` DEBE usar: gravedad, drag aerodinámico, lift (efecto spin), densidad del
aire.

La densidad del aire DEBE calcularse como `ρ = f(temperatura, presión, humedad)` usando los
datos del BME280. Usar densidad estándar sin corrección está PROHIBIDO cuando el BME280 esté
operativo.

## UX e Interacción de Usuario

### Encoder rotativo
- **Giro** → cambiar palo seleccionado
- **Click** → aceptar / armar sistema
- **Long press** → cambiar modo (`MODE_RANGE` ↔ `MODE_SIMULATOR`)

### Botones físicos
| Botón              | Acción                        |
|--------------------|-------------------------------|
| `BAD_SHOT`         | Marcar último golpe como malo |
| `SAVE_SESSION`     | Guardar y cerrar sesión       |
| `CALIBRATE`        | Iniciar calibración           |
| `RESET_SESSION`    | Resetear sesión (long press)  |

### NFC
- Lectura de tarjeta/tag → selección rápida de perfil de jugador o palo
- El encoder permite ajuste manual como alternativa

## Calibración

El sistema DEBE permitir: calibración de inclinación del dispositivo, validación de nivel,
y compensación trigonométrica de ángulos medidos por el radar según la inclinación del IMU.

## Feedback (Buzzer + LEDs)

DEBE indicar: estado actual del sistema, errores, confirmación de acciones, modo activo.
Los patrones de feedback DEBEN ser consistentes y documentados.

## UI

DEBE mostrar: métricas principales del golpe con su categoría (M/C/E), trayectoria (vistas
lateral y superior), apex, modo activo, confianza global del golpe.

## Logging

Todo evento importante DEBE registrarse: inputs de usuario, eventos radar, calibración, errores,
resultados de golpe. El log DEBE ser consultable para debug sin afectar al flujo normal.

## Evolución

El sistema DEBE diseñarse para permitir: mejora de modelos físicos, mejora de spin estimation,
incorporación futura de ML, y adición de nuevos sensores sin reescribir la arquitectura core.

## Governance

Esta constitución tiene precedencia sobre cualquier otra guía o práctica del proyecto. Las
enmiendas DEBEN:
1. Documentar la motivación del cambio
2. Incrementar la versión según semver (MAJOR: eliminación/redefinición de principios;
   MINOR: nuevos principios o secciones; PATCH: aclaraciones)
3. Actualizar los templates afectados antes de fusionar

Todos los PRs/revisiones DEBEN verificar el cumplimiento de los principios I-VII. La complejidad
añadida DEBE justificarse explícitamente contra el Principio VII.

**Version**: 1.2.2 | **Ratified**: 2026-05-05 | **Last Amended**: 2026-05-06

### I. Precisión de Medición (NON-NEGOTIABLE)

Los datos de sensores DEBEN ser validados antes de ser procesados o almacenados. Toda medición
DEBE incluir metadatos de confianza (calidad de señal, timestamp, fuente del sensor). Los
parámetros calculados DEBEN derivarse de mediciones validadas; nunca de datos crudos sin
verificar.

**Rationale**: La precisión es la razón de ser del dispositivo. Un golpe mal medido es peor que
ningún golpe medido.

### II. Modularidad de Sensores

Cada tipo de sensor DEBE encapsularse en su propio módulo con interfaz estandarizada. Los módulos
de sensor DEBEN ser intercambiables e independientemente testeables. El sistema central NO DEBE
depender de la implementación concreta de ningún sensor.

Inventario de sensores/periféricos conocidos (a 2026-05-05):
- **Radar**: Texas Instruments IWR6842BOOST (conectado directo a RPi)
- **Micrófono**: SparkFun SEN-14262 (conectado a RPi Pico)
- **Ambiental**: BME280 — temperatura, presión, humedad (conectado a RPi Pico)
- **IMU**: MPU6050 — acelerómetro + giroscopio para inclinación del dispositivo (RPi Pico)
- **NFC**: PN532 (conectado a RPi Pico)
- **UI física**: buzzer, LEDs, botones físicos, encoder rotativo con pulsador (RPi Pico)

**Rationale**: El hardware evoluciona; la arquitectura modular permite añadir o sustituir sensores
sin reescribir el sistema.

### III. Test-First

El desarrollo DEBE seguir el ciclo Red-Green-Refactor: tests escritos y aprobados → tests
fallando → implementación → tests en verde. Los tests unitarios son OBLIGATORIOS para toda lógica
de cálculo de parámetros balísticos. Los tests de integración son OBLIGATORIOS para flujos de
sesión completa (inicio → golpe → almacenamiento).

**Rationale**: Los errores en cálculos de física del golf son difíciles de detectar sin tests
explícitos.

### IV. Persistencia Fiable de Sesiones

Cada sesión de golpeos DEBE persistirse atómicamente (todo o nada). Los datos crudos del sensor
DEBEN guardarse junto con los parámetros calculados para permitir recálculo posterior. El esquema
de base de datos DEBE versionarse; las migraciones DEBEN ser reproducibles.

**Rationale**: Las sesiones de entrenamiento tienen valor a largo plazo; la pérdida de datos es
inaceptable.

### V. Simplicidad y YAGNI

La complejidad DEBE justificarse con un requisito concreto y activo. Las abstracciones prematuras
están PROHIBIDAS. MicroPython impone restricciones de memoria y CPU que DEBEN respetarse; el
código para hardware embebido DEBE ser explícito y predecible, sin magia.

**Rationale**: El sistema corre en hardware con recursos limitados; la simplicidad es una
restricción técnica, no solo una preferencia.

## Arquitectura de Hardware

```
┌─────────────────────────────────────────────────────┐
│                  Raspberry Pi (cerebro)              │
│  Python 3.11+  |  SQLite  |  UI en pantalla directa │
│                                                     │
│  ┌──────────────┐    ┌───────────────────────────┐  │
│  │ IWR6842BOOST │    │     Raspberry Pi Pico      │  │
│  │    (radar)   │    │       MicroPython          │  │
│  │  USB/serial  │    │                           │  │
│  └──────────────┘    │  ┌─────────┐ ┌─────────┐  │  │
│                      │  │SEN-14262│ │ BME280  │  │  │
│                      │  │  (mic)  │ │(amb.)   │  │  │
│                      │  └─────────┘ └─────────┘  │  │
│                      │  ┌─────────┐ ┌─────────┐  │  │
│                      │  │ MPU6050 │ │  PN532  │  │  │
│                      │  │  (IMU)  │ │  (NFC)  │  │  │
│                      │  └─────────┘ └─────────┘  │  │
│                      │  ┌──────────────────────┐  │  │
│                      │  │ buzzer·LEDs·botones  │  │  │
│                      │  │   encoder rotativo   │  │  │
│                      │  └──────────────────────┘  │  │
│                      └───────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Nodos**:
- **RPi (host)**: lógica de negocio, cálculos, persistencia, UI en pantalla
- **RPi Pico (periféricos)**: firmware MicroPython, gestiona todos los sensores excepto el radar
- **IWR6842BOOST**: conectado directamente a la RPi (USB o UART)

## Stack y Restricciones de Plataforma

- **Lenguajes**: Python 3.11+ (RPi host), MicroPython (RPi Pico firmware)
- **Base de datos**: SQLite en RPi; esquema migratable con versionado explícito
- **Testing**: `pytest` en RPi; scripts de verificación en MicroPython para el Pico
- **Comunicación RPi ↔ Pico**: protocolo serial sobre USB; contrato de mensajes JSON definido
  y versionado (TODO: confirmar protocolo exacto en primer feature de comunicación)
- **Comunicación RPi ↔ Radar**: protocolo propietario TI sobre USB/UART; encapsulado en módulo
  `sensors/radar.py` en el host
- **Dependencias externas**: DEBEN minimizarse en el firmware Pico; en el host se permiten con
  justificación explícita
- **Formato de datos internos**: JSON para intercambio RPi↔Pico; estructuras nativas en memoria

## Flujo de Desarrollo

1. Toda nueva funcionalidad comienza con una especificación (`/speckit.specify`)
2. Los tests se escriben y revisan ANTES de la implementación
3. Las ramas de feature siguen la convención `###-nombre-feature`
4. Se realizan commits al completar cada tarea definida en `tasks.md`
5. Los cambios de contrato sensor↔host requieren actualización del esquema de mensajes antes
   de implementar
6. Toda sesión de datos generada durante pruebas DEBE ser borrable / aislada del entorno de
   producción

## Governance

Esta constitución tiene precedencia sobre cualquier otra guía o práctica del proyecto. Las
enmiendas DEBEN:
1. Documentar la motivación del cambio
2. Incrementar la versión según semver (MAJOR: eliminación/redefinición de principios;
   MINOR: nuevos principios o secciones; PATCH: aclaraciones)
3. Actualizar los templates afectados antes de fusionar

Todos los PRs/revisiones DEBEN verificar el cumplimiento de los principios I-V. La complejidad
añadida DEBE justificarse explícitamente contra el Principio V.

**Version**: 1.1.0 | **Ratified**: 2026-05-05 | **Last Amended**: 2026-05-05
