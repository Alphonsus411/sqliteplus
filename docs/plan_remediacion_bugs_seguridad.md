[Read in English](en/security_remediation_plan.md)

# Auditoría técnica: bugs, problemas de funcionamiento y fisuras de seguridad

## Resumen ejecutivo

Se ejecutaron pruebas automáticas y análisis estático del repositorio para identificar fallos reproducibles.

- **Resultado de tests:** `57 failed, 92 passed, 10 skipped`.
- **Resultado de seguridad (Bandit):** 9 hallazgos (7 medios, 2 bajos), incluyendo SQL dinámico, `urlopen` sin hardening y bloques `except` demasiado amplios.

## Evidencia usada

1. `pytest -q`
2. `bandit -q -r sqliteplus -x sqliteplus/core/*.pyx,sqliteplus/utils/*.pyx`

## Hallazgos principales

### H1) Regresión funcional masiva en rutas API/DB
- Síntoma: múltiples tests de API y gestores asíncronos fallan con estados HTTP inesperados (`404/503`) o comportamiento no compatible.
- Impacto: el flujo principal de crear tabla/insertar/consultar no es confiable.
- Severidad: **Crítica**.

### H2) Flujo de cifrado SQLCipher rompe escenarios no cifrados y mixtos
- **Estado**: Resuelto.
- **Acción tomada**: Se implementó una negociación robusta de claves en `apply_cipher_key` (síncrono) y `apply_cipher_key_async` (asíncrono), soportando escenarios mixtos y validando correctamente la presencia de SQLCipher.
- **Severidad original**: Alta.

### H3) Incompatibilidades de contrato CLI (salida y códigos de error)
- **Estado**: Resuelto.
- **Acción tomada**: Se unificaron los códigos de salida y mensajes de error en la CLI. El comando `backup` ahora valida la existencia de la base de datos origen antes de proceder.

### H4) Construcción SQL dinámica dispersa
- **Estado**: Resuelto.
- **Acción tomada**: Se centralizó la lógica de escape en `sqliteplus.core.schemas.escape_sqlite_identifier`. Todos los módulos (API, Sync, Async, CLI) ahora utilizan esta función única para sanear identificadores, eliminando el riesgo de inyección SQL por construcción manual de cadenas.
- **Severidad original**: Media-Alta.

### H5) Rate limiter en memoria sin poda global
- Síntoma: el rate limiter mantiene mapas por IP/usuario sin estrategia de expiración de entradas completas.
- Impacto: crecimiento indefinido de memoria bajo ataques distribuidos o tráfico de alta cardinalidad.
- Severidad: **Media**.

### H6) Llamada de red con `urllib.request.urlopen` sin endurecimiento adicional
- Síntoma: Bandit B310 detecta `urlopen`; actualmente se usa URL fija pero falta reforzar validación/timeout/control de esquema y manejo estricto de errores.
- Impacto: superficie de riesgo en futuras modificaciones del chequeo de versión remota.
- Severidad: **Media**.

## Plan de tareas estructurado (paso a paso)

### Fase 1 — Estabilización funcional (prioridad máxima)

#### Tarea 1.1 — Restaurar contrato API mínimo estable
- **Estado**: Completado.
- **Detalle**: Se aislaron y corrigieron los fallos en tests de API, ajustando el mapeo de errores HTTP/SQL (409 Conflict para violaciones de integridad, 400 Bad Request para errores de esquema).

#### Tarea 1.2 — Corregir ciclo de vida de conexiones en `AsyncDatabaseManager`
- **Estado**: Completado.
- **Detalle**: Se corrigió la gestión de conexiones asíncronas, asegurando que se cierren y reinicien correctamente ante cambios de loop de eventos o solicitudes de reinicio (`reset_on_init`).

#### Tarea 1.3 — Unificar comportamiento CLI con expectativas
- **Estado**: Completado.
- **Detalle**: La CLI ahora reporta errores de forma consistente y valida pre-condiciones críticas (como la existencia del archivo de base de datos) antes de ejecutar operaciones.

### Fase 2 — Seguridad y robustez

#### Tarea 2.1 — Endurecer manejo de cifrado SQLCipher
- **Estado**: Completado.
- **Detalle**: Se implementaron `apply_cipher_key` y `apply_cipher_key_async` con validación estricta de soporte y manejo de claves vacías/inválidas. Se añadieron tests exhaustivos en `tests/test_crypto_sqlite.py` y su variante async.

#### Tarea 2.2 — Reducir superficie SQL dinámica
- **Estado**: Completado.
- **Detalle**: Se centralizó el escapado en `schemas.py` y se refactorizaron todos los puntos de interpolación de identificadores para usar esta utilidad única.

#### Tarea 2.3 — Limitar crecimiento del rate limiter en memoria
**Pasos:**
1. Añadir limpieza periódica de estados vencidos por IP/usuario.
2. Definir techo de entradas con política TTL/LRU.
3. Exponer métricas de estados activos.

**Criterios de aceptación:** test de carga sintético con memoria acotada.

#### Tarea 2.4 — Endurecer consulta remota de versión en CLI
**Pasos:**
1. Aislar consulta remota y validar esquema `https` + host permitido.
2. Mantener timeout explícito y manejo estricto de errores.
3. Añadir tests con mocking de red.

**Criterios de aceptación:** Bandit B310 mitigado o justificado.

### Fase 3 — Cierre de calidad

#### Tarea 3.1 — Pipeline de regresión objetivo
**Pasos:**
1. Crear target CI `core-regression` (API, DB async, CLI, Bandit).
2. Publicar baseline de benchmarks para separar regresión funcional/rendimiento.

**Criterios de aceptación:** pipeline falla automáticamente ante ruptura de contratos críticos.

## Orden recomendado
1. Tarea 1.1
2. Tarea 1.2
3. Tarea 2.1
4. Tarea 1.3
5. Tarea 2.2
6. Tarea 2.3
7. Tarea 2.4
8. Tarea 3.1
