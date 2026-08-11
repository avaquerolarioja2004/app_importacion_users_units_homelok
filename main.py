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

    args = parser.parse_args()

    try:

        importer = Importer()

        if args.clear:

            importer.clear_units()
            return

        importer.run()

    except Exception as e:

        print("\nERROR:")
        print(e)

        raise


if __name__ == "__main__":
    main()