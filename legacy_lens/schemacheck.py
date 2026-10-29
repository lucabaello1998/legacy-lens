"""Patologias de esquema.

No mira el codigo: mira la base. Cada regla responde a algo que se paga caro
al migrar, porque el framework nuevo espera un modelo explicito y este no lo
tiene.
"""

from __future__ import annotations

import re

from .model import Finding, Occurrence, Relation, Schema

PALABRAS_RESERVADAS = {
    "order", "group", "key", "index", "table", "select", "where", "from", "by",
    "desc", "asc", "status", "date", "time", "user", "password", "check",
}
_RE_NOMBRE_RARO = re.compile(r"[ .'\"\-#@/\\]|^[0-9]|[A-Z]")
_RE_FECHA = re.compile(r"^(?:fec|fecha|date|dt)", re.IGNORECASE)


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            actual.append(min(previa[j] + 1, actual[j - 1] + 1, previa[j - 1] + (ca != cb)))
        previa = actual
    return previa[-1]


def _hallazgo(rule: str, title: str, severity: str, detail: str) -> Finding:
    return Finding(rule=rule, title=title, severity=severity, category="esquema", detail=detail)


def _ocurrencias(tabla: str, items: list[str], limite: int = 25) -> list[Occurrence]:
    return [Occurrence(file=tabla, line=0, snippet=s) for s in items[:limite]]


