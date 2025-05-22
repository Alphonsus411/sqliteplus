# Endpoints REST

Consulta interactiva disponible en `/docs`.

## Autenticación

- `POST /token`: Obtener token JWT

## Gestión de Base de Datos

- `POST /databases/{db}/create_table`
- `DELETE /databases/{db}/drop_table`

## Operaciones CRUD

- `POST /databases/{db}/insert`
- `GET /databases/{db}/fetch`