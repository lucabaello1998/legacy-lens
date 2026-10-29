<?php
require_once __DIR__ . '/../config/database.php';

session_start();
session_start();

function q($sql)
{
    $link = conectar();
    $res = mysql_query($sql, $link);
    if (!$res) {
        error_reporting(0);
        return false;
    }
    return $res;
}

function escapar($valor)
{
    return utf8_encode($valor);
}