def revisar_esquema(schema: Schema, relaciones: list[Relation]) -> list[Finding]:
    hallazgos: list[Finding] = []
    if not schema.tables:
        return hallazgos

    sin_pk = [t.name for t in schema.tables if not t.has_primary_key]
    if sin_pk:
        f = _hallazgo(
            "sin_pk",
            "Tablas sin clave primaria",
            "alta" if len(sin_pk) > len(schema.tables) / 2 else "media",
            "Sin PK no hay forma segura de actualizar una fila ni de idempotear una migracion.",
        )
        f.occurrences = _ocurrencias("esquema", sin_pk)
        f.total = len(sin_pk)
        f.affected_files = len(sin_pk)
        hallazgos.append(f)

    declaradas = sum(1 for r in relaciones if r.kind == "declarada")
    convencion = [r for r in relaciones if r.kind == "convencion"]
    huerfanas = [r for r in relaciones if r.kind == "huerfana"]

    if declaradas == 0:
        f = _hallazgo(
            "sin_fk",
            "Esquema sin claves foraneas",
            "alta",
            "La integridad se sostiene solo en el codigo: cualquier consulta puede dejar huerfanos.",
        )
        f.occurrences = _ocurrencias("esquema", ["0 FOREIGN KEY declaradas en toda la base"])
        f.total = 1
        hallazgos.append(f)

    if convencion:
        f = _hallazgo(
            "relacion_convencion",
            "Relaciones por convencion de nombre",
            "media",
            "Columnas tipo id_cliente que apuntan a otra tabla sin FK: hay que documentarlas antes de migrar.",
        )
        f.occurrences = _ocurrencias(
            "esquema", [f"{r.table}.{r.column} -> {r.target}" for r in convencion]
        )
        f.total = len(convencion)
        f.affected_files = len({r.table for r in convencion})
        hallazgos.append(f)

    if huerfanas:
        f = _hallazgo(
            "relacion_huerfana",
            "Columnas que apuntan a tablas inexistentes",
            "media",
            "El nombre promete una relacion que no existe: datos muertos o tablas que se borraron.",
        )
        f.occurrences = _ocurrencias(
            "esquema", [f"{r.table}.{r.column} (sin tabla destino)" for r in huerfanas]
        )
        f.total = len(huerfanas)
        f.affected_files = len({r.table for r in huerfanas})
        hallazgos.append(f)

    id_texto = [
        f"{t.name}.{c.name} ({c.type})"
        for t in schema.tables
        for c in t.columns
        if re.match(r"^(?:id_|.*_id$)", c.name, re.IGNORECASE) and c.base_type in {"varchar", "char", "text", "tinytext"}
    ]
    if id_texto:
        f = _hallazgo(
            "id_como_texto",
            "Identificadores guardados como texto",
            "media",
            "Los IDs en VARCHAR no comparan igual que un INT: joins lentos y orden lexicografico.",
        )
        f.occurrences = _ocurrencias("esquema", id_texto)
        f.total = len(id_texto)
        hallazgos.append(f)

    myisam = [t.name for t in schema.tables if t.engine.lower() == "myisam"]
    if myisam:
        f = _hallazgo(
            "myisam",
            "Tablas MyISAM (sin transacciones)",
            "media",
            "MyISAM no soporta transacciones ni FK: migrar sin atomicidad es una ruleta.",
        )
        f.occurrences = _ocurrencias("esquema", myisam)
        f.total = len(myisam)
        hallazgos.append(f)

    charset = [
        f"{t.name} ({t.charset})"
        for t in schema.tables
        if t.charset and t.charset.lower() not in {"utf8mb4", "utf8mb4_unicode_ci", "utf8mb4_general_ci"}
    ]
    if charset:
        f = _hallazgo(
            "charset_viejo",
            "Charset distinto de utf8mb4",
            "baja",
            "latin1/utf8 de 3 bytes rompe emojis y acentos al pasar a un framework moderno.",
        )
        f.occurrences = _ocurrencias("esquema", charset)
        f.total = len(charset)
        hallazgos.append(f)

    raros = []
    for t in schema.tables:
        if _RE_NOMBRE_RARO.search(t.name) or t.name.lower() in PALABRAS_RESERVADAS:
            raros.append(f"tabla `{t.name}`")
        for c in t.columns:
            if _RE_NOMBRE_RARO.search(c.name) or c.name.lower() in PALABRAS_RESERVADAS:
                raros.append(f"{t.name}.`{c.name}`")
    if raros:
        f = _hallazgo(
            "nombres_raros",
            "Nombres de tabla o columna hostiles",
            "media",
            "Espacios, puntos, mayusculas o palabras reservadas obligan a escapar todo el tiempo.",
        )
        f.occurrences = _ocurrencias("esquema", raros)
        f.total = len(raros)
        hallazgos.append(f)

    fechas = [
        f"{t.name}.{c.name} ({c.type})"
        for t in schema.tables
        for c in t.columns
        if _RE_FECHA.match(c.name) and c.base_type in {"varchar", "char", "text"}
    ]
    if fechas:
        f = _hallazgo(
            "fecha_texto",
            "Fechas guardadas como texto",
            "media",
            "Comparar y ordenar fechas en VARCHAR devuelve resultados incorrectos.",
        )
        f.occurrences = _ocurrencias("esquema", fechas)
        f.total = len(fechas)
        hallazgos.append(f)

    enums = [
        f"{t.name}.{c.name} ({c.type})"
        for t in schema.tables
        for c in t.columns
        if c.base_type == "enum"
    ]
    if enums:
        f = _hallazgo(
            "enum",
            "Columnas ENUM",
            "baja",
            "Un ENUM es un catalogo escondido en el DDL: agregar un valor es un ALTER TABLE.",
        )
        f.occurrences = _ocurrencias("esquema", enums)
        f.total = len(enums)
        hallazgos.append(f)

    gemelas = []
    nombres = [t.name.lower() for t in schema.tables]
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            if a == b or min(len(a), len(b)) < 5:
                continue
            if _levenshtein(a, b) <= 2:
                gemelas.append(f"{a} ~ {b}")
    if gemelas:
        f = _hallazgo(
            "tablas_gemelas",
            "Tablas con nombres casi iguales",
            "baja",
            "Suelen ser copias o restos de una migracion anterior: confirmar cual esta viva.",
        )
        f.occurrences = _ocurrencias("esquema", gemelas)
        f.total = len(gemelas)
        hallazgos.append(f)

    vacias = [t.name for t in schema.tables if t.rows == 0 and not t.rows_estimated]
    if vacias:
        f = _hallazgo(
            "tablas_vacias",
            "Tablas sin filas",
            "baja",
            "Candidatas a no migrar: verificar antes de arrastrarlas al modelo nuevo.",
        )
        f.occurrences = _ocurrencias("esquema", vacias)
        f.total = len(vacias)
        hallazgos.append(f)

    orden = {"alta": 0, "media": 1, "baja": 2}
    hallazgos.sort(key=lambda f: (orden.get(f.severity, 9), -f.count))
    return hallazgos
