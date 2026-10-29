<?php
require_once __DIR__ . '/includes/db.php';

$desde = $_GET['desde'];
$hasta = $_GET['hasta'];

$sql = "SELECT p.id, c.nombre, p.fecha, p.total FROM pedidos p, clientes c "
     . "WHERE p.id_cliente = c.id AND p.fecha BETWEEN '$desde' AND '$hasta'";

$rs = q($sql);

// each() desaparecio en PHP 8.
while ($fila = mysql_fetch_assoc($rs)) {
    list($id, $datos) = each($fila);
    echo "<div class='pedido'>" . $fila['nombre'] . " - " . $fila['total'] . "</div>";
}
