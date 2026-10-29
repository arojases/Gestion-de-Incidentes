"""Create a source-only ZIP for manual upload to GitHub."""
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Incidentes-GitHub.zip"
ROOT_FILES = (".gitattributes", ".gitignore", "README.md", "SECURITY.md",
              "app.py", "requirements.txt", "iniciar_aplicacion.bat", "uploads/.gitkeep")
ALLOWED = {
    "docs": {".html", ".css", ".js", ".md", ".png"},
    "templates": {".html"},
    "static": {".css", ".js", ".svg"},
    "scripts": {".py"},
    "tests": {".py"},
}


def main():
    files = [ROOT / name for name in ROOT_FILES]
    files.append(ROOT / "docs" / ".nojekyll")
    for directory, suffixes in ALLOWED.items():
        files.extend(path for path in (ROOT / directory).rglob("*")
                     if path.is_file() and path.suffix in suffixes
                     and not any(part.startswith(".") or part == "__pycache__"
                                 for part in path.relative_to(ROOT / directory).parts))
    for path in files:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise RuntimeError(f"Archivo ausente o fuera del proyecto: {path.name}")
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            archive.write(path, path.relative_to(ROOT).as_posix())
    print(f"Preparado: {OUTPUT.name} ({len(set(files))} archivos publicos).")
    print("Extrae el ZIP y sube su contenido a GitHub. No incluye datos locales ni credenciales.")


if __name__ == "__main__":
    main()
