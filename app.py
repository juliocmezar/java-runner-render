import os, re, tempfile, subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)
API_KEY = os.environ.get("API_KEY", "")

def clean_java(code):
    code = re.sub(r'^\s*package\s+[\w.]+\s*;\s*', '', code, flags=re.MULTILINE)
    m = re.search(r'public\s+class\s+([A-Za-z_][A-Za-z0-9_]*)', code)
    class_name = m.group(1) if m else "Main"
    return code, class_name

@app.post("/run-java")
def run_java():
    if API_KEY and request.headers.get("X-API-Key") != API_KEY:
        return jsonify({"ok": False, "error": "API Key inválida"}), 401

    data = request.get_json(force=True)
    code = data.get("code", "")
    stdin = data.get("stdin", "")
    timeout = int(data.get("timeout", 5))

    if not code.strip():
        return jsonify({"ok": False, "error": "Código vacío"}), 400

    code, class_name = clean_java(code)

    with tempfile.TemporaryDirectory() as tmp:
        java_file = os.path.join(tmp, f"{class_name}.java")
        with open(java_file, "w", encoding="utf-8") as f:
            f.write(code)

        comp = subprocess.run(
            ["javac", java_file],
            cwd=tmp,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if comp.returncode != 0:
            return jsonify({
                "ok": False,
                "stage": "compile",
                "stdout": comp.stdout,
                "stderr": comp.stderr,
                "exit_code": comp.returncode
            })

        run = subprocess.run(
            ["java", "-cp", tmp, class_name],
            input=stdin,
            cwd=tmp,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        return jsonify({
            "ok": run.returncode == 0,
            "stage": "run",
            "stdout": run.stdout,
            "stderr": run.stderr,
            "exit_code": run.returncode
        })

@app.get("/")
def health():
    return {"ok": True, "service": "java-runner"}