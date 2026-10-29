"""Modelo de datos del informe.

Todo lo que produce el analisis se guarda en estructuras serializables, para
poder emitir JSON, HTML y Markdown desde el mismo objeto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

SEVERIDADES = ("alta", "media", "baja")


@dataclass
class Column:
    name: str
    type: str
    nullable: bool = True
    key: str = ""
    default: str | None = None
    extra: str = ""

    @property
    def base_type(self) -> str:
        return self.type.split("(")[0].strip().lower()

    @property
    def is_numeric(self) -> bool:
        return self.base_type in {
            "int", "bigint", "smallint", "tinyint", "mediumint",
            "decimal", "float", "double", "numeric",
        }

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "nullable": self.nullable,
            "key": self.key,
            "default": self.default,
            "extra": self.extra,
        }


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    engine: str = ""
    charset: str = ""
    rows: int = 0
    rows_estimated: bool = True
    size_bytes: int = 0
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def has_primary_key(self) -> bool:
        return bool(self.primary_key)

    def column(self, name: str) -> Column | None:
        for c in self.columns:
            if c.name.lower() == name.lower():
                return c
        return None

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "columns": [c.as_dict() for c in self.columns],
            "engine": self.engine,
            "charset": self.charset,
            "rows": self.rows,
            "rows_estimated": self.rows_estimated,
            "size_bytes": self.size_bytes,
            "primary_key": self.primary_key,
            "foreign_keys": [
                {"column": c, "ref_table": t, "ref_column": r} for c, t, r in self.foreign_keys
            ],
        }


@dataclass
class Schema:
    tables: list[Table] = field(default_factory=list)
    source: str = ""

    def table(self, name: str) -> Table | None:
        for t in self.tables:
            if t.name.lower() == name.lower():
                return t
        return None

    @property
    def rows(self) -> int:
        return sum(t.rows for t in self.tables)

    @property
    def size_bytes(self) -> int:
        return sum(t.size_bytes for t in self.tables)

    @property
    def columns(self) -> int:
        return sum(len(t.columns) for t in self.tables)


@dataclass
class Occurrence:
    file: str
    line: int
    snippet: str = ""

    def as_dict(self) -> dict:
        return {"file": self.file, "line": self.line, "snippet": self.snippet}


@dataclass
class Finding:
    """Un hallazgo agregado por regla (no por ocurrencia)."""

    rule: str
    title: str
    severity: str
    category: str  # codigo | seguridad | esquema
    detail: str = ""
    occurrences: list[Occurrence] = field(default_factory=list)
    affected_files: int = 0
    total: int = 0  # ocurrencias reales (puede superar las guardadas)

    @property
    def count(self) -> int:
        return self.total or len(self.occurrences)

    def as_dict(self) -> dict:
        return {
            "rule": self.rule,
            "title": self.title,
            "severity": self.severity,
            "category": self.category,
            "detail": self.detail,
            "count": self.count,
            "affected_files": self.affected_files,
            "occurrences": [o.as_dict() for o in self.occurrences],
        }


@dataclass
class CodeStats:
    files: int = 0
    loc: int = 0
    bytes: int = 0
    with_sql: int = 0
    with_sessions: int = 0
    largest: list[tuple[str, int]] = field(default_factory=list)
    has_composer: bool = False
    has_namespaces: bool = False
    has_tests: bool = False

    def as_dict(self) -> dict:
        return {
            "files": self.files,
            "loc": self.loc,
            "bytes": self.bytes,
            "with_sql": self.with_sql,
            "with_sessions": self.with_sessions,
            "largest": [{"file": f, "loc": n} for f, n in self.largest],
            "has_composer": self.has_composer,
            "has_namespaces": self.has_namespaces,
            "has_tests": self.has_tests,
        }


@dataclass
class Relation:
    """Relacion inferida por convencion de nombre (sin FK declarada)."""

    table: str
    column: str
    target: str | None
    kind: str  # declarada | convencion | huerfana

    def as_dict(self) -> dict:
        return {
            "table": self.table,
            "column": self.column,
            "target": self.target,
            "kind": self.kind,
        }


@dataclass
class Dimension:
    key: str
    label: str
    value: int  # 0 = sano, 100 = critico
    weight: float
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "weight": self.weight,
            "reasons": self.reasons,
        }


@dataclass
class Score:
    total: int
    label: str
    dimensions: list[Dimension] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "label": self.label,
            "dimensions": [d.as_dict() for d in self.dimensions],
        }


@dataclass
class Action:
    priority: int
    title: str
    why: str
    effort: str  # bajo | medio | alto

    def as_dict(self) -> dict:
        return {
            "priority": self.priority,
            "title": self.title,
            "why": self.why,
            "effort": self.effort,
        }


@dataclass
class Report:
    title: str
    target_path: str
    schema: Schema
    code: CodeStats
    findings: list[Finding] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    score: Score | None = None
    actions: list[Action] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def by_category(self, category: str) -> list[Finding]:
        return [f for f in self.findings if f.category == category]

    def as_dict(self) -> dict:
        return {
            "tool": {"name": "legacy-lens", "version": "1.0.0"},
            "generated_at": self.generated_at.isoformat(timespec="seconds"),
            "title": self.title,
            "target": {
                "path": self.target_path,
                "schema_source": self.schema.source,
                "tables": len(self.schema.tables),
                "columns": self.schema.columns,
                "rows": self.schema.rows,
                "size_bytes": self.schema.size_bytes,
            },
            "score": self.score.as_dict() if self.score else None,
            "code": self.code.as_dict(),
            "schema": {
                "tables": [t.as_dict() for t in self.schema.tables],
            },
            "relations": [r.as_dict() for r in self.relations],
            "findings": [f.as_dict() for f in self.findings],
            "actions": [a.as_dict() for a in self.actions],
        }
