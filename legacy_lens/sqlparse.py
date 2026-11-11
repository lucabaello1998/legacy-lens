"""Lector de esquemas MySQL a partir de un dump .sql.

No hace falta una base viva para analizar el esquema: alcanza con el
`mysqldump --no-data`. El parser es deliberadamente tolerante, porque los
dumps legacy tienen de todo: comentarios de mysqldump, tablas sin backticks,
`IF NOT EXISTS`, engines viejos y columnas con nombres imposibles.
"""

from __future__ import annotations

import re
from pathlib import Path

from .model import Column, Schema, Table

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
    """Saca comentarios de MySQL respetando los literales y los saltos de línea.

    Con una regex se borraba `/* ... */` también adentro de un string
    (``DEFAULT 'a/*b'``) y se perdían tablas enteras sin aviso. Los saltos se
    conservan para que las posiciones sigan siendo las del archivo.
    """
    salida: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        caracter = sql[i]

        if caracter in "'\"":
            j = i + 1
            while j < n:
                if sql[j] == "\\":
                    j += 2
                    continue
                if sql[j] == caracter:
                    j += 1
                    break
                j += 1
            salida.append(sql[i:j])
            i = j
            continue

        if caracter == "/" and i + 1 < n and sql[i + 1] == "*":
            fin = sql.find("*/", i + 2)
            fin = n if fin < 0 else fin + 2
            salida.append("\n" * sql.count("\n", i, fin))
            i = fin
            continue

        # `-- ` (con espacio, como pide MySQL) y `#`.
        if (
            caracter == "-" and sql.startswith("--", i) and i + 2 < n and sql[i + 2] in " \t\r\n"
        ) or (caracter == "#"):
            fin = sql.find("\n", i)
            fin = n if fin < 0 else fin
            salida.append("\n" * sql.count("\n", i, fin))
            i = fin
            continue

        salida.append(caracter)
        i += 1
    return "".join(salida)


def _identificador(nombre: str) -> str:
    # `PRIMARY KEY (`code`(10))` trae el prefijo de índice pegado: se descarta.
    limpio = re.sub(r"\([^)]*\)", "", nombre)
    return limpio.strip().strip('`"').strip()


def _dividir_definiciones(cuerpo: str) -> list[str]:
    """Separa por comas de primer nivel, respetando paréntesis y comillas escapadas."""
    partes: list[str] = []
    actual: list[str] = []
    profundidad = 0
    comilla = ""
    i = 0
    while i < len(cuerpo):
        ch = cuerpo[i]
        if comilla:
            actual.append(ch)
            if ch == "\\" and i + 1 < len(cuerpo):
                # `\'` no cierra el literal: se copia el siguiente caracter tal cual.
                actual.append(cuerpo[i + 1])
                i += 2
                continue
            if ch == comilla:
                comilla = ""
            i += 1
            continue
        if ch in "'\"`":
            comilla = ch
            actual.append(ch)
            i += 1
            continue
        if ch == "(":
            profundidad += 1
        elif ch == ")":
            profundidad -= 1
        if ch == "," and profundidad == 0:
            partes.append("".join(actual).strip())
            actual = []
            i += 1
            continue
        actual.append(ch)
        i += 1
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
        resto = texto[fin + 1 :].strip()
    else:
        partes = texto.split(None, 1)
        if len(partes) < 2:
            return None
        nombre, resto = partes[0], partes[1].strip()

    # Tipo: solo la primera palabra y su paréntesis. Antes se tomaban dos palabras
    # cuando no había paréntesis y `text NOT NULL` quedaba como tipo "text not"
    # (y ninguna regla lo reconocía como texto).
    m = re.match(r"([A-Za-z]+)\s*(\([^)]*\))?", resto)
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


