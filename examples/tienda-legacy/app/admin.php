<?php
require_once __DIR__ . '/includes/db.php';
session_start();

$plantilla = $_GET['plantilla'];

// preg_replace con /e ejecuta el reemplazo como codigo.
$salida = preg_replace('/\{(\w+)\}/e', '$plantilla', $_GET['texto']);

// create_function desaparecio en PHP 8.
$formatear = create_function('$n', 'return number_format($n, 2, ",", ".");');

echo $formatear($salida);
