# API REST - SQLitePlus Enhanced

La API proporciona endpoints para gestionar bases de datos SQLite de forma segura y asincrónica, protegidos con JWT.

> 📍 Swagger disponible en: `http://localhost:8000/docs`

---

## 🔐 Autenticación

### `POST /token`

Genera un token JWT válido por 1 hora.

#### Parámetros (form-data):
- `username`: `admin`
- `password`: `admin`

#### Respuesta:
```json
{
  "access_token": "<JWT>",
  "token_type": "bearer"
}
````

## 🧱 Gestión de Tablas

```
POST /databases/{db_name}/create_table
```

Crea una tabla en la base de datos indicada.

Headers:
- ````Authorization: Bearer <token>````

Query:
- ```table_name: Nombre de la tabla```

# Body (JSON):

```json
{
  "columns": {
    "id": "INTEGER PRIMARY KEY",
    "msg": "TEXT"
  }
}

```

```
DELETE /databases/{db_name}/drop_table
```
Elimina una tabla.

# Query:

- table_name: Nombre de la tabla a eliminar

## 📝 CRUD sobre Datos

```POST /databases/{db_name}/insert```

Inserta un registro en una tabla existente.

# Query:

```table_name: nombre de la tabla```

# Body (JSON):

```json
{
  "msg": "Texto de ejemplo"
}
```

```GET /databases/{db_name}/fetch```

Recupera todos los registros de la tabla indicada.

# Query:

```table_name: Nombre de la tabla a consultar```

# Respuesta:

```json
{
  "data": [
    [1, "Texto de ejemplo"]
  ]
}
```

## 🛑 Requiere Token

Todos los endpoints excepto ```/token``` requieren un token JWT en el header:

```http
Authorization: Bearer <token>
```





