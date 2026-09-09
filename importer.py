import csv
import logging
import os
import sys
from datetime import datetime, timezone

from salto_api import SaltoAPI


# =============================================================
# LOGGING
# =============================================================
#
# Cada "acción" (una ejecución del CLI, o cada Importar/--clear
# lanzado desde la GUI) genera un fichero de log nuevo dentro
# de la carpeta "logs", nombrado con la fecha y hora exacta de
# inicio (ej: logs/2026-08-11_10-31-50.log).
#
# El fichero recoge TODO lo que se muestra por terminal, tanto
# los print() como los mensajes de logging (info/warning/error).
# Además, cualquier stream adicional registrado con
# register_stream() (por ejemplo la ventana de la GUI) recibe,
# en tiempo real, exactamente lo mismo.
# =============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOGS_DIR = os.path.join(
    BASE_DIR,
    "logs"
)

os.makedirs(
    LOGS_DIR,
    exist_ok=True
)


class _Tee:
    """
    Duplica cada escritura hacia varios streams a la vez
    (por ejemplo: terminal + fichero de log + ventana GUI).
    """

    def __init__(self, *streams):
        self.streams = list(streams)

    def write(self, data):

        for stream in self.streams:

            try:
                stream.write(data)
                stream.flush()
            except Exception:
                # Si un stream falla (p.ej. la ventana se
                # cerró), no debe romper el resto del log.
                pass

    def flush(self):

        for stream in self.streams:

            try:
                stream.flush()
            except Exception:
                pass

    def add_stream(self, stream):
        self.streams.append(stream)

    def replace_stream(self, old, new):

        for i, stream in enumerate(self.streams):

            if stream is old:
                self.streams[i] = new
                return

        self.streams.append(new)


# -------------------------------------------------------------
# Si se ejecuta sin consola (p.ej. pythonw.exe en Windows, o
# la GUI empaquetada con --windowed), sys.stdout/stderr pueden
# ser None. Se sustituyen por un "sumidero" para no romper.
# -------------------------------------------------------------

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")

if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

_stdout_tee = _Tee(sys.stdout)
_stderr_tee = _Tee(sys.stderr)

sys.stdout = _stdout_tee
sys.stderr = _stderr_tee

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(
    "salto_importer"
)

_current_log_file = None


def start_new_log():
    """
    Abre un fichero de log nuevo (logs/YYYY-MM-DD_HH-MM-SS.log)
    y lo convierte en el destino activo de todo lo que se
    imprima a partir de ahora (print y logging), sustituyendo
    al fichero de log anterior si lo había.

    Se llama automáticamente una vez al importar este módulo
    (uso normal por CLI, un proceso = una ejecución = un log).

    La GUI la vuelve a llamar antes de cada acción (Importar o
    --clear) para que cada acción tenga su propio fichero de
    log, aunque la ventana se mantenga abierta entre acciones.

    Devuelve la ruta del fichero de log creado.
    """

    global _current_log_file

    base_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    path = os.path.join(
        LOGS_DIR,
        base_name + ".log"
    )

    # Evita colisiones si dos acciones se lanzan en el mismo
    # segundo (posible desde la GUI, pulsando muy rápido).
    counter = 2

    while os.path.exists(path):

        path = os.path.join(
            LOGS_DIR,
            f"{base_name}_{counter}.log"
        )

        counter += 1

    new_file = open(
        path,
        "a",
        encoding="utf-8"
    )

    if _current_log_file is not None:

        _stdout_tee.replace_stream(_current_log_file, new_file)
        _stderr_tee.replace_stream(_current_log_file, new_file)

        try:
            _current_log_file.close()
        except Exception:
            pass

    else:

        _stdout_tee.add_stream(new_file)
        _stderr_tee.add_stream(new_file)

    _current_log_file = new_file

    logger.info(
        f"Log de esta ejecución: {path}"
    )

    return path


def register_stream(stream):
    """
    Registra un stream adicional (p.ej. un widget de texto de
    una GUI) para que reciba también todo lo que se imprime
    por terminal/log, en tiempo real. Queda registrado de forma
    permanente, incluso si luego se llama a start_new_log().
    """

    _stdout_tee.add_stream(stream)
    _stderr_tee.add_stream(stream)


