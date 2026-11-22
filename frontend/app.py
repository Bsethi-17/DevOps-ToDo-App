import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for


def create_app(backend_url=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
    api = (backend_url or os.environ.get("BACKEND_URL", "http://127.0.0.1:5000")).rstrip("/")

    def backend(method, path, payload=None):
        headers = {"Accept": "application/json"}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode()
        with urlopen(Request(f"{api}{path}", data, headers, method=method), timeout=4) as response:
            if response.status != 204:
                return json.load(response)

    def task_page(error=None, status=200, draft=""):
        tasks = []
        available = True
        try:
            tasks = backend("GET", "/tasks")
        except HTTPError as response:
            response.close()
            available = False
        except (URLError, TimeoutError, ValueError):
            available = False
        if not available:
            error = error or "Tasks are temporarily unavailable. Refresh to try again."
            status = 503
        return render_template(
            "index.html", tasks=tasks, available=available, error=error, draft=draft,
            completed=sum(task["completed"] for task in tasks),
        ), status

    @app.before_request
    def require_same_origin_for_writes():
        if request.method == "POST":
            origin = request.headers.get("Origin")
            fetch_site = request.headers.get("Sec-Fetch-Site")
            if (origin is not None and origin != request.host_url.rstrip("/")) or (
                fetch_site is not None and fetch_site != "same-origin"
            ):
                abort(403)

    @app.get("/healthz")
    def health():
        return jsonify(status="ok")

    @app.get("/")
    def index():
        return task_page()

    def change_task(method, path, payload=None, draft=""):
        try:
            backend(method, path, payload)
        except HTTPError as error:
            error.close()
            if error.code == 404:
                return task_page("This task is no longer available.", 404, draft)
            if error.code == 400:
                return task_page("The task update was rejected. Check your input.", 400, draft)
            return task_page("The task service could not confirm the change.", 503, draft)
        except (URLError, TimeoutError, ValueError):
            return task_page("The task service could not confirm the change.", 503, draft)
        return redirect(url_for("index"), code=303)

    @app.post("/tasks")
    def add_task():
        title = request.form.get("title", "").strip()
        if not 1 <= len(title) <= 200 or "\x00" in title:
            return task_page("Enter a task title with 1 to 200 characters.", 400, title[:200])
        return change_task("POST", "/tasks", {"title": title}, draft=title)

    @app.post("/tasks/<int:task_id>/completion")
    def set_completion(task_id):
        completed = request.form.get("completed")
        if completed not in ("true", "false"):
            return task_page("Choose a valid completion status.", 400)
        return change_task("PATCH", f"/tasks/{task_id}", {"completed": completed == "true"})

    @app.post("/tasks/<int:task_id>/delete")
    def delete_task(task_id):
        return change_task("DELETE", f"/tasks/{task_id}")

    return app
