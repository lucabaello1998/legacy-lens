<?php
require_once __DIR__ . '/includes/db.php';

$busqueda = $_GET['q'];
$categoria = $_GET['cat'];
$orden = isset($_GET['orden']) ? $_GET['orden'] : 'nombre';

// Dos clasicos: LIKE concatenado y ORDER BY que viene del request.
$sql = "SELECT id, nombre, precio FROM productos " .
       "WHERE nombre LIKE '%$busqueda%' AND id_categoria = $categoria " .
       "ORDER BY $orden";

$rs = q($sql);

$filas = array();
while ($fila = mysql_fetch_array($rs)) {
    $filas[] = $fila;
}
?>
<table>
<?php foreach ($filas as $f): ?>
  <tr>
    <td><?php echo utf8_decode($f['nombre']); ?></td>
    <td><?php echo $f['precio']; ?></td>
  </tr>
<?php endforeach; ?>
</table>
