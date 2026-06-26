import argparse
import sys
import webbrowser
from pathlib import Path

from ..repository import WikiRepo
from . import server as dash_server


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="wiseman-dash")
    parser.add_argument("--db", required=True, help="Path to the project's wiki.db")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true",
                        help="Do not open a browser window")
    args = parser.parse_args(argv)

    db_path = Path(args.db).expanduser()
    if not db_path.exists():
        parser.error(f"db not found: {db_path} (run /summon-wiseman first)")

    repo = WikiRepo(str(db_path))
    try:
        httpd = dash_server.serve(repo, host=args.host, port=args.port)
    except OSError as exc:
        print(f"wiseman-dash: cannot bind {args.host}:{args.port}: {exc}",
              file=sys.stderr)
        print("try a different --port", file=sys.stderr)
        raise SystemExit(1)

    url = f"http://{args.host}:{args.port}/"
    print(f"wiseman-dash serving {db_path} at {url}  (Ctrl-C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nwiseman-dash: shutting down")
        httpd.shutdown()


if __name__ == "__main__":
    main()
