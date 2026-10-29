"""Introspeccion de una base MySQL/MariaDB viva.

Es opcional: sin driver (pymysql) o sin base, legacy-lens trabaja igual con un
dump .sql. Cuando hay base, ademas de la estructura se obtienen motores,
charsets, tamanos y conteos reales de filas.
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from .model import Column, Schema, Table


class ErrorConexion(RuntimeError):
    pass


def _parsear_dsn(dsn: str) -> dict:
    if not dsn.startswith("mysql"):
        raise ErrorConexion("El DSN tiene que empezar con mysql://")
    partes = urlparse(dsn)
    if not partes.hostname or not partes.path.strip("/"):
        raise ErrorConexion("DSN incompleto: mysql://usuario:clave@host:puerto/base")
    return {
        "host": partes.hostname,
        "port": partes.port or 3306,
        "user": unquote(partes.username or ""),
        "password": unquote(partes.password or ""),
        "database": partes.path.strip("/"),
    }


def _driver():
    try:
        import pymysql  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ErrorConexion(
            "Falta el driver de MySQL. Instalar con: pip install 'legacy-lens[mysql]'"
        ) from exc
    return pymysql


def leer_mysql(dsn: str, contar_filas: bool = True, timeout: int = 10) -> Schema:
    """Devuelve el esquema real, con conteos exactos si se piden."""
    datos = _parsear_dsn(dsn)
    pymysql = _driver()
    try:
        conexion = pymysql.connect(
            host=datos["host"],
            port=datos["port"],
            user=datos["user"],
            password=datos["password"],
            database=datos["database"],
            connect_timeout=timeout,
            read_timeout=timeout,
            charset="utf8mb4",
        )
    except Exception as exc:  # pragma: no cover - red
        raise ErrorConexion(f"No se pudo conectar a MySQL: {exc}") from exc

    schema = Schema(source=f"mysql://{datos['host']}/{datos['database']}")
    base = datos["database"]
    with conexion:
        with conexion.cursor() as cur:
            cur.execute(
                """
                SELECT TABLE_NAME, ENGINE, TABLE_COLLATION, TABLE_ROWS,
                       COALESCE(DATA_LENGTH, 0) + COALESCE(INDEX_LENGTH, 0)
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
                """,
                (base,),
            )
            for nombre, motor, collation, filas, tamano in cur.fetchall():
                tabla = Table(name=nombre, engine=motor or "", rows=int(filas or 0))
                tabla.size_bytes = int(tamano or 0)
                if collation:
                    tabla.charset = collation.split("_")[0]
                schema.tables.append(tabla)

            cur.execute(
                """
                SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
                       COLUMN_KEY, COLUMN_DEFAULT, EXTRA
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s
                ORDER BY TABLE_NAME, ORDINAL_POSITION
                """,
                (base,),
            )
            por_tabla = {t.name: t for t in schema.tables}
            for tabla, col, tipo, nullable, key, default, extra in cur.fetchall():
                t = por_tabla.get(tabla)
                if not t:
                    continue
                t.columns.append(
                    Column(
                        name=col,
                        type=tipo,
                        nullable=(nullable == "YES"),
                        key=key or "",
                        default=default,
                        extra=extra or "",
                    )
                )
                if key == "PRI":
                    t.primary_key.append(col)

            cur.execute(
                """
                SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL
                """,
                (base,),
            )
            for tabla, col, ref_tabla, ref_col in cur.fetchall():
                t = por_tabla.get(tabla)
                if t:
                    t.foreign_keys.append((col, ref_tabla, ref_col))

            if contar_filas:
                for t in schema.tables:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM `{t.name.replace('`', '``')}`")
                        t.rows = int(cur.fetchone()[0])
                        t.rows_estimated = False
                    except Exception:  # pragma: no cover - permisos/tabla rota
                        t.rows_estimated = True

    return schema


def leer_dsn_o_dump(dsn: str | None, dump: str | None) -> Schema | None:
    if dsn:
        return leer_mysql(dsn)
    if dump:
        from .sqlparse import leer_dump

        return leer_dump(dump)
    return None


_RE_DSN = re.compile(r"^mysql(\+\w+)?://")
