"""El indice de dolor de migracion.

Un numero de 0 a 100 y cinco dimensiones. No pretende ser cientifico: pretende
ser comparable entre sistemas y explicable en una reunion. 0 es un proyecto
sano, 100 es "esto no se migra, se reescribe".
"""

from __future__ import annotations

import math

from .model import Action, CodeStats, Dimension, Finding, Relation, Report, Schema, Score

PESOS = {
    "esquema": 0.30,
    "datos": 0.15,
    "codigo": 0.25,
    "seguridad": 0.20,
    "modernidad": 0.10,
}

ACCIONES: dict[str, tuple[str, str, str]] = {
    "sin_fk": (
        "Documentar las relaciones por convencion y decidir el modelo",
        "Sin FK, el ORM nuevo no puede inferir nada: hay que escribir el mapa a mano antes de migrar.",
        "alto",
    ),
    "relacion_convencion": (
        "Escribir el mapa de relaciones por convencion",
        "Cada id_xxx es una relacion no declarada: sin ese mapa, las consultas del sistema nuevo salen mal.",
        "medio",
    ),
    "sin_pk": (
        "Agregar clave primaria a las tablas que no tienen",
        "Sin PK no hay updates seguros ni migraciones idempotentes.",
        "medio",
    ),
    "sql_superglobal": (
        "Sacar el input del usuario del SQL",
        "Es inyeccion directa: cualquier migracion que copie estas consultas hereda el agujero.",
        "alto",
    ),
    "sql_query_sin_prepare": (
        "Pasar las consultas a prepared statements",
        "Se arregla de a una, con tests que cubran el caso real.",
        "medio",
    ),
    "sql_interpolado": (
        "Reemplazar interpolacion por bindings",
        "Mismo trabajo que los prepared statements, pero en las consultas de lectura.",
        "medio",
    ),
    "mysql_extinta": (
        "Reescribir el acceso a datos",
        "mysql_* no existe en PHP 7+: esa capa se escribe de nuevo, no se parchea.",
        "alto",
    ),
    "secret_hardcodeado": (
        "Rotar credenciales y moverlas a variables de entorno",
        "Una credencial que estuvo en el codigo ya esta comprometida, aunque se borre.",
        "medio",
    ),
    "credencial_db": (
        "Rotar el usuario de base y externalizar la configuracion",
        "El password de la base esta en un archivo versionado.",
        "medio",
    ),
    "clave_privada": (
        "Rotar la clave privada y sacarla del historial",
        "Material criptografico versionado: hay que asumirlo expuesto.",
        "alto",
    ),
    "aws_key": (
        "Revocar la access key",
        "Credencial de nube expuesta en el repositorio.",
        "alto",
    ),
    "md5_password": (
        "Rehashear contrasenas con password_hash()",
        "Se migra en el login: hash nuevo la primera vez que entra cada usuario.",
        "medio",
    ),
    "md5_token": (
        "Generar tokens con random_bytes()",
        "md5/uniqid son predecibles: un token de recuperacion adivinable es una cuenta tomada.",
        "bajo",
    ),
    "eval": (
        "Eliminar la ejecucion de codigo dinamico",
        "eval no tiene traduccion a un framework: hay que entender que hace y reescribirlo.",
        "alto",
    ),
    "shell": (
        "Revisar y encapsular los comandos de sistema",
        "Cada exec/system es una puerta de ejecucion remota si toca el request.",
        "alto",
    ),
    "include_variable": (
        "Fijar las rutas de include",
        "Las inclusiones dinamicas esconden dependencias y habilitan LFI.",
        "medio",
    ),
    "file_superglobal": (
        "Validar todo acceso a archivos",
        "El usuario no deberia poder decidir que archivo se lee o se borra.",
        "medio",
    ),
    "echo_superglobal": (
        "Escapar la salida",
        "XSS reflejado: en Blade sale gratis, en PHP hay que ponerlo a mano.",
        "bajo",
    ),
    "each_extinta": (
        "Actualizar sintaxis extinta",
        "Cada each() y mysql_* es un archivo que no arranca en PHP 8.",
        "bajo",
    ),
    "funciones_muertas": (
        "Actualizar funciones eliminadas",
        "Se reemplazan por su equivalente moderno, archivo por archivo.",
        "bajo",
    ),
    "utf8_encode": (
        "Unificar la codificacion en utf8mb4",
        "utf8_encode/decode ya estan deprecadas y generan datos rotos al reimportar.",
        "bajo",
    ),
    "error_reporting_off": (
        "Prender los errores",
        "Migrar con los errores apagados es migrar a ciegas.",
        "bajo",
    ),
    "nombres_raros": (
        "Mapear los nombres hostiles en una capa de acceso",
        "Renombrar en la base rompe reportes y vistas: mejor un mapa explicito.",
        "medio",
    ),
    "fecha_texto": (
        "Normalizar las fechas a DATE/DATETIME",
        "Las fechas en VARCHAR comparan mal y ordenan peor.",
        "medio",
    ),
    "id_como_texto": (
        "Normalizar los identificadores numericos",
        "IDs en VARCHAR hacen joins lentos y rompen el tipado del ORM.",
        "medio",
    ),
    "myisam": (
        "Pasar las tablas a InnoDB",
        "Sin transacciones, una migracion a medias deja la base inconsistente.",
        "medio",
    ),
    "charset_viejo": (
        "Convertir a utf8mb4",
        "Se hace con conversion verificada, no con un ALTER a ciegas.",
        "bajo",
    ),
    "tablas_gemelas": (
        "Definir la tabla fuente de verdad",
        "Nombres casi iguales suelen ser restos de una migracion anterior.",
        "bajo",
    ),
    "tablas_vacias": (
        "Definir si las tablas vacias entran al alcance",
        "Arrastrar tablas muertas agranda el modelo sin agregar valor.",
        "bajo",
    ),
    "enum": (
        "Llevar los catalogos ENUM a tabla o a enum del dominio",
        "Agregar un valor a un ENUM es un ALTER TABLE en produccion.",
        "bajo",
    ),
    "relacion_huerfana": (
        "Limpiar las columnas que apuntan a tablas inexistentes",
        "Datos muertos que confunden a cualquiera que lea el esquema.",
        "bajo",
    ),
}


