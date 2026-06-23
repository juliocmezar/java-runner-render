import os
import re
import tempfile
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)

# API KEY
API_KEY = os.environ.get("API_KEY", "")


def clean_java(code):
    """
    Elimina la línea package y obtiene el nombre de la clase pública.
    """

    # eliminar package
    code = re.sub(
        r'^\s*package\s+[\w\.]+\s*;\s*',
        '',
        code,
        flags=re.MULTILINE
    )

    # buscar clase publica
    match = re.search(
        r'public\s+class\s+([A-Za-z_][A-Za-z0-9_]*)',
        code
    )

    if match:
        class_name = match.group(1)
    else:
        class_name = "Main"

    return code, class_name


@app.get("/")
def health():

    return jsonify({
        "ok": True,
        "service": "java-runner"
    })


@app.get("/jdk")
def jdk():

    try:

        version = subprocess.run(
            ["javac", "-version"],
            capture_output=True,
            text=True,
            timeout=10
        )

        return jsonify({

            "ok": True,
            "returncode": version.returncode,
            "stdout": version.stdout,
            "stderr": version.stderr

        })

    except Exception as e:

        return jsonify({

            "ok": False,
            "error": str(e)

        }), 500


@app.post("/run-java")
def run_java():

    # validar api key

    if API_KEY:

        if request.headers.get("X-API-Key") != API_KEY:

            return jsonify({

                "ok": False,
                "error": "API Key inválida"

            }), 401

    data = request.get_json(force=True)

    code = data.get("code", "")
    stdin = data.get("stdin", "")
    timeout = int(data.get("timeout", 30))

    if code.strip() == "":

        return jsonify({

            "ok": False,
            "error": "Código vacío"

        }), 400

    code, class_name = clean_java(code)

    try:

        with tempfile.TemporaryDirectory() as tmp:

            java_file = os.path.join(
                tmp,
                class_name + ".java"
            )

            with open(
                java_file,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(code)

            # -----------------------------
            # COMPILAR
            # -----------------------------

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

            # -----------------------------
            # EJECUTAR
            # -----------------------------

            run = subprocess.run(

                ["java", "-cp", tmp, class_name],

                cwd=tmp,

                input=stdin,

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

    except subprocess.TimeoutExpired:

        return jsonify({

            "ok": False,

            "stage": "timeout",

            "error": f"Tiempo máximo excedido ({timeout} segundos)."

        }), 408

    except Exception as e:

        return jsonify({

            "ok": False,

            "stage": "server",

            "error": str(e)

        }), 500


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(

        host="0.0.0.0",

        port=port

    )