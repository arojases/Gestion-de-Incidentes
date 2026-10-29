"""Security regression checks using an isolated application and database."""
import importlib.util
import io
import os
from pathlib import Path
import secrets
import shutil
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".security-check-", dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        shutil.copy2(ROOT / "app.py", folder / "app.py")
        shutil.copytree(ROOT / "templates", folder / "templates")
        self.password = secrets.token_urlsafe(24)
        env = patch.dict(os.environ, {
            "SECRET_KEY": secrets.token_urlsafe(48),
            "INITIAL_ADMIN_PASSWORD": self.password,
            "INITIAL_ADMIN_USER": "admin",
            "RESPONSABLES_TI": "Responsable de prueba",
        })
        env.start()
        self.addCleanup(env.stop)
        spec = importlib.util.spec_from_file_location("isolated_app", folder / "app.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.client = self.module.app.test_client()

    def login(self):
        self.client.get("/login")
        with self.client.session_transaction() as session:
            token = session["csrf_token"]
        return self.client.post("/login", data={
            "username": "admin", "password": self.password, "csrf_token": token,
        })

    def test_anonymous_access_requires_login(self):
        for route in ("/informes", "/usuarios", "/historial", "/estadisticas", "/informes/1/pdf"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.location)

    def test_login_requires_csrf(self):
        response = self.client.post("/login", data={
            "username": "admin", "password": self.password,
        })
        self.assertEqual(response.status_code, 400)

    def test_initial_password_must_be_changed(self):
        self.assertEqual(self.login().status_code, 302)
        self.assertTrue(self.client.get("/informes").location.endswith("/mi-clave"))

    def test_reader_cannot_manage_users_or_delete_reports(self):
        self.login()
        with self.module.get_db() as db:
            db.execute("UPDATE usuarios SET debe_cambiar_password=0, rol='lector'")
        self.assertEqual(self.client.get("/usuarios").status_code, 403)
        with self.client.session_transaction() as session:
            token = session["csrf_token"]
        response = self.client.post("/informes/1/eliminar", data={"csrf_token": token})
        self.assertEqual(response.status_code, 403)

    def test_pdf_route_rejects_files_outside_uploads(self):
        self.login()
        outside = Path(self.temp.name) / "private.pdf"
        outside.write_bytes(b"%PDF-1.4\nprivate fixture")
        with self.module.get_db() as db:
            db.execute("UPDATE usuarios SET debe_cambiar_password=0")
            db.execute("""INSERT INTO informes(numero_informe,fecha_incidente,
                fecha_ingreso,nombre_corto,estado,sector,equipo_afectado,pdf_path)
                VALUES(?,?,?,?,?,?,?,?)""",
                ("TEST", "2026-01-01", "test", "test", "Pendiente", "test", "test", "private.pdf"))
        self.assertEqual(self.client.get("/informes/1/pdf").status_code, 404)

    def test_responses_disable_cache_and_mime_sniffing(self):
        response = self.client.get("/login")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_editor_has_report_crud_but_no_admin_access(self):
        self.login()
        with self.module.get_db() as db:
            db.execute("UPDATE usuarios SET debe_cambiar_password=0, rol='editor'")
        with self.client.session_transaction() as session:
            token = session["csrf_token"]
        self.assertEqual(self.client.get("/").status_code, 200)
        for route in ("/usuarios", "/historial", "/estadisticas"):
            self.assertEqual(self.client.get(route).status_code, 403)
        for route in ("/usuarios", "/usuarios/1/actualizar"):
            self.assertEqual(self.client.post(route, data={"csrf_token": token}).status_code, 403)
        data = {"csrf_token": token, "numero_informe": "CRUD-DEMO", "fecha_incidente": "2026-01-01",
                "estado": "Pendiente", "sector": "Prueba", "equipo_afectado": "Equipo de prueba",
                "responsable_ti": "Responsable de prueba"}
        response = self.client.post("/informes/nuevo", data={**data,
            "pdf": (io.BytesIO(b"%PDF-1.4\nfictional fixture"), "prueba.pdf")})
        self.assertEqual(response.status_code, 302)
        detail = self.client.get("/informes/1")
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn(b"Historial de cambios", detail.data)
        self.assertIn(b"Eliminar informe", detail.data)
        with self.client.get("/informes/1/pdf") as pdf_response:
            self.assertEqual(pdf_response.status_code, 200)
        response = self.client.post("/informes/1/editar", data={**data, "estado": "Archivado"})
        self.assertEqual(response.status_code, 302)
        with self.module.get_db() as db:
            self.assertEqual(db.execute("SELECT estado FROM informes WHERE id=1").fetchone()[0], "Archivado")
        self.assertEqual(self.client.post("/informes/1/eliminar", data={"csrf_token": token}).status_code, 302)
        self.assertEqual(self.client.get("/informes/1").status_code, 404)
        with self.module.get_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM auditoria WHERE entidad='informe'").fetchone()[0], 3)

    def test_missing_secret_fails_at_startup(self):
        with patch.dict(os.environ, {"SECRET_KEY": ""}):
            spec = importlib.util.spec_from_file_location("invalid_app", Path(self.temp.name) / "app.py")
            with self.assertRaises(RuntimeError):
                spec.loader.exec_module(importlib.util.module_from_spec(spec))


if __name__ == "__main__":
    unittest.main()
