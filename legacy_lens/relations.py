"""Relaciones inferidas por convencion de nombre.

En un esquema sin foreign keys, la unica documentacion que existe es el
nombre de la columna: `id_cliente`, `id_tec`, `cliente_id`. Este modulo
intenta reconstruir ese mapa y separa tres casos:

- declarada: hay FOREIGN KEY de verdad.
- convencion: la columna apunta a una tabla que existe.
- huerfana: apunta a una tabla que no existe (o el nombre no alcanza).
"""

from __future__ import annotations

import re

from .model import Relation, Schema

# Abreviaturas que aparecen en sistemas viejos y no resuelven solas.
ALIAS_POR_DEFECTO: dict[str, str] = {
    "tec": "tecnicos",
    "tecnicos": "tecnicos",
    "usr": "usuarios",
    "user": "usuarios",
    "usu": "usuarios",
    "cli": "clientes",
    "prov": "proveedores",
    "art": "articulos",
    "prod": "productos",
    "dep": "depositos",
    "suc": "sucursales",
    "emp": "empresas",
    "fac": "facturas",
    "ped": "pedidos",
    "ot": "ordenes_trabajo",
    "oc": "ordenes_compra",
    "ven": "vendedores",
    "loc": "localidades",
}

_RE_ID_PREFIJO = re.compile(r"^id[_-]?(?P<ent>.+)$", re.IGNORECASE)
_RE_ID_SUFIJO = re.compile(r"^(?P<ent>.+?)[_-]?id$", re.IGNORECASE)
_RE_ID_SUFIJO2 = re.compile(r"^(?P<ent>.+?)[_-]?(?:id|cod|code|nro|num)$", re.IGNORECASE)


def _variantes(entidad: str) -> list[str]:
    base = entidad.lower().strip()
    variantes = [base]
    if base.endswith("es"):
        variantes.append(base[:-2])
    if base.endswith("s"):
        variantes.append(base[:-1])
    else:
        variantes += [base + "s", base + "es"]
    if base.endswith("y"):
        variantes.append(base[:-1] + "ies")
    return list(dict.fromkeys(variantes))


def _resolver(entidad: str, tablas: set[str], alias: dict[str, str]) -> str | None:
    if entidad in alias and alias[entidad] in tablas:
        return alias[entidad]
    for variante in _variantes(entidad):
        if variante in tablas:
            return variante
        if variante in alias and alias[variante] in tablas:
            return alias[variante]
    return None


def _entidad_de_columna(nombre: str) -> str | None:
    if nombre.lower() == "id":
        return None
    m = _RE_ID_PREFIJO.match(nombre)
    if m and len(m.group("ent")) > 1:
        return m.group("ent")
    m = _RE_ID_SUFIJO.match(nombre)
    if m and len(m.group("ent")) > 1:
        return m.group("ent")
    return None


def inferir_relaciones(
    schema: Schema, alias: dict[str, str] | None = None
) -> list[Relation]:
    tablas = {t.name.lower(): t.name for t in schema.tables}
    mapa_alias = {**ALIAS_POR_DEFECTO, **(alias or {})}
    mapa_alias = {k.lower(): v.lower() for k, v in mapa_alias.items()}
    relaciones: list[Relation] = []
    declaradas = {
        (t.name.lower(), col.lower()) for t in schema.tables for col, _, _ in t.foreign_keys
    }

    for tabla in schema.tables:
        for columna in tabla.columns:
            clave = (tabla.name.lower(), columna.name.lower())
            if clave in declaradas:
                ref = next(
                    (r for c, rt, r in tabla.foreign_keys if c.lower() == columna.name.lower()),
                    None,
                )
                ref_tabla = next(
                    (rt for c, rt, _ in tabla.foreign_keys if c.lower() == columna.name.lower()),
                    None,
                )
                relaciones.append(
                    Relation(tabla.name, columna.name, ref_tabla, "declarada")
                )
                del ref
                continue

            entidad = _entidad_de_columna(columna.name)
            if not entidad:
                continue

            destino = _resolver(entidad.lower(), set(tablas), mapa_alias)
            if destino and destino != tabla.name.lower():
                relaciones.append(
                    Relation(tabla.name, columna.name, tablas[destino], "convencion")
                )
            elif destino is None:
                relaciones.append(Relation(tabla.name, columna.name, None, "huerfana"))

    return relaciones


def resumen(relaciones: list[Relation]) -> dict[str, int]:
    conteo = {"declarada": 0, "convencion": 0, "huerfana": 0}
    for r in relaciones:
        conteo[r.kind] = conteo.get(r.kind, 0) + 1
    return conteo
