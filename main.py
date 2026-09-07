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
        "--no-remove",
        action="store_true",
        help=(
            "En --update, no borrar los accesos que el usuario "
            "tenga y ya no estén en el CSV"
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
                remove_missing=not args.no_remove
            )

            return

        importer.run()

    except Exception as e:

        print("\nERROR:")
        print(e)

        raise


if __name__ == "__main__":
    main()