"""Windows launcher: prepare the local demo and open it in the browser."""
import argparse
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
URL = "http://127.0.0.1:8080/login"
ALLOWED = {"SECRET_KEY", "INITIAL_ADMIN_USER", "INITIAL_ADMIN_PASSWORD", "USER_DEMO_PASSWORD", "RESPONSABLES_TI", "COOKIE_SECURE"}


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verificar el arranque sin abrir el navegador y detener el servidor")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise RuntimeError("Se necesita Python 3.11 o superior.")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 8080)) == 0:
            raise RuntimeError("El puerto 8080 ya esta ocupado. Cierra la instancia anterior antes de iniciar otra.")
    valid = PYTHON.exists() and subprocess.run(
        [str(PYTHON), "-c", "import sys; sys.exit(sys.version_info < (3,11))"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not valid:
        print("Preparando el entorno de Python...", flush=True)
        run(sys.executable, "-m", "venv", str(ROOT / ".venv"))
    ready = subprocess.run([str(PYTHON), "-c",
        "import flask, importlib.metadata; assert importlib.metadata.version('Flask') == '3.1.1'"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not ready:
        print("Instalando dependencias. Este paso necesita internet...", flush=True)
        run(str(PYTHON), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt"))
    config = ROOT / ".env.demo"
    if not config.exists():
        settings = {"SECRET_KEY": secrets.token_urlsafe(48), "INITIAL_ADMIN_USER": "admin.demo",
                    "INITIAL_ADMIN_PASSWORD": secrets.token_urlsafe(24), "RESPONSABLES_TI": "Responsable TI"}
        with config.open("x", encoding="utf-8") as output:
            output.write("".join(f"{key}={value}\n" for key, value in settings.items()))
    for line in config.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() in ALLOWED:
            os.environ[key.strip()] = value.strip()
    if len(os.environ.get("SECRET_KEY", "")) < 32:
        raise RuntimeError("La SECRET_KEY de .env.demo debe tener al menos 32 caracteres.")
    if not (ROOT / "incidentes.db").exists():
        print("Creando datos ficticios de demostracion...", flush=True)
        run(str(PYTHON), str(ROOT / "scripts" / "cargar_demo.py"))
    print("Iniciando en http://127.0.0.1:8080", flush=True)
    print("Usuario de la demo: admin.demo. Clave inicial: INITIAL_ADMIN_PASSWORD en .env.demo.", flush=True)
    print("Si ya cambiaste la clave, utiliza tu clave actual.", flush=True)
    print("Deja esta ventana abierta. Para detener el programa, presiona Ctrl+C.", flush=True)
    server = subprocess.Popen([str(PYTHON), str(ROOT / "app.py")], cwd=ROOT)
    try:
        for _ in range(120):
            if server.poll() is not None:
                raise RuntimeError("El servidor no pudo arrancar. Revisa el mensaje anterior.")
            try:
                with urllib.request.urlopen(URL, timeout=1) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.5)
        else:
            raise RuntimeError("El servidor no respondio a tiempo.")
        if args.check:
            print("OK: servidor iniciado y pagina de acceso disponible.", flush=True)
        else:
            webbrowser.open("http://127.0.0.1:8080")
            server.wait()
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAplicacion detenida.")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"\nNo se pudo iniciar: {error}", file=sys.stderr)
        sys.exit(1)
