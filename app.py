import hmac, json, os, secrets, shutil, sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path
from flask import Flask, abort, flash, g, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATABASE, UPLOADS_DIR = BASE_DIR / "incidentes.db", BASE_DIR / "uploads"
ESTADOS = ("Pendiente", "En revisi\u00f3n", "Archivado")
ROLES = {"admin": "Administrador", "editor": "Editor", "lector": "Lector"}
RESPONSABLES_TI = tuple(n.strip() for n in os.environ.get("RESPONSABLES_TI", "Responsable TI").split(",") if n.strip())
CAMPOS_OBLIGATORIOS = ("numero_informe", "fecha_incidente", "estado", "sector", "equipo_afectado", "responsable_ti")
CAMPOS_AUDITADOS = ("numero_informe", "fecha_incidente", "estado", "sector", "equipo_afectado", "numero_equipo", "responsable_ti", "observaciones", "pdf_nombre")

app = Flask(__name__)
secret_key = os.environ.get("SECRET_KEY", "")
if len(secret_key) < 32:
    raise RuntimeError("Define SECRET_KEY con al menos 32 caracteres aleatorios antes de iniciar.")
app.config.update(SECRET_KEY=secret_key, MAX_CONTENT_LENGTH=25*1024*1024,
    SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1")

def ahora(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class ConexionDB(sqlite3.Connection):
    """Commit or roll back the transaction and always release the connection."""
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

def get_db():
    db = sqlite3.connect(DATABASE, factory=ConexionDB); db.row_factory = sqlite3.Row; return db

def init_db():
    UPLOADS_DIR.mkdir(exist_ok=True)
    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS informes (id INTEGER PRIMARY KEY AUTOINCREMENT, numero_informe TEXT NOT NULL, fecha_incidente TEXT NOT NULL, fecha_ingreso TEXT NOT NULL, nombre_corto TEXT NOT NULL, estado TEXT NOT NULL, sector TEXT NOT NULL, equipo_afectado TEXT NOT NULL, numero_equipo TEXT, empresa TEXT, responsable_ti TEXT, observaciones TEXT, pdf_nombre TEXT, pdf_path TEXT, fecha_creacion TEXT, fecha_modificacion TEXT)""")
        db.execute("""CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE, nombre TEXT NOT NULL, password_hash TEXT NOT NULL, rol TEXT NOT NULL CHECK(rol IN ('admin','editor','lector')), activo INTEGER NOT NULL DEFAULT 1, debe_cambiar_password INTEGER NOT NULL DEFAULT 0, fecha_creacion TEXT NOT NULL, ultimo_acceso TEXT)""")
        db.execute("""CREATE TABLE IF NOT EXISTS auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, usuario_nombre TEXT NOT NULL, accion TEXT NOT NULL, entidad TEXT NOT NULL, entidad_id INTEGER, detalle TEXT NOT NULL, fecha TEXT NOT NULL, ip TEXT)""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_auditoria_entidad ON auditoria(entidad,entidad_id)")
        if not db.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
            initial_password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
            if len(initial_password) < 14:
                raise RuntimeError("Define INITIAL_ADMIN_PASSWORD con al menos 14 caracteres para crear la primera cuenta.")
            db.execute("INSERT INTO usuarios(username,nombre,password_hash,rol,activo,debe_cambiar_password,fecha_creacion) VALUES(?,?,?,?,1,1,?)", (os.environ.get("INITIAL_ADMIN_USER", "admin"), "Administrador inicial", generate_password_hash(initial_password), "admin", ahora()))
        db.execute("UPDATE informes SET estado='Archivado' WHERE estado='Cerrado'")

def obtener_informe(informe_id):
    with get_db() as db: item = db.execute("SELECT * FROM informes WHERE id=?", (informe_id,)).fetchone()
    if item is None: abort(404)
    return item

