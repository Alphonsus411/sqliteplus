# Crear carpeta .idea si no existe
$ideaPath = ".idea"
if (-not (Test-Path $ideaPath)) {
    New-Item -Path $ideaPath -ItemType Directory
}

# Crear archivo misc.xml
$miscXmlContent = @"
<project version="4">
  <component name="ProjectRootManager" version="2" languageLevel="Python 3.10" project-jdk-name="Python 3.10" project-jdk-type="Python SDK" />
</project>
"@
Set-Content -Path ".idea\misc.xml" -Value $miscXmlContent -Encoding UTF8

# Crear archivo workspace.xml con configuración básica para pytest
$workspaceXmlContent = @"
<project version="4">
  <component name="RunManager">
    <configuration name="Test sqliteplus" type="PythonTestConfigurationType" factoryName="pytest">
      <module name="sqliteplus" />
      <option name="SCRIPT_NAME" value="\$PROJECT_DIR\tests\test_insert_and_fetch_data.py" />
      <option name="PARAMETERS" value="" />
      <option name="WORKING_DIRECTORY" value="\$PROJECT_DIR\$" />
      <option name="INTERPRETER_OPTIONS" value="" />
      <option name="SDK_HOME" value="\$PROJECT_DIR\.venv\Scripts\python.exe" />
      <method v="2">
        <option name="Make" enabled="true" />
      </method>
    </configuration>
  </component>
</project>
"@
Set-Content -Path ".idea\workspace.xml" -Value $workspaceXmlContent -Encoding UTF8
