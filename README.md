# legacy-lens

**Radiografia de un sistema legacy PHP/MySQL en un comando.** Apunta a una carpeta de codigo y a un
dump de esquema, y devuelve un informe HTML con un numero: **cuanto duele migrarlo**.

[![CI](https://github.com/lucabaello1998/legacy-lens/actions/workflows/ci.yml/badge.svg)](https://github.com/lucabaello1998/legacy-lens/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-16a34a)](LICENSE)

![Informe de ejemplo](docs/capturas/reporte.png)

> El informe de ejemplo esta versionado en [`docs/ejemplo-reporte.html`](docs/ejemplo-reporte.html):
> se puede abrir sin instalar nada.

---

## El problema

Entrar a un sistema de hace 10 o 15 anos es siempre la misma escena: nadie sabe cuantas tablas hay,
no existen las claves foraneas, las relaciones viven en el nombre de las columnas, hay credenciales
escritas en un `.php` y la mitad del SQL se arma concatenando `$_POST`. Antes de decidir *que* hacer
(migrar, reescribir o convivir) hace falta una foto honesta del desastre.

`legacy-lens` saca esa foto en segundos y la convierte en tres cosas:

1. **Un indice de dolor** de 0 a 100, comparable entre sistemas.
2. **Un inventario** de esquema, relaciones inferidas y hallazgos de codigo con archivo y linea.
3. **Un plan de accion** ordenado por severidad, con esfuerzo estimado.

## Que hace

- **Esquema**: tablas, columnas, PKs, FKs, motores, charsets, filas y tamano. Detecta tablas sin
  clave primaria, ausencia total de foreign keys, IDs guardados como texto, fechas en `varchar`,
  `MyISAM`, `latin1`, `ENUM` como catalogo escondido, nombres hostiles (`total.'MES 1'`, `Order`) y
  tablas gemelas (`proveedor` / `proveedores`).
- **Relaciones por convencion**: reconstruye el mapa que nunca se documento (`id_cliente` →
  `clientes`, `id_tec` → `tecnicos`) y separa las que apuntan a una tabla que no existe.
- **Codigo**: 24 reglas sobre PHP — SQL concatenado, queries sin preparar, `mysql_*`, `each()`,
  `eval`, `include` variable, `system`, `unserialize`, `md5` para contrasenas, salida sin escapar,
  errores silenciados y funciones extintas.
- **Secretos**: credenciales, claves de base, access keys de AWS y claves privadas. **Se muestran
  enmascaradas**: el informe nunca imprime el valor, solo donde esta.

## Instalacion

```bash
# como herramienta suelta
pipx install git+https://github.com/lucabaello1998/legacy-lens

# o desde el repo
git clone https://github.com/lucabaello1998/legacy-lens
cd legacy-lens
pip install -e ".[mysql]"    # [mysql] solo si vas a apuntar a una base viva
```

Con Docker, sin instalar Python:

```bash
docker build -t legacy-lens .
docker run --rm -v "$PWD:/work" legacy-lens scan --path /work/app --dump /work/schema.sql --out /work/out
```

## Uso

Lo minimo: un dump de esquema (no hace falta una base viva).

```bash
mysqldump --no-data -u root mi_base > schema.sql
legacy-lens scan --path ./public_html --dump schema.sql --title "Sistema de facturacion"
```

Contra una base viva, con conteos reales de filas y tamanos:

```bash
legacy-lens scan --dsn mysql://usuario:clave@localhost:3306/mi_base --path ./public_html
```

Salida:

```
legacy-lens 1.0.0
  objetivo : ./public_html
  esquema  : schema.sql -> 76 tablas, 1517 columnas
  codigo   : 378 archivos PHP, 148302 lineas

indice de dolor: 81/100 (Critico)
  Esquema       88  ##################..
  Datos         64  #############.......
  Codigo        92  ###################.
  Seguridad     95  ###################.
  Modernidad    85  #################...

hallazgos altos:
  - Consulta SQL armada con datos del request (2452)
  - Funciones mysql_* (extintas desde PHP 7) (318)
  - Credencial hardcodeada (14)
```

### Opciones

| Flag | Para que |
|---|---|
| `--path DIR` | carpeta con el codigo PHP (recursiva, ignora `vendor` y `node_modules`) |
| `--dump FILE` | esquema en `.sql` (sirve `mysqldump --no-data`) |
| `--dsn URL` | `mysql://usuario:clave@host:3306/base` (requiere `[mysql]`) |
| `--out DIR` | donde escribir el informe (default `legacy-lens-out`) |
| `--format` | `html,json,md` (default los tres) |
| `--alias` | alias de tablas: `--alias tec=tecnicos,cli=clientes` |
| `--fail-over N` | sale con codigo 2 si el indice llega a N (para CI) |
| `--quiet` | no imprime el resumen en consola |

### En un pipeline

`--fail-over` convierte el indice en un gate: un sistema nuevo no deberia superar 40, uno legacy en
migracion puede tener 70 con un plan en curso.

```yaml
- run: legacy-lens scan --path . --dump schema.sql --out out --fail-over 80 --quiet
```

## Como se calcula el indice

Cinco dimensiones, cada una de 0 a 100 (mas alto = peor), con pesos explicitos:

| Dimension | Peso | Que mira |
|---|---:|---|
| Esquema | 30% | tablas sin PK, ausencia de FK, relaciones por nombre, tipos raros, motores y charsets |
| Codigo | 25% | hallazgos ponderados por severidad, proporcion de archivos con SQL, volumen de codigo |
| Seguridad | 20% | hallazgos altos y medios (SQLi, secretos, ejecucion de comandos) |
| Datos | 15% | volumen total, concentracion en una tabla, tablas millonarias |
| Modernidad | 10% | composer, namespaces, tests |

| Indice | Etiqueta | Lectura |
|---|---|---|
| 0-25 | Sano | migracion de rutina |
| 26-50 | Moderado | hay que documentar y ordenar, pero el modelo existe |
| 51-75 | Doloroso | conviene migrar por modulos, con capa de compatibilidad |
| 76-100 | Critico | primero estabilizar (seguridad, PKs), despues pensar en framework |

El puntaje no es cientifico: es **comparable y explicable**. Cada dimension trae sus razones
("2 de 13 tablas sin PK", "cero foreign keys declaradas"), asi que se puede discutir con datos.

## El ejemplo

`examples/tienda-legacy` es un sistema **inventado**, armado a proposito con todos los vicios:
credenciales en el codigo, `mysql_*`, SQL concatenado, `eval`, `system`, esquema sin FK, `MyISAM`,
`latin1` y nombres imposibles. Nada proviene de un sistema real.

```bash
legacy-lens scan \
  --path examples/tienda-legacy/app \
  --dump examples/tienda-legacy/schema.sql \
  --title "Tienda legacy (ejemplo)" --out out
```

Con Docker y base real (MySQL 8 se inicializa con el esquema y los datos del ejemplo):

```bash
docker compose up -d mysql
docker compose run --rm lens
# informe en ./out/report.html
```

## Origen

Nacio al modernizar un sistema de gestion de campo de 378 archivos PHP 7.4 sin framework, 76 tablas
sin claves foraneas y 11,3 millones de filas en una sola tabla. El analisis que se hizo a mano para
ese proyecto es el que hoy corre este CLI, generalizado y sin un solo dato del sistema original.

Ese caso de estudio esta en [fieldops-modernization](https://github.com/lucabaello1998/fieldops-modernization).

## Limites

- Es un **escaner por expresiones regulares**, no un parser de PHP: encuentra patrones, no flujo de
  datos. Un hallazgo es un candidato a revisar, no una sentencia.
- No ejecuta nada del sistema analizado ni se conecta a nada que no sea la base que le pasas.
- Los conteos de filas de un dump son 0: para volumen real hace falta `--dsn`.
- Los secretos se enmascaran, pero **igual hay que rotarlos**: estuvieron expuestos.

## Desarrollo

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
```

50 tests cubren el parser de dumps, la inferencia de relaciones, las reglas de codigo, el calculo del
indice y la generacion de los tres formatos.

## Licencia

MIT. Hecho por [Luca Baello](https://lucabaello1998.github.io).
