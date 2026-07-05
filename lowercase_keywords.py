"""Lowercase fixed Armenian keywords in addr_texts.region / street.

Usage:
    uv run python lowercase_keywords.py [ID ...]
    uv run python lowercase_keywords.py --all

If no arguments are passed, defaults to id=1574.
"""

import os
import sys

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

REGION_REPLACEMENTS = {"Մարզ": "մարզ"}
STREET_REPLACEMENTS = {
    "Փողոց": "փողոց",
    "Պողոտա": "պողոտա",
    "Նրբանցք": "նրբանցք",
    "Խճուղի": "խճուղի",
    "Թաղամաս": "թաղամաս",
}


def apply_replacements(value, replacements):
    if value is None:
        return None
    new_value = value
    for src, dst in replacements.items():
        new_value = new_value.replace(src, dst)
    return new_value


def get_conn():
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ.get("DB_PASSWORD") or None,
        row_factory=dict_row,
    )


def process(ids):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, region, street FROM addr_texts WHERE id = ANY(%s)",
            (list(ids),),
        )
        rows = cur.fetchall()

        found_ids = {r["id"] for r in rows}
        missing = [i for i in ids if i not in found_ids]
        for i in missing:
            print(f"id={i}: not found")

        for row in rows:
            new_region = apply_replacements(row["region"], REGION_REPLACEMENTS)
            new_street = apply_replacements(row["street"], STREET_REPLACEMENTS)
            if new_region == row["region"] and new_street == row["street"]:
                print(f"id={row['id']}: no changes")
                continue
            cur.execute(
                "UPDATE addr_texts SET region = %s, street = %s WHERE id = %s",
                (new_region, new_street, row["id"]),
            )
            print(
                f"id={row['id']}: "
                f"region {row['region']!r} -> {new_region!r}, "
                f"street {row['street']!r} -> {new_street!r}"
            )


def process_all():
    region_expr = "region"
    for src, dst in REGION_REPLACEMENTS.items():
        region_expr = f"REPLACE({region_expr}, %s, %s)"
    street_expr = "street"
    for src, dst in STREET_REPLACEMENTS.items():
        street_expr = f"REPLACE({street_expr}, %s, %s)"

    region_params = [v for pair in REGION_REPLACEMENTS.items() for v in pair]
    street_params = [v for pair in STREET_REPLACEMENTS.items() for v in pair]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE addr_texts SET region = {region_expr} "
            f"WHERE region IS DISTINCT FROM {region_expr}",
            [*region_params, *region_params],
        )
        region_updated = cur.rowcount
        cur.execute(
            f"UPDATE addr_texts SET street = {street_expr} "
            f"WHERE street IS DISTINCT FROM {street_expr}",
            [*street_params, *street_params],
        )
        street_updated = cur.rowcount
        print(f"region updated: {region_updated}")
        print(f"street updated: {street_updated}")


def main(argv):
    load_dotenv()
    if len(argv) > 1 and argv[1] == "--all":
        process_all()
        return
    if len(argv) > 1:
        ids = [int(a) for a in argv[1:]]
    else:
        ids = [1574]
    process(ids)


if __name__ == "__main__":
    main(sys.argv)
