from legacy_lens.model import Column, Schema, Table
from legacy_lens.relations import inferir_relaciones, resumen


def _tabla(nombre, columnas):
    return Table(name=nombre, columns=[Column(name=c, type="int(11)") for c in columnas])


def test_relacion_por_convencion():
    schema = Schema(
        tables=[
            _tabla("clientes", ["id", "nombre"]),
            _tabla("pedidos", ["id", "id_cliente", "total"]),
        ]
    )
    relaciones = inferir_relaciones(schema)
    assert len(relaciones) == 1
    r = relaciones[0]
    assert (r.table, r.column, r.target, r.kind) == ("pedidos", "id_cliente", "clientes", "convencion")


def test_relacion_huerfana():
    schema = Schema(tables=[_tabla("pedidos", ["id", "id_factura"])])
    relaciones = inferir_relaciones(schema)
    assert relaciones[0].kind == "huerfana"
    assert relaciones[0].target is None


def test_sufijo_id():
    schema = Schema(
        tables=[
            _tabla("productos", ["id"]),
            _tabla("items", ["id", "producto_id"]),
        ]
    )
    relaciones = inferir_relaciones(schema)
    assert relaciones[0].target == "productos"


def test_alias_resuelve_abreviaturas():
    schema = Schema(
        tables=[
            _tabla("choferes", ["id"]),
            _tabla("viajes", ["id", "id_chof"]),
        ]
    )
    assert inferir_relaciones(schema)[0].kind == "huerfana"
    relaciones = inferir_relaciones(schema, {"chof": "choferes"})
    assert relaciones[0].kind == "convencion"
    assert relaciones[0].target == "choferes"


def test_alias_por_defecto_resuelve_tec():
    schema = Schema(tables=[_tabla("tecnicos", ["id"]), _tabla("tareas", ["id", "id_tec"])])
    relaciones = inferir_relaciones(schema)
    assert relaciones[0].kind == "convencion"
    assert relaciones[0].target == "tecnicos"


def test_fk_declarada_no_se_duplica():
    schema = Schema(tables=[_tabla("clientes", ["id"]), _tabla("pedidos", ["id", "id_cliente"])])
    schema.table("pedidos").foreign_keys = [("id_cliente", "clientes", "id")]
    relaciones = inferir_relaciones(schema)
    assert [r.kind for r in relaciones] == ["declarada"]
    assert resumen(relaciones) == {"declarada": 1, "convencion": 0, "huerfana": 0}


def test_no_infiere_la_pk_ni_columnas_sin_patron():
    schema = Schema(tables=[_tabla("pedidos", ["id", "total", "estado"])])
    assert inferir_relaciones(schema) == []
