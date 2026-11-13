@echo off
setlocal
cd /d "%~dp0"

rem Nome do zip = nome da pasta do projeto
for %%I in ("%~dp0.") do set "NOME=%%~nxI"
set "STAGE=%TEMP%\%NOME%_stage"
set "DIST=%~dp0dist"
set "ZIP=%DIST%\%NOME%.zip"

rem Cria a pasta dist se nao existir
if not exist "%DIST%" mkdir "%DIST%"

rem Limpa restos de execucoes anteriores (pasta temporaria e zip antigo)
if exist "%STAGE%" rmdir /s /q "%STAGE%"
if exist "%ZIP%" del /q "%ZIP%"

rem Copia o projeto para uma pasta temporaria, deixando de fora:
rem   .git, *.egg-info, dist, .venv, build, __pycache__, *.zip, build.bat e build_.bat
robocopy "%~dp0." "%STAGE%" /E /XD .git .venv dist build __pycache__ *.egg-info /XF *.zip build.bat build_.bat /NFL /NDL /NJH /NJS /NP
if errorlevel 8 (
    echo ERRO: falha ao copiar os arquivos.
    exit /b 1
)

rem Remove da copia temporaria todos os .md, EXCETO README.md
powershell -NoProfile -Command "Get-ChildItem -Path '%STAGE%' -Recurse -File -Filter *.md | Where-Object { $_.Name -ne 'README.md' } | Remove-Item -Force"
if errorlevel 1 (
    echo ERRO: falha ao filtrar os arquivos .md.
    rmdir /s /q "%STAGE%"
    exit /b 1
)

rem Cria o main.py na raiz da copia temporaria (o projeto original nao e alterado)
rem O nome do modulo chamado e o nome da pasta do projeto (%NOME%)
(
    echo import runpy
    echo.
    echo if __name__ == "__main__":
    echo     runpy.run_module^("%NOME%", run_name="__main__"^)
) > "%STAGE%\main.py"
if errorlevel 1 (
    echo ERRO: falha ao criar o main.py.
    rmdir /s /q "%STAGE%"
    exit /b 1
)

rem Zipa o CONTEUDO da pasta temporaria (main.py fica na raiz do zip).
rem Entradas com barra normal (/) e com as pastas listadas antes dos arquivos,
rem para o runner extrair corretamente (Compress-Archive usa barra invertida).
powershell -NoProfile -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; $src='%STAGE%'; $z=[IO.Compression.ZipFile]::Open('%ZIP%','Create'); Get-ChildItem -LiteralPath $src -Recurse | Sort-Object FullName | ForEach-Object { $rel=$_.FullName.Substring($src.Length+1).Replace('\','/'); if ($_.PSIsContainer) { [void]$z.CreateEntry($rel+'/') } else { [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($z,$_.FullName,$rel) } }; $z.Dispose()"
if errorlevel 1 (
    echo ERRO: falha ao gerar o zip.
    rmdir /s /q "%STAGE%"
    exit /b 1
)

rmdir /s /q "%STAGE%"
echo.
echo Zip gerado: %ZIP%
exit /b 0