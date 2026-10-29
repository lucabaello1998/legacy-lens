import json
from pathlib import Path

import pytest

from legacy_lens.cli import main

EJEMPLO = Path(__file__).resolve().parent.parent / "examples" / "tienda-legacy"
APP = EJEMPLO / "app"
DUMP = EJEMPLO / "schema.sql"


def test_scan_genera_informes(tmp_path):
    codigo = main(
        [
            "scan",
            "--path",
            str(APP),
            "--dump",
            str(DUMP),
            "--out",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert codigo == 0
    assert (tmp_path / "report.html").exists()
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.md").exists()


def test_scan_detecta_el_desastre_del_ejemplo(tmp_path):
    main(["scan", "--path", str(APP), "--dump", str(DUMP), "--out", str(tmp_path), "--quiet"])
    datos = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    reglas = {f["rule"] for f in datos["findings"]}
    assert "mysql_extinta" in reglas
    assert "secret_hardcodeado" in reglas
    assert "sin_fk" in reglas
    assert datos["score"]["total"] >= 50


def test_fail_over_devuelve_codigo_2(tmp_path):
    assert (
        main(
            [
                "scan",
                "--path",
                str(APP),
                "--dump",
                str(DUMP),
                "--out",
                str(tmp_path),
                "--quiet",
                "--fail-over",
                "1",
            ]
        )
        == 2
    )


def test_fail_over_alto_no_falla(tmp_path):
    assert (
        main(
            [
                "scan",
                "--path",
                str(APP),
                "--dump",
                str(DUMP),
                "--out",
                str(tmp_path),
                "--quiet",
                "--fail-over",
                "100",
            ]
        )
        == 0
    )


def test_rules_lista_reglas(capsys):
    assert main(["rules"]) == 0
    salida = capsys.readouterr().out
    assert "mysql_extinta" in salida
    assert "sql_superglobal" in salida


def test_version(capsys):
    assert main(["version"]) == 0
    assert "legacy-lens" in capsys.readouterr().out


def test_sin_objetivo_falla():
    with pytest.raises(SystemExit):
        main(["scan"])


def test_path_inexistente_falla():
    with pytest.raises(SystemExit):
        main(["scan", "--path", "no-existe-esta-ruta", "--out", "x"])


def test_formato_json_solo(tmp_path):
    main(
        [
            "scan",
            "--path",
            str(APP),
            "--dump",
            str(DUMP),
            "--out",
            str(tmp_path),
            "--quiet",
            "--format",
            "json",
        ]
    )
    assert (tmp_path / "report.json").exists()
    assert not (tmp_path / "report.html").exists()
