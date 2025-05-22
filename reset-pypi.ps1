# reset-pypi.ps1

Write-Host "🧹 Limpiando artefactos antiguos..."

# Elimina carpetas comunes de empaquetado
@(
    "build",
    "dist",
    "*.egg-info",
    "**/__pycache__",
    "**/*.pyc",
    "**/*.pyo"
) | ForEach-Object {
    Get-ChildItem -Path $_ -Recurse -Force -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "✅ Limpieza completada."

# Opcional: Reinstalar build y twine por si acaso
Write-Host "`n🔄 Verificando herramientas..."
python -m pip install --upgrade build twine

Write-Host "`n📦 Generando nuevo paquete..."
python -m build

Write-Host "`n📤 Subiendo a PyPI..."
twine upload dist/*

Write-Host "`n🚀 Proceso finalizado. Tu paquete debería estar actualizado en PyPI."
