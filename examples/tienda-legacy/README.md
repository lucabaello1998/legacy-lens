# tienda-legacy (ejemplo)

Este directorio **no es un proyecto real**: es un sistema inventado, armado a propósito con los
vicios que `legacy-lens` sabe detectar. No ejecutarlo en ningún lado.

Qué tiene adentro:

| Vicio | Dónde |
|---|---|
| Credenciales hardcodeadas | `app/config/database.php` |
| `mysql_*` extintas | `app/includes/db.php`, `app/utils.php` |
| SQL concatenado con el request | `app/login.php`, `app/productos.php`, `app/clientes.php` |
| `md5()` para contraseñas | `app/login.php` |
| `eval`, `unserialize`, `include` variable | `app/pago.php`, `app/export.php` |
| `system` / `shell_exec` | `app/backup.php` |
| `each()`, `create_function()`, `preg_replace /e` | `app/pedidos.php`, `app/admin.php` |
| Esquema sin FK, MyISAM, latin1, fechas en texto | `schema.sql` |

Para regenerar el informe de ejemplo:

```bash
legacy-lens scan --path examples/tienda-legacy/app \
  --dump examples/tienda-legacy/schema.sql \
  --title "Tienda legacy (ejemplo)" --out out
```
