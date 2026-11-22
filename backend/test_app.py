import os
import unittest
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from backend.app import create_app


class TaskApiTest(unittest.TestCase):
    def setUp(self):
        self.database_url = make_conninfo(
            os.environ["TEST_DATABASE_URL"], connect_timeout=3
        )
        # Isolate each test from existing tasks and concurrent test runs.
        self.schema = sql.Identifier(f"test_{uuid4().hex}")
        with psycopg.connect(self.database_url) as connection:
            connection.execute(sql.SQL("CREATE SCHEMA {}").format(self.schema))
        self.addCleanup(self.drop_schema)
        self.isolated_url = make_conninfo(
            self.database_url, options=f"-csearch_path={self.schema.as_string()}"
        )
        self.client = create_app(self.isolated_url).test_client()

    def drop_schema(self):
        with psycopg.connect(self.database_url) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(self.schema))

    def test_task_lifecycle(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/readyz").status_code, 503)
        schema_file = Path(__file__).resolve().parents[1] / "database" / "init.sql"
        with psycopg.connect(self.isolated_url) as connection:
            connection.execute(schema_file.read_text(encoding="utf-8"))
        self.assertEqual(self.client.get("/readyz").status_code, 200)
        self.assertEqual(self.client.get("/tasks").json, [])
        self.assertEqual(self.client.post("/tasks", json={"title": " "}).status_code, 400)

        created = self.client.post("/tasks", json={"title": "  Deploy the app  "})
        self.assertEqual(created.status_code, 201)
        task = created.json
        self.assertEqual(task["title"], "Deploy the app")
        self.assertIs(task["completed"], False)
        self.assertEqual(self.client.get("/tasks").json, [task])

        url = f"/tasks/{task['id']}"
        self.assertEqual(self.client.patch(url, json={"completed": "true"}).status_code, 400)
        updated = self.client.patch(url, json={"completed": True})
        self.assertEqual(updated.status_code, 200)
        self.assertIs(self.client.get("/tasks").json[0]["completed"], True)
        self.assertIs(self.client.patch(url, json={"completed": False}).json["completed"], False)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.get("/tasks").json, [])
        self.assertEqual(self.client.delete(url).status_code, 404)
