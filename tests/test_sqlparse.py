from legacy_lens.sqlparse import parsear_dump

DDL = """
-- comentario
/* bloque */
CREATE TABLE `clientes` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(120) DEFAULT NULL,
  `id_pais` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_pais` (`id_pais`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS pedidos (
  id int NOT NULL,
  id_cliente int DEFAULT NULL,
  total decimal(10,2) DEFAULT '0.00',
  PRIMARY KEY (id),
  CONSTRAINT fk_cliente FOREIGN KEY (id_cliente) REFERENCES clientes (id)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;
"""


def test_parsea_tablas_y_columnas():
    schema = parsear_dump(DDL, source="demo.sql")
    assert [t.name for t in schema.tables] == ["clientes", "pedidos"]
    clientes = schema.table("clientes")
    assert clientes is not None
    assert [c.name for c in clientes.columns] == ["id", "nombre", "id_pais"]
    assert clientes.primary_key == ["id"]
    assert clientes.engine == "InnoDB"
    assert clientes.charset == "utf8mb4"


def test_marca_la_pk_en_la_columna():
    schema = parsear_dump(DDL)
    columna = schema.table("clientes").column("id")
    assert columna.key == "PRI"
    assert columna.extra == "auto_increment"


def test_parsea_fk_declarada():
    schema = parsear_dump(DDL)
    pedidos = schema.table("pedidos")
    assert pedidos.foreign_keys == [("id_cliente", "clientes", "id")]
    assert pedidos.engine == "MyISAM"
    assert pedidos.charset == "latin1"


def test_default_y_nullable():
    schema = parsear_dump(DDL)
    total = schema.table("pedidos").column("total")
    assert total.default == "'0.00'"
    assert total.nullable is True
    assert schema.table("pedidos").column("id").nullable is False


def test_tipo_con_parentesis():
    schema = parsear_dump(DDL)
    assert schema.table("clientes").column("nombre").type == "varchar(120)"
    assert schema.table("pedidos").column("total").type == "decimal(10,2)"


def test_dump_vacio():
    schema = parsear_dump("-- nada aca\n")
    assert schema.tables == []


def test_identificadores_hostiles():
    sql = """
    CREATE TABLE `reportes` (
      `id` int(11) NOT NULL,
      `total.'MES 1'` decimal(12,2) DEFAULT NULL,
      `Order` varchar(20) DEFAULT NULL,
      PRIMARY KEY (`id`)
    ) ENGINE=MyISAM;
    """
    tabla = parsear_dump(sql).table("reportes")
    assert [c.name for c in tabla.columns] == ["id", "total.'MES 1'", "Order"]
