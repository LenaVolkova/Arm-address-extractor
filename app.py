import os
from urllib.parse import urlencode

import psycopg
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from psycopg.rows import dict_row

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev")

PAGE_SIZE = 50

EDITABLE_FIELDS = (
    "addr_num",
    "region",
    "cityname",
    "citytype",
    "district",
    "street",
    "bldnum",
    "bldlist",
)
CITYTYPE_CHOICES = ("", "քաղաք", "գյուղ")


def get_conn():
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ.get("DB_PASSWORD") or None,
        row_factory=dict_row,
    )


def normalize(value):
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def get_neighbors(row_id):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT prev_id, next_id FROM ("
            "  SELECT id, "
            "    LAG(id) OVER (ORDER BY key NULLS LAST, id) AS prev_id, "
            "    LEAD(id) OVER (ORDER BY key NULLS LAST, id) AS next_id "
            "  FROM addr_texts"
            ") sub WHERE id = %s",
            (row_id,),
        )
        result = cur.fetchone()
    return result or {"prev_id": None, "next_id": None}


def get_lookups(cityname):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT region FROM osmaddr "
            "WHERE region IS NOT NULL AND region <> '' ORDER BY region"
        )
        regions = [r["region"] for r in cur.fetchall()]

        cur.execute(
            "SELECT DISTINCT city FROM osmaddr "
            "WHERE city IS NOT NULL AND city <> '' ORDER BY city"
        )
        cities = [r["city"] for r in cur.fetchall()]

        cur.execute(
            "SELECT DISTINCT district FROM osmaddr "
            "WHERE district IS NOT NULL AND district <> '' ORDER BY district"
        )
        districts = [r["district"] for r in cur.fetchall()]

        cur.execute(
            "SELECT street, BOOL_OR(COALESCE(city, '') = %s) AS in_city "
            "FROM osmaddr "
            "WHERE street IS NOT NULL AND street <> '' "
            "GROUP BY street "
            "ORDER BY in_city DESC, street",
            (cityname or "",),
        )
        streets = [r["street"] for r in cur.fetchall()]

    return {
        "regions": regions,
        "cities": cities,
        "districts": districts,
        "streets": streets,
    }


@app.route("/")
def index():
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    q = (request.args.get("q") or "").strip()

    where_sql = ""
    params: list = []
    if q:
        try:
            where_sql = "WHERE id = %s"
            params = [int(q)]
        except ValueError:
            where_sql = "WHERE FALSE"
            params = []

    offset = (page - 1) * PAGE_SIZE

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS c FROM addr_texts {where_sql}", params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"SELECT * FROM addr_texts {where_sql} "
            "ORDER BY key NULLS LAST, id LIMIT %s OFFSET %s",
            [*params, PAGE_SIZE, offset],
        )
        rows = cur.fetchall()

    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)

    def page_url(p):
        args = {"page": p}
        if q:
            args["q"] = q
        return url_for("index") + "?" + urlencode(args)

    return render_template(
        "index.html",
        rows=rows,
        page=page,
        total_pages=total_pages,
        total=total,
        q=q,
        page_url=page_url,
    )


@app.route("/delete/<int:row_id>", methods=["POST"])
def delete(row_id):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM addr_texts WHERE id = %s", (row_id,))
        deleted = cur.rowcount

    if deleted:
        flash(f"Row id={row_id} deleted.", "success")
    else:
        flash(f"Row id={row_id} not found.", "error")

    page = request.form.get("page") or request.args.get("page") or "1"
    q = request.form.get("q") or request.args.get("q") or ""
    args = {"page": page}
    if q:
        args["q"] = q
    return redirect(url_for("index") + "?" + urlencode(args))


@app.route("/edit/<int:row_id>", methods=["GET", "POST"])
def edit(row_id):
    return_page = (
        request.form.get("return_page") or request.args.get("page") or "1"
    )
    return_q = request.form.get("return_q") or request.args.get("q") or ""

    if request.method == "POST":
        action = request.form.get("action")
        values = {f: normalize(request.form.get(f)) for f in EDITABLE_FIELDS}

        if values["citytype"] not in CITYTYPE_CHOICES and values["citytype"] is not None:
            abort(400, description="Invalid citytype value")

        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM addr_texts WHERE id = %s", (row_id,))
            current = cur.fetchone()
            if current is None:
                abort(404)

            target_id = row_id
            if action in ("save", "save_prev", "save_next"):
                set_sql = ", ".join(f"{f} = %s" for f in EDITABLE_FIELDS)
                cur.execute(
                    f"UPDATE addr_texts SET {set_sql} WHERE id = %s",
                    [*[values[f] for f in EDITABLE_FIELDS], row_id],
                )
                flash(f"Row id={row_id} updated.", "success")
                if action in ("save_prev", "save_next"):
                    neighbors = get_neighbors(row_id)
                    candidate = neighbors[
                        "prev_id" if action == "save_prev" else "next_id"
                    ]
                    if candidate is not None:
                        target_id = candidate
            elif action == "save_as_new":
                cols = ("text", *EDITABLE_FIELDS, "key")
                placeholders = ", ".join(["%s"] * len(cols))
                params = [
                    current["text"],
                    *[values[f] for f in EDITABLE_FIELDS],
                    current["key"],
                ]
                cur.execute(
                    f"INSERT INTO addr_texts ({', '.join(cols)}) "
                    f"VALUES ({placeholders}) RETURNING id",
                    params,
                )
                target_id = cur.fetchone()["id"]
                flash(
                    f"New row id={target_id} created (original id={row_id} unchanged).",
                    "success",
                )
            else:
                abort(400, description="Unknown action")

        args = {"page": return_page}
        if return_q:
            args["q"] = return_q
        return redirect(url_for("edit", row_id=target_id) + "?" + urlencode(args))

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM addr_texts WHERE id = %s", (row_id,))
        row = cur.fetchone()
    if row is None:
        abort(404)

    lookups = get_lookups(row["cityname"])
    neighbors = get_neighbors(row_id)

    close_args = {"page": return_page}
    if return_q:
        close_args["q"] = return_q
    close_url = url_for("index") + "?" + urlencode(close_args)

    return render_template(
        "edit.html",
        row=row,
        citytype_choices=CITYTYPE_CHOICES,
        lookups=lookups,
        return_page=return_page,
        return_q=return_q,
        close_url=close_url,
        prev_id=neighbors["prev_id"],
        next_id=neighbors["next_id"],
    )
