import argparse

from importer import Importer


def main():

    parser = argparse.ArgumentParser(
        description="Importador SALTO Nebula"
    )

    parser.add_argument(
        "--clear",
        action="store_true",
        help="Borra todas las units de la instalación"
    )

    parser.add_argument(
        "--update",
        metavar="ACCESS_CSV",
        help=(
            "Actualiza los accesos de los usuarios ya existentes "
            "de las units mencionadas en ACCESS_CSV (mismo formato "
            "que access.csv)"
        )
    )

    parser.add_argument(
        "--no-add",
        action="store_true",
        help="En --update, no añadir los accesos nuevos del CSV"
    )

    parser.add_argument(
        "--remove-listed",
        action="store_true",
        help=(
            "En --update, borrar los accesos que el usuario "
            "tenga y que estén indicados en el CSV (por "
            "defecto solo se borra la asignación al usuario; "
            "combínalo con --remove-from-unit para borrar el "
            "access right entero)"
        )
    )

    parser.add_argument(
        "--remove-from-unit",
        action="store_true",
        help=(
            "Junto con --remove-listed: en vez de borrar solo "
            "la asignación al usuario, borra el access right "
            "entero a nivel de unit (afecta a TODOS los "
            "usuarios que lo tuvieran, no solo a los del CSV)"
        )
    )

    parser.add_argument(
        "--remove-missing",
        action="store_true",
        help=(
            "En --update, borrar los accesos que el usuario "
            "tenga y que NO estén en el CSV (deja al usuario "
            "solo con los accesos del CSV)"
        )
    )

    args = parser.parse_args()

    try:

        importer = Importer()

        if args.clear:

            importer.clear_units()
            return

        if args.update:

            rows = importer.read_csv(args.update)

            importer.update_access(
                rows,
                add_new=not args.no_add,
                remove_listed=args.remove_listed,
                remove_from_unit=args.remove_from_unit,
                remove_missing=args.remove_missing
            )

            return

        importer.run()

    except Exception as e:

        print("\nERROR:")
        print(e)

        raise


if __name__ == "__main__":
    main()