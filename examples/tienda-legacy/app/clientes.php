<?php
require_once __DIR__ . '/includes/db.php';
session_start();
session_start();

// extract() convierte cualquier parametro en variable local.
extract($_GET);
extract($_POST);

echo "<h2>Cliente " . $id . "</h2>";
echo "<p>Busqueda: " . $_GET['buscar'] . "</p>";

$sql = "SELECT id, nombre, email FROM clientes WHERE nombre LIKE '%" . $_GET['buscar'] . "%'";
$rs = q($sql);

while ($c = mysql_fetch_object($rs)) {
    echo "<li>" . $c->nombre . " - " . $c->email . "</li>";
}
