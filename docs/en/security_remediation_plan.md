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
- **Status**: Resolved.
- **Action Taken**: Robust key negotiation implemented in `apply_cipher_key` (sync) and `apply_cipher_key_async` (async), supporting mixed scenarios and correctly validating SQLCipher presence.
- **Original Severity**: High.

### H3) CLI Contract Incompatibilities (Output and Error Codes)
- **Status**: Resolved.
- **Action Taken**: CLI exit codes and error messages unified. The `backup` command now validates source database existence before proceeding.

### H4) Scattered Dynamic SQL Construction
- **Status**: Resolved.
- **Action Taken**: Escaping logic centralized in `sqliteplus.core.schemas.escape_sqlite_identifier`. All modules (API, Sync, Async, CLI) now use this single utility to sanitize identifiers, eliminating SQL injection risk from manual string construction.
- **Original Severity**: Medium-High.

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
- **Status**: Completed.
- **Detail**: API test failures isolated and fixed, adjusting HTTP/SQL error mapping (409 Conflict for integrity violations, 400 Bad Request for schema errors).

#### Task 1.2 — Fix Connection Lifecycle in `AsyncDatabaseManager`
- **Status**: Completed.
- **Detail**: Async connection management fixed, ensuring correct closing and resetting upon event loop changes or restart requests (`reset_on_init`).

#### Task 1.3 — Unify CLI Behavior with Expectations
- **Status**: Completed.
- **Detail**: CLI now reports errors consistently and validates critical preconditions (like database file existence) before executing operations.

### Phase 2 — Security and Robustness

#### Task 2.1 — Harden SQLCipher Encryption Handling
- **Status**: Completed.
- **Detail**: `apply_cipher_key` and `apply_cipher_key_async` implemented with strict support validation and empty/invalid key handling. Comprehensive tests added in `tests/test_crypto_sqlite.py` and its async variant.

#### Task 2.2 — Reduce Dynamic SQL Surface
- **Status**: Completed.
- **Detail**: Escaping centralized in `schemas.py`, and all identifier interpolation points refactored to use this single utility.

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