# -------------------------------------------------------------
# Uso normal por CLI: se abre el log inmediatamente al
# importar el módulo. La GUI puede desactivar esto poniendo
# la variable de entorno IMPORTER_SKIP_AUTOLOG=1 antes de
# importar este módulo, y llamar a start_new_log() ella misma
# en el momento adecuado (una vez por cada acción).
# -------------------------------------------------------------

if os.environ.get("IMPORTER_SKIP_AUTOLOG") != "1":
    start_new_log()


# =============================================================
# DAY MAPPING
# =============================================================

DAY_MAPPING = {

    "LUNES": "MONDAY",
    "MARTES": "TUESDAY",
    "MIERCOLES": "WEDNESDAY",
    "MIÉRCOLES": "WEDNESDAY",
    "JUEVES": "THURSDAY",
    "VIERNES": "FRIDAY",
    "SABADO": "SATURDAY",
    "SÁBADO": "SATURDAY",
    "DOMINGO": "SUNDAY",

}


# =============================================================
# DATE / TIMESTAMP
# =============================================================

def parse_timestamp(value):

    """
    Convierte:

        DD/MM/YYYY

    o:

        DD/MM/YYYY HH:MM

    a:

        YYYY-MM-DDTHH:MM:SSZ

    """

    if not value:
        return None

    value = value.strip()

    formats = [
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M"
    ]

    for fmt in formats:

        try:

            dt = datetime.strptime(
                value,
                fmt
            )

            dt = dt.replace(
                tzinfo=timezone.utc
            )

            return dt.isoformat().replace(
                "+00:00",
                "Z"
            )

        except ValueError:
            pass

    raise ValueError(
        f"Fecha no válida: '{value}'. "
        f"Usa DD/MM/YYYY o DD/MM/YYYY HH:MM"
    )


# =============================================================
# TIME OF DAY
# =============================================================


def parse_time(value):
    """
    Convierte un horario del CSV a (hora, minuto).

    Acepta:
        8       -> (8, 0)
        8:00    -> (8, 0)
        8:15    -> (8, 15)
        08:30   -> (8, 30)
        23:59   -> (23, 59)
    """

    if value is None:
        return 0, 0

    value = str(value).strip()

    if not value:
        return 0, 0

    if ":" in value:
        parts = value.split(":")

        if len(parts) != 2:
            raise ValueError(
                f"Hora no válida: '{value}'. "
                f"Usa HH o HH:MM."
            )

        hour = int(parts[0])
        minute = int(parts[1])

    else:
        hour = int(value)
        minute = 0

    if not 0 <= hour <= 23:
        raise ValueError(
            f"Hora fuera de rango: '{value}'. "
            f"La hora debe estar entre 0 y 23."
        )

    if not 0 <= minute <= 59:
        raise ValueError(
            f"Minutos fuera de rango: '{value}'. "
            f"Los minutos deben estar entre 0 y 59."
        )

    return hour, minute


# =============================================================
# IMPORTER
# =============================================================