def _clip(valor: float) -> int:
    return int(max(0, min(100, round(valor))))


def _dim_esquema(schema: Schema, relaciones: list[Relation], hallazgos: list[Finding]) -> Dimension:
    razones: list[str] = []
    if not schema.tables:
        return Dimension("esquema", "Esquema", 0, PESOS["esquema"], ["Sin base para analizar"])

    sin_pk = sum(1 for t in schema.tables if not t.has_primary_key)
    ratio_pk = sin_pk / len(schema.tables)
    puntos = ratio_pk * 40
    if sin_pk:
        razones.append(f"{sin_pk} de {len(schema.tables)} tablas sin PK")

    declaradas = sum(1 for r in relaciones if r.kind == "declarada")
    convencion = sum(1 for r in relaciones if r.kind == "convencion")
    if declaradas == 0:
        puntos += 25
        razones.append("cero foreign keys declaradas")
    if convencion:
        puntos += min(15, convencion * 1.5)
        razones.append(f"{convencion} relaciones solo por nombre de columna")

    por_regla = {h.rule: h.count for h in hallazgos}
    for regla, peso, texto in (
        ("nombres_raros", 10, "nombres hostiles"),
        ("myisam", 8, "tablas MyISAM"),
        ("id_como_texto", 8, "IDs como texto"),
        ("fecha_texto", 6, "fechas como texto"),
        ("charset_viejo", 5, "charset viejo"),
        ("tablas_gemelas", 4, "tablas gemelas"),
    ):
        if por_regla.get(regla):
            puntos += peso
            razones.append(f"{texto}: {por_regla[regla]}")

    return Dimension("esquema", "Esquema", _clip(puntos), PESOS["esquema"], razones)


def _dim_datos(schema: Schema) -> Dimension:
    razones: list[str] = []
    if not schema.tables:
        return Dimension("datos", "Datos", 0, PESOS["datos"], ["Sin datos para analizar"])
    if schema.rows == 0:
        return Dimension(
            "datos",
            "Datos",
            15,
            PESOS["datos"],
            ["Sin conteos de filas (dump sin datos): el volumen no se pudo medir"],
        )

    puntos = min(60.0, 10 * math.log10(max(schema.rows, 1)))
    razones.append(f"{schema.rows:,} filas en total".replace(",", "."))
    mayor = max(schema.tables, key=lambda t: t.rows)
    if schema.rows:
        share = mayor.rows / schema.rows
        puntos += share * 20
        if share > 0.5:
            razones.append(f"{mayor.name} concentra {share:.0%} de las filas")
    if mayor.rows >= 1_000_000:
        puntos += 20
        razones.append(f"{mayor.name} supera el millon de filas")
    return Dimension("datos", "Datos", _clip(puntos), PESOS["datos"], razones)


