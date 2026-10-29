<?php
require_once __DIR__ . '/includes/db.php';

// Inclusion dinamica: el usuario decide que archivo se ejecuta.
$pagina = $_GET['pagina'];
include $pagina . '.php';

// Y lectura de archivos sin validar la ruta.
$archivo = $_GET['archivo'];
$contenido = file_get_contents($archivo);
echo $contenido;

// Descarga de comprobantes con el nombre que viene del request.
if (isset($_GET['descargar'])) {
    readfile($_GET['descargar']);
}
