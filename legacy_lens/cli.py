"""Interfaz de linea de comandos."""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .codescan import REGLAS, escanear_codigo
from .dbscan import ErrorConexion, leer_dsn_o_dump
from .model import CodeStats, Report, Schema
from .relations import inferir_relaciones
from .report import escribir
from .schemacheck import revisar_esquema
from .score import calcular_score, plan_de_accion


def _parsear_alias(texto: str | None) -> dict[str, str]:
    if not texto:
        return {}
    alias: dict[str, str] = {}
    for par in texto.split(","):
        if "=" in par:
            clave, valor = par.split("=", 1)
            alias[clave.strip().lower()] = valor.strip().lower()
    return alias


def _barra(valor: int, ancho: int = 20) -> str:
    lleno = int(round(valor / 100 * ancho))
    return "#" * lleno + "." * (ancho - lleno)


def _analizar(args: argparse.Namespace) -> Report:
    if not args.path and not args.dump and not args.dsn:
        raise SystemExit("Nada para analizar: pasa --path, --dump o --dsn")

    schema = leer_dsn_o_dump(args.dsn, args.dump)
    code_stats = CodeStats()
    hallazgos_codigo = []
    if args.path:
        if not os.path.isdir(args.path):
            raise SystemExit(f"No existe el directorio: {args.path}")
        code_stats, hallazgos_codigo = escanear_codigo(args.path)

    schema_obj = schema or Schema()
    relaciones = inferir_relaciones(schema_obj, _parsear_alias(args.alias))
    hallazgos_esquema = revisar_esquema(schema_obj, relaciones)

    report = Report(
        title=args.title
        or os.path.basename(os.path.abspath(args.path or args.dump or args.dsn or ".")),
        target_path=args.path or "",
        schema=schema_obj,
        code=code_stats,
        findings=hallazgos_esquema + hallazgos_codigo,
        relations=relaciones,
    )
    orden = {"alta": 0, "media": 1, "baja": 2}
    report.findings.sort(key=lambda f: (orden.get(f.severity, 9), -f.count))
    report.score = calcular_score(report)
    report.actions = plan_de_accion(report)
    return report


def _imprimir_resumen(report: Report, salidas: list[str]) -> None:
    s = report.schema
    print(f"legacy-lens {__version__}")
    print(f"  objetivo : {report.target_path or '-'}")
    print(f"  esquema  : {s.source or '-'} -> {len(s.tables)} tablas, {s.columns} columnas")
    if report.code.files:
        print(f"  codigo   : {report.code.files} archivos PHP, {report.code.loc} lineas")

    if report.score:
        print("")
        print(f"indice de dolor: {report.score.total}/100 ({report.score.label})")
        for d in report.score.dimensions:
            print(f"  {d.label:<12} {d.value:>3}  {_barra(d.value)}")

    altos = [f for f in report.findings if f.severity == "alta"]
    if altos:
        print("")
        print("hallazgos altos:")
        for f in altos[:6]:
            print(f"  - {f.title} ({f.count})")

    if report.actions:
        print("")
        print("plan sugerido:")
        for a in report.actions[:5]:
            print(f"  {a.priority}. {a.title} [{a.effort}]")

    print("")
    for salida in salidas:
        print(f"informe: {salida}")


def cmd_scan(args: argparse.Namespace) -> int:
    report = _analizar(args)
    formatos = tuple(f.strip() for f in args.format.split(",") if f.strip())
    salidas = escribir(report, args.out, formatos)
    if not args.quiet:
        _imprimir_resumen(report, salidas)
    if args.fail_over is not None and report.score and report.score.total >= args.fail_over:
        if not args.quiet:
            print(
                f"\nFalla el umbral: {report.score.total} >= {args.fail_over}",
                file=sys.stderr,
            )
        return 2
    return 0


def cmd_rules(_: argparse.Namespace) -> int:
    print(f"{len(REGLAS)} reglas de codigo\n")
    for regla in REGLAS:
        print(f"  [{regla.severity:<5}] {regla.id:<22} {regla.title}")
    print("\nReglas de esquema: ver legacy_lens/schemacheck.py")
    return 0


def cmd_version(_: argparse.Namespace) -> int:
    print(f"legacy-lens {__version__}")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legacy-lens",
        description=(
            "Radiografia de un sistema legacy PHP/MySQL: esquema, codigo, "
            "secretos y dolor de migracion."
        ),
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    scan = sub.add_parser("scan", help="analiza un proyecto y genera el informe")
    scan.add_argument("--path", help="directorio con el codigo PHP")
    scan.add_argument("--dump", help="archivo .sql con el esquema (mysqldump --no-data)")
    scan.add_argument("--dsn", help="mysql://usuario:clave@host:3306/base")
    scan.add_argument(
        "--out", default="legacy-lens-out", help="directorio de salida (default: legacy-lens-out)"
    )
    scan.add_argument("--title", help="titulo del informe")
    scan.add_argument("--format", default="html,json,md", help="html,json,md")
    scan.add_argument("--alias", help="alias de tablas: tec=tecnicos,cli=clientes")
    scan.add_argument(
        "--fail-over", type=int, help="sale con codigo 2 si el indice llega a este valor"
    )
    scan.add_argument("--quiet", action="store_true", help="no imprime el resumen")
    scan.set_defaults(func=cmd_scan)

    rules = sub.add_parser("rules", help="lista las reglas de codigo")
    rules.set_defaults(func=cmd_rules)

    version = sub.add_parser("version", help="muestra la version")
    version.set_defaults(func=cmd_version)

    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = construir_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ErrorConexion as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
