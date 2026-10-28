"""Small real HTTP application with SQLite persistence and semantic events."""
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
from threading import Thread


class NotesApp:
    def __init__(self, database: Path, emit: Callable[[str, dict], None]):
        self.database = database
        self.emit = emit
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, text TEXT NOT NULL)")
        app = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != "/notes":
                    self.send_error(404)
                    return
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                text = payload.get("text", "").strip()
                if not text:
                    app.emit("note.rejected", {"reason": "empty_text"})
                    self.reply(422, {"error": "text is required"})
                    return
                with sqlite3.connect(app.database) as connection:
                    note_id = connection.execute("INSERT INTO notes (text) VALUES (?)", (text,)).lastrowid
                app.emit("note.created", {"note_id": note_id, "text": text, "storage": "sqlite"})
                self.reply(201, {"id": note_id, "text": text})

            def do_GET(self):
                if not self.path.startswith("/notes/"):
                    self.send_error(404)
                    return
                try:
                    note_id = int(self.path.removeprefix("/notes/"))
                except ValueError:
                    self.send_error(404)
                    return
                with sqlite3.connect(app.database) as connection:
                    row = connection.execute("SELECT text FROM notes WHERE id = ?", (note_id,)).fetchone()
                self.reply(200 if row else 404, {"id": note_id, "text": row[0]} if row else {"error": "not found"})

            def reply(self, status, payload):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def start(self):
        self.thread.start()
        self.emit("application.started", {"transport": "http"})

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError("HTTP server thread did not stop")
        self.emit("application.stopped", {"transport": "http"})
