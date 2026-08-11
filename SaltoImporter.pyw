"""
Lanzador de doble clic para Windows.

Este fichero tiene extensión .pyw en vez de .py: Windows lo asocia
automáticamente con "pythonw.exe" (en vez de "python.exe"), por lo
que al hacer doble clic se abre directamente la ventana, SIN que
aparezca ninguna consola/terminal negra detrás.

Requisito: tener Python instalado (con la opción "Add python.exe
to PATH" marcada durante la instalación) y haber ejecutado una vez,
desde una terminal:

    pip install -r requirements.txt

A partir de ahí, este fichero ya se abre solo con doble clic.
"""

import os
import sys

# Asegura que Python encuentra importer.py, salto_api.py y gui.py
# aunque el doble clic se haga desde otra carpeta o acceso directo.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":

    try:

        from gui import main
        main()

    except Exception as e:

        # Al abrir con doble clic no hay terminal donde ver el
        # error (p.ej. si falta "pip install -r requirements.txt"),
        # así que se muestra en una ventana.

        import traceback
        import tkinter as tk
        from tkinter import messagebox

        details = traceback.format_exc()

        root = tk.Tk()
        root.withdraw()

        messagebox.showerror(
            "Error al iniciar el Importador SALTO Nebula",
            "No se ha podido iniciar la aplicación:\n\n"
            f"{e}\n\n"
            "Si es la primera vez que lo usas, abre una terminal "
            "en esta carpeta y ejecuta:\n\n"
            "    pip install -r requirements.txt\n\n"
            f"Detalle técnico:\n{details}"
        )
