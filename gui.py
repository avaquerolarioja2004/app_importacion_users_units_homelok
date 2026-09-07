"""
Interfaz gráfica del Importador SALTO Nebula.

Permite introducir:
    - Installation ID
    - Token (Bearer)
    - Rutas de units.csv, access.csv y users.csv
    - Dónde guardar el passcodes.csv generado

Y lanzar la importación mostrando el log en tiempo real
dentro de la propia ventana (además de guardarse, como
siempre, en la carpeta "logs/", con un fichero nuevo por
cada acción que se lance).

Requisitos: los mismos que el proyecto (requirements.txt).
Tkinter viene incluido con la instalación estándar de
Python en Windows, no hace falta instalar nada más.
"""

import json
import os
import sys
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# La GUI controla ella misma cuándo se abre cada fichero de
# log (uno por cada acción), en vez del log automático que se
# abre al importar el módulo (pensado para el uso por CLI).
os.environ["IMPORTER_SKIP_AUTOLOG"] = "1"

from importer import Importer, register_stream, start_new_log


# =================================================================
# CONFIG (recordar últimos valores usados, salvo el token)
# =================================================================

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "gui_config.json"
)


def load_config():

    if not os.path.exists(CONFIG_PATH):
        return {}

    try:

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {}


def save_config(data):

    try:

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    except Exception:
        pass


# =================================================================
# REDIRECTOR DE TEXTO -> COLA (para actualizar la GUI desde
# el hilo secundario de forma segura)
# =================================================================

class QueueWriter:

    def __init__(self, msg_queue):
        self.msg_queue = msg_queue

    def write(self, data):
        self.msg_queue.put(("log", data))

    def flush(self):
        pass


# =================================================================
# APP
# =================================================================

