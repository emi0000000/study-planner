@echo off
rem Abre la ventana del planificador de estudio. Se usa con doble clic.
rem Si algo falla, esta ventana negra se queda abierta para que puedas leer el mensaje.

rem Trabajamos en la carpeta de este archivo (donde estan interfaz.py y tus datos).
cd /d "%~dp0"

rem Comprobamos que Python este instalado.
where python >nul 2>nul
if errorlevel 1 (
    echo No encuentro Python en este ordenador.
    echo Instalalo siguiendo el paso 1 de GUIA_DE_INICIO.md y vuelve a intentarlo.
    pause
    exit /b 1
)

rem Comprobamos que Python tenga tkinter, la parte que dibuja ventanas.
python -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo No pude abrir Python con su parte de ventanas, tkinter.
    echo Revisa el paso 1 de GUIA_DE_INICIO.md y vuelve a intentarlo.
    pause
    exit /b 1
)

rem pythonw abre la ventana sin dejar esta consola abierta.
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw interfaz.py
    exit /b 0
)

rem Si no hay pythonw, usamos python: esta consola se queda abierta mientras uses la ventana.
python interfaz.py
if errorlevel 1 pause
