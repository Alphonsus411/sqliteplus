# Limpia residuos de builds anteriores

Write-Host "🧹 Limpiando archivos de distribución y metadatos..."

# Borrar carpetas comunes de build
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue `
    dist, build, *.egg-info

# Borrar cualquier carpeta __pycache__ en subdirectorios
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

# Confirmación final
Write-Host "`n✅ Limpieza completada correctamente."
