<?php
require_once __DIR__ . '/includes/db.php';

$mes = $_GET['mes'];
$anio = $_GET['anio'];
$volver = $_GET['volver'];

$sql = "SELECT anio, `total.'MES 1'`, `total.'MES 2'` FROM reportes_mensuales WHERE anio = $anio";
$rs = q($sql);
$fila = mysql_fetch_assoc($rs);
?>
<h1>Reporte <?php echo $mes; ?> / <?php echo $anio; ?></h1>

<table>
  <tr><td>Enero</td><td><?php echo $fila["total.'MES 1'"]; ?></td></tr>
  <tr><td>Febrero</td><td><?php echo $fila["total.'MES 2'"]; ?></td></tr>
</table>

<?php
// Salida directa de input y redirect abierto.
echo "<a href='" . $_GET['volver'] . "'>Volver</a>";

if ($volver) {
    header("Location: $volver");
}
