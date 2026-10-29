<?php
// Utilidades copiadas y pegadas en cada pantalla.
session_start();

function limpiar($texto)
{
    return utf8_encode(trim($texto));
}

function moneda($valor)
{
    return money_format('%.2n', $valor);
}

function borrar_pedido()
{
    $id = $_POST['id'];
    $sql = "DELETE FROM pedidos WHERE id = $id";
    mysql_query($sql);
}
