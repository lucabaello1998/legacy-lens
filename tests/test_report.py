import json
from pathlib import Path

from legacy_lens.model import CodeStats, Column, Finding, Occurrence, Report, Schema, Table
from legacy_lens.report import escribir, generar_html, generar_json, generar_markdown
from legacy_lens.score import calcular_score, plan_de_accion


def _reporte() -> Report:
    schema = Schema(
        tables=[
            Table(
                name="clientes<script>",
                columns=[Column(name="id", type="int(11)")],
                engine="MyISAM",
                charset="latin1",
            )
        ],
        source="dump.sql",
    )
    report = Report(title="Demo <b>raro</b>", target_path="app", schema=schema, code=CodeStats(files=2, loc=30))
    report.findings = [
        Finding(
            rule="mysql_extinta",
            title="Funciones mysql_*",
            severity="alta",
            category="codigo",
            total=1,
            occurrences=[Occurrence("a.php", 3, "mysql_query('x')")],
        )
    ]
    report.score = calcular_score(report)
    report.actions = plan_de_accion(report)
    return report


def test_html_escapa_el_contenido():
    html = generar_html(_reporte())
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;raro&lt;/b&gt;" in html
    assert "<script>" not in html


def test_html_tiene_score_y_secciones():
    html = generar_html(_reporte())
    assert "Indice de dolor de migracion" in html
    assert "Plan de accion" in html
    assert "mysql_query" in html


def test_json_es_valido_y_completo():
    datos = json.loads(generar_json(_reporte()))
    assert datos["tool"]["name"] == "legacy-lens"
    assert datos["score"]["total"] >= 0
    assert datos["target"]["tables"] == 1
    assert datos["findings"][0]["rule"] == "mysql_extinta"


def test_markdown_resume():
    md = generar_markdown(_reporte())
    assert md.startswith("# legacy-lens")
    assert "Indice de dolor" in md
    assert "mysql" in md.lower()


def test_escribir_genera_los_tres_formatos(tmp_path: Path):
    salidas = escribir(_reporte(), str(tmp_path))
    nombres = sorted(Path(s).name for s in salidas)
    assert nombres == ["report.html", "report.json", "report.md"]
    for salida in salidas:
        assert Path(salida).stat().st_size > 0
