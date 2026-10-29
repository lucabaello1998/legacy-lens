"""Analisis estatico de un arbol de codigo PHP.

Es un escaner por expresiones regulares, no un parser: la idea es encontrar
patrones que duelen al migrar (SQL concatenado, funciones extintas, secretos
a la vista) en segundos y sin instalar nada. Cada regla declara severidad y
una explicacion en castellano.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .model import CodeStats, Finding, Occurrence

EXTENSIONES = {".php", ".inc", ".phtml", ".php3", ".php4", ".php5", ".module"}
DIRS_IGNORADOS = {".git", "node_modules", "vendor", ".idea", ".vscode", "storage", "cache"}

MAX_OCURRENCIAS_POR_REGLA = 25
MAX_ARCHIVOS = 20000

# Como se tapa cada regla que expone valores: se conserva lo que no es secreto
# (nombre de la variable o de la constante) y se tapa el valor.
MASCARA = {
    "secret_hardcodeado": "ultimo",
    "credencial_db": "primero",
    "clave_privada": "ninguno",
    "aws_key": "ninguno",
}


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    severity: str
    category: str
    pattern: str
    detail: str
    flags: int = re.IGNORECASE
    mask: bool = False
    per_file: bool = False


SQL_KEYWORDS = r"(?:SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|REPLACE\s+INTO)"
SUPERGLOBAL = r"\$_(?:GET|POST|REQUEST|COOKIE)"

REGLAS: tuple[Rule, ...] = (
    Rule(
        "sql_superglobal",
        "Consulta SQL armada con datos del request",
        "alta",
        "seguridad",
        rf"{SUPERGLOBAL}.{{0,120}}{SQL_KEYWORDS}|{SQL_KEYWORDS}.{{0,120}}{SUPERGLOBAL}",
        "Un parametro del usuario entra directo en el SQL: inyeccion segura.",
        flags=re.IGNORECASE | re.DOTALL,
    ),
    Rule(
        "sql_query_sin_prepare",
        "Query sin sentencia preparada",
        "alta",
        "codigo",
        r"(?:mysqli_query|->query|mysql_query)\s*\(\s*[^,)]*\$",
        "El SQL se arma con interpolacion de variables en vez de parametros.",
    ),
    Rule(
        "sql_interpolado",
        "SQL con variables interpoladas",
        "media",
        "codigo",
        rf"[\"'][^\"']*{SQL_KEYWORDS}[^\"']*\$[A-Za-z_]",
        "El string de la consulta se construye concatenando variables.",
        flags=re.IGNORECASE | re.DOTALL,
    ),
    Rule(
        "mysql_extinta",
        "Funciones mysql_* (extintas desde PHP 7)",
        "alta",
        "codigo",
        r"\bmysql_(?:query|connect|pconnect|fetch_array|fetch_assoc|fetch_row|num_rows|"
        r"real_escape_string|select_db|error|close|result)\s*\(",
        "No existen en PHP 7+: el archivo no corre sin reescribir el acceso a datos.",
    ),
    Rule(
        "each_extinta",
        "each() (extinta desde PHP 8.0)",
        "media",
        "codigo",
        r"\beach\s*\(",
        "Se elimino en PHP 8: reemplazar por foreach.",
    ),
    Rule(
        "utf8_encode",
        "utf8_encode / utf8_decode (deprecadas en 8.2)",
        "baja",
        "codigo",
        r"\butf8_(?:en|de)code\s*\(",
        "Deprecadas: migrar a mb_convert_encoding o a utf8mb4 de punta a punta.",
    ),
    Rule(
        "md5_password",
        "Hash debil para contrasenas",
        "alta",
        "seguridad",
        r"(?:md5|sha1|crc32)\s*\(\s*[^)]*(?:pass|clave|contras|pwd|password)",
        "MD5/SHA1 no sirven para contrasenas: password_hash() con bcrypt o argon2.",
    ),
    Rule(
        "md5_token",
        "Token predecible (md5/uniqid)",
        "media",
        "seguridad",
        r"\b(?:md5|uniqid)\s*\(",
        "Tokens de sesion o de recuperacion generados con funciones predecibles.",
    ),
    Rule(
        "eval",
        "eval() / assert() con codigo dinamico",
        "alta",
        "seguridad",
        r"\b(?:eval|assert)\s*\(\s*[^)]*\$",
        "Ejecucion de codigo arbitrario: no tiene traduccion directa a un framework.",
    ),
    Rule(
        "shell",
        "Ejecucion de comandos del sistema",
        "alta",
        "seguridad",
        r"\b(?:system|exec|shell_exec|passthru|popen|proc_open)\s*\(",
        "Si el argumento toca datos del request, es ejecucion remota de comandos.",
    ),
    Rule(
        "include_variable",
        "include/require con ruta variable",
        "alta",
        "seguridad",
        r"\b(?:include|require)(?:_once)?\s*\(?\s*\$",
        "Inclusion remota de archivos (LFI/RFI) y dependencias invisibles para el IDE.",
    ),
    Rule(
        "file_superglobal",
        "Acceso a archivos con datos del request",
        "alta",
        "seguridad",
        r"\b(?:file_get_contents|fopen|readfile|file|unlink|copy)\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)",
        "Lectura o borrado de archivos controlado por el usuario.",
    ),
    Rule(
        "unserialize",
        "unserialize() sobre datos externos",
        "media",
        "seguridad",
        r"\bunserialize\s*\(",
        "Deserializacion insegura: preferir JSON.",
    ),
    Rule(
        "extract",
        "extract() / variables variables",
        "media",
        "codigo",
        r"\bextract\s*\(|\$\$[A-Za-z_]",
        "Variables que aparecen de la nada: imposible de tipar o testear.",
    ),
    Rule(
        "error_reporting_off",
        "Errores silenciados",
        "media",
        "codigo",
        r"error_reporting\s*\(\s*0\s*\)|ini_set\s*\(\s*['\"]display_errors['\"]\s*,\s*['\"]?(?:0|off)",
        "Los errores se ocultan en vez de corregirse; migrar asi es a ciegas.",
    ),
    Rule(
        "header_variable",
        "Redireccion con variable (open redirect)",
        "media",
        "seguridad",
        r"header\s*\(\s*['\"]Location:\s*[^'\"]*\$",
        "El destino del redirect lo decide el request.",
    ),
    Rule(
        "preg_e",
        "preg_replace con modificador /e",
        "alta",
        "seguridad",
        r"preg_replace\s*\([^;]*?/[a-zA-Z]*e[a-zA-Z]*['\"]",
        "El modificador /e ejecuta codigo: se elimino en PHP 7.",
    ),
    Rule(
        "secret_hardcodeado",
        "Credencial hardcodeada",
        "alta",
        "seguridad",
        r"(?:pass(?:word)?|pwd|clave|secret|token|api[_-]?key)\s*=\s*['\"](?!\$)[^'\"]{3,}['\"]",
        "Credenciales en el codigo: hay que rotarlas y pasarlas a variables de entorno.",
        mask=True,
    ),
    Rule(
        "credencial_db",
        "Credenciales de base en el codigo",
        "alta",
        "seguridad",
        r"define\s*\(\s*['\"](?:DB_(?:PASS|PASSWORD|USER|HOST)|HOST|USER|PASSWORD)['\"]",
        "El acceso a la base esta escrito en un .php versionado.",
        mask=True,
    ),
    Rule(
        "clave_privada",
        "Clave privada en el repositorio",
        "alta",
        "seguridad",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "Material criptografico versionado: rotar y sacar del historial.",
        mask=True,
    ),
    Rule(
        "aws_key",
        "Access key de AWS",
        "alta",
        "seguridad",
        r"\bAKIA[0-9A-Z]{16}\b",
        "Credencial de nube expuesta.",
        mask=True,
    ),
    Rule(
        "echo_superglobal",
        "Salida directa de datos del request (XSS)",
        "media",
        "seguridad",
        r"\becho\s+\$_|\bprint\s+\$_",
        "Se imprime input sin escapar: XSS reflejado.",
    ),
    Rule(
        "session_repetido",
        "session_start() repetido",
        "baja",
        "codigo",
        r"\bsession_start\s*\(",
        "Sesiones abiertas en cada include: sintoma de que no hay bootstrap.",
        per_file=True,
    ),
    Rule(
        "funciones_muertas",
        "Funciones eliminadas o deprecadas",
        "baja",
        "codigo",
        r"\b(?:create_function|money_format|ereg|eregi|split|mysql_escape_string|get_magic_quotes_gpc)\s*\(",
        "No existen en PHP 8: cada una rompe el archivo donde aparece.",
    ),
)

_RE_SQL = re.compile(SQL_KEYWORDS, re.IGNORECASE)
_RE_SESSION = re.compile(r"\bsession_start\s*\(", re.IGNORECASE)
_RE_NAMESPACE = re.compile(r"^\s*namespace\s+[A-Za-z_]", re.MULTILINE)
_RE_COMENTARIO = re.compile(r"^[ \t]*(?://|#|\*).*$", re.MULTILINE)


def _archivos_php(base: str) -> list[str]:
    encontrados: list[str] = []
    for raiz, dirs, archivos in os.walk(base):
        dirs[:] = [d for d in dirs if d.lower() not in DIRS_IGNORADOS]
        for nombre in archivos:
            if os.path.splitext(nombre)[1].lower() in EXTENSIONES:
                encontrados.append(os.path.join(raiz, nombre))
                if len(encontrados) >= MAX_ARCHIVOS:
                    return encontrados
    return encontrados


def _enmascarar(texto: str, conservar: str = "ultimo") -> str:
    """Tapa los literales entre comillas de un fragmento.

    - conservar="ultimo": deja ver todos menos el ultimo (credencial = valor).
    - conservar="primero": deja ver el primero (define('DB_HOST', '***')).
    - conservar="ninguno": tapa todo (claves, tokens).
    """
    literales = list(re.finditer(r"(['\"])([^'\"]{3,})\1", texto))
    if not literales:
        return "***"
    if conservar == "primero":
        visibles = {0}
    elif conservar == "ultimo":
        visibles = set(range(len(literales) - 1))
    else:
        visibles = set()
    salida: list[str] = []
    cursor = 0
    for i, m in enumerate(literales):
        salida.append(texto[cursor: m.start(2)])
        salida.append(m.group(2) if i in visibles else "***")
        cursor = m.end(2)
    salida.append(texto[cursor:])
    return "".join(salida)


def _recortar(texto: str, limite: int = 180) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _leer(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def escanear_codigo(base: str, limite_ocurrencias: int = MAX_OCURRENCIAS_POR_REGLA) -> tuple[
    CodeStats, list[Finding]
]:
    """Recorre el arbol PHP y devuelve estadisticas + hallazgos agregados."""
    stats = CodeStats()
    acumulado: dict[str, Finding] = {}
    archivos_por_regla: dict[str, set[str]] = {}
    totales: dict[str, int] = {}
    nombres = _archivos_php(base)
    stats.files = len(nombres)
    stats.has_composer = os.path.exists(os.path.join(base, "composer.json")) or os.path.exists(
        os.path.join(os.path.dirname(os.path.abspath(base)), "composer.json")
    )

    for path in nombres:
        try:
            contenido = _leer(path)
        except OSError:
            continue
        relativo = os.path.relpath(path, base)
        lineas = contenido.splitlines()
        stats.bytes += len(contenido.encode("utf-8", errors="replace"))
        stats.loc += len(lineas)
        if _RE_SQL.search(contenido):
            stats.with_sql += 1
        if _RE_SESSION.search(contenido):
            stats.with_sessions += 1
        if not stats.has_namespaces and _RE_NAMESPACE.search(contenido):
            stats.has_namespaces = True
        if len(lineas) > 0:
            stats.largest.append((relativo, len(lineas)))

        # Se analiza sin comentarios: un comentario no ejecuta SQL ni guarda claves.
        limpio = _RE_COMENTARIO.sub("", contenido)
        for regla in REGLAS:
            coincidencias = list(re.finditer(regla.pattern, limpio))
            if not coincidencias:
                continue
            totales[regla.id] = totales.get(regla.id, 0) + len(coincidencias)
            archivos_por_regla.setdefault(regla.id, set()).add(relativo)
            if regla.id not in acumulado:
                acumulado[regla.id] = Finding(
                    rule=regla.id,
                    title=regla.title,
                    severity=regla.severity,
                    category=regla.category,
                    detail=regla.detail,
                )
            hallazgo = acumulado[regla.id]
            if len(hallazgo.occurrences) >= limite_ocurrencias:
                continue
            for m in coincidencias:
                if len(hallazgo.occurrences) >= limite_ocurrencias:
                    break
                numero = limpio.count("\n", 0, m.start()) + 1
                original = lineas[numero - 1] if numero - 1 < len(lineas) else m.group(0)
                if regla.mask:
                    modo = MASCARA.get(regla.id, "ninguno")
                    if modo == "ultimo":
                        original = original.replace(m.group(0), _enmascarar(m.group(0), "ultimo"))
                    else:
                        original = _enmascarar(original, modo)
                snippet = _recortar(original)
                hallazgo.occurrences.append(
                    Occurrence(file=relativo, line=numero, snippet=snippet)
                )

    stats.largest.sort(key=lambda x: x[1], reverse=True)
    stats.largest = stats.largest[:10]

    # Tests: la ausencia es en si misma un hallazgo de modernidad.
    stats.has_tests = any(
        os.path.isdir(os.path.join(base, d)) for d in ("tests", "test", "spec")
    )

    hallazgos: list[Finding] = []
    for regla in REGLAS:
        if regla.id not in acumulado:
            continue
        hallazgo = acumulado[regla.id]
        hallazgo.total = totales.get(regla.id, len(hallazgo.occurrences))
        hallazgo.affected_files = len(archivos_por_regla.get(regla.id, ()))
        # session_start repetido solo duele si aparece muchas veces.
        if regla.id == "session_repetido" and hallazgo.total < 4:
            continue
        hallazgos.append(hallazgo)

    orden = {"alta": 0, "media": 1, "baja": 2}
    hallazgos.sort(key=lambda f: (orden.get(f.severity, 9), -f.count))
    return stats, hallazgos
