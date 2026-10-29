<?php
// Configuracion de ejemplo: credenciales a la vista, como en el 90% de los legacy.
define('DB_HOST', 'localhost');
define('DB_USER', 'tienda');
define('DB_PASSWORD', 'root1234');
define('DB_NAME', 'tienda');

$password = 'supersecreto123';
$api_key = 'sk_demo_1234567890abcdef';

function conectar()
{
    // mysql_* no existe desde PHP 7.
    $link = mysql_connect(DB_HOST, DB_USER, DB_PASSWORD);
    mysql_select_db(DB_NAME, $link);
    return $link;
}
