# Subir el proyecto a GitHub

## Preparar los archivos

Desde la carpeta principal, ejecuta:

```powershell
python scripts/preparar_publicacion.py
```

Se crea `Incidentes-GitHub.zip`, con código, documentación, pruebas y demo. No incluye bases de datos, PDF, contraseñas, entornos virtuales ni historial de Git.

Extrae el ZIP en una carpeta vacía y sube **su contenido** al repositorio con **Add file → Upload files**. No subas el ZIP como único archivo ni arrastres la carpeta de trabajo original.

Puedes utilizar este texto en la descripción del repositorio:

> Gestor de informes de incidentes TI con seguimiento, PDF, historial y permisos por usuario. Proyecto de origen laboral con demo interactiva y datos ficticios.

## Activar la demo

Después de subir los archivos al repositorio público:

1. Abre **Settings → Pages**.
2. En **Build and deployment**, selecciona **Deploy from a branch**.
3. Elige la rama donde subiste el proyecto, normalmente `main`, y la carpeta `/docs`.
4. Guarda los cambios y espera a que GitHub indique que la página está publicada.

Para el repositorio `arojases/Gestion-de-Incidentes`, la dirección esperada es:

<https://arojases.github.io/Gestion-de-Incidentes/>

Si cambias el propietario o el nombre del repositorio, actualiza los enlaces del README y de `docs/index.html`. El enlace del README está preparado para esa dirección; no implica que la demo ya esté publicada.

La demo funciona con archivos estáticos. No ejecuta Flask ni conecta con la base local. Permite explorar datos ficticios y simular cambios de estado sin compartir cuentas ni contraseñas.

Referencia: [configurar la publicación en GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

## Antes de compartirlo

- Abre el enlace de la demo y comprueba búsqueda, filtros y detalle.
- Añade la dirección publicada al campo **Website** del repositorio.
- Mantén `.env.demo` y cualquier contraseña fuera de las cargas manuales.
- Para probar la aplicación completa, utiliza las instrucciones de [instalación](INSTALACION.md).
