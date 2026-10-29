"""Lector de esquemas MySQL a partir de un dump .sql.

No hace falta una base viva para analizar el esquema: alcanza con el
`mysqldump --no-data`. El parser es deliberadamente tolerante, porque los
dumps legacy tienen de todo: comentarios de mysqldump, tablas sin backticks,
`IF NOT EXISTS`, engines viejos y columnas con nombres imposibles.
"""

from __future__ import annotations

import re

from .model import Column, Schema, Table

_RE_COMENTARIO_LINEA = re.compile(r"^\s*(--|#).*$", re.MULTILINE)
_RE_COMENTARIO_BLOQUE = re.compile(r"/\*.*?\*/", re.DOTALL)
_RE_CREATE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?P<name>`[^`]+`|\"[^\"]+\"|[A-Za-z0-9_$.]+)\s*\(",
    re.IGNORECASE,
)
_RE_ENGINE = re.compile(r"ENGINE\s*=\s*(\w+)", re.IGNORECASE)
_RE_CHARSET = re.compile(r"(?:DEFAULT\s+)?CHARSET\s*=\s*(\w+)", re.IGNORECASE)
_RE_FK = re.compile(
    r"FOREIGN\s+KEY\s*\(\s*(?P<col>`[^`]+`|[A-Za-z0-9_]+)\s*\)\s*"
    r"REFERENCES\s+(?P<tabla>`[^`]+`|[A-Za-z0-9_]+)\s*"
    r"\(\s*(?P<refcol>`[^`]+`|[A-Za-z0-9_]+)\s*\)",
    re.IGNORECASE,
)
_RE_PK = re.compile(r"PRIMARY\s+KEY\s*\((?P<cols>[^)]*)\)", re.IGNORECASE)


def _limpiar(sql: str) -> str:
    sql = _RE_COMENTARIO_BLOQUE.sub(" ", sql)
    sql = _RE_COMENTARIO_LINEA.sub("", sql)
    return sql


def _identificador(nombre: str) -> str:
    return nombre.strip().strip("`\"").strip()


def _dividir_definiciones(cuerpo: str) -> list[str]:
    """Separa por comas de primer nivel, respetando parentesis y comillas."""
    partes: list[str] = []
    actual: list[str] = []
    profundidad = 0
    comilla = ""
    for ch in cuerpo:
        if comilla:
            actual.append(ch)
            if ch == comilla:
                comilla = ""
            continue
        if ch in "'\"`":
            comilla = ch
            actual.append(ch)
            continue
        if ch == "(":
            profundidad += 1
        elif ch == ")":
            profundidad -= 1
        if ch == "," and profundidad == 0:
            partes.append("".join(actual).strip())
            actual = []
            continue
        actual.append(ch)
    if actual:
        partes.append("".join(actual).strip())
    return [p for p in partes if p]


def _parsear_columna(definicion: str) -> Column | None:
    texto = definicion.strip()
    if not texto:
        return None

    # Nombre: con backticks o identificador simple.
    if texto.startswith("`"):
        fin = texto.find("`", 1)
        if fin == -1:
            return None
        nombre = texto[1:fin]
        resto = texto[fin + 1:].strip()
    else:
        partes = texto.split(None, 1)
        if len(partes) < 2:
            return None
        nombre, resto = partes[0], partes[1].strip()

    # Tipo: primera palabra + parentesis opcional.
    m = re.match(r"([A-Za-z]+(?:\s+[A-Za-z]+)?)\s*(\([^)]*\))?", resto)
    if not m:
        return None
    tipo = m.group(1).lower()
    if m.group(2):
        tipo += m.group(2).replace(" ", "")

    nullable = not re.search(r"\bNOT\s+NULL\b", resto, re.IGNORECASE)
    default = None
    md = re.search(r"\bDEFAULT\s+('(?:[^'\\]|\\.)*'|[A-Za-z0-9_.+-]+|NULL)", resto, re.IGNORECASE)
    if md:
        default = md.group(1)
    extra = ""
    if re.search(r"AUTO_INCREMENT", resto, re.IGNORECASE):
        extra = "auto_increment"
    return Column(name=nombre, type=tipo, nullable=nullable, default=default, extra=extra)


def parsear_dump(sql: str, source: str = "dump.sql") -> Schema:
    """Extrae tablas, columnas, PKs y FKs de un dump MySQL."""
    texto = _limpiar(sql)
    schema = Schema(source=source)

    for match in _RE_CREATE.finditer(texto):
        nombre_tabla = _identificador(match.group("name"))
        inicio = match.end()  # justo despues del parentesis de apertura

        profundidad = 1
        i = inicio
        comilla = ""
        while i < len(texto) and profundidad > 0:
            ch = texto[i]
            if comilla:
                if ch == comilla and texto[i - 1] != "\\":
                    comilla = ""
            elif ch in "'\"`":
                comilla = ch
            elif ch == "(":
                profundidad += 1
            elif ch == ")":
                profundidad -= 1
            i += 1

        cuerpo = texto[inicio:i - 1]
        cola = texto[i:i + 400]
        tabla = Table(name=nombre_tabla)

        motor = _RE_ENGINE.search(cola)
        if motor:
            tabla.engine = motor.group(1)
        charset = _RE_CHARSET.search(cola)
        if charset:
            tabla.charset = charset.group(1)

        for definicion in _dividir_definiciones(cuerpo):
            mayus = definicion.upper()
            if mayus.startswith("PRIMARY KEY"):
                pk = _RE_PK.search(definicion)
                if pk:
                    tabla.primary_key = [
                        _identificador(c) for c in pk.group("cols").split(",") if c.strip()
                    ]
                continue
            if mayus.startswith(("KEY ", "UNIQUE KEY", "INDEX ", "FULLTEXT", "CONSTRAINT")):
                fk = _RE_FK.search(definicion)
                if fk:
                    tabla.foreign_keys.append(
                        (
                            _identificador(fk.group("col")),
                            _identificador(fk.group("tabla")),
                            _identificador(fk.group("refcol")),
                        )
                    )
                continue
            columna = _parsear_columna(definicion)
            if columna:
                tabla.columns.append(columna)

        # La PK se declara despues de las columnas: se marca al final.
        for nombre_pk in tabla.primary_key:
            columna = tabla.column(nombre_pk)
            if columna:
                columna.key = "PRI"

        schema.tables.append(tabla)

    return schema


def leer_dump(path: str) -> Schema:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return parsear_dump(fh.read(), source=path)
