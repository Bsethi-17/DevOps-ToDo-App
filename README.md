# DevOps Task Manager

A small To-Do app for the Containerized Microservices Deployment Using Docker,
Kubernetes, and Jenkins project. The Flask frontend calls a separate
Flask API, which stores tasks in PostgreSQL.

## Run the backend in Ubuntu WSL

This walkthrough uses Docker and Python 3 with `venv` support. On Ubuntu,
install the `python3-venv` package if `python3 -m venv` reports that
`ensurepip` is unavailable.

From the repository root, start a local PostgreSQL instance and initialize the
schema. The example credentials are for local development only. The named
volume preserves tasks when the container stops.

```bash
docker run --name todo-db --rm -d \
  -e POSTGRES_DB=todo -e POSTGRES_PASSWORD=todo-dev-password \
  -p 127.0.0.1:5433:5432 -v todo-db-data:/var/lib/postgresql/data postgres:17

# Wait until PostgreSQL is accepting connections.
docker exec todo-db pg_isready -h 127.0.0.1 -U postgres -d todo
docker exec -i todo-db psql -v ON_ERROR_STOP=1 -U postgres -d todo < database/init.sql

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
export DATABASE_URL=postgresql://postgres:todo-dev-password@127.0.0.1:5433/todo
python -m flask --app backend.app run
```

## Run the frontend

Keep the backend running and open another Ubuntu terminal at the repository root.

```bash
source .venv/bin/activate
python -m pip install -r frontend/requirements.txt
export BACKEND_URL=http://127.0.0.1:5000
python -m flask --app frontend.app run --port 8000
```

Open [My tasks](http://localhost:8000). The frontend sends task changes to the
backend over HTTP, and PostgreSQL stores the result. The frontend process has
its own liveness endpoint at `/healthz`.

## API

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/healthz` | Checks that Flask is running |
| GET | `/readyz` | Checks that the task table is accessible |
| GET | `/tasks` | Lists tasks in creation order |
| POST | `/tasks` | Creates a task from `{"title":"Deploy the app"}` |
| PATCH | `/tasks/<id>` | Sets completion using `{"completed":true}` or `false` |
| DELETE | `/tasks/<id>` | Deletes a task |

In a second terminal, use `curl http://127.0.0.1:5000/readyz` to check the
running backend. To run the integration test from the activated environment:

```bash
TEST_DATABASE_URL="$DATABASE_URL" python -m unittest -v backend.test_app
```

The integration test creates and removes an isolated schema. The test database
user needs permission to create schemas.
