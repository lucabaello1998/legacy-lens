"""Salida del informe: HTML autocontenido, Markdown y JSON."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .model import Finding, Report

SEV_COLOR = {"alta": "#dc2626", "media": "#d97706", "baja": "#2563eb"}
SEV_LABEL = {"alta": "Alta", "media": "Media", "baja": "Baja"}
CAT_LABEL = {"esquema": "Esquema", "codigo": "Codigo", "seguridad": "Seguridad"}


def _n(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def _bytes(valor: int) -> str:
    unidades = ["B", "KB", "MB", "GB", "TB"]
    tamano = float(valor)
    for unidad in unidades:
        if tamano < 1024 or unidad == unidades[-1]:
            return f"{tamano:.1f} {unidad}" if unidad != "B" else f"{int(tamano)} B"
        tamano /= 1024
    return f"{valor} B"


def _e(texto: str) -> str:
    return html.escape(str(texto), quote=True)


def _barra(valor: int, color: str = "#4f46e5") -> str:
    return (
        f'<div class="bar"><span style="width:{max(2, valor)}%;background:{color}"></span></div>'
    )


def _gauge(score: int, etiqueta: str) -> str:
    color = "#16a34a" if score <= 25 else "#d97706" if score <= 50 else "#ea580c" if score <= 75 else "#dc2626"
    radio = 62
    circunferencia = 2 * 3.14159 * radio
    offset = circunferencia * (1 - score / 100)
    return f"""
    <div class="gauge">
      <div class="gauge-ring">
        <svg viewBox="0 0 160 160" width="160" height="160" role="img" aria-label="Indice {score} de 100">
          <circle cx="80" cy="80" r="{radio}" fill="none" stroke="#e6e8f0" stroke-width="14"/>
          <circle cx="80" cy="80" r="{radio}" fill="none" stroke="{color}" stroke-width="14"
                  stroke-linecap="round" stroke-dasharray="{circunferencia:.1f}"
                  stroke-dashoffset="{offset:.1f}" transform="rotate(-90 80 80)"/>
        </svg>
        <div class="gauge-value"><strong>{score}</strong><span>/100</span></div>
      </div>
      <div class="gauge-label" style="color:{color}">{_e(etiqueta)}</div>
    </div>
    """


def _kpi(valor: str, etiqueta: str, nota: str = "") -> str:
    nota_html = f'<span class="kpi-note">{_e(nota)}</span>' if nota else ""
    return f"""
    <div class="kpi">
      <strong>{_e(valor)}</strong>
      <span>{_e(etiqueta)}</span>
      {nota_html}
    </div>
    """


def _finding_card(f: Finding) -> str:
    color = SEV_COLOR.get(f.severity, "#475569")
    filas = ""
    if f.occurrences:
        items = []
        for o in f.occurrences:
            ubicacion = f"{o.file}:{o.line}" if o.line else o.file
            items.append(
                f'<li><code class="loc">{_e(ubicacion)}</code>'
                f'<span class="snippet">{_e(o.snippet)}</span></li>'
            )
        resto = f.total - len(f.occurrences)
        mas = f'<li class="more">y {_n(resto)} casos mas...</li>' if resto > 0 else ""
        filas = f'<ul class="occ">{ "".join(items) }{mas}</ul>'
    return f"""
    <article class="finding">
      <header>
        <span class="sev" style="background:{color}">{_e(SEV_LABEL.get(f.severity, f.severity))}</span>
        <h4>{_e(f.title)}</h4>
        <span class="count">{_n(f.count)} caso{'s' if f.count != 1 else ''}</span>
      </header>
      <p class="detail">{_e(f.detail)}</p>
      {filas}
    </article>
    """


def generar_html(report: Report) -> str:
    score = report.score
    s = report.schema
    total_findings = len(report.findings)
    altas = sum(1 for f in report.findings if f.severity == "alta")
    medias = sum(1 for f in report.findings if f.severity == "media")

    dimensiones = ""
    if score:
        for d in score.dimensions:
            color = "#16a34a" if d.value <= 25 else "#d97706" if d.value <= 50 else "#ea580c" if d.value <= 75 else "#dc2626"
            razones = "".join(f"<li>{_e(r)}</li>" for r in d.reasons)
            dimensiones += f"""
            <div class="dim">
              <div class="dim-head">
                <span>{_e(d.label)}</span>
                <strong style="color:{color}">{d.value}</strong>
              </div>
              {_barra(d.value, color)}
              <ul class="reasons">{razones}</ul>
            </div>
            """

    acciones = ""
    for a in report.actions:
        acciones += f"""
        <li class="action">
          <span class="prio">{a.priority}</span>
          <div>
            <strong>{_e(a.title)}</strong>
            <p>{_e(a.why)}</p>
          </div>
          <span class="effort effort-{a.effort}">{_e(a.effort)}</span>
        </li>
        """

    filas_tablas = ""
    for t in sorted(s.tables, key=lambda x: x.rows, reverse=True)[:40]:
        pk = "si" if t.has_primary_key else "no"
        fk = len(t.foreign_keys)
        filas_tablas += f"""
        <tr>
          <td><code>{_e(t.name)}</code></td>
          <td class="num">{_n(t.rows)}{'' if not t.rows_estimated else '*'}</td>
          <td class="num">{_n(len(t.columns))}</td>
          <td>{_e(t.engine or '-')}</td>
          <td class="{'ok' if t.has_primary_key else 'bad'}">{pk}</td>
          <td class="num">{fk}</td>
        </tr>
        """

    relaciones_conv = [r for r in report.relations if r.kind == "convencion"]
    relaciones_huerfanas = [r for r in report.relations if r.kind == "huerfana"]
    filas_rel = ""
    for r in (relaciones_conv + relaciones_huerfanas)[:40]:
        destino = r.target if r.target else "<sin tabla>"
        clase = "ok" if r.target else "bad"
        filas_rel += f"""
        <tr>
          <td><code>{_e(r.table)}.{_e(r.column)}</code></td>
          <td class="{clase}">{_e(destino)}</td>
          <td>{_e(r.kind)}</td>
        </tr>
        """

    secciones = ""
    for categoria, titulo in (("esquema", "Esquema"), ("seguridad", "Seguridad"), ("codigo", "Codigo")):
        hallazgos = report.by_category(categoria)
        if not hallazgos:
            continue
        tarjetas = "".join(_finding_card(f) for f in hallazgos)
        secciones += f"""
        <section>
          <h2>{_e(titulo)} <span class="h2-count">{len(hallazgos)} reglas</span></h2>
          <div class="findings">{tarjetas}</div>
        </section>
        """

    generado = report.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    score_html = _gauge(score.total, score.label) if score else ""

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>legacy-lens · {_e(report.title)}</title>
<style>
  :root {{
    --ink:#0f172a; --muted:#5b6679; --line:#e4e7f0; --bg:#f6f7fb; --card:#ffffff;
    --accent:#4f46e5; --accent-soft:#eef0ff;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    line-height:1.55; }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:40px 24px 72px; }}
  header.top {{ display:flex; flex-wrap:wrap; gap:24px; align-items:center; justify-content:space-between;
    background:var(--card); border:1px solid var(--line); border-radius:18px; padding:28px 32px; }}
  .brand {{ font-size:12px; letter-spacing:.16em; text-transform:uppercase; color:var(--accent); font-weight:700; }}
  h1 {{ margin:6px 0 6px; font-size:30px; letter-spacing:-.02em; }}
  .meta {{ color:var(--muted); font-size:13px; }}
  .gauge {{ display:flex; flex-direction:column; align-items:center; gap:4px; flex:0 0 auto; }}
  .gauge-ring {{ position:relative; width:160px; height:160px; }}
  .gauge-value {{ position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
    gap:1px; }}
  .gauge-value strong {{ font-size:38px; letter-spacing:-.03em; }}
  .gauge-value span {{ font-size:12px; color:var(--muted); transform:translateY(7px); }}
  .gauge-label {{ text-align:center; font-size:12px; font-weight:700; text-transform:uppercase;
    letter-spacing:.1em; }}
  .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin:22px 0 8px; }}
  .kpi {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px 18px; }}
  .kpi strong {{ display:block; font-size:24px; letter-spacing:-.02em; }}
  .kpi span {{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; }}
  .kpi-note {{ display:block; margin-top:4px; font-size:11px; color:var(--muted); text-transform:none; letter-spacing:0; }}
  section {{ margin-top:34px; }}
  h2 {{ font-size:19px; margin:0 0 14px; display:flex; align-items:center; gap:10px; }}
  .h2-count {{ font-size:12px; font-weight:600; color:var(--muted); background:var(--accent-soft);
    border-radius:999px; padding:2px 10px; }}
  .dims {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; }}
  .dim {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px 18px; }}
  .dim-head {{ display:flex; justify-content:space-between; font-size:13px; font-weight:600; margin-bottom:8px; }}
  .bar {{ height:8px; background:#eceef6; border-radius:999px; overflow:hidden; }}
  .bar span {{ display:block; height:100%; border-radius:999px; }}
  .reasons {{ margin:10px 0 0; padding-left:16px; font-size:12px; color:var(--muted); }}
  .actions {{ list-style:none; margin:0; padding:0; display:grid; gap:10px; }}
  .action {{ display:flex; gap:14px; align-items:flex-start; background:var(--card);
    border:1px solid var(--line); border-radius:14px; padding:14px 18px; }}
  .action p {{ margin:2px 0 0; font-size:13px; color:var(--muted); }}
  .prio {{ flex:0 0 auto; width:26px; height:26px; border-radius:50%; background:var(--accent);
    color:#fff; font-size:13px; font-weight:700; display:flex; align-items:center; justify-content:center; }}
  .effort {{ margin-left:auto; font-size:11px; text-transform:uppercase; letter-spacing:.08em;
    border-radius:999px; padding:3px 10px; border:1px solid var(--line); color:var(--muted); }}
  .effort-alto {{ color:#b91c1c; border-color:#fecaca; background:#fef2f2; }}
  .effort-medio {{ color:#b45309; border-color:#fde68a; background:#fffbeb; }}
  .effort-bajo {{ color:#15803d; border-color:#bbf7d0; background:#f0fdf4; }}
  .table-wrap {{ overflow-x:auto; background:var(--card); border:1px solid var(--line);
    border-radius:14px; }}
  .table-wrap table {{ border:none; border-radius:0; min-width:520px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line);
    border-radius:14px; overflow:hidden; font-size:13px; }}
  th, td {{ text-align:left; padding:10px 14px; border-bottom:1px solid var(--line); }}
  th {{ font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); background:#fbfbfe; }}
  tr:last-child td {{ border-bottom:none; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  code {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:12px;
    background:#f2f3f9; padding:1px 6px; border-radius:6px; }}
  .ok {{ color:#15803d; }} .bad {{ color:#b91c1c; }}
  .findings {{ display:grid; gap:12px; }}
  .finding {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px 18px; }}
  .finding header {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
  .finding h4 {{ margin:0; font-size:15px; }}
  .sev {{ color:#fff; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.08em;
    border-radius:999px; padding:2px 9px; }}
  .count {{ margin-left:auto; font-size:12px; color:var(--muted); font-variant-numeric:tabular-nums; }}
  .detail {{ margin:6px 0 0; font-size:13px; color:var(--muted); }}
  .occ {{ list-style:none; margin:10px 0 0; padding:0; display:grid; gap:4px; }}
  .occ li {{ display:flex; gap:10px; font-size:12px; align-items:baseline; }}
  .loc {{ flex:0 0 auto; color:var(--accent); background:var(--accent-soft); }}
  .snippet {{ color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .more {{ color:var(--muted); font-style:italic; }}
  footer {{ margin-top:44px; color:var(--muted); font-size:12px; border-top:1px solid var(--line); padding-top:16px; }}
  @media (max-width:640px) {{
    .wrap {{ padding:20px 14px 48px; }}
    header.top {{ padding:20px; }}
    h1 {{ font-size:23px; }}
    .snippet {{ white-space:normal; }}
  }}
  @media print {{
    body {{ background:#fff; }}
    .wrap {{ max-width:none; padding:0; }}
    .finding, .kpi, .dim, table, .action {{ break-inside:avoid; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div>
      <div class="brand">legacy-lens · radiografia de un sistema legacy</div>
      <h1>{_e(report.title)}</h1>
      <div class="meta">
        Codigo: <code>{_e(report.target_path or '-')}</code> ·
        Esquema: <code>{_e(s.source or '-')}</code> ·
        Generado: {_e(generado)}
      </div>
    </div>
    {score_html}
  </header>

  <div class="kpis">
    {_kpi(_n(len(s.tables)), "tablas")}
    {_kpi(_n(s.columns), "columnas")}
    {_kpi(_n(s.rows) if s.rows else "-", "filas", "estimadas" if s.rows and any(t.rows_estimated for t in s.tables) else ("exactas" if s.rows else "sin conteos"))}
    {_kpi(_bytes(s.size_bytes) if s.size_bytes else "-", "tamano en disco")}
    {_kpi(_n(report.code.files), "archivos PHP")}
    {_kpi(_n(report.code.loc), "lineas")}
    {_kpi(_n(altas), "hallazgos altos")}
    {_kpi(_n(medias), "hallazgos medios")}
  </div>

  <section>
    <h2>Indice de dolor de migracion</h2>
    <div class="dims">{dimensiones}</div>
  </section>

  <section>
    <h2>Plan de accion</h2>
    <ol class="actions">{acciones}</ol>
  </section>

  {secciones}

  <section>
    <h2>Tablas <span class="h2-count">{_n(len(s.tables))}</span></h2>
    <div class="table-wrap">
    <table>
      <thead><tr><th>Tabla</th><th class="num">Filas</th><th class="num">Columnas</th>
      <th>Motor</th><th>PK</th><th class="num">FK</th></tr></thead>
      <tbody>{filas_tablas}</tbody>
    </table>
    </div>
  </section>

  <section>
    <h2>Relaciones inferidas <span class="h2-count">{_n(len(report.relations))}</span></h2>
    <div class="table-wrap">
    <table>
      <thead><tr><th>Columna</th><th>Destino</th><th>Tipo</th></tr></thead>
      <tbody>{filas_rel}</tbody>
    </table>
    </div>
  </section>

  <footer>
    <p><strong>legacy-lens</strong> analiza por heuristica: los hallazgos de codigo son candidatos a revisar,
    no una auditoria formal. Los secretos se muestran enmascarados a proposito.</p>
    <p>{_n(total_findings)} reglas con hallazgos · {_n(len(report.relations))} relaciones inferidas ·
    puntaje calculado con pesos esquema 30% / codigo 25% / seguridad 20% / datos 15% / modernidad 10%.</p>
  </footer>
</div>
</body>
</html>
"""


