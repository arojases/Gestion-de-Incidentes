"""Create the restricted demo account without changing administrator credentials."""
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]


def clave_demo():
    config = ROOT / ".env.demo"
    lines = config.read_text(encoding="utf-8-sig").splitlines() if config.exists() else []
    values = dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))
    password = os.environ.get("USER_DEMO_PASSWORD") or values.get("USER_DEMO_PASSWORD")
    if not password:
        password = secrets.token_urlsafe(24)
    if len(password) < 10:
        raise RuntimeError("USER_DEMO_PASSWORD debe tener al menos 10 caracteres.")
    # Keep the credential local; never write it into source files or console output.
    if values.get("USER_DEMO_PASSWORD") != password:
        lines = [line for line in lines if not line.startswith("USER_DEMO_PASSWORD=")]
        lines.append("USER_DEMO_PASSWORD=" + password)
        config.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return password


def crear_usuario(db, password, fecha):
    from werkzeug.security import generate_password_hash
    existing = db.execute("SELECT id,rol FROM usuarios WHERE username='user.demo'").fetchone()
    if existing:
        raise RuntimeError("user.demo ya existe; no se modifico su cuenta ni su clave.")
    db.execute("""INSERT INTO usuarios(username,nombre,password_hash,rol,activo,
        debe_cambiar_password,fecha_creacion) VALUES(?,?,?,'editor',1,1,?)""",
        ("user.demo", "Usuario de demostracion", generate_password_hash(password), fecha))


def main():
    config = ROOT / ".env.demo"
    if config.exists():
        for line in config.read_text(encoding="utf-8-sig").splitlines():
            key, sep, value = line.partition("=")
            if sep and key in {"SECRET_KEY", "INITIAL_ADMIN_PASSWORD", "USER_DEMO_PASSWORD", "RESPONSABLES_TI"}:
                os.environ[key] = value
    password = clave_demo()
    sys.path.insert(0, str(ROOT))
    import app
    with app.get_db() as db:
        crear_usuario(db, password, app.ahora())
    print("Cuenta user.demo creada como Editor. Clave inicial en USER_DEMO_PASSWORD de .env.demo.")
    print("Debe cambiar su clave al ingresar. No se modifico la cuenta administradora.")


if __name__ == "__main__":
    main()
