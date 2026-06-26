import argparse

from . import db, server


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="wiseman-mcp")
    parser.add_argument("--db", required=True, help="Path to the project's wiki.db")
    args = parser.parse_args(argv)
    db.ensure_db(args.db).close()
    server.build_server(args.db).run()


if __name__ == "__main__":
    main()
