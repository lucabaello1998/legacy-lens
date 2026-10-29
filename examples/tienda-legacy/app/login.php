<?php
require_once __DIR__ . '/includes/db.php';

$usuario = $_POST['usuario'];
$clave = $_POST['clave'];

// Hash debil y consulta armada con el request.
$hash = md5($clave);
$sql = "SELECT id, usuario, id_rol FROM usuarios WHERE usuario = '$usuario' AND clave = '$hash'";

$resultado = mysql_query($sql);
if ($resultado && mysql_num_rows($resultado) > 0) {
    $fila = mysql_fetch_assoc($resultado);
    $_SESSION['usuario'] = $fila['usuario'];
    $_SESSION['rol'] = $fila['id_rol'];
    header("Location: panel.php");
    exit;
}

$error = 'Usuario o clave incorrectos';
?>
<html>
<body>
  <form method="post" action="login.php">
    <input name="usuario"><input type="password" name="clave">
    <button>Entrar</button>
  </form>
  <p><?php echo $error; ?></p>
</body>
</html>
