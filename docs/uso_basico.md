# Uso Básico

## Iniciar servidor

```bash
uvicorn sqliteplus.main:app --reload
```

## Obtener un token JWT

```bash
curl -X POST "http://127.0.0.1:8000/token" \
-d "username=admin&password=admin"
```

## Crear una tabla

```bash
curl -X POST "http://127.0.0.1:8000/databases/test_db/create_table?table_name=logs" \
-H "Authorization: Bearer <TOKEN>" \
-H "Content-Type: application/json" \
-d '{"columns": {"id": "INTEGER PRIMARY KEY", "msg": "TEXT"}}'
```

