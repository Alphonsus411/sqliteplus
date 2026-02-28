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
- Síntoma: errores de seguridad/503 y excepciones `SQLitePlusCipherError` en rutas de backup/export e inicialización.
- Impacto: bloquea operaciones válidas cuando no hay soporte SQLCipher o cuando la clave/capacidad no se negocia correctamente.
- Severidad: **Alta**.

### H3) Incompatibilidades de contrato CLI (salida y códigos de error)
- Síntoma: tests de CLI esperan mensajes/códigos distintos; por ejemplo `backup` sin fuente no falla como debería.
- Impacto: scripts de automatización y DX inestables.
- Severidad: **Alta**.

### H4) Construcción SQL dinámica dispersa
- Síntoma: uso de SQL con `f-strings` en varios puntos (Bandit B608), aunque parte de los identificadores ya se escapan.
- Impacto: riesgo de regresión futura hacia inyección SQL si se omite validación en una nueva ruta.
- Severidad: **Media-Alta**.

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
**Pasos:**
1. Reproducir y aislar fallos de `tests/test_database_api.py`, `tests/test_server_endpoints.py`, `tests/test_insert_and_fetch_data.py`.
2. Ajustar mapeo de errores SQL/HTTP (404, 400, 409, 500) según caso.
3. Añadir pruebas parametrizadas de mapeo de errores.

**Criterios de aceptación:** pasan esos módulos de tests sin regresión de autenticación.

#### Tarea 1.2 — Corregir ciclo de vida de conexiones en `AsyncDatabaseManager`
**Pasos:**
1. Reproducir fallos de `tests/test_database_manager_async.py`.
2. Revisar `_INITIALIZED_DATABASES`, `_initialized_keys` y recreación por loop.
3. Añadir no-regresión para `reset_on_init`, `SQLITEPLUS_FORCE_RESET` y reapertura multi-loop.

**Criterios de aceptación:** pasa `tests/test_database_manager_async.py` completo.

#### Tarea 1.3 — Unificar comportamiento CLI con expectativas
**Pasos:**
1. Corregir `backup` para fallar explícitamente si falta la base origen.
2. Homogeneizar salida y códigos de retorno.
3. Asegurar propagación de errores operativos con exit code no-cero.

**Criterios de aceptación:** pasan `tests/test_cli_export.py` y `tests/test_relative_imports.py`.

### Fase 2 — Seguridad y robustez

#### Tarea 2.1 — Endurecer manejo de cifrado SQLCipher
**Pasos:**
1. Definir matriz de comportamiento para clave ausente/vacía, soporte ausente, DB cifrada/no cifrada.
2. Implementar negociación segura en `apply_cipher_key` y `verify_cipher_support`.
3. Añadir suite de pruebas dedicada sync/async/replication.

**Criterios de aceptación:** pasan `tests/test_sqliteplus_sync.py`, `tests/test_crypto_sqlite.py`, `tests/test_crypto_sqlite_async.py`.

#### Tarea 2.2 — Reducir superficie SQL dinámica
**Pasos:**
1. Centralizar helper seguro para componer SQL de identificadores.
2. Reemplazar interpolaciones SQL en API/replicación/sync.
3. Añadir tests negativos con nombres maliciosos.

**Criterios de aceptación:** Bandit sin B608 relevantes (o con excepciones documentadas).

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
