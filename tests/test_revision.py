"""Regresiones del gauntlet: el informe se publica, así que nada de lo que entra
por el código analizado (ni las contraseñas) puede salir tal cual."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from legacy_lens import __version__
from legacy_lens.cli import main
from legacy_lens.codescan import escanear_codigo
from legacy_lens.model import Column, Schema, Table
from legacy_lens.relations import inferir_relaciones, resumen
from legacy_lens.report import generar_json, generar_markdown
from legacy_lens.sqlparse import leer_dump, parsear_dump

# --- parser -------------------------------------------------------------------


def test_fk_sin_constraint_no_se_parsea_como_columna():
    schema = parsear_dump(
        "CREATE TABLE a (id int NOT NULL, b_id int, PRIMARY KEY (id), "
        "FOREIGN KEY (b_id) REFERENCES b (id)) ENGINE=InnoDB;"
    )
    tabla = schema.tables[0]

    assert [c.name for c in tabla.columns] == ["id", "b_id"]
    assert tabla.foreign_keys == [("b_id", "b", "id")]


def test_pk_con_constraint_se_reconoce():
    tabla = parsear_dump("CREATE TABLE a (id int, CONSTRAINT pk_a PRIMARY KEY (id));").tables[0]

    assert tabla.primary_key == ["id"]
    assert tabla.column("id").key == "PRI"


def test_pk_con_prefijo_de_indice_no_se_come_la_columna():
    tabla = parsear_dump(
        "CREATE TABLE a (`code` varchar(20) NOT NULL, PRIMARY KEY (`code`(10))) ENGINE=InnoDB;"
    ).tables[0]

    assert tabla.primary_key == ["code"]


def test_un_comentario_escapado_no_se_come_las_columnas():
    tabla = parsear_dump(
        "CREATE TABLE a (nombre varchar(50) COMMENT 'apellido\\'s, nombre', "
        "id int NOT NULL, PRIMARY KEY (id)) ENGINE=InnoDB;"
    ).tables[0]

    assert [c.name for c in tabla.columns] == ["nombre", "id"]


def test_un_comentario_dentro_de_un_string_no_borra_la_tabla_siguiente():
    schema = parsear_dump(
        "CREATE TABLE a (nota varchar(20) DEFAULT 'a/*b', id int NOT NULL, PRIMARY KEY (id)) "
        "ENGINE=MyISAM;\nCREATE TABLE b (id int NOT NULL, PRIMARY KEY (id)) ENGINE=InnoDB;"
    )

    assert [t.name for t in schema.tables] == ["a", "b"]
    assert schema.tables[1].engine == "InnoDB"


def test_una_tabla_sin_engine_no_hereda_el_de_la_siguiente():
    schema = parsear_dump(
        "CREATE TABLE a (id int NOT NULL, PRIMARY KEY (id));\n"
        "CREATE TABLE b (id int NOT NULL, PRIMARY KEY (id)) ENGINE=MyISAM;"
    )

    assert schema.tables[0].engine == ""
    assert schema.tables[1].engine == "MyISAM"


def test_el_tipo_no_se_come_el_not_null():
    tabla = parsear_dump("CREATE TABLE a (id_obs text NOT NULL, id int NOT NULL);").tables[0]

    assert tabla.column("id_obs").type == "text"


def test_un_dump_utf16_se_lee(tmp_path):
    # Así guarda PowerShell 5.1 con `>`: antes daba cero tablas sin avisar.
    archivo = Path(tmp_path) / "dump.sql"
    archivo.write_bytes("CREATE TABLE pedidos (id int NOT NULL);".encode("utf-16"))

    assert [t.name for t in leer_dump(str(archivo)).tables] == ["pedidos"]


# --- relaciones ---------------------------------------------------------------


def test_no_inventa_relaciones_con_columnas_que_terminan_en_id():
    schema = Schema(
        tables=[
            Table(
                name="pedidos",
                columns=[
                    Column(name="idioma", type="varchar"),
                    Column(name="valid", type="tinyint"),
                    Column(name="guid", type="char"),
                    Column(name="cliente_id", type="int"),
                ],
            )
        ]
    )

    relaciones = inferir_relaciones(schema)

    assert [r.column for r in relaciones] == ["cliente_id"]
    assert resumen(relaciones)["huerfana"] == 1


# --- código y secretos --------------------------------------------------------


def _escanear(tmp_path, contenido: str):
    carpeta = Path(tmp_path) / "app"
    carpeta.mkdir()
    (carpeta / "config.php").write_text(contenido, encoding="utf-8")
    _, hallazgos = escanear_codigo(str(carpeta))
    return [o.snippet for f in hallazgos for o in f.occurrences]


def test_ningun_secreto_sobrevive_en_el_snippet(tmp_path):
    snippets = _escanear(
        tmp_path,
        "<?php\n"
        'mysql_connect("localhost", "root", "Pa55w0rd!Mysql");\n'
        'system("mysqldump -u root -pSup3rS3cretDB db");\n'
        "define('DB_PASS', 'ab');\n"
        "$k = AKIAIOSFODNN7EXAMPLE;\n",
    )
    unido = "\n".join(snippets)

    for secreto in ("Pa55w0rd", "Sup3rS3cretDB", "ab'", "AKIAIOSFODNN7EXAMPLE"):
        assert secreto not in unido, f"se filtró {secreto}"


def test_un_literal_con_comillas_escapadas_se_tapa_entero(tmp_path):
    snippets = _escanear(tmp_path, "<?php\n$pass = 'p@\\'ss9';\n")

    assert "ss9" not in "\n".join(snippets)


def test_no_marca_mysqli_con_consulta_literal(tmp_path):
    _, hallazgos = escanear_codigo(
        str(_crear(tmp_path, '<?php\nmysqli_query($conn, "SELECT id FROM t");\n'))
    )

    assert all(f.rule != "sql_query_sin_prepare" for f in hallazgos)


def test_marca_mysqli_con_consulta_interpolada(tmp_path):
    _, hallazgos = escanear_codigo(
        str(_crear(tmp_path, '<?php\nmysqli_query($conn, "SELECT id FROM t WHERE id = $id");\n'))
    )

    assert any(f.rule == "sql_query_sin_prepare" for f in hallazgos)


def test_pdo_exec_no_es_ejecucion_de_comandos(tmp_path):
    _, hallazgos = escanear_codigo(str(_crear(tmp_path, '<?php\n$pdo->exec("SET NAMES utf8");\n')))

    assert all(f.rule != "shell" for f in hallazgos)


def test_las_funciones_mysql_extintas_incluyen_las_que_faltaban(tmp_path):
    _, hallazgos = escanear_codigo(
        str(
            _crear(
                tmp_path,
                "<?php\n$r = mysql_fetch_object($q); mysql_insert_id(); ereg_replace('a', 'b', $x);\n",
            )
        )
    )
    reglas = {f.rule for f in hallazgos}

    assert "mysql_extinta" in reglas
    assert "funciones_muertas" in reglas


def test_un_bloque_de_comentario_no_genera_hallazgos(tmp_path):
    _, hallazgos = escanear_codigo(
        str(_crear(tmp_path, "<?php\n/*\n$pass = 'abc123';\nsystem('ls');\n*/\n$ok = 1;\n"))
    )

    assert hallazgos == []


def test_no_sigue_symlinks_fuera_del_arbol(tmp_path):
    fuera = Path(tempfile.mkdtemp()) / "secreto.php"
    fuera.write_text("<?php system('ls');", encoding="utf-8")
    app = Path(_crear(tmp_path, "<?php $ok = 1;\n"))
    enlace = app / "enlace.php"
    try:
        os.symlink(fuera, enlace)
    except (OSError, NotImplementedError):
        pytest.skip("este sistema no permite crear symlinks sin privilegios")

    stats, hallazgos = escanear_codigo(str(app))

    assert stats.files == 1
    assert hallazgos == []


def _crear(tmp_path, contenido: str) -> str:
    carpeta = Path(tmp_path) / f"app{len(list(Path(tmp_path).iterdir()))}"
    carpeta.mkdir()
    (carpeta / "index.php").write_text(contenido, encoding="utf-8")
    return str(carpeta)


# --- salidas ------------------------------------------------------------------


def test_el_markdown_no_se_rompe_con_pipes_ni_saltos():
    schema = Schema(tables=[Table(name="a|b\nc", columns=[])])
    report = _reporte_de_prueba(schema)

    markdown = generar_markdown(report)

    assert "# legacy-lens · a\\|b c" in markdown
    assert "rr\\|ss" in markdown


def test_el_json_escapa_comillas_y_saltos():
    schema = Schema(tables=[Table(name='pe"didos\n', columns=[])])
    datos = json.loads(generar_json(_reporte_de_prueba(schema)))

    assert datos["schema"]["tables"][0]["name"] == 'pe"didos\n'


def _reporte_de_prueba(schema: Schema):
    from legacy_lens.model import CodeStats, Finding, Occurrence, Report

    return Report(
        title="a|b\nc",
        target_path="app",
        schema=schema,
        code=CodeStats(),
        findings=[
            Finding(
                rule="x",
                title="rr|ss",
                severity="alta",
                category="codigo",
                detail="d",
                occurrences=[Occurrence(file="a.php", line=1, snippet="x")],
            )
        ],
        relations=[],
    )


# --- CLI ----------------------------------------------------------------------


def test_la_version_sigue_siendo_la_del_paquete(capsys):
    assert main(["version"]) == 0
    assert __version__ in capsys.readouterr().out
