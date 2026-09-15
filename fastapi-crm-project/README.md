# FastAPI CRM Project

A small customer-management REST API built with FastAPI, Pydantic, PostgreSQL,
and Psycopg. It supports creating, reading, updating, and deleting customer
records.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL

## Setup

Clone the repository and enter the project directory, then install the locked
dependencies:

```bash
uv sync
```

Create a PostgreSQL database named `customer-management`:

```bash
createdb customer-management
```

Update `DB_CONFIG` in `database.py` with your PostgreSQL username, password,
host, and port. The current defaults connect to PostgreSQL on `localhost:5432`.

Create the `customers` table:

```sql
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(15) NOT NULL,
    city VARCHAR(100) NOT NULL,
    age INTEGER CHECK (age >= 18),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

The beginning of `pgadmin.sql` also contains this schema and a sample `INSERT`
statement that you can copy into pgAdmin's Query Tool.

## Run the API

```bash
uv run main.py
```

The development server runs at <http://127.0.0.1:8000> and automatically
reloads when Python files change.

Interactive API documentation is available at:

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>

## API endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | Check that the API is running |
| `GET` | `/customers` | List all customers |
| `GET` | `/customers/{customer_id}` | Get one customer |
| `POST` | `/customers` | Create a customer |
| `PUT` | `/customers/{customer_id}` | Replace a customer's details |
| `DELETE` | `/customer/{customer_id}` | Delete a customer |

## Customer data

Requests that create or update a customer use this shape:

```json
{
  "name": "Aarav Sharma",
  "phone": "9876543210",
  "city": "Delhi",
  "email": "aarav@example.com",
  "age": 28
}
```

The email must be valid, and `age` must be at least 18.

## Example requests

Create a customer:

```bash
curl -X POST http://127.0.0.1:8000/customers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Aarav Sharma",
    "phone": "9876543210",
    "city": "Delhi",
    "email": "aarav@example.com",
    "age": 28
  }'
```

List all customers:

```bash
curl http://127.0.0.1:8000/customers
```

Get a customer by ID:

```bash
curl http://127.0.0.1:8000/customers/1
```

Update a customer:

```bash
curl -X PUT http://127.0.0.1:8000/customers/1 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Aarav Sharma",
    "phone": "9876543210",
    "city": "Jaipur",
    "email": "aarav@example.com",
    "age": 29
  }'
```

Delete a customer:

```bash
curl -X DELETE http://127.0.0.1:8000/customer/1
```

## Project structure

```text
.
├── main.py          # FastAPI routes and development server entry point
├── crud.py          # PostgreSQL CRUD operations
├── database.py      # Database connection configuration
├── schemas.py       # Pydantic request model
├── pgadmin.sql      # Database schema, sample data, and example queries
├── pyproject.toml   # Project metadata and dependencies
└── uv.lock          # Locked dependency versions
```