def _dim_codigo(code: CodeStats, hallazgos: list[Finding]) -> Dimension:
    razones: list[str] = []
    if code.files == 0:
        return Dimension("codigo", "Codigo", 0, PESOS["codigo"], ["Sin codigo para analizar"])

    peso_sev = {"alta": 3.0, "media": 2.0, "baja": 1.0}
    peso = 0.0
    for h in hallazgos:
        if h.category != "codigo":
            continue
        peso += peso_sev.get(h.severity, 1.0) * math.sqrt(min(h.count, 100))
    factor_hallazgos = min(1.0, peso / 30)
    ratio_sql = code.with_sql / code.files
    factor_tamano = min(1.0, math.log10(max(code.loc, 1)) / 5)

    puntos = 100 * (0.45 * factor_hallazgos + 0.25 * ratio_sql + 0.30 * factor_tamano)
    if ratio_sql:
        razones.append(f"{code.with_sql} de {code.files} archivos tocan SQL")
    if code.loc:
        razones.append(f"{code.loc:,} lineas de PHP".replace(",", "."))
    return Dimension("codigo", "Codigo", _clip(puntos), PESOS["codigo"], razones)


def _dim_seguridad(hallazgos: list[Finding]) -> Dimension:
    altas = sum(h.count for h in hallazgos if h.category == "seguridad" and h.severity == "alta")
    medias = sum(h.count for h in hallazgos if h.category == "seguridad" and h.severity == "media")
    bajas = sum(h.count for h in hallazgos if h.category == "seguridad" and h.severity == "baja")
    puntos = 20 * math.log2(1 + altas) + 8 * math.log2(1 + medias) + 3 * math.log2(1 + bajas)
    razones = []
    if altas:
        razones.append(f"{altas} hallazgos de severidad alta")
    if medias:
        razones.append(f"{medias} de severidad media")
    if not altas and not medias:
        razones.append("sin hallazgos criticos detectados")
    return Dimension("seguridad", "Seguridad", _clip(puntos), PESOS["seguridad"], razones)


def _dim_modernidad(code: CodeStats) -> Dimension:
    puntos = 0
    razones: list[str] = []
    if code.files == 0:
        return Dimension("modernidad", "Modernidad", 0, PESOS["modernidad"], [])
    if not code.has_composer:
        puntos += 35
        razones.append("sin composer.json")
    if not code.has_namespaces:
        puntos += 25
        razones.append("sin namespaces")
    if not code.has_tests:
        puntos += 25
        razones.append("sin tests")
    if code.loc > 5000 and not code.has_composer:
        puntos += 15
        razones.append("proyecto grande sin gestor de dependencias")
    return Dimension("modernidad", "Modernidad", _clip(puntos), PESOS["modernidad"], razones)


def calcular_score(report: Report) -> Score:
    hallazgos_esquema = [h for h in report.findings if h.category == "esquema"]
    dimensiones = [
        _dim_esquema(report.schema, report.relations, hallazgos_esquema),
        _dim_datos(report.schema),
        _dim_codigo(report.code, report.findings),
        _dim_seguridad(report.findings),
        _dim_modernidad(report.code),
    ]
    total = sum(d.value * d.weight for d in dimensiones)
    if total <= 25:
        etiqueta = "Sano"
    elif total <= 50:
        etiqueta = "Moderado"
    elif total <= 75:
        etiqueta = "Doloroso"
    else:
        etiqueta = "Critico"
    return Score(total=_clip(total), label=etiqueta, dimensions=dimensiones)


def plan_de_accion(report: Report, maximo: int = 8) -> list[Action]:
    orden = {"alta": 0, "media": 1, "baja": 2}
    hallazgos = sorted(report.findings, key=lambda h: (orden.get(h.severity, 9), -h.count))
    acciones: list[Action] = []
    vistos: set[str] = set()
    for h in hallazgos:
        if h.rule in vistos:
            continue
        plantilla = ACCIONES.get(h.rule)
        if not plantilla:
            continue
        titulo, porque, esfuerzo = plantilla
        acciones.append(
            Action(
                priority=len(acciones) + 1,
                title=titulo,
                why=f"{porque} ({h.count} caso{'s' if h.count != 1 else ''})",
                effort=esfuerzo,
            )
        )
        vistos.add(h.rule)
        if len(acciones) >= maximo:
            break
    return acciones
