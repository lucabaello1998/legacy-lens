<?php
require_once __DIR__ . '/includes/db.php';

$id_pedido = $_POST['id_pedido'];
$metodo = $_POST['metodo'];
$importe = $_POST['importe'];

// Codigo generado en runtime: no hay forma de leerlo ni de testearlo.
$regla = "return $importe * 1.21;";
$total = eval($regla);

$sql = "INSERT INTO pagos (id_pedido, id_metodo, importe, fecha_pago) "
     . "VALUES ($id_pedido, '$metodo', $total, '" . date('Y-m-d') . "')";
q($sql);

// Y de paso, un unserialize sobre datos del request.
$carrito = unserialize(base64_decode($_POST['carrito']));
$_SESSION['carrito'] = $carrito;

echo "ok";