def generar_markdown(report: Report) -> str:
    s = report.schema
    lineas = [
        f"# legacy-lens · {report.title}",
        "",
        f"- Codigo: `{report.target_path}`",
        f"- Esquema: `{s.source}`",
        f"- Tablas: **{len(s.tables)}** · Columnas: **{s.columns}** · Filas: **{_n(s.rows)}**",
        f"- Archivos PHP: **{report.code.files}** · Lineas: **{_n(report.code.loc)}**",
    ]
    if report.score:
        lineas += [
            "",
            f"## Indice de dolor: **{report.score.total}/100** ({report.score.label})",
            "",
            "| Dimension | Valor | Peso |",
            "|---|---:|---:|",
        ]
        for d in report.score.dimensions:
            lineas.append(f"| {d.label} | {d.value} | {int(d.weight * 100)}% |")
    if report.actions:
        lineas += ["", "## Plan de accion", ""]
        for a in report.actions:
            lineas.append(f"{a.priority}. **{a.title}** ({a.effort}) — {a.why}")
    for categoria in ("esquema", "seguridad", "codigo"):
        hallazgos = report.by_category(categoria)
        if not hallazgos:
            continue
        lineas += ["", f"## {CAT_LABEL.get(categoria, categoria)}", ""]
        for f in hallazgos:
            lineas.append(f"- **{f.title}** — {f.count} caso(s), {f.affected_files} archivo(s)")
    lineas += ["", "---", "_Generado con legacy-lens._"]
    return "\n".join(lineas) + "\n"


def generar_json(report: Report) -> str:
    return json.dumps(report.as_dict(), ensure_ascii=False, indent=2)


def escribir(report: Report, out_dir: str, formatos: tuple[str, ...] = ("html", "json", "md")) -> list[str]:
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)
    generados: list[str] = []
    if "html" in formatos:
        destino = base / "report.html"
        destino.write_text(generar_html(report), encoding="utf-8")
        generados.append(str(destino))
    if "json" in formatos:
        destino = base / "report.json"
        destino.write_text(generar_json(report), encoding="utf-8")
        generados.append(str(destino))
    if "md" in formatos:
        destino = base / "report.md"
        destino.write_text(generar_markdown(report), encoding="utf-8")
        generados.append(str(destino))
    return generados
