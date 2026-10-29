from legacy_lens.model import CodeStats, Column, Finding, Occurrence, Report, Schema, Table
from legacy_lens.schemacheck import revisar_esquema
from legacy_lens.score import calcular_score, plan_de_accion


def _esquema_minimo() -> Schema:
    clientes = Table(
        name="clientes",
        columns=[Column(name="id", type="int(11)"), Column(name="nombre", type="varchar(50)")],
        primary_key=["id"],
        engine="InnoDB",
        charset="utf8mb4",
    )
    pedidos = Table(
        name="pedidos",
        columns=[Column(name="id_cliente", type="int(11)"), Column(name="fecha", type="varchar(10)")],
        engine="MyISAM",
        charset="latin1",
    )
    return Schema(tables=[clientes, pedidos])


def test_detecta_tablas_sin_pk():
    hallazgos = {h.rule: h for h in revisar_esquema(_esquema_minimo(), [])}
    assert "sin_pk" in hallazgos
    assert hallazgos["sin_pk"].count == 1


def test_detecta_ausencia_de_fk():
    hallazgos = {h.rule: h for h in revisar_esquema(_esquema_minimo(), [])}
    assert "sin_fk" in hallazgos
    assert hallazgos["sin_fk"].severity == "alta"


def test_detecta_myisam_y_charset_viejo():
    hallazgos = {h.rule: h for h in revisar_esquema(_esquema_minimo(), [])}
    assert hallazgos["myisam"].count == 1
    assert hallazgos["charset_viejo"].count == 1


def test_detecta_fechas_como_texto():
    hallazgos = {h.rule: h for h in revisar_esquema(_esquema_minimo(), [])}
    assert "fecha_texto" in hallazgos


def test_score_en_rango_y_etiqueta():
    report = Report(
        title="demo",
        target_path=".",
        schema=_esquema_minimo(),
        code=CodeStats(files=3, loc=400, with_sql=3),
    )
    report.findings = revisar_esquema(report.schema, [])
    score = calcular_score(report)
    assert 0 <= score.total <= 100
    assert score.label in {"Sano", "Moderado", "Doloroso", "Critico"}
    assert len(score.dimensions) == 5


def test_sistema_sano_puntua_bajo():
    sano = Schema(
        tables=[
            Table(
                name="clientes",
                columns=[Column(name="id", type="int(11)", key="PRI")],
                primary_key=["id"],
                engine="InnoDB",
                charset="utf8mb4",
                rows=10,
                rows_estimated=False,
            )
        ]
    )
    report = Report(
        title="sano",
        target_path=".",
        schema=sano,
        code=CodeStats(files=5, loc=100, has_composer=True, has_namespaces=True, has_tests=True),
    )
    score = calcular_score(report)
    assert score.total < 40


def test_plan_de_accion_ordena_por_severidad():
    report = Report(title="demo", target_path=".", schema=_esquema_minimo(), code=CodeStats())
    report.findings = [
        Finding(rule="utf8_encode", title="x", severity="baja", category="codigo", total=1),
        Finding(rule="sin_fk", title="y", severity="alta", category="esquema", total=1),
    ]
    acciones = plan_de_accion(report)
    assert acciones[0].title.startswith("Documentar las relaciones")


def test_plan_sin_hallazgos_es_vacio():
    report = Report(title="demo", target_path=".", schema=Schema(), code=CodeStats())
    assert plan_de_accion(report) == []


def test_ocurrencias_no_alteran_el_score_por_regla():
    report = Report(title="demo", target_path=".", schema=_esquema_minimo(), code=CodeStats())
    base = Finding(
        rule="mysql_extinta",
        title="mysql",
        severity="alta",
        category="codigo",
        total=100,
        occurrences=[Occurrence("a.php", 1, "x")],
    )
    report.findings = [base]
    assert base.count == 100
