<?php
require_once __DIR__ . '/includes/db.php';

$base = $_GET['base'];

// Comando armado con el request.
system("mysqldump " . $base . " > /tmp/backup.sql");

// Y un shell_exec con la fecha del sistema.
$hoy = shell_exec('date +%Y%m%d');
echo "backup-" . $hoy;
