# Gestor de informes de incidentes TI

Aplicación web para centralizar informes de incidentes, conservar sus documentos PDF y registrar la actividad de los usuarios. Desarrollada con Python, Flask y SQLite, con una interfaz en español y permisos según el rol de cada cuenta.

El proyecto nace de una necesidad de gestión de incidentes en un entorno laboral. Esta es la edición pública del código; la versión utilizada en el trabajo evoluciona de forma independiente. El repositorio no distribuye información de la organización, cuentas, informes ni documentos internos.

## Funcionalidades

- Registro, consulta, edición y eliminación de informes con su PDF asociado.
- Búsqueda por número de informe, sector, equipo, responsable y observaciones.
- Seguimiento de estados: pendiente, en revisión y archivado.
- Administración de usuarios y cambio obligatorio de la contraseña inicial.
- Historial de cambios y auditoría de operaciones.
- Estadísticas de informes y actividad de usuarios para administradores.

| Rol | Acceso |
| --- | --- |
| Administrador | Informes, usuarios, estadísticas y auditoría general |
| Editor | Consulta, creación y edición de informes |
| Lector | Consulta de informes y sus documentos |

## Tecnología y estructura

El servidor renderiza las páginas con Jinja y guarda los datos en SQLite. Los PDF permanecen en el sistema de archivos y se entregan mediante una ruta que exige autenticación.

```text
app.py                   Rutas, permisos, validaciones y persistencia
templates/               Vistas HTML
static/                  Estilos, iconos y JavaScript
uploads/                 Documentos locales; excluidos de Git
tests/                   Pruebas con datos temporales
requirements.txt         Dependencias de ejecución
iniciar_aplicacion.bat    Lanzador para Windows
```

La base `incidentes.db` se crea al iniciar y se excluye del repositorio.

## Instalación local en Windows

Requisitos: Python 3.11 o superior y PowerShell. Ejecuta desde la carpeta del proyecto:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Configura las variables de entorno antes de iniciar:

```powershell
$env:SECRET_KEY = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))")
$env:INITIAL_ADMIN_USER = "admin"
$claveInicial = Read-Host "Contraseña temporal del administrador (mínimo 14 caracteres)" -AsSecureString
$env:INITIAL_ADMIN_PASSWORD = [System.Net.NetworkCredential]::new("", $claveInicial).Password
$env:RESPONSABLES_TI = "Responsable TI"
.\.venv\Scripts\python.exe app.py
```

Abre <http://127.0.0.1:8080>. Para detener el servidor, presiona `Ctrl+C` en la terminal.

`INITIAL_ADMIN_PASSWORD` solo se utiliza cuando la base no tiene usuarios. La primera cuenta debe cambiar su contraseña antes de acceder a los informes. No hay credenciales predeterminadas.

| Variable | Uso |
| --- | --- |
| `SECRET_KEY` | Obligatoria: clave aleatoria de al menos 32 caracteres para firmar sesiones |
| `INITIAL_ADMIN_USER` | Nombre de la primera cuenta; por defecto, `admin` |
| `INITIAL_ADMIN_PASSWORD` | Obligatoria en una base nueva; mínimo 14 caracteres |
| `RESPONSABLES_TI` | Nombres de responsables separados por comas; por defecto, `Responsable TI` |
| `COOKIE_SECURE` | Establecer en `1` cuando se sirva mediante HTTPS |

Las variables de estos comandos duran únicamente en la terminal actual. Conserva la clave de sesión en una configuración privada y reutilízala entre arranques; cambiarla invalida las sesiones existentes. La aplicación no carga archivos `.env` automáticamente. No incluyas valores reales en scripts versionados.

El lanzador `iniciar_aplicacion.bat` utiliza el mismo entorno virtual y requiere las variables configuradas en la terminal desde la que se ejecuta.

## Seguridad y alcance

- Contraseñas almacenadas como hashes mediante Werkzeug.
- Comprobación de permisos en el servidor y protección CSRF en formularios.
- Cookies `HttpOnly` y `SameSite=Lax`, con opción `Secure` para HTTPS.
- Consultas SQL parametrizadas para los datos de entrada.
- Límite de 25 MB por archivo y comprobación de extensión y cabecera PDF.
- Acceso a documentos restringido a archivos PDF dentro de `uploads`.
- Respuestas de la aplicación con `Cache-Control: no-store`.

La validación de cabecera no sustituye el análisis antivirus de los documentos. El servidor incluido escucha en `127.0.0.1` y está destinado a uso local. Un despliegue de red necesita una revisión específica, HTTPS, un servidor WSGI de producción y límites de intentos de autenticación. Estas medidas no constituyen una auditoría completa ni una garantía de ausencia de vulnerabilidades.

Consulta [SECURITY.md](SECURITY.md) para comunicar un problema de seguridad sin divulgar datos privados.

## Validación

### Datos de demostración

Para cargar ocho informes ficticios con sus PDF y un historial de ejemplo, configura `SECRET_KEY` e `INITIAL_ADMIN_PASSWORD` como se indica en la instalación y ejecuta:

```powershell
.\.venv\Scripts\python.exe scripts/cargar_demo.py
```

La cuenta creada es `admin.demo` y utiliza la contraseña que configuraste, con cambio obligatorio al ingresar. No se distribuye ninguna contraseña de demostración. Los responsables de estos ejemplos usan la configuración predeterminada `Responsable TI`.

En esta copia local, la configuración nueva de la demostración está guardada en `.env.demo`, excluido de Git. Puedes cargarla en PowerShell sin imprimir sus valores y luego iniciar la aplicación:

```powershell
Get-Content .env.demo | ForEach-Object {
    $nombre, $valor = $_ -split '=', 2
    if ($nombre -in @('SECRET_KEY', 'INITIAL_ADMIN_PASSWORD', 'RESPONSABLES_TI')) {
        [Environment]::SetEnvironmentVariable($nombre, $valor, 'Process')
    }
}
.\.venv\Scripts\python.exe app.py
```

Ese archivo local no se incluye al clonar el repositorio. Para una instalación nueva, configura tus propias variables siguiendo los pasos anteriores.

Si ya hay datos, el script se detiene. La opción `--reemplazar` elimina definitivamente la base y los adjuntos locales antes de instalar los ejemplos; detén primero la aplicación. Los datos generados permanecen excluidos de Git: se publica el generador, no la base de datos.

### Pruebas automatizadas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas crean una base temporal y no consultan ni modifican la base de uso local.

Para revisar el flujo completo, utiliza datos ficticios: crea un informe con un PDF de prueba, búscalo, edítalo, verifica su historial y elimínalo con una cuenta administradora.

## Respaldo

Con el servidor detenido, copia juntos `incidentes.db` y `uploads/` a una ubicación protegida. Para restaurar, utiliza ambos elementos del mismo respaldo. La base incluye datos de usuarios y auditoría; trátala como información confidencial.

## Publicación

El repositorio público debe contener exclusivamente código, documentación y recursos de interfaz. `.gitignore` excluye bases, adjuntos, logs, entornos virtuales y secretos locales. No arrastres toda la carpeta al navegador de GitHub: la carga manual no aplica las exclusiones de Git.

Antes de publicar, revisa los archivos del commit y utiliza únicamente el historial limpio de esta edición. Eliminar un repositorio remoto no limpia por sí solo el historial de una copia local. No publiques respaldos de versiones anteriores.