def _columnas_pk(definicion: str) -> list[str]:
    """Columnas de la PK, respetando el `(10)` de prefijo y las comillas.

    Con `PRIMARY KEY (`code`(10))` una regex corta en el primer `)` y deja
    `code`(10` como nombre de columna: la PK parece incompleta.
    """
    m = re.search(r"PRIMARY\s+KEY\s*\(", definicion, re.IGNORECASE)
    if not m:
        return []

    inicio = m.end()
    profundidad = 1
    i = inicio
    comilla = ""
    while i < len(definicion) and profundidad > 0:
        ch = definicion[i]
        if comilla:
            if ch == comilla:
                comilla = ""
        elif ch in "'\"`":
            comilla = ch
        elif ch == "(":
            profundidad += 1
        elif ch == ")":
            profundidad -= 1
        i += 1

    cuerpo = definicion[inicio : i - 1]
    return [_identificador(c) for c in cuerpo.split(",") if c.strip()]


def _clausulas_de_tabla(definicion: str) -> bool:
    """True si la definición es una cláusula de tabla y no una columna.

    `CONSTRAINT pk PRIMARY KEY (...)` parece una columna llamada CONSTRAINT si no
    se mira con cuidado, y eso generaba un "sin PK" falso.
    """
    mayus = definicion.strip().upper()
    if mayus.startswith(
        ("PRIMARY KEY", "FOREIGN KEY", "KEY ", "UNIQUE KEY", "INDEX ", "FULLTEXT", "SPATIAL")
    ):
        return True
    if mayus.startswith("CONSTRAINT"):
        return "PRIMARY KEY" in mayus or "FOREIGN KEY" in mayus or "UNIQUE" in mayus
    return False


def parsear_dump(sql: str, source: str = "dump.sql") -> Schema:
    """Extrae tablas, columnas, PKs y FKs de un dump MySQL."""
    texto = _limpiar(sql)
    schema = Schema(source=source)

    for match in _RE_CREATE.finditer(texto):
        nombre_tabla = _identificador(match.group("name"))
        inicio = match.end()  # justo después del paréntesis de apertura

        profundidad = 1
        i = inicio
        comilla = ""
        while i < len(texto) and profundidad > 0:
            ch = texto[i]
            if comilla:
                if ch == "\\":
                    i += 2
                    continue
                if ch == comilla:
                    comilla = ""
            elif ch in "'\"`":
                comilla = ch
            elif ch == "(":
                profundidad += 1
            elif ch == ")":
                profundidad -= 1
            i += 1

        cuerpo = texto[inicio : i - 1]

        # Las opciones de la tabla terminan en el `;` o en el próximo CREATE: la
        # ventana fija hacía que una tabla sin ENGINE heredara el de la siguiente.
        fin_cola = len(texto)
        for corte in (";", "CREATE "):
            encontrado = texto.find(corte, i)
            if encontrado != -1:
                fin_cola = min(fin_cola, encontrado)
        cola = texto[i:fin_cola]

        tabla = Table(name=nombre_tabla)

        motor = _RE_ENGINE.search(cola)
        if motor:
            tabla.engine = motor.group(1)
        charset = _RE_CHARSET.search(cola)
        if charset:
            tabla.charset = charset.group(1)

        for definicion in _dividir_definiciones(cuerpo):
            if _clausulas_de_tabla(definicion):
                columnas_pk = _columnas_pk(definicion)
                if columnas_pk:
                    tabla.primary_key = columnas_pk
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

        # La PK se declara después de las columnas: se marca al final.
        for nombre_pk in tabla.primary_key:
            columna = tabla.column(nombre_pk)
            if columna:
                columna.key = "PRI"

        schema.tables.append(tabla)

    return schema


def _decodificar(datos: bytes) -> str:
    """Decodifica el dump según el BOM.

    En Windows, `>` de PowerShell 5.1 guarda UTF-16: leerlo como UTF-8 daba un
    esquema con cero tablas y ningún error.
    """
    if datos.startswith((b"\xff\xfe", b"\xfe\xff")):
        return datos.decode("utf-16", "replace")
    if datos.startswith(b"\xef\xbb\xbf"):
        return datos[3:].decode("utf-8", "replace")
    return datos.decode("utf-8", "replace")


def leer_dump(path: str) -> Schema:
    datos = Path(path).read_bytes()
    return parsear_dump(_decodificar(datos), source=path)
