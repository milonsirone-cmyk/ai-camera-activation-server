from flask import Flask, request, jsonify
import calendar
import hashlib
import os
import secrets
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
TOKEN = os.environ.get("ACTIVATION_ADMIN_TOKEN", "CHANGE_THIS")


def db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor,
        sslmode="require"
    )


def h(key):
    return hashlib.sha256(
        key.strip().upper().encode("utf-8")
    ).hexdigest()


def add_months(dt, months):
    m = dt.month - 1 + int(months)
    year = dt.year + m // 12
    month = m % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def make_key():
    value = secrets.token_hex(12).upper()
    return "ACS3-" + "-".join(
        value[i:i + 6] for i in range(0, 24, 6)
    )


@app.get("/health")
def health():
    try:
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

        return jsonify(ok=True)

    except Exception:
        app.logger.exception("Database health check failed")
        return jsonify(
            ok=False,
            message="Database unavailable."
        ), 503


@app.post("/activate")
def activate():
    data = request.get_json(silent=True) or {}

    key = str(data.get("key", "")).strip().upper()
    product = str(
        data.get("product", "AI-CAMERA-STUDIO")
    )
    machine_id = str(
        data.get("machine_id", "")
    )

    if not key or not machine_id:
        return jsonify(
            ok=False,
            message="Missing activation key or machine information."
        ), 400

    try:
        with db() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT *
                    FROM licenses
                    WHERE key_hash=%s
                      AND product=%s
                      AND active=true
                    FOR UPDATE
                    """,
                    (h(key), product)
                )

                row = cur.fetchone()

                if not row:
                    return jsonify(
                        ok=False,
                        message="Invalid or disabled activation key."
                    ), 403

                now = datetime.now(timezone.utc)

                existing_machine = row.get("machine_id")

                if (
                    existing_machine
                    and existing_machine != machine_id
                ):
                    return jsonify(
                        ok=False,
                        message="This key is already activated on another PC."
                    ), 409

                expires_at = row.get("expires_at")

                if expires_at:

                    if expires_at <= now:
                        return jsonify(
                            ok=False,
                            message="This activation key has expired."
                        ), 403

                else:

                    expires_at = add_months(
                        now,
                        row["months"]
                    )

                    cur.execute(
                        """
                        UPDATE licenses
                        SET expires_at=%s,
                            machine_id=%s,
                            activated_at=%s
                        WHERE id=%s
                        """,
                        (
                            expires_at,
                            machine_id,
                            now,
                            row["id"]
                        )
                    )

                activated_at = (
                    row.get("activated_at")
                    or now
                )

                return jsonify(
                    ok=True,
                    license_id=row["id"],
                    expires_at=expires_at.isoformat().replace(
                        "+00:00", "Z"
                    ),
                    activated_at=activated_at.isoformat().replace(
                        "+00:00", "Z"
                    )
                )

    except Exception:
        app.logger.exception(
            "Activation request failed"
        )

        return jsonify(
            ok=False,
            message="Activation server database error."
        ), 500


@app.post("/validate")
def validate():

    data = request.get_json(silent=True) or {}

    license_id = data.get("license_id")

    machine_id = str(
        data.get("machine_id", "")
    )

    if not license_id or not machine_id:
        return jsonify(
            ok=False,
            message="Missing license or machine information."
        ), 400

    try:

        with db() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT *
                    FROM licenses
                    WHERE id=%s
                      AND active=true
                    """,
                    (int(license_id),)
                )

                row = cur.fetchone()

                if not row:
                    return jsonify(
                        ok=False,
                        message="License is invalid or disabled."
                    ), 403

                if (
                    row.get("machine_id")
                    and row["machine_id"] != machine_id
                ):
                    return jsonify(
                        ok=False,
                        message="This activation belongs to another PC."
                    ), 409

                expires_at = row.get("expires_at")

                if not expires_at:
                    return jsonify(
                        ok=False,
                        message="License has not been activated."
                    ), 409

                if expires_at <= datetime.now(timezone.utc):
                    return jsonify(
                        ok=False,
                        message="Activation has expired."
                    ), 403

                return jsonify(
                    ok=True,
                    license_id=row["id"],
                    expires_at=expires_at.isoformat().replace(
                        "+00:00", "Z"
                    )
                )

    except Exception:
        app.logger.exception(
            "Validation request failed"
        )

        return jsonify(
            ok=False,
            message="Activation server database error."
        ), 500


@app.post("/admin/create")
def create():

    if request.headers.get(
        "X-Admin-Token"
    ) != TOKEN:

        return jsonify(
            ok=False,
            message="Unauthorized."
        ), 401

    data = request.get_json(silent=True) or {}

    try:
        months = int(
            data.get("months", 3)
        )

    except (TypeError, ValueError):

        return jsonify(
            ok=False,
            message="Months must be 3, 6, or 12."
        ), 400

    if months not in (3, 6, 12):

        return jsonify(
            ok=False,
            message="Allowed terms: 3, 6, 12 months."
        ), 400

    product = str(
        data.get(
            "product",
            "AI-CAMERA-STUDIO"
        )
    )

    key = make_key()

    try:

        with db() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO licenses
                    (
                        key_hash,
                        product,
                        months,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        h(key),
                        product,
                        months,
                        datetime.now(timezone.utc)
                    )
                )

                cur.fetchone()

        return jsonify(
            ok=True,
            key=key,
            months=months
        )

    except Exception:
        app.logger.exception(
            "Key creation failed"
        )

        return jsonify(
            ok=False,
            message="Could not create license key."
        ), 500


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                8000
            )
        )
    )