class Importer:

    def __init__(
        self,
        token=None,
        installation_id=None,
        passcode_file="passcodes.csv"
    ):

        self.api = SaltoAPI(
            token=token,
            installation_id=installation_id
        )

        # -----------------------------------------------------
        # UNIT
        #
        # {
        #     "TEST": "installations/.../units/XXXXX"
        # }
        # -----------------------------------------------------

        self.units = {}

        # -----------------------------------------------------
        # PRIVACIDAD FINAL DE CADA UNIT
        # -----------------------------------------------------

        self.unit_privacy = {}

        # -----------------------------------------------------
        # CSV DE PASSCODES
        # -----------------------------------------------------

        self.passcode_file = passcode_file

        # -----------------------------------------------------
        # ACCESS RIGHTS
        #
        # {
        #     ("TEST", "Acceso Mañana"):
        #         "installations/.../access-rights/XXXXX"
        # }
        # -----------------------------------------------------

        self.access_rights = {}

        # -----------------------------------------------------
        # ACCESS POINT GROUPS
        #
        # {
        #     "grupo":
        #         "installations/.../access-point-groups/XXXXX"
        # }
        # -----------------------------------------------------

        self.access_groups = {}

    # =========================================================
    # CSV
    # =========================================================

    @staticmethod
    def read_csv(filename):

        with open(
            filename,
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            return list(
                csv.DictReader(file)
            )

    # =========================================================
    # PASSCODES CSV
    # =========================================================

    def initialize_passcode_csv(self):

        with open(
            self.passcode_file,
            "w",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                "unit",
                "nombre",
                "apellido",
                "email",
                "passcode"
            ])

        logger.info(
            f"Fichero de passcodes creado: {self.passcode_file}"
        )

    def save_passcode(
        self,
        unit,
        first_name,
        last_name,
        email,
        passcode
    ):

        with open(
            self.passcode_file,
            "a",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                unit,
                first_name,
                last_name,
                email,
                passcode
            ])

    # =========================================================
    # GROUPS
    # =========================================================

    def load_access_groups(self):

        print(
            "\n========== ACCESS POINT GROUPS =========="
        )

        print(
            "Obteniendo grupos de puertas..."
        )

        logger.info(
            "Obteniendo grupos de puertas..."
        )

        response = (
            self.api.get_access_point_groups()
        )

        groups = response.get(
            "access_point_groups",
            []
        )

        for group in groups:

            display_name = group.get(
                "display_name"
            )

            resource_name = group.get(
                "name"
            )

            if display_name and resource_name:

                key = (
                    display_name
                    .strip()
                    .lower()
                )

                self.access_groups[key] = (
                    resource_name
                )

                print(
                    f"Grupo encontrado: "
                    f"{display_name} -> "
                    f"{resource_name}"
                )

        print(
            f"Total grupos: "
            f"{len(self.access_groups)}"
        )

        logger.info(
            f"Total grupos: "
            f"{len(self.access_groups)}"
        )

    # =========================================================
    # UNITS
    # =========================================================

    def create_units(self, rows):

        print(
            "\n========== UNITS =========="
        )

        print(
            "Comprobando units existentes..."
        )

        logger.info(
            "Comprobando units existentes..."
        )

        existing_units = self.api.list_units()

        existing_by_display_name = {}

        for unit in existing_units:

            display_name = unit.get(
                "display_name"
            )

            resource_name = unit.get(
                "name"
            )

            if display_name and resource_name:

                existing_by_display_name[
                    display_name.strip().lower()
                ] = {
                    "name": resource_name,
                    "privacy": (
                        unit.get("privacy_settings", {})
                        .get("enabled", False)
                    )
                }

        logger.info(
            f"Units existentes encontradas: {len(existing_by_display_name)}"
        )

        for row in rows:

            name = row[
                "unit_name"
            ].strip()

            privacy = (
                row.get("privacidad", "false")
                .strip()
                .lower()
                == "true"
            )

            self.unit_privacy[name] = privacy

            key = name.lower()

            if key in existing_by_display_name:

                existing = existing_by_display_name[key]
                resource_name = existing["name"]

                print(
                    f"Unit ya existe: {name}"
                )

                print(
                    f"Reutilizando -> {resource_name}"
                )

                logger.info(
                    f"Unit ya existe: {name} -> {resource_name}"
                )

                self.units[name] = resource_name

                if privacy:

                    print(
                        f"Privacidad temporal FALSE: {name}"
                    )

                    logger.info(
                        f"Unit {name}: privacidad temporal FALSE"
                    )

                    self.api.update_unit_privacy(
                        resource_name,
                        name,
                        False
                    )

                continue

            print(
                f"Creando Unit: {name}"
            )

            logger.info(
                f"Creando Unit: {name}"
            )

            response = self.api.create_unit(
                name,
                False
            )

            resource_name = response[
                "name"
            ]

            self.units[name] = resource_name

            print(
                f"OK -> {resource_name}"
            )

            logger.info(
                f"Unit creada: {name} -> {resource_name} "
                f"(privacy temporal FALSE)"
            )

    # =========================================================
    # ACCESS RIGHTS
    # =========================================================

    def create_access_rights(self, rows):

        print(
            "\n========== ACCESS RIGHTS =========="
        )

        for row in rows:

            unit_display_name = row[
                "unit"
            ].strip()

            # -------------------------------------------------
            # COMPROBAR UNIT
            # -------------------------------------------------

            if (
                unit_display_name
                not in self.units
            ):

                raise RuntimeError(
                    f"Unit no encontrada: "
                    f"{unit_display_name}"
                )

            unit_name = self.units[
                unit_display_name
            ]

            access_name = row[
                "nombre_acceso"
            ].strip()

            group_name = row[
                "nombre_grupo_cerraduras"
            ].strip()

            # -------------------------------------------------
            # DAYS
            # -------------------------------------------------

            days = []

            for day in row[
                "dias"
            ].split(";"):

                day = day.strip().upper()

                if day not in DAY_MAPPING:

                    raise RuntimeError(
                        f"Día no válido: {day}"
                    )

                days.append(
                    DAY_MAPPING[day]
                )

            # -------------------------------------------------
            # HOURS
            # -------------------------------------------------

            start_hour, start_minute = parse_time(
                row["horario_in"]
            )

            end_hour, end_minute = parse_time(
                row["horario_out"]
            )

            print(
                f"Creando access right "
                f"'{access_name}' "
                f"en '{unit_display_name}'"
            )

            logger.info(
                f"Creando access right "
                f"'{access_name}' "
                f"en '{unit_display_name}'"
            )

            # -------------------------------------------------
            # CREAR ACCESS RIGHT
            # -------------------------------------------------

            response = (
                self.api.create_access_right(
                    unit_name=unit_name,
                    display_name=access_name,
                    days=days,
                    start_hour=start_hour,
                    start_minute=start_minute,
                    end_hour=end_hour,
                    end_minute=end_minute
                )
            )

            # -------------------------------------------------
            # RESOURCE NAME REAL
            # -------------------------------------------------

            access_right_name = response[
                "name"
            ]

            print(
                f"Access Right -> "
                f"{access_right_name}"
            )

            # -------------------------------------------------
            # BUSCAR GRUPO
            # -------------------------------------------------

            group_key = (
                group_name
                .strip()
                .lower()
            )

            if (
                group_key
                not in self.access_groups
            ):

                raise RuntimeError(
                    f"No existe el grupo "
                    f"de puertas "
                    f"'{group_name}'"
                )

            group_resource = (
                self.access_groups[
                    group_key
                ]
            )

            print(
                f"Asociando grupo -> "
                f"{group_name}"
            )

            # -------------------------------------------------
            # ASOCIAR GRUPO
            # -------------------------------------------------

            self.api.attach_group_to_access_right(
                access_right_name,
                group_resource
            )

            # -------------------------------------------------
            # GUARDAR ACCESS RIGHT
            # -------------------------------------------------

            key = (
                unit_display_name,
                access_name
            )

            self.access_rights[key] = (
                access_right_name
            )

    # =========================================================
    # USERS
    # =========================================================

    def create_users(self, rows):

        print(
            "\n========== USERS =========="
        )

        for row in rows:

            unit_display_name = row[
                "unit"
            ].strip()

            # -------------------------------------------------
            # COMPROBAR UNIT
            # -------------------------------------------------

            if (
                unit_display_name
                not in self.units
            ):

                raise RuntimeError(
                    f"Unit no encontrada: "
                    f"{unit_display_name}"
                )

            # -------------------------------------------------
            # RESOURCE NAME DE LA UNIT
            # -------------------------------------------------

            unit_name = self.units[
                unit_display_name
            ]

            first_name = row[
                "nombre"
            ].strip()

            last_name = row[
                "apellido"
            ].strip()

            email = row[
                "email"
            ].strip()

            role = row[
                "rol"
            ].strip()

            # -------------------------------------------------
            # NUEVOS CAMPOS
            # -------------------------------------------------

            passcode = row.get(
                "passcode",
                ""
            ).strip()

            activate_time = parse_timestamp(
                row.get(
                    "activate_time",
                    ""
                )
            )

            expire_time = parse_timestamp(
                row.get(
                    "expire_time",
                    ""
                )
            )

            print(
                f"\nCreando usuario: "
                f"{first_name} "
                f"{last_name}"
            )

            logger.info(
                f"Creando usuario: "
                f"{first_name} {last_name}"
            )

            # =================================================
            # BUSCAR ACCESS RIGHTS DE ESTA UNIT
            # =================================================

            user_access_rights = []

            for (
                (access_unit, access_name),
                access_right
            ) in self.access_rights.items():

                if (
                    access_unit
                    == unit_display_name
                ):

                    user_access_rights.append(
                        access_right
                    )

            print(
                f"Access Rights para "
                f"{first_name}: "
                f"{len(user_access_rights)}"
            )

            # =================================================
            # CREAR USUARIO
            # =================================================

            response = self.api.create_user(
                unit_name=unit_name,
                given_name=first_name,
                family_name=last_name,
                email=email,
                role=role,
                activate_time=activate_time,
                expire_time=expire_time
            )

            # -------------------------------------------------
            # RESOURCE NAME REAL DEL USUARIO
            # -------------------------------------------------

            user_name = response[
                "name"
            ]

            print(
                f"Usuario creado -> "
                f"{user_name}"
            )

            logger.info(
                f"Usuario creado: "
                f"{first_name} {last_name}"
            )

            # =================================================
            # ASIGNAR ACCESS RIGHTS
            # =================================================

            for access_right in (
                user_access_rights
            ):

                print(
                    f"Asignando access right -> "
                    f"{access_right}"
                )

                self.api.assign_access_right(
                    user_name,
                    access_right
                )

            # =================================================
            # APP KEY
            # =================================================

            app_key = row[
                "app_key"
            ].strip()

            if (
                app_key.upper()
                == "ACTIVE"
            ):

                print(
                    "Asignando App Key..."
                )

                self.api.assign_app_key(
                    user_name
                )

                print(
                    "App Key asignada correctamente"
                )

                logger.info(
                    f"App Key asignada a "
                    f"{first_name} {last_name}"
                )

            # =================================================
            # CARD KEY
            # =================================================

            card_key = row[
                "card_key"
            ].strip()

            if card_key:

                print(
                    f"Asignando Card Key -> "
                    f"{card_key}"
                )

                self.api.assign_card_key(
                    user_name,
                    card_key
                )

                print(
                    "Card Key asignada correctamente"
                )

                logger.info(
                    f"Card Key asignada a "
                    f"{first_name} {last_name}"
                )

            # =================================================
            # PASSCODE
            # =================================================

            if (
                passcode.upper()
                == "ACTIVE"
            ):

                print(
                    "Asignando Passcode..."
                )

                response = self.api.assign_passcode(
                    user_name
                )

                value = response.get(
                    "value"
                )

                print(
                    "Passcode asignado correctamente"
                )

                # -------------------------------------------------
                # IMPORTANTE:
                # El passcode NO se escribe en el log.
                # -------------------------------------------------

                logger.info(
                    f"Passcode asignado a "
                    f"{first_name} {last_name}"
                )

                # El valor sí se muestra por consola
                # para que puedas entregárselo al usuario.
                if value:

                    print(
                        f"Passcode generado: {value}"
                    )

                    self.save_passcode(
                        unit=unit_display_name,
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        passcode=value
                    )

                    logger.info(
                        f"Passcode guardado en {self.passcode_file} "
                        f"para {first_name} {last_name}"
                    )

            # =================================================
            # FIN USUARIO
            # =================================================

            print(
                f"Usuario {first_name} "
                f"{last_name} procesado correctamente."
            )

            logger.info(
                f"Usuario {first_name} "
                f"{last_name} procesado correctamente."
            )

    # =========================================================
    # FINALIZAR PRIVACIDAD
    # =========================================================

    def finalize_unit_privacy(self):

        print(
            "\n========== FINALIZANDO PRIVACIDAD =========="
        )

        logger.info(
            "Aplicando privacidad final de las units..."
        )

        for unit_name, privacy in self.unit_privacy.items():

            if not privacy:

                print(
                    f"{unit_name} -> PRIVACY FALSE"
                )

                logger.info(
                    f"Unit {unit_name}: privacidad final FALSE"
                )

                continue

            resource_name = self.units.get(
                unit_name
            )

            if not resource_name:

                raise RuntimeError(
                    f"No se encuentra el resource name de la unit: {unit_name}"
                )

            print(
                f"Activando privacidad: {unit_name}"
            )

            logger.info(
                f"Activando privacidad: {unit_name}"
            )

            self.api.update_unit_privacy(
                resource_name,
                unit_name,
                True
            )

            print(
                f"OK -> {unit_name} PRIVACY TRUE"
            )

            logger.info(
                f"Unit {unit_name}: privacidad final TRUE"
            )

    # =========================================================
    # UPDATE (actualizar accesos de usuarios ya existentes)
    # =========================================================
    #
    # A diferencia de run(), update_access() NO crea units ni
    # usuarios nuevos. Recibe las filas de un CSV con el MISMO
    # formato que access.csv (unit, nombre_acceso,
    # nombre_grupo_cerraduras, dias, horario_in, horario_out) y,
    # para cada unit mencionada:
    #
    #   1. Se asegura de que existan los access rights del CSV
    #      (reutiliza los que ya existan con el mismo nombre,
    #      crea los que falten).
    #   2. Recorre TODOS los usuarios que ya existen en esa unit.
    #   3. Para cada usuario compara sus accesos actuales con los
    #      del CSV para esa unit:
    #         - add_new=True         -> asigna los accesos del CSV
    #                                    que el usuario todavía no
    #                                    tiene.
    #         - remove_listed=True   -> borra los accesos que el
    #                                    usuario tiene Y que SÍ
    #                                    están en el CSV. Por
    #                                    defecto solo borra la
    #                                    asignación al usuario.
    #         - remove_from_unit=True (junto con remove_listed) ->
    #                                    en vez de borrar solo la
    #                                    asignación al usuario,
    #                                    borra el access right
    #                                    ENTERO a nivel de unit
    #                                    (afecta a TODOS los
    #                                    usuarios que lo tuvieran).
    #         - remove_missing=True  -> borra los accesos que el
    #                                    usuario tiene y que NO
    #                                    están en el CSV (deja al
    #                                    usuario solo con lo del
    #                                    CSV).
    #
    # =========================================================

    def _ensure_units_exist(self, unit_display_names):

        existing_units = self.api.list_units()

        for unit in existing_units:

            display_name = unit.get("display_name")
            resource_name = unit.get("name")

            if display_name and resource_name:

                self.units[
                    display_name.strip().lower()
                ] = resource_name

        missing = [
            name for name in unit_display_names
            if name.lower() not in self.units
        ]

        if missing:

            raise RuntimeError(
                "Las siguientes units no existen en la "
                "instalación y no se pueden actualizar "
                "(usa 'Cargar' primero para crearlas): "
                + ", ".join(missing)
            )

    def _ensure_access_rights_for_unit(
        self,
        unit_display_name,
        unit_name,
        rows
    ):

        """
        Se asegura de que existan (reutilizando o creando) los
        access rights del CSV para una unit concreta.

        Devuelve un dict {nombre_acceso_en_minusculas: resource_name}
        """

        existing = self.api.list_access_rights(unit_name)

        existing_by_name = {
            item["display_name"].strip().lower(): item["name"]
            for item in existing
            if item.get("display_name") and item.get("name")
        }

        result = {}

        for row in rows:

            access_name = row["nombre_acceso"].strip()
            group_name = row["nombre_grupo_cerraduras"].strip()

            key = access_name.lower()

            if key in existing_by_name:

                print(
                    f"Access right ya existe: "
                    f"'{access_name}' en '{unit_display_name}'"
                )

                logger.info(
                    f"Access right ya existe: "
                    f"'{access_name}' en '{unit_display_name}' -> "
                    f"{existing_by_name[key]}"
                )

                result[key] = existing_by_name[key]

                continue

            days = []

            for day in row["dias"].split(";"):

                day = day.strip().upper()

                if day not in DAY_MAPPING:

                    raise RuntimeError(
                        f"Día no válido: {day}"
                    )

                days.append(DAY_MAPPING[day])

            start_hour, start_minute = parse_time(
                row["horario_in"]
            )

            end_hour, end_minute = parse_time(
                row["horario_out"]
            )

            print(
                f"Creando access right nuevo -> "
                f"'{access_name}' en '{unit_display_name}'"
            )

            logger.info(
                f"Creando access right nuevo -> "
                f"'{access_name}' en '{unit_display_name}'"
            )

            response = self.api.create_access_right(
                unit_name=unit_name,
                display_name=access_name,
                days=days,
                start_hour=start_hour,
                start_minute=start_minute,
                end_hour=end_hour,
                end_minute=end_minute
            )

            access_right_name = response["name"]

            group_key = group_name.strip().lower()

            if group_key not in self.access_groups:

                raise RuntimeError(
                    f"No existe el grupo de puertas "
                    f"'{group_name}'"
                )

            self.api.attach_group_to_access_right(
                access_right_name,
                self.access_groups[group_key]
            )

            result[key] = access_right_name

        return result

    def update_access(
        self,
        rows,
        add_new=True,
        remove_listed=False,
        remove_from_unit=False,
        remove_missing=False
    ):

        print(
            "\n========== UPDATE: ACCESOS DE USUARIOS =========="
        )

        logger.warning(
            f"Iniciando UPDATE "
            f"(añadir={add_new}, "
            f"borrar_del_csv={remove_listed}, "
            f"borrar_a_nivel_unit={remove_from_unit}, "
            f"borrar_lo_que_no_esta_en_csv={remove_missing})"
        )

        # -----------------------------------------------------
        # AGRUPAR FILAS POR UNIT
        # -----------------------------------------------------

        rows_by_unit = {}

        for row in rows:

            unit_display_name = row["unit"].strip()

            rows_by_unit.setdefault(
                unit_display_name, []
            ).append(row)

        # -----------------------------------------------------
        # COMPROBAR QUE TODAS LAS UNITS YA EXISTEN
        # -----------------------------------------------------

        self._ensure_units_exist(
            rows_by_unit.keys()
        )

        # -----------------------------------------------------
        # GRUPOS DE PUERTAS (necesarios para crear access
        # rights que falten)
        # -----------------------------------------------------

        self.load_access_groups()

        total_added = 0
        total_removed = 0
        total_removed_unit = 0

        for unit_display_name, unit_rows in rows_by_unit.items():

            unit_name = self.units[
                unit_display_name.lower()
            ]

            print(
                f"\n---- Unit: {unit_display_name} ----"
            )

            logger.info(
                f"Actualizando unit: {unit_display_name}"
            )

            # ---------------------------------------------------
            # 1. ACCESS RIGHTS DESEADOS PARA ESTA UNIT
            # ---------------------------------------------------

            desired = self._ensure_access_rights_for_unit(
                unit_display_name,
                unit_name,
                unit_rows
            )

            # desired: {nombre_en_minusculas: resource_name}

            # ---------------------------------------------------
            # 2. USUARIOS ACTUALES DE LA UNIT
            # ---------------------------------------------------

            users = self.api.list_users(unit_name)

            print(
                f"Usuarios encontrados en "
                f"{unit_display_name}: {len(users)}"
            )

            logger.info(
                f"Usuarios encontrados en "
                f"{unit_display_name}: {len(users)}"
            )

            for user in users:

                user_name = user.get("name")

                display_name = user.get(
                    "display_name",
                    user_name
                )

                if not user_name:
                    continue

                current = self.api.list_user_access_rights(
                    user_name
                )

                current_by_name = {
                    item["display_name"].strip().lower(): item["name"]
                    for item in current
                    if item.get("display_name") and item.get("name")
                }

                print(
                    f"\nUsuario: {display_name}"
                )

                logger.info(
                    f"Procesando usuario: {display_name}"
                )

                # -----------------------------------------------
                # AÑADIR ACCESOS NUEVOS DEL CSV
                # -----------------------------------------------

                if add_new:

                    for key, access_right_name in desired.items():

                        if key in current_by_name:
                            continue

                        print(
                            f"  + Asignando acceso -> {key}"
                        )

                        self.api.assign_access_right(
                            user_name,
                            access_right_name
                        )

                        logger.info(
                            f"Acceso asignado a {display_name}: "
                            f"{key}"
                        )

                        total_added += 1

                # -----------------------------------------------
                # BORRAR (SOLO LA ASIGNACIÓN AL USUARIO) LOS
                # ACCESOS QUE SÍ ESTÁN EN EL CSV. Si además hay
                # que borrar el access right entero a nivel de
                # unit (remove_from_unit), esto es un paso
                # PREVIO obligatorio: la API no deja borrar un
                # access right mientras siga asociado a algún
                # usuario, así que primero hay que desasignarlo
                # de TODOS los usuarios de la unit.
                # -----------------------------------------------

                if remove_listed:

                    for key in desired:

                        association_name = current_by_name.get(key)

                        if not association_name:
                            continue

                        print(
                            f"  - Borrando acceso -> {key}"
                        )

                        self.api.delete_user_access_right(
                            association_name
                        )

                        logger.info(
                            f"Acceso borrado a {display_name}: "
                            f"{key}"
                        )

                        total_removed += 1

                # -----------------------------------------------
                # BORRAR (SOLO AL USUARIO) LOS ACCESOS QUE EL
                # USUARIO TENGA Y QUE NO ESTÉN EN EL CSV
                # -----------------------------------------------

                if remove_missing:

                    for key, association_name in current_by_name.items():

                        if key in desired:
                            continue

                        print(
                            f"  - Borrando acceso -> {key}"
                        )

                        self.api.delete_user_access_right(
                            association_name
                        )

                        logger.info(
                            f"Acceso borrado a {display_name}: "
                            f"{key}"
                        )

                        total_removed += 1

            # ---------------------------------------------------
            # 3. BORRAR A NIVEL DE UNIT LOS ACCESS RIGHTS DEL
            # CSV. Esto los borra ENTERAMENTE (afecta a TODOS
            # los usuarios que los tuvieran, no solo a los del
            # CSV). Se hace DESPUÉS de recorrer a todos los
            # usuarios, porque la API no permite borrar un
            # access right mientras siga asociado a alguien.
            # ---------------------------------------------------

            if remove_listed and remove_from_unit:

                for key, access_right_name in desired.items():

                    print(
                        f"  -- Borrando access right "
                        f"(a nivel de unit) -> {key}"
                    )

                    self.api.delete_access_right(
                        access_right_name
                    )

                    logger.info(
                        f"Access right borrado a nivel de unit "
                        f"en '{unit_display_name}': {key}"
                    )

                    total_removed_unit += 1

        print(
            "\n================================"
        )

        print(
            f"UPDATE FINALIZADO "
            f"(accesos añadidos: {total_added}, "
            f"accesos borrados a usuarios: {total_removed}, "
            f"access rights borrados a nivel de unit: "
            f"{total_removed_unit})"
        )

        print(
            "================================"
        )

        logger.warning(
            f"UPDATE FINALIZADO "
            f"(accesos añadidos: {total_added}, "
            f"accesos borrados a usuarios: {total_removed}, "
            f"access rights borrados a nivel de unit: "
            f"{total_removed_unit})"
        )

    # =========================================================
    # CLEAR UNITS

    # =========================================================

    def clear_units(self):

        print(
            "\n========== CLEAR UNITS =========="
        )

        logger.warning(
            "Iniciando --clear"
        )

        units = self.api.list_units()

        print(
            f"Units encontradas: "
            f"{len(units)}"
        )

        logger.warning(
            f"Units encontradas: "
            f"{len(units)}"
        )

        for unit in units:

            unit_name = unit.get(
                "name"
            )

            display_name = unit.get(
                "display_name",
                unit_name
            )

            if not unit_name:

                logger.error(
                    "Se encontró una unit "
                    "sin campo 'name'. "
                    "Se omite."
                )

                continue

            print(
                f"Borrando Unit: "
                f"{display_name}"
            )

            logger.warning(
                f"Borrando Unit: "
                f"{display_name} "
                f"({unit_name})"
            )

            self.api.delete_unit(
                unit_name
            )

            print(
                f"OK -> {display_name}"
            )

            logger.info(
                f"Unit eliminada: "
                f"{display_name}"
            )

        print(
            "\nCLEAR FINALIZADO"
        )

        logger.warning(
            "CLEAR FINALIZADO"
        )

    # =========================================================
    # RUN
    # =========================================================

    def run(
        self,
        units_path="csv/units.csv",
        access_path="csv/access.csv",
        users_path="csv/users.csv"
    ):

        # -----------------------------------------------------
        # LEER CSV
        # -----------------------------------------------------

        units = self.read_csv(
            units_path
        )

        access = self.read_csv(
            access_path
        )

        users = self.read_csv(
            users_path
        )

        logger.info(
            "CSV cargados correctamente"
        )

        self.initialize_passcode_csv()

        # -----------------------------------------------------
        # 1. CREAR UNITS
        # -----------------------------------------------------

        self.create_units(
            units
        )

        # -----------------------------------------------------
        # 2. OBTENER GRUPOS DE PUERTAS
        # -----------------------------------------------------

        self.load_access_groups()

        # -----------------------------------------------------
        # 3. CREAR ACCESS RIGHTS
        # -----------------------------------------------------

        self.create_access_rights(
            access
        )

        # -----------------------------------------------------
        # 4. CREAR USUARIOS
        # -----------------------------------------------------

        self.create_users(
            users
        )

        # -----------------------------------------------------
        # 5. APLICAR PRIVACIDAD DEFINITIVA
        # -----------------------------------------------------

        self.finalize_unit_privacy()

        # -----------------------------------------------------
        # FIN
        # -----------------------------------------------------

        print(
            "\n================================"
        )

        print(
            "IMPORTACIÓN FINALIZADA"
        )

        print(
            "================================"
        )

        logger.info(
            "IMPORTACIÓN FINALIZADA"
        )