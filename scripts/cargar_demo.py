"""Replace local records with entirely fictional demonstration data."""
import argparse
from datetime import datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def crear_pdf(path, numero, sector, equipo):
    lines = ["DEMOSTRACION - DATOS FICTICIOS", numero, sector, equipo,
             "Documento de ejemplo. No representa un incidente real."]
    content = "BT /F1 14 Tf 50 760 Td "
    for line in lines:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content += f"({escaped}) Tj 0 -28 Td "
    content = (content + "ET").encode("ascii")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reemplazar", action="store_true", help="Eliminar la base y los PDF locales existentes")
    args = parser.parse_args()
    database = ROOT / "incidentes.db"
    uploads = ROOT / "uploads"
    if not args.reemplazar and (database.exists() or any(p.name != ".gitkeep" for p in uploads.glob("*"))):
        parser.error("Ya existen datos. Usa --reemplazar solo si deseas eliminarlos definitivamente.")
    if len(os.environ.get("INITIAL_ADMIN_PASSWORD", "")) < 14:
        parser.error("Configura INITIAL_ADMIN_PASSWORD con al menos 14 caracteres; no hay clave de demo predeterminada.")
    if len(os.environ.get("SECRET_KEY", "")) < 32:
        parser.error("Configura SECRET_KEY con al menos 32 caracteres aleatorios.")
    # Build and validate the replacement before touching existing local data.
    with tempfile.TemporaryDirectory(prefix=".demo-stage-", dir=ROOT) as temp:
        folder = Path(temp)
        shutil.copy2(ROOT / "app.py", folder / "app.py")
        spec = importlib.util.spec_from_file_location("demo_app", folder / "app.py")
        module = importlib.util.module_from_spec(spec)
        previous_user = os.environ.get("INITIAL_ADMIN_USER")
        os.environ["INITIAL_ADMIN_USER"] = "admin.demo"
        try:
            spec.loader.exec_module(module)
        finally:
            if previous_user is None:
                os.environ.pop("INITIAL_ADMIN_USER", None)
            else:
                os.environ["INITIAL_ADMIN_USER"] = previous_user
        sectors = ("Laboratorio A", "Sala de pruebas B", "Oficina de ejemplo C", "Taller de pruebas D")
        with module.get_db() as db:
            db.execute("UPDATE usuarios SET nombre='Administrador de demostracion'")
            for i in range(1, 9):
                numero = f"DEMO-{i:04d}"
                sector = sectors[(i - 1) % len(sectors)]
                equipo = ("Notebook de prueba", "Monitor de prueba", "Tablet de prueba", "Impresora de prueba")[(i - 1) % 4]
                estado = module.ESTADOS[(i - 1) % len(module.ESTADOS)]
                fecha = (datetime(2026, 1, 10) + timedelta(days=i * 3)).strftime("%Y-%m-%d")
                timestamp = fecha + " 10:00:00"
                relative = Path("uploads") / f"INC-{i:04d}" / f"{numero}.pdf"
                crear_pdf(folder / relative, numero, sector, equipo)
                observaciones = "DATOS FICTICIOS. Incidente simulado para demostrar el flujo de registro y seguimiento."
                db.execute("""INSERT INTO informes(numero_informe,fecha_incidente,fecha_ingreso,
                    nombre_corto,estado,sector,equipo_afectado,numero_equipo,empresa,responsable_ti,
                    observaciones,pdf_nombre,pdf_path,fecha_creacion,fecha_modificacion)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (numero, fecha, timestamp, numero, estado, sector, equipo, f"DEMO-EQ-{i:03d}",
                     "", "Responsable TI", observaciones, relative.name, relative.as_posix(), timestamp, timestamp))
                db.execute("""INSERT INTO auditoria(usuario_id,usuario_nombre,accion,entidad,
                    entidad_id,detalle,fecha,ip) VALUES(1,?,'creacion','informe',?,?,?,?)""",
                    ("Administrador de demostracion", i,
                     json.dumps({"numero_informe": numero, "estado": estado, "demo": True}), timestamp, "127.0.0.1"))
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        # Stop the application before running: Windows refuses locked database files.
        for sidecar in (ROOT / "incidentes.db-wal", ROOT / "incidentes.db-shm", ROOT / "incidentes.db-journal"):
            if sidecar.exists():
                parser.error("Hay archivos de una transaccion SQLite. Deten la aplicacion antes de reemplazar los datos.")
        if uploads.exists():
            if uploads.is_symlink() or uploads.resolve() != ROOT / "uploads":
                parser.error("La carpeta uploads no coincide con la ruta local esperada.")
            for item in uploads.iterdir():
                if item.is_dir() and not item.is_symlink():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        os.replace(folder / "incidentes.db", database)
        shutil.copytree(folder / "uploads", uploads, dirs_exist_ok=True)
        (uploads / ".gitkeep").touch()
    print("Demo creada: 8 informes, 8 PDF, 8 eventos y la cuenta admin.demo.")
    print("Usa la clave INITIAL_ADMIN_PASSWORD configurada; deberas cambiarla al ingresar.")


if __name__ == "__main__":
    main()