class ImporterApp:

    def __init__(self, root):

        self.root = root
        self.root.title("Importador SALTO Nebula")
        self.root.geometry("780x620")
        self.root.minsize(680, 520)

        self.msg_queue = queue.Queue()
        self.worker_thread = None

        self.config_data = load_config()

        self._build_ui()

        # Conecta el log del importer (prints + logging) a esta
        # ventana, en tiempo real.
        register_stream(QueueWriter(self.msg_queue))

        self.root.after(80, self._poll_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # =============================================================
    # UI
    # =============================================================

    def _build_ui(self):

        pad = {"padx": 8, "pady": 4}

        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        # ---------------------------------------------------------
        # CREDENCIALES
        # ---------------------------------------------------------

        creds = ttk.LabelFrame(main, text="Credenciales SALTO Nebula")
        creds.pack(fill="x", **pad)

        ttk.Label(creds, text="Installation ID:").grid(
            row=0, column=0, sticky="w", **pad
        )

        self.installation_var = tk.StringVar(
            value=self.config_data.get("installation_id", "")
        )

        ttk.Entry(
            creds, textvariable=self.installation_var, width=55
        ).grid(row=0, column=1, sticky="we", **pad)

        ttk.Label(creds, text="Token:").grid(
            row=1, column=0, sticky="w", **pad
        )

        self.token_var = tk.StringVar()

        self.token_entry = ttk.Entry(
            creds, textvariable=self.token_var, width=55, show="•"
        )
        self.token_entry.grid(row=1, column=1, sticky="we", **pad)

        self.show_token_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(
            creds,
            text="Mostrar",
            variable=self.show_token_var,
            command=self._toggle_token_visibility
        ).grid(row=1, column=2, sticky="w", **pad)

        creds.columnconfigure(1, weight=1)

        # ---------------------------------------------------------
        # ZONAS DE CARGA DE CSV (una por cada fichero)
        # ---------------------------------------------------------

        zones_frame = ttk.LabelFrame(main, text="Ficheros CSV")
        zones_frame.pack(fill="x", **pad)

        self.units_var = tk.StringVar(
            value=self.config_data.get("units_path", "")
        )
        self.access_var = tk.StringVar(
            value=self.config_data.get("access_path", "")
        )
        self.users_var = tk.StringVar(
            value=self.config_data.get("users_path", "")
        )

        self._build_csv_zone(zones_frame, 0, "units.csv", self.units_var)
        self._build_csv_zone(zones_frame, 1, "access.csv", self.access_var)
        self._build_csv_zone(zones_frame, 2, "users.csv", self.users_var)

        zones_frame.columnconfigure(0, weight=1)
        zones_frame.columnconfigure(1, weight=1)
        zones_frame.columnconfigure(2, weight=1)

        # ---------------------------------------------------------
        # SALIDA (passcodes.csv)
        # ---------------------------------------------------------

        output_frame = ttk.LabelFrame(main, text="Salida")
        output_frame.pack(fill="x", **pad)

        default_passcode_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "passcodes.csv"
        )

        self.passcode_var = tk.StringVar(
            value=self.config_data.get(
                "passcode_path", default_passcode_path
            )
        )

        ttk.Label(output_frame, text="Guardar passcodes.csv en:").grid(
            row=0, column=0, sticky="w", padx=8, pady=4
        )

        ttk.Entry(output_frame, textvariable=self.passcode_var).grid(
            row=0, column=1, sticky="we", padx=8, pady=4
        )

        ttk.Button(
            output_frame, text="Examinar...",
            command=self._browse_passcode_output
        ).grid(row=0, column=2, padx=8, pady=4)

        output_frame.columnconfigure(1, weight=1)

        # ---------------------------------------------------------
        # BOTONES DE ACCIÓN: CARGAR / BORRAR
        # ---------------------------------------------------------

        actions = ttk.Frame(main)
        actions.pack(fill="x", **pad)

        self.run_button = ttk.Button(
            actions,
            text="⬆  Cargar",
            command=self._start_import
        )
        self.run_button.pack(side="left", padx=4, ipadx=14, ipady=4)

        self.clear_button = ttk.Button(
            actions,
            text="🗑  Borrar",
            command=self._start_clear
        )
        self.clear_button.pack(side="left", padx=4, ipadx=14, ipady=4)

        self.update_button = ttk.Button(
            actions,
            text="🔄  Actualizar",
            command=self._start_update
        )
        self.update_button.pack(side="left", padx=4, ipadx=14, ipady=4)

        self.progress = ttk.Progressbar(
            actions, mode="indeterminate", length=160
        )
        self.progress.pack(side="right", padx=4)

        # ---------------------------------------------------------
        # OPCIONES DE ACTUALIZACIÓN (solo afectan al botón
        # "Actualizar"). Usa el mismo fichero access.csv que ya
        # se ha seleccionado arriba como origen de los accesos
        # deseados para cada unit.
        # ---------------------------------------------------------

        update_opts = ttk.LabelFrame(
            main, text="Opciones de Actualizar (usa access.csv de arriba)"
        )
        update_opts.pack(fill="x", **pad)

        self.update_add_var = tk.BooleanVar(value=True)
        self.update_remove_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(
            update_opts,
            text="Añadir accesos nuevos que estén en el CSV y el usuario no tenga",
            variable=self.update_add_var
        ).pack(anchor="w", padx=8, pady=(4, 0))

        ttk.Checkbutton(
            update_opts,
            text="Borrar accesos antiguos que el usuario tenga y ya NO estén en el CSV",
            variable=self.update_remove_var
        ).pack(anchor="w", padx=8, pady=(0, 4))

        # ---------------------------------------------------------
        # LOG
        # ---------------------------------------------------------

        log_frame = ttk.LabelFrame(main, text="Log")
        log_frame.pack(fill="both", expand=True, **pad)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap="word", state="disabled",
            background="#111111", foreground="#e0e0e0",
            insertbackground="#e0e0e0", font=("Consolas", 9)
        )
        self.log_text.pack(fill="both", expand=True)

    def _build_csv_zone(self, parent, col, title, var):

        zone = tk.Frame(
            parent, relief="groove", borderwidth=2, cursor="hand2"
        )
        zone.grid(row=0, column=col, sticky="nsew", padx=8, pady=8)

        icon_label = ttk.Label(zone, text="📄", font=("Segoe UI", 22))
        icon_label.pack(pady=(12, 2))

        title_label = ttk.Label(
            zone, text=title, font=("Segoe UI", 10, "bold")
        )
        title_label.pack()

        display_var = tk.StringVar()

        def update_display(*_args):

            path = var.get()

            display_var.set(
                os.path.basename(path) if path else "Sin seleccionar"
            )

        var.trace_add("write", update_display)
        update_display()

        file_label = ttk.Label(
            zone, textvariable=display_var,
            wraplength=150, justify="center",
            foreground="#2a7a2a"
        )
        file_label.pack(pady=(2, 8), padx=6)

        browse_btn = ttk.Button(
            zone, text="Examinar...",
            command=lambda v=var: self._browse_file(v)
        )
        browse_btn.pack(pady=(0, 12))

        # Toda la zona es clicable, no solo el botón.
        for widget in (zone, icon_label, title_label, file_label):

            widget.bind(
                "<Button-1>",
                lambda _e, v=var: self._browse_file(v)
            )

    # =============================================================
    # HELPERS UI
    # =============================================================

    def _toggle_token_visibility(self):

        self.token_entry.config(
            show="" if self.show_token_var.get() else "•"
        )

    def _browse_file(self, var):

        path = filedialog.askopenfilename(
            title="Selecciona el CSV",
            filetypes=[("CSV files", "*.csv"), ("Todos los ficheros", "*.*")]
        )

        if path:
            var.set(path)

    def _browse_passcode_output(self):

        current = self.passcode_var.get().strip()

        initial_dir = os.path.dirname(current) if current else os.getcwd()
        initial_file = os.path.basename(current) if current else "passcodes.csv"

        path = filedialog.asksaveasfilename(
            title="Guardar passcodes.csv como...",
            defaultextension=".csv",
            initialdir=initial_dir if os.path.isdir(initial_dir) else os.getcwd(),
            initialfile=initial_file,
            filetypes=[("CSV files", "*.csv"), ("Todos los ficheros", "*.*")]
        )

        if path:
            self.passcode_var.set(path)

    def _append_log(self, text):

        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_running(self, running):

        state = "disabled" if running else "normal"

        self.run_button.config(state=state)
        self.clear_button.config(state=state)
        self.update_button.config(state=state)

        if running:
            self.progress.start(12)
        else:
            self.progress.stop()

    # =============================================================
    # VALIDACIÓN
    # =============================================================

    def _get_credentials(self):

        installation_id = self.installation_var.get().strip()
        token = self.token_var.get().strip()

        if not installation_id:
            messagebox.showerror("Falta información", "Introduce el Installation ID.")
            return None

        if not token:
            messagebox.showerror("Falta información", "Introduce el Token.")
            return None

        return installation_id, token

    def _get_csv_paths(self):

        units_path = self.units_var.get().strip()
        access_path = self.access_var.get().strip()
        users_path = self.users_var.get().strip()

        for label, path in (
            ("units.csv", units_path),
            ("access.csv", access_path),
            ("users.csv", users_path),
        ):

            if not path:
                messagebox.showerror(
                    "Falta información", f"Selecciona el fichero {label}."
                )
                return None

            if not os.path.isfile(path):
                messagebox.showerror(
                    "Fichero no encontrado", f"No se encuentra: {path}"
                )
                return None

        return units_path, access_path, users_path

    def _get_passcode_path(self):

        passcode_path = self.passcode_var.get().strip()

        if not passcode_path:
            messagebox.showerror(
                "Falta información",
                "Indica dónde guardar el passcodes.csv."
            )
            return None

        passcode_dir = os.path.dirname(passcode_path)

        if passcode_dir and not os.path.isdir(passcode_dir):

            try:
                os.makedirs(passcode_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror(
                    "Ruta no válida",
                    f"No se pudo crear la carpeta de destino:\n{e}"
                )
                return None

        return passcode_path

    def _save_current_config(self):

        save_config({
            "installation_id": self.installation_var.get().strip(),
            "units_path": self.units_var.get().strip(),
            "access_path": self.access_var.get().strip(),
            "users_path": self.users_var.get().strip(),
            "passcode_path": self.passcode_var.get().strip(),
        })

    # =============================================================
    # ACCIONES
    # =============================================================

    def _start_import(self):

        creds = self._get_credentials()

        if not creds:
            return

        csv_paths = self._get_csv_paths()

        if not csv_paths:
            return

        passcode_path = self._get_passcode_path()

        if not passcode_path:
            return

        installation_id, token = creds
        units_path, access_path, users_path = csv_paths

        self._save_current_config()
        self._set_running(True)

        self.worker_thread = threading.Thread(
            target=self._run_import_worker,
            args=(
                installation_id, token,
                units_path, access_path, users_path,
                passcode_path
            ),
            daemon=True
        )
        self.worker_thread.start()

    def _run_import_worker(
        self, installation_id, token,
        units_path, access_path, users_path,
        passcode_path
    ):

        try:

            start_new_log()

            importer = Importer(
                token=token,
                installation_id=installation_id,
                passcode_file=passcode_path
            )

            importer.run(units_path, access_path, users_path)

            self.msg_queue.put(("done", True, None))

        except Exception as e:

            self.msg_queue.put(("done", False, str(e)))

    def _start_update(self):

        creds = self._get_credentials()

        if not creds:
            return

        access_path = self.access_var.get().strip()

        if not access_path:
            messagebox.showerror(
                "Falta fichero",
                "Selecciona el fichero access.csv arriba "
                "antes de actualizar."
            )
            return

        installation_id, token = creds
        add_new = self.update_add_var.get()
        remove_missing = self.update_remove_var.get()

        self._save_current_config()
        self._set_running(True)

        self.worker_thread = threading.Thread(
            target=self._run_update_worker,
            args=(
                installation_id, token,
                access_path, add_new, remove_missing
            ),
            daemon=True
        )
        self.worker_thread.start()

    def _run_update_worker(
        self, installation_id, token,
        access_path, add_new, remove_missing
    ):

        try:

            start_new_log()

            importer = Importer(
                token=token,
                installation_id=installation_id
            )

            rows = importer.read_csv(access_path)

            importer.update_access(
                rows,
                add_new=add_new,
                remove_missing=remove_missing
            )

            self.msg_queue.put(("done", True, None))

        except Exception as e:

            self.msg_queue.put(("done", False, str(e)))

    def _start_clear(self):

        creds = self._get_credentials()

        if not creds:
            return

        confirm = messagebox.askyesno(
            "Confirmar borrado",
            "Esto borrará TODAS las units de la instalación indicada.\n\n"
            "¿Seguro que quieres continuar?",
            icon="warning"
        )

        if not confirm:
            return

        installation_id, token = creds

        self._set_running(True)

        self.worker_thread = threading.Thread(
            target=self._run_clear_worker,
            args=(installation_id, token),
            daemon=True
        )
        self.worker_thread.start()

    def _run_clear_worker(self, installation_id, token):

        try:

            start_new_log()

            importer = Importer(
                token=token,
                installation_id=installation_id
            )

            importer.clear_units()

            self.msg_queue.put(("done", True, None))

        except Exception as e:

            self.msg_queue.put(("done", False, str(e)))

    # =============================================================
    # COLA -> UI (se ejecuta siempre en el hilo principal)
    # =============================================================

    def _poll_queue(self):

        try:

            while True:

                kind, *payload = self.msg_queue.get_nowait()

                if kind == "log":
                    self._append_log(payload[0])

                elif kind == "done":

                    ok, error = payload

                    self._set_running(False)

                    if ok:
                        messagebox.showinfo(
                            "Finalizado", "Proceso finalizado correctamente."
                        )
                    else:
                        messagebox.showerror(
                            "Error", f"El proceso terminó con un error:\n\n{error}"
                        )

        except queue.Empty:
            pass

        self.root.after(80, self._poll_queue)

    def _on_close(self):

        if self.worker_thread and self.worker_thread.is_alive():

            if not messagebox.askyesno(
                "Proceso en curso",
                "Hay un proceso en marcha. ¿Seguro que quieres cerrar?"
            ):
                return

        self.root.destroy()


def main():

    root = tk.Tk()

    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass

    ImporterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()