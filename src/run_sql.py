import sys
from pathlib import Path

import duckdb
import pandas as pd

import config

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)


def prepare(text: str) -> str:
    return (
        text.replace("{PROCESSED}", config.PROCESSED_DIR.as_posix())
            .replace("{INTERIM}", config.INTERIM_DIR.as_posix())
    )


def statements(text: str):
    for chunk in prepare(text).split(";"):
        if chunk.strip():
            yield chunk


def title_of(chunk: str) -> str:
    for line in chunk.splitlines():
        if line.strip().startswith("--"):
            return line.strip().lstrip("-").strip()
    return ""


def body_of(chunk: str) -> str:
    lines = [l for l in chunk.splitlines() if not l.strip().startswith("--")]
    return "\n".join(lines).strip()


def main() -> None:
    views = config.ROOT / "sql" / "01_views.sql"
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else config.ROOT / "sql" / "02_checks.sql"

    con = duckdb.connect()                       # in memory, nothing is saved
    for chunk in statements(views.read_text()):
        body = body_of(chunk)
        if body:
            con.execute(body)

    if target.resolve() == views.resolve():
        print("Views created.")
        return

    for chunk in statements(target.read_text()):
        body = body_of(chunk)
        if not body:
            continue
        if body.upper().startswith("CREATE"):    # new
            con.execute(body)                    # new
            continue
        print(f"\n{title_of(chunk)}")
        print(con.execute(body).fetchdf().to_string(index=False))


if __name__ == "__main__":
    main()