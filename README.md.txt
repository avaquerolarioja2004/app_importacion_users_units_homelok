IMPORTADOR SALTO NEBULA - GUÍA RÁPIDA (Windows)
=================================================

FICHEROS DEL PROYECTO
----------------------
    SaltoImporter.pyw      -> Doble clic para abrir la aplicación
    Iniciar Importador.bat -> Alternativa por si el doble clic
                               sobre el .pyw no funciona
    gui.py                 -> Código de la ventana (no tocar)
    importer.py             -> Lógica de importación (no tocar)
    salto_api.py             -> Cliente de la API de SALTO (no tocar)
    main.py                  -> Versión por terminal (opcional, ya
                                 no hace falta usarla)
    requirements.txt         -> Dependencias necesarias


INSTALACIÓN (solo la primera vez)
----------------------------------
1. Instala Python desde https://www.python.org/downloads/
   IMPORTANTE: en el instalador, marca la casilla
   "Add python.exe to PATH" antes de darle a instalar.

2. Abre una terminal (CMD o PowerShell) en la carpeta del
   proyecto y ejecuta:

       pip install -r requirements.txt

   Esto solo hay que hacerlo una vez.


USO DEL DÍA A DÍA (sin terminal)
----------------------------------
1. Haz doble clic en "SaltoImporter.pyw".
   (Si no se abre nada, prueba con "Iniciar Importador.bat")

2. En la ventana:
     - Escribe el Installation ID.
     - Escribe el Token.
     - Haz clic en cada una de las tres zonas (users.csv,
       units.csv, access.csv) para seleccionar cada fichero.
     - Indica dónde quieres guardar el passcodes.csv generado
       (por defecto se guarda en esta misma carpeta).

3. Pulsa "Cargar" para lanzar la importación completa,
   o "Borrar" para eliminar TODAS las units de esa instalación
   (te pedirá confirmación antes de hacerlo).

4. El progreso se ve en tiempo real en el cuadro de log de la
   propia ventana. Además, cada vez que pulsas "Cargar" o
   "Borrar" se guarda un fichero de log nuevo dentro de la
   carpeta "logs/" (con la fecha y hora exactas), por si
   necesitas revisarlo más tarde.

La aplicación recuerda el Installation ID, las rutas de los
CSV y dónde guardar el passcodes.csv entre una sesión y otra
(NO recuerda el Token, hay que escribirlo cada vez, por
seguridad).


CONVERTIRLO EN UN .EXE (opcional)
-----------------------------------
Si prefieres un único .exe que no dependa de tener Python
instalado, puedes generarlo tú mismo en Windows con:

    pip install pyinstaller
    pyinstaller --onefile --windowed --name SaltoImporter SaltoImporter.pyw

El .exe resultante aparecerá en la carpeta "dist".
