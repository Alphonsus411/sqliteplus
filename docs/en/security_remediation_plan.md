[Leer en español](../plan_remediacion_bugs_seguridad.md)

# Technical Audit: Bugs, Operational Issues, and Security Gaps

## Executive Summary

Automated tests and static analysis of the repository were executed to identify reproducible failures.

- **Test Result:** `57 failed, 92 passed, 10 skipped`.
- **Security Result (Bandit):** 9 findings (7 medium, 2 low), including dynamic SQL, unhardened `urlopen`, and overly broad `except` blocks.

## Evidence Used

1. `pytest -q`
2. `bandit -q -r sqliteplus -x sqliteplus/core/*.pyx,sqliteplus/utils/*.pyx`

## Main Findings

### H1) Massive Functional Regression in API/DB Routes
- Symptom: multiple API and async manager tests fail with unexpected HTTP statuses (`404/503`) or incompatible behavior.
- Impact: the main flow of create table/insert/query is unreliable.
- Severity: **Critical**.

### H2) SQLCipher Encryption Flow Breaks Unencrypted and Mixed Scenarios
- Symptom: security/503 errors and `SQLitePlusCipherError` exceptions in backup/export and initialization routes.
- Impact: blocks valid operations when there is no SQLCipher support or when key/capability is not negotiated correctly.
- Severity: **High**.

### H3) CLI Contract Incompatibilities (Output and Error Codes)
- Symptom: CLI tests expect different messages/codes; for example `backup` without source does not fail as it should.
- Impact: unstable automation scripts and DX.
- Severity: **High**.

### H4) Scattered Dynamic SQL Construction
- Symptom: use of SQL with `f-strings` in several points (Bandit B608), although part of the identifiers are already escaped.
- Impact: risk of future regression towards SQL injection if validation is omitted in a new route.
- Severity: **Medium-High**.

### H5) In-Memory Rate Limiter Without Global Pruning
- Symptom: the rate limiter maintains maps per IP/user without a strategy for expiring complete entries.
- Impact: indefinite memory growth under distributed attacks or high cardinality traffic.
- Severity: **Medium**.

### H6) Network Call with `urllib.request.urlopen` Without Additional Hardening
- Symptom: Bandit B310 detects `urlopen`; currently a fixed URL is used but validation/timeout/scheme control and strict error handling are missing.
- Impact: risk surface in future modifications of the remote version check.
- Severity: **Medium**.

## Structured Task Plan (Step by Step)

### Phase 1 — Functional Stabilization (Top Priority)

#### Task 1.1 — Restore Minimum Stable API Contract
**Steps:**
1. Reproduce and isolate failures in `tests/test_database_api.py`, `tests/test_server_endpoints.py`, `tests/test_insert_and_fetch_data.py`.
2. Adjust SQL/HTTP error mapping (404, 400, 409, 500) as appropriate.
3. Add parameterized error mapping tests.

**Acceptance Criteria:** those test modules pass without authentication regression.

#### Task 1.2 — Fix Connection Lifecycle in `AsyncDatabaseManager`
**Steps:**
1. Reproduce failures in `tests/test_database_manager_async.py`.
2. Review `_INITIALIZED_DATABASES`, `_initialized_keys`, and recreation by loop.
3. Add non-regression for `reset_on_init`, `SQLITEPLUS_FORCE_RESET`, and multi-loop reopening.

**Acceptance Criteria:** passes `tests/test_database_manager_async.py` completely.

#### Task 1.3 — Unify CLI Behavior with Expectations
**Steps:**
1. Fix `backup` to explicitly fail if the source database is missing.
2. Homogenize output and return codes.
3. Ensure propagation of operational errors with non-zero exit code.

**Acceptance Criteria:** passes `tests/test_cli_export.py` and `tests/test_relative_imports.py`.

### Phase 2 — Security and Robustness

#### Task 2.1 — Harden SQLCipher Encryption Handling
**Steps:**
1. Define behavior matrix for missing/empty key, missing support, encrypted/unencrypted DB.
2. Implement secure negotiation in `apply_cipher_key` and `verify_cipher_support`.
3. Add dedicated test suite sync/async/replication.

**Acceptance Criteria:** passes `tests/test_sqliteplus_sync.py`, `tests/test_crypto_sqlite.py`, `tests/test_crypto_sqlite_async.py`.

#### Task 2.2 — Reduce Dynamic SQL Surface
**Steps:**
1. Centralize secure helper to compose identifier SQL.
2. Replace SQL interpolations in API/replication/sync.
3. Add negative tests with malicious names.

**Acceptance Criteria:** Bandit without relevant B608 (or with documented exceptions).

#### Task 2.3 — Limit In-Memory Rate Limiter Growth
**Steps:**
1. Add periodic cleanup of expired states by IP/user.
2. Define entry ceiling with TTL/LRU policy.
3. Expose active state metrics.

**Acceptance Criteria:** synthetic load test with bounded memory.

#### Task 2.4 — Harden Remote Version Check in CLI
**Steps:**
1. Isolate remote query and validate `https` scheme + allowed host.
2. Maintain explicit timeout and strict error handling.
3. Add tests with network mocking.

**Acceptance Criteria:** Bandit B310 mitigated or justified.

### Phase 3 — Quality Closure

#### Task 3.1 — Target Regression Pipeline
**Steps:**
1. Create CI target `core-regression` (API, DB async, CLI, Bandit).
2. Publish benchmarks baseline to separate functional/performance regression.

**Acceptance Criteria:** pipeline fails automatically upon critical contract rupture.

## Recommended Order
1. Task 1.1
2. Task 1.2
3. Task 2.1
4. Task 1.3
5. Task 2.2
6. Task 2.3
7. Task 2.4
8. Task 3.1
