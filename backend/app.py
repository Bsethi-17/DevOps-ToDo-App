import os

import psycopg
from flask import Flask, g, jsonify, request
from psycopg.rows import dict_row


def create_app(database_url=None):
    app = Flask(__name__)
    app.config["DATABASE_URL"] = database_url or os.environ.get("DATABASE_URL")

    def db():
        if "db" not in g:
            g.db = psycopg.connect(
                app.config["DATABASE_URL"], row_factory=dict_row, connect_timeout=3
            )
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()

    @app.errorhandler(psycopg.OperationalError)
    def database_unavailable(error):
        app.logger.warning("Database operation failed: %s", type(error).__name__)
        return jsonify(error="Database unavailable"), 503

    @app.get("/healthz")
    def health():
        return jsonify(status="ok")

    @app.get("/readyz")
    def readiness():
        try:
            db().execute("SELECT 1 FROM tasks LIMIT 1")
        except psycopg.errors.UndefinedTable:
            return jsonify(error="Task table has not been initialized"), 503
        return jsonify(status="ready")

    @app.get("/tasks")
    def list_tasks():
        tasks = db().execute(
            "SELECT id, title, completed FROM tasks ORDER BY id"
        ).fetchall()
        return jsonify(tasks)

    @app.post("/tasks")
    def create_task():
        payload = request.get_json(silent=True)
        title = payload.get("title") if isinstance(payload, dict) else None
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200 or "\x00" in title:
            return jsonify(error="Provide a valid title with 1 to 200 characters"), 400

        connection = db()
        task = connection.execute(
            "INSERT INTO tasks (title) VALUES (%s) RETURNING id, title, completed",
            (title.strip(),),
        ).fetchone()
        connection.commit()
        return jsonify(task), 201

    @app.patch("/tasks/<int:task_id>")
    def update_task(task_id):
        payload = request.get_json(silent=True)
        completed = payload.get("completed") if isinstance(payload, dict) else None
        if not isinstance(completed, bool):
            return jsonify(error="Provide completed as a boolean"), 400
        if task_id > 2147483647:
            return jsonify(error="Task not found"), 404

        connection = db()
        task = connection.execute(
            "UPDATE tasks SET completed = %s WHERE id = %s RETURNING id, title, completed",
            (completed, task_id),
        ).fetchone()
        connection.commit()
        if task is None:
            return jsonify(error="Task not found"), 404
        return jsonify(task)

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        if task_id > 2147483647:
            return jsonify(error="Task not found"), 404

        connection = db()
        result = connection.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        connection.commit()
        if result.rowcount == 0:
            return jsonify(error="Task not found"), 404
        return "", 204

    return app