def registrar_auditoria(db, accion, entidad, entidad_id, detalle):
    u = getattr(g, "usuario", None)
    db.execute("INSERT INTO auditoria(usuario_id,usuario_nombre,accion,entidad,entidad_id,detalle,fecha,ip) VALUES(?,?,?,?,?,?,?,?)", (u["id"] if u else None, u["nombre"] if u else "Sistema", accion, entidad, entidad_id, json.dumps(detalle, ensure_ascii=False), ahora(), request.remote_addr))

def login_requerido(vista):
    @wraps(vista)
    def envuelta(*args, **kwargs):
        if g.usuario is None: return redirect(url_for("login", siguiente=request.full_path.rstrip("?")))
        return vista(*args, **kwargs)
    return envuelta

def roles_requeridos(*roles):
    def decorador(vista):
        @wraps(vista)
        @login_requerido
        def envuelta(*args, **kwargs):
            if g.usuario["rol"] not in roles: abort(403)
            return vista(*args, **kwargs)
        return envuelta
    return decorador

@app.before_request
def seguridad_solicitud():
    g.usuario = None
    if session.get("usuario_id"):
        with get_db() as db: g.usuario = db.execute("SELECT * FROM usuarios WHERE id=? AND activo=1", (session["usuario_id"],)).fetchone()
        if g.usuario is None: session.clear()
    if request.method == "POST" and (not session.get("csrf_token") or not hmac.compare_digest(request.form.get("csrf_token", ""), session["csrf_token"])):
        abort(400, "Token de seguridad inválido. Recarga la página.")
    if g.usuario and g.usuario["debe_cambiar_password"] and request.endpoint not in {"cambiar_password", "logout", "static"}:
        return redirect(url_for("cambiar_password"))

