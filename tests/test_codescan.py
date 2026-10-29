from pathlib import Path

from legacy_lens.codescan import escanear_codigo


def _escribir(tmp_path: Path, nombre: str, contenido: str) -> Path:
    destino = tmp_path / nombre
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")
    return destino


def _reglas(hallazgos):
    return {h.rule: h for h in hallazgos}


def test_cuenta_archivos_y_lineas(tmp_path):
    _escribir(tmp_path, "a.php", "<?php\necho 1;\n")
    _escribir(tmp_path, "sub/b.php", "<?php\necho 2;\n")
    stats, _ = escanear_codigo(str(tmp_path))
    assert stats.files == 2
    assert stats.loc == 4


def test_ignora_node_modules_y_vendor(tmp_path):
    _escribir(tmp_path, "app.php", "<?php\n")
    _escribir(tmp_path, "vendor/lib.php", "<?php\n")
    _escribir(tmp_path, "node_modules/x.php", "<?php\n")
    stats, _ = escanear_codigo(str(tmp_path))
    assert stats.files == 1


def test_detecta_sql_concatenado(tmp_path):
    _escribir(
        tmp_path,
        "login.php",
        "<?php\n$sql = \"SELECT * FROM usuarios WHERE id = \" . $_GET['id'];\n",
    )
    _, hallazgos = escanear_codigo(str(tmp_path))
    assert "sql_superglobal" in _reglas(hallazgos)


def test_detecta_mysql_extinta(tmp_path):
    _escribir(tmp_path, "db.php", "<?php\n$r = mysql_query('SELECT 1');\n")
    _, hallazgos = escanear_codigo(str(tmp_path))
    assert _reglas(hallazgos)["mysql_extinta"].count == 1


def test_enmascara_el_valor_del_secreto(tmp_path):
    _escribir(tmp_path, "config.php", "<?php\n$password = 'superclave123';\n")
    _, hallazgos = escanear_codigo(str(tmp_path))
    hallazgo = _reglas(hallazgos)["secret_hardcodeado"]
    snippet = hallazgo.occurrences[0].snippet
    assert "superclave123" not in snippet
    assert "***" in snippet


def test_enmascara_password_de_define_pero_deja_el_nombre(tmp_path):
    _escribir(tmp_path, "config.php", "<?php\ndefine('DB_PASSWORD', 'root1234');\n")
    _, hallazgos = escanear_codigo(str(tmp_path))
    snippet = _reglas(hallazgos)["credencial_db"].occurrences[0].snippet
    assert "root1234" not in snippet
    assert "DB_PASSWORD" in snippet


def test_no_marca_una_variable_como_secreto(tmp_path):
    _escribir(tmp_path, "login.php", "<?php\n$sql = \"clave = '$hash'\";\n")
    _, hallazgos = escanear_codigo(str(tmp_path))
    assert "secret_hardcodeado" not in _reglas(hallazgos)


def test_los_comentarios_no_generan_hallazgos(tmp_path):
    _escribir(tmp_path, "a.php", "<?php\n// $r = mysql_query('x');\n# eval($x);\n")
    _, hallazgos = escanear_codigo(str(tmp_path))
    assert "mysql_extinta" not in _reglas(hallazgos)
    assert "eval" not in _reglas(hallazgos)


def test_las_lineas_no_se_corren_por_los_comentarios(tmp_path):
    _escribir(
        tmp_path,
        "a.php",
        "<?php\n\n\n// un comentario\n\n$r = mysql_query('SELECT 1');\n",
    )
    _, hallazgos = escanear_codigo(str(tmp_path))
    ocurrencia = _reglas(hallazgos)["mysql_extinta"].occurrences[0]
    assert ocurrencia.line == 6


def test_agrupa_por_regla_con_total_real(tmp_path):
    _escribir(tmp_path, "a.php", "<?php\nmysql_query('a');\nmysql_query('b');\n")
    _, hallazgos = escanear_codigo(str(tmp_path))
    hallazgo = _reglas(hallazgos)["mysql_extinta"]
    assert hallazgo.count == 2
    assert hallazgo.affected_files == 1


def test_limita_las_ocurrencias_guardadas(tmp_path):
    cuerpo = "<?php\n" + "mysql_query('x');\n" * 40
    _escribir(tmp_path, "a.php", cuerpo)
    _, hallazgos = escanear_codigo(str(tmp_path), limite_ocurrencias=5)
    hallazgo = _reglas(hallazgos)["mysql_extinta"]
    assert len(hallazgo.occurrences) == 5
    assert hallazgo.count == 40


def test_session_start_repetido_solo_si_es_recurrente(tmp_path):
    _escribir(tmp_path, "a.php", "<?php\nsession_start();\n")
    _, hallazgos = escanear_codigo(str(tmp_path))
    assert "session_repetido" not in _reglas(hallazgos)

    _escribir(
        tmp_path,
        "b.php",
        "<?php\nsession_start();\nsession_start();\nsession_start();\nsession_start();\n",
    )
    _, hallazgos = escanear_codigo(str(tmp_path))
    assert "session_repetido" in _reglas(hallazgos)


def test_detecta_secretos_de_nube_y_claves(tmp_path):
    _escribir(
        tmp_path,
        "keys.php",
        "<?php\n$k = 'AKIAABCDEFGHIJKLMNOP';\n$pk = '-----BEGIN RSA PRIVATE KEY-----';\n",
    )
    _, hallazgos = escanear_codigo(str(tmp_path))
    reglas = _reglas(hallazgos)
    assert "aws_key" in reglas
    assert "clave_privada" in reglas
    assert "AKIA" not in reglas["aws_key"].occurrences[0].snippet
