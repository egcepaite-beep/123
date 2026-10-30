"""Upload one product photo, get a full 360 campaign board.

Run:  python app.py   then open http://127.0.0.1:5000
"""
import threading
import traceback
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory

import pipeline

RUNS = Path(__file__).parent / "runs"
RUNS.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

jobs: dict[str, dict] = {}


def _job_dir(job_id: str) -> Path:
    if job_id not in jobs and not (RUNS / job_id / "board.html").exists():
        abort(404)
    return RUNS / job_id


@app.get("/")
def index():
    return render_template("index.html", live_text=pipeline.live_text(), live_images=pipeline.live_images())


@app.post("/generate")
def generate():
    product = request.files.get("product")
    if not product or not product.filename:
        return jsonify(error="Įkelkite produkto nuotrauką."), 400
    style = request.files.get("style")
    style_bytes = style.read() if style and style.filename else None
    num_posts = max(3, min(9, int(request.form.get("num_posts", 9))))

    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {"status": "running", "step": "Pradedama", "error": None}
    args = dict(product_bytes=product.read(), style_bytes=style_bytes,
                brand=request.form.get("brand", "").strip(), notes=request.form.get("notes", "").strip(),
                language=request.form.get("language", "English"), num_posts=num_posts)

    def work():
        def progress(step):
            jobs[job_id]["step"] = step
        try:
            pipeline.run(RUNS / job_id, progress=progress, **args)
            jobs[job_id]["status"] = "done"
        except Exception as e:  # surface any failure to the page
            traceback.print_exc()
            jobs[job_id].update(status="error", error=str(e))

    threading.Thread(target=work, daemon=True).start()
    return jsonify(job=job_id)


@app.get("/status/<job_id>")
def status(job_id):
    return jsonify(jobs.get(job_id) or abort(404))


@app.get("/c/<job_id>/")
def board(job_id):
    return send_from_directory(_job_dir(job_id), "board.html")


@app.get("/c/<job_id>")
def board_redirect(job_id):
    return redirect(f"/c/{job_id}/")


@app.get("/c/<job_id>/campaign.zip")
def download(job_id):
    _job_dir(job_id)
    return send_from_directory(RUNS, f"{job_id}-campaign.zip", as_attachment=True)


@app.get("/c/<job_id>/<path:name>")
def asset(job_id, name):
    return send_from_directory(_job_dir(job_id), name)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