@app.after_request
def cabeceras_seguridad(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.endpoint != "static":
        response.headers["Cache-Control"] = "no-store"
    return response

@app.context_processor
def opciones_globales():
    session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return {"responsables_ti": RESPONSABLES_TI, "roles": ROLES, "csrf_token": session["csrf_token"]}

@app.route("/login", methods=("GET", "POST"))
def login():
    if g.usuario: return redirect(url_for("dashboard"))
    if request.method == "POST":
        with get_db() as db:
            u = db.execute("SELECT * FROM usuarios WHERE username=?", (request.form.get("username", "").strip(),)).fetchone()
            if u and u["activo"] and check_password_hash(u["password_hash"], request.form.get("password", "")):
                session.clear(); session["usuario_id"] = u["id"]; session["csrf_token"] = secrets.token_urlsafe(32)
                db.execute("UPDATE usuarios SET ultimo_acceso=? WHERE id=?", (ahora(), u["id"]))
                return redirect(url_for("cambiar_password") if u["debe_cambiar_password"] else url_for("dashboard"))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html")

@app.post("/logout")
@login_requerido
def logout(): session.clear(); return redirect(url_for("login"))

@app.route("/mi-clave", methods=("GET", "POST"))
@login_requerido
def cambiar_password():
    if request.method == "POST":
        actual, nueva = request.form.get("actual", ""), request.form.get("nueva", "")
        if not check_password_hash(g.usuario["password_hash"], actual): flash("La contraseña actual no es correcta.", "error")
        elif len(nueva) < 10: flash("La nueva contraseña debe tener al menos 10 caracteres.", "error")
        elif nueva != request.form.get("confirmacion", ""): flash("Las contraseñas nuevas no coinciden.", "error")
        elif nueva == actual: flash("La nueva contraseña debe ser diferente.", "error")
        else:
            with get_db() as db:
                db.execute("UPDATE usuarios SET password_hash=?,debe_cambiar_password=0 WHERE id=?", (generate_password_hash(nueva), g.usuario["id"])); registrar_auditoria(db, "cambio_clave", "usuario", g.usuario["id"], {})
            flash("Contraseña actualizada.", "exito"); return redirect(url_for("dashboard"))
    return render_template("cambiar_password.html")

def datos_formulario(): return {c: request.form.get(c, "").strip() for c in ("numero_informe", "fecha_incidente", "estado", "sector", "equipo_afectado", "numero_equipo", "responsable_ti", "observaciones")}
def validar_datos(datos, pdf=None, pdf_obligatorio=False):
    errores=[]
    if any(not datos.get(c) for c in CAMPOS_OBLIGATORIOS): errores.append("Completa todos los campos obligatorios.")
    if datos.get("estado") not in ESTADOS: errores.append("Selecciona un estado válido.")
    if datos.get("responsable_ti") not in RESPONSABLES_TI: errores.append("Selecciona un responsable válido.")
    if pdf_obligatorio and (pdf is None or not pdf.filename): errores.append("Debes adjuntar el PDF.")
    if pdf and pdf.filename:
        cabecera=pdf.stream.read(5); pdf.stream.seek(0)
        if Path(pdf.filename).suffix.lower() != ".pdf" or cabecera != b"%PDF-": errores.append("El archivo no es un PDF válido.")
    return errores
def guardar_pdf(pdf, informe_id):
    rel=Path("uploads")/f"INC-{informe_id:04d}"; carpeta=BASE_DIR/rel; carpeta.mkdir(parents=True, exist_ok=True)
    nombre=secure_filename(pdf.filename) or "informe.pdf"; destino=carpeta/nombre; pdf.save(destino); return nombre, rel/nombre

@app.route("/")
@login_requerido
def dashboard():
    if g.usuario["rol"] == "admin":
        return redirect(url_for("estadisticas"))
    with get_db() as db:
        total=db.execute("SELECT COUNT(*) FROM informes").fetchone()[0]; conteos={e:db.execute("SELECT COUNT(*) FROM informes WHERE estado=?",(e,)).fetchone()[0] for e in ESTADOS}; ultimos=db.execute("SELECT * FROM informes ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("dashboard.html", total=total, conteos=conteos, ultimos=ultimos)

@app.route("/informes")
@login_requerido
def lista_informes():
    q, estado, orden=request.args.get("q","").strip(),request.args.get("estado","").strip(),request.args.get("orden","recientes")
    sql,params="SELECT * FROM informes WHERE 1=1",[]
    if q:
        cols=("numero_informe","pdf_nombre","sector","equipo_afectado","numero_equipo","estado","responsable_ti","observaciones"); sql+=" AND ("+" OR ".join(f"{c} LIKE ?" for c in cols)+")"; params += [f"%{q}%"]*len(cols)
    if estado == "abiertos":
        sql += " AND estado IN (?,?)"; params.extend((ESTADOS[0], ESTADOS[1]))
    elif estado in ESTADOS: sql+=" AND estado=?"; params.append(estado)
    sql += " ORDER BY fecha_incidente ASC,id ASC" if orden=="antiguos" else " ORDER BY fecha_incidente DESC,id DESC"
    with get_db() as db: informes=db.execute(sql,params).fetchall()
    return render_template("lista.html", informes=informes,busqueda=q,estado=estado,estados=ESTADOS,orden="antiguos" if orden=="antiguos" else "recientes")

@app.route("/informes/nuevo", methods=("GET","POST"))
@roles_requeridos("admin","editor")
def nuevo_informe():
    if request.method=="POST":
        datos,pdf=datos_formulario(),request.files.get("pdf"); errores=validar_datos(datos,pdf,True)
        if errores:
            for e in errores: flash(e,"error")
            return render_template("nuevo.html",datos=datos,estados=ESTADOS),400
        fecha=ahora()
        with get_db() as db:
            cur=db.execute("INSERT INTO informes(numero_informe,fecha_incidente,fecha_ingreso,nombre_corto,estado,sector,equipo_afectado,numero_equipo,empresa,responsable_ti,observaciones,pdf_nombre,pdf_path,fecha_creacion,fecha_modificacion) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(datos["numero_informe"],datos["fecha_incidente"],fecha,datos["numero_informe"],datos["estado"],datos["sector"],datos["equipo_afectado"],datos["numero_equipo"],"",datos["responsable_ti"],datos["observaciones"],"","",fecha,fecha)); iid=cur.lastrowid
            try:
                nombre,ruta=guardar_pdf(pdf,iid); db.execute("UPDATE informes SET pdf_nombre=?,pdf_path=? WHERE id=?",(nombre,ruta.as_posix(),iid)); registrar_auditoria(db,"creacion","informe",iid,{**datos,"pdf_nombre":nombre})
            except OSError:
                db.execute("DELETE FROM informes WHERE id=?",(iid,)); shutil.rmtree(UPLOADS_DIR/f"INC-{iid:04d}",ignore_errors=True); flash("No fue posible guardar el PDF.","error"); return render_template("nuevo.html",datos=datos,estados=ESTADOS),500
        flash("Informe registrado correctamente.","exito"); return redirect(url_for("detalle_informe",informe_id=iid))
    return render_template("nuevo.html",datos={},estados=ESTADOS)

@app.route("/informes/<int:informe_id>")
@login_requerido
def detalle_informe(informe_id):
    informe=obtener_informe(informe_id)
    with get_db() as db: historial=db.execute("SELECT * FROM auditoria WHERE entidad='informe' AND entidad_id=? ORDER BY id DESC",(informe_id,)).fetchall()
    return render_template("detalle.html",informe=informe,historial=historial)

@app.route("/informes/<int:informe_id>/editar",methods=("GET","POST"))
@roles_requeridos("admin","editor")
def editar_informe(informe_id):
    informe=obtener_informe(informe_id)
    if request.method=="POST":
        datos,pdf=datos_formulario(),request.files.get("pdf"); errores=validar_datos(datos,pdf)
        if errores:
            for e in errores: flash(e,"error")
            datos.update(id=informe_id,pdf_nombre=informe["pdf_nombre"]); return render_template("editar.html",informe=datos,estados=ESTADOS),400
        nombre,ruta=informe["pdf_nombre"],informe["pdf_path"]
        if pdf and pdf.filename:
            try: nombre,ruta_obj=guardar_pdf(pdf,informe_id); ruta=ruta_obj.as_posix()
            except OSError: flash("No fue posible reemplazar el PDF.","error"); return render_template("editar.html",informe=informe,estados=ESTADOS),500
        nuevos={**datos,"pdf_nombre":nombre}; cambios={c:{"antes":informe[c] or "","despues":nuevos[c] or ""} for c in CAMPOS_AUDITADOS if (informe[c] or "")!=(nuevos[c] or "")}
        with get_db() as db:
            db.execute("UPDATE informes SET numero_informe=?,fecha_incidente=?,nombre_corto=?,estado=?,sector=?,equipo_afectado=?,numero_equipo=?,empresa=?,responsable_ti=?,observaciones=?,pdf_nombre=?,pdf_path=?,fecha_modificacion=? WHERE id=?",(datos["numero_informe"],datos["fecha_incidente"],datos["numero_informe"],datos["estado"],datos["sector"],datos["equipo_afectado"],datos["numero_equipo"],"",datos["responsable_ti"],datos["observaciones"],nombre,ruta,ahora(),informe_id))
            if cambios: registrar_auditoria(db,"edicion","informe",informe_id,cambios)
        flash("Informe actualizado correctamente.","exito"); return redirect(url_for("detalle_informe",informe_id=informe_id))
    return render_template("editar.html",informe=informe,estados=ESTADOS)

@app.post("/informes/<int:informe_id>/eliminar")
@roles_requeridos("admin")
def eliminar_informe(informe_id):
    informe=obtener_informe(informe_id)
    with get_db() as db: registrar_auditoria(db,"eliminacion","informe",informe_id,{c:informe[c] for c in CAMPOS_AUDITADOS}); db.execute("DELETE FROM informes WHERE id=?",(informe_id,))
    shutil.rmtree(UPLOADS_DIR/f"INC-{informe_id:04d}",ignore_errors=True); flash("Informe y PDF eliminados.","exito"); return redirect(url_for("lista_informes"))

@app.route("/informes/<int:informe_id>/pdf")
@login_requerido
def abrir_pdf(informe_id):
    i=obtener_informe(informe_id); ruta=(BASE_DIR/i["pdf_path"]).resolve() if i["pdf_path"] else None
    if not ruta or UPLOADS_DIR.resolve() not in ruta.parents or ruta.suffix.lower() != ".pdf" or not ruta.is_file(): abort(404)
    return send_file(ruta,mimetype="application/pdf",as_attachment=request.args.get("descargar")=="1",download_name=i["pdf_nombre"])

@app.route("/usuarios",methods=("GET","POST"))
@roles_requeridos("admin")
def usuarios():
    if request.method=="POST":
        username,nombre,rol,password=request.form.get("username","").strip(),request.form.get("nombre","").strip(),request.form.get("rol",""),request.form.get("password","")
        if not username or not nombre or rol not in ROLES or len(password)<10: flash("Completa los datos y usa una contraseña de al menos 10 caracteres.","error")
        else:
            try:
                with get_db() as db: cur=db.execute("INSERT INTO usuarios(username,nombre,password_hash,rol,activo,debe_cambiar_password,fecha_creacion) VALUES(?,?,?,?,1,1,?)",(username,nombre,generate_password_hash(password),rol,ahora())); registrar_auditoria(db,"creacion","usuario",cur.lastrowid,{"username":username,"nombre":nombre,"rol":rol})
                flash("Usuario creado; deberá cambiar su contraseña al ingresar.","exito"); return redirect(url_for("usuarios"))
            except sqlite3.IntegrityError: flash("Ese usuario ya existe.","error")
    with get_db() as db: lista=db.execute("SELECT * FROM usuarios ORDER BY nombre").fetchall()
    return render_template("usuarios.html",usuarios=lista)

@app.post("/usuarios/<int:usuario_id>/actualizar")
@roles_requeridos("admin")
def actualizar_usuario(usuario_id):
    rol,activo,password=request.form.get("rol",""),1 if request.form.get("activo")=="1" else 0,request.form.get("password","")
    if rol not in ROLES or (password and len(password)<10): flash("Rol inválido o contraseña menor a 10 caracteres.","error"); return redirect(url_for("usuarios"))
    if usuario_id==g.usuario["id"] and (not activo or rol!="admin"): flash("No puedes quitar tu propio acceso de administrador.","error"); return redirect(url_for("usuarios"))
    with get_db() as db:
        u=db.execute("SELECT * FROM usuarios WHERE id=?",(usuario_id,)).fetchone()
        if not u: abort(404)
        cambios={"rol":{"antes":u["rol"],"despues":rol},"activo":{"antes":u["activo"],"despues":activo}}; db.execute("UPDATE usuarios SET rol=?,activo=? WHERE id=?",(rol,activo,usuario_id))
        if password: db.execute("UPDATE usuarios SET password_hash=?,debe_cambiar_password=1 WHERE id=?",(generate_password_hash(password),usuario_id)); cambios["password"]="restablecida"
        registrar_auditoria(db,"edicion","usuario",usuario_id,cambios)
    flash("Usuario actualizado.","exito"); return redirect(url_for("usuarios"))

@app.route("/historial")
@roles_requeridos("admin")
def auditoria():
    with get_db() as db: registros=db.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT 500").fetchall()
    return render_template("auditoria.html",registros=registros)

@app.route("/estadisticas")
@roles_requeridos("admin")
def estadisticas():
    with get_db() as db:
        filas = db.execute("""
            SELECT u.id, u.nombre, u.username, u.rol, u.activo,
                   COUNT(DISTINCT CASE WHEN a.entidad='informe' AND a.accion='creacion' THEN a.entidad_id END) AS ingresados,
                   SUM(CASE WHEN a.entidad='informe' AND a.accion='edicion' THEN 1 ELSE 0 END) AS ediciones,
                   SUM(CASE WHEN a.entidad='informe' AND a.accion='eliminacion' THEN 1 ELSE 0 END) AS eliminados,
                   SUM(CASE WHEN a.entidad='informe' THEN 1 ELSE 0 END) AS actividad,
                   MAX(CASE WHEN a.entidad='informe' THEN a.fecha END) AS ultima_actividad
            FROM usuarios u LEFT JOIN auditoria a ON a.usuario_id=u.id
            GROUP BY u.id ORDER BY ingresados DESC, actividad DESC, u.nombre
        """).fetchall()
        total_informes = db.execute("SELECT COUNT(*) FROM informes").fetchone()[0]
        atribuidos = db.execute("""SELECT COUNT(DISTINCT a.entidad_id)
            FROM auditoria a JOIN informes i ON i.id=a.entidad_id
            WHERE a.entidad='informe' AND a.accion='creacion'""").fetchone()[0]
        activos = db.execute("SELECT COUNT(*) FROM usuarios WHERE activo=1").fetchone()[0]
        actividad_mes = db.execute("""
            SELECT substr(fecha,1,7) AS mes,
                   COUNT(DISTINCT CASE WHEN accion='creacion' THEN entidad_id END) AS cantidad
            FROM auditoria WHERE entidad='informe' AND accion='creacion'
            GROUP BY mes ORDER BY mes DESC LIMIT 6
        """).fetchall()
        eventos = db.execute("""SELECT a.*, i.numero_informe, i.estado
            FROM auditoria a LEFT JOIN informes i ON i.id=a.entidad_id
            WHERE a.entidad='informe' ORDER BY a.fecha DESC, a.id DESC""").fetchall()
        total_solucionados = db.execute("SELECT COUNT(*) FROM informes WHERE estado='Archivado'").fetchone()[0]
    resumen = [dict(fila) for fila in filas]
    por_usuario = {fila["id"]: fila for fila in resumen}
    soluciones = {fila["id"]: set() for fila in resumen}
    ultimo_solucionado = None
    for evento in eventos:
        try:
            detalle = json.loads(evento["detalle"])
        except (TypeError, json.JSONDecodeError):
            detalle = {}
        fue_solucionado = (
            (evento["accion"] == "creacion" and detalle.get("estado") == "Archivado") or
            (evento["accion"] == "edicion" and isinstance(detalle.get("estado"), dict)
             and detalle["estado"].get("despues") == "Archivado")
        )
        if fue_solucionado and evento["usuario_id"] in soluciones:
            soluciones[evento["usuario_id"]].add(evento["entidad_id"])
            if ultimo_solucionado is None and evento["numero_informe"] and evento["estado"] == "Archivado":
                ultimo_solucionado = dict(evento)
    for usuario_id, ids in soluciones.items():
        por_usuario[usuario_id]["solucionados"] = len(ids)
    max_grafico = max((max(fila["ingresados"], fila["solucionados"]) for fila in resumen), default=0)
    porcentaje_resuelto = round(total_solucionados * 100 / total_informes) if total_informes else 0
    return render_template("estadisticas.html", resumen=resumen,
        total_informes=total_informes, atribuidos=atribuidos,
        sin_atribuir=max(total_informes-atribuidos, 0), activos=activos,
        actividad_mes=list(reversed(actividad_mes)), max_grafico=max_grafico,
        total_solucionados=total_solucionados,
        total_pendientes=total_informes-total_solucionados,
        porcentaje_resuelto=porcentaje_resuelto,
        ultimo_solucionado=ultimo_solucionado)

@app.template_filter("detalle_auditoria")
def detalle_auditoria(valor):
    try: return json.loads(valor)
    except (TypeError,json.JSONDecodeError): return {}

@app.errorhandler(403)
def prohibido(_): return render_template("403.html"),403
@app.errorhandler(413)
def grande(_): flash("El PDF supera el máximo de 25 MB.","error"); return redirect(url_for("nuevo_informe"))
@app.errorhandler(404)
def no_encontrado(_): return render_template("404.html"),404

init_db()
if __name__=="__main__": app.run(host="127.0.0.1",port=8080,debug=False)
