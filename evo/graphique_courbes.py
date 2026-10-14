"""Graphique des courbes du duel (v2) : une figure par manche, meilleure hauteur accrochée en fonction du nombre de
lézards testés (échelle log), un trait par joueur (moyenne des graines ou tirages) et sa bande (min–max), repères à 50
et 200 essais (budgets du joueur LLM), infobulle au survol et tableau de valeurs. Page HTML autonome, clair et sombre.

Entrée : les résumés `*_resume.json` d'evo/courbes.py (runs d'évolution et tirages du hasard), rangés par joueur :
évolution à corps libre (`frozen_body` faux), évolution à corps figé, hasard pur de la manche.
"""
import glob
import json
import os

import numpy as np

import config

JOUEURS = (("evolution", "Évolution (corps libre)", "--series-1"),
           ("corps_fige", "Évolution à corps figé", "--series-2"),
           ("hasard", "Hasard pur", "--series-3"))
REPERES = ((config.DUEL_BUDGET_ANNONCE, "50 essais"), (config.DUEL_BUDGET_MAX, "200 essais"))
POINTS_TABLE = (1, 10, 50, 200, 1000, 10000, 100000)
MANCHES = ((1, "Manche 1 : le chorégraphe (corps imposé)"), (2, "Manche 2 : le créateur (corps libre)"))


def _joueur(resume):
    if resume["source"] == "hasard":
        return "hasard", resume["manche"]
    return ("corps_fige" if resume["frozen_body"] else "evolution"), None


def lire_resumes(dossier):
    """Résumés *_resume.json d'un dossier (récursif) : {(joueur, manche du hasard ou None): [résumés]}."""
    out = {}
    for path in sorted(glob.glob(os.path.join(dossier, "**", "*_resume.json"), recursive=True)):
        with open(path, encoding="utf-8") as fh:
            r = json.load(fh)
        out.setdefault(_joueur(r), []).append(r)
    return out


def escalier(resume, n):
    """Meilleure hauteur accrochée après n évaluations (n ≤ total), d'après les paliers du résumé."""
    ev_, h = np.array(resume["paliers"], dtype=float).T
    return float(h[np.searchsorted(ev_, n, side="right") - 1])


def serie(resumes):
    """(n, moyenne, min, max) sur une grille de 1 au plus petit total : chaque entier jusqu'à 1 000, puis une grille log,
    plus chaque palier (les marches de l'escalier tombent juste)."""
    total = min(r["evaluations"] for r in resumes)
    parts = [np.arange(1, min(total, 1000) + 1), [total], [n for r in resumes for n, _ in r["paliers"] if n <= total]]
    if total > 1000:
        parts.append(np.round(np.logspace(3, np.log10(total), 400)).astype(int))
    grid = np.unique(np.concatenate([np.asarray(p, dtype=int) for p in parts]))
    values = np.array([[escalier(r, n) for n in grid] for r in resumes])
    return grid, values.mean(axis=0), values.min(axis=0), values.max(axis=0)


def donnees(dossier):
    """Données des figures (une par manche) pour la page."""
    res = lire_resumes(dossier)
    figures = []
    for manche, titre in MANCHES:
        series = []
        for key, label, var in JOUEURS:
            rs = res.get((key, manche) if key == "hasard" else (key, None), [])
            if not rs:
                continue
            n, mean, lo, hi = serie(rs)
            kind = "tirages" if key == "hasard" else "graines"
            series.append({"cle": key, "label": label, "var": var, "n": n.tolist(), "moy": mean.round(3).tolist(),
                           "min": lo.round(3).tolist(), "max": hi.round(3).tolist(),
                           "detail": f"{len(rs)} {kind}, {min(r['evaluations'] for r in rs)} évaluations",
                           "finales": [round(r["meilleure_hauteur_accrochee"], 2) for r in rs]})
        figures.append({"manche": manche, "titre": titre, "series": series})
    return {"figures": figures, "reperes": REPERES, "table": POINTS_TABLE}


def graphique(dossier, sortie, titre="Gecko v2 : courbes des témoins"):
    """Écrit la page HTML ; renvoie son chemin."""
    page = _PAGE.replace("__TITRE__", titre).replace("__DONNEES__", json.dumps(donnees(dossier), ensure_ascii=False))
    os.makedirs(os.path.dirname(os.path.abspath(sortie)), exist_ok=True)
    with open(sortie, "w", encoding="utf-8") as fh:
        fh.write(page)
    return sortie


_PAGE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITRE__</title>
<style>
.viz-root { color-scheme: light; --surface-1:#fcfcfb; --page:#f9f9f7; --text-primary:#0b0b0b; --text-secondary:#52514e;
  --muted:#898781; --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,0.10);
  --series-1:#2a78d6; --series-2:#eb6834; --series-3:#1baf7a; }
@media (prefers-color-scheme: dark) { :root:where(:not([data-theme="light"])) .viz-root { color-scheme: dark;
  --surface-1:#1a1a19; --page:#0d0d0d; --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10); --series-1:#3987e5; --series-2:#d95926;
  --series-3:#199e70; } }
:root[data-theme="dark"] .viz-root { color-scheme: dark; --surface-1:#1a1a19; --page:#0d0d0d; --text-primary:#ffffff;
  --text-secondary:#c3c2b7; --muted:#898781; --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
  --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70; }
html, body { margin:0; }
body.viz-root { background:var(--page); color:var(--text-primary); font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width:980px; margin:0 auto; padding:24px 16px 48px; }
h1 { font-size:20px; margin:0 0 4px; }
p.lead { color:var(--text-secondary); margin:0 0 20px; }
section { background:var(--surface-1); border:1px solid var(--border); border-radius:10px; padding:16px; margin-bottom:24px; }
h2 { font-size:16px; margin:0 0 8px; }
.legend { display:flex; flex-wrap:wrap; gap:6px 18px; margin:0 0 8px; color:var(--text-secondary); font-size:13px; }
.sw { display:inline-block; width:14px; height:3px; border-radius:2px; margin-right:6px; vertical-align:middle; }
.chart { position:relative; }
svg { display:block; width:100%; height:auto; overflow:visible; }
.tick { fill:var(--muted); font-size:11px; font-variant-numeric:tabular-nums; }
.lab { fill:var(--text-secondary); font-size:12px; }
.tip { position:absolute; pointer-events:none; background:var(--surface-1); border:1px solid var(--border);
  border-radius:8px; padding:8px 10px; font-size:12px; box-shadow:0 4px 14px rgba(0,0,0,.12); display:none; white-space:nowrap; }
.tip b { font-variant-numeric:tabular-nums; }
.muted { color:var(--muted); }
table { border-collapse:collapse; width:100%; margin-top:12px; font-size:12.5px; }
th, td { padding:4px 8px; border-bottom:1px solid var(--grid); text-align:right; font-variant-numeric:tabular-nums; }
th:first-child, td:first-child { text-align:left; }
th { color:var(--text-secondary); font-weight:600; }
details summary { cursor:pointer; color:var(--text-secondary); margin-top:8px; }
@media (max-width:600px) { section { padding:10px; } .legend { font-size:12px; } }
</style></head>
<body class="viz-root"><main>
<h1>__TITRE__</h1>
<p class="lead">Meilleure hauteur accrochée (m) en fonction du nombre de lézards testés, échelle logarithmique.
Trait : moyenne des 3 graines (ou tirages) ; bande : du minimum au maximum. Chiffres recalculés sur le runner GitHub.</p>
<div id="figs"></div>
</main>
<script>
const D = __DONNEES__;
const W = 920, H = 420, M = {l:52, r:170, t:16, b:44};
const fmt = v => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(2).replace(".", ",");
const NS = "http://www.w3.org/2000/svg";
function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}
function at(s, n) {                       // indice du dernier point de grille <= n (null avant le début ou après la fin)
  if (n > s.n[s.n.length - 1]) return null;
  let i = s.n.findIndex(x => x > n);
  i = (i === -1 ? s.n.length : i) - 1;
  return i < 0 ? null : i;
}
const short = s => s.label.split(" (")[0];
for (const f of D.figures) {
  const sec = document.createElement("section");
  sec.innerHTML = `<h2>${f.titre}</h2>`;
  const leg = document.createElement("div");
  leg.className = "legend";
  for (const s of f.series)
    leg.innerHTML += `<span><span class="sw" style="background:var(${s.var})"></span>${s.label} <span class="muted">(${s.detail})</span></span>`;
  sec.appendChild(leg);
  const box = document.createElement("div");
  box.className = "chart";
  sec.appendChild(box);
  const svg = el("svg", {viewBox:`0 0 ${W} ${H}`, role:"img", "aria-label":f.titre}, box);
  const all = f.series.flatMap(s => s.min.concat(s.max));
  const y0 = Math.floor(Math.min(...all) / 10) * 10, y1 = Math.ceil(Math.max(...all) / 10) * 10;
  const xmax = Math.max(...f.series.map(s => s.n[s.n.length - 1]));
  const L = Math.log10(Math.max(xmax, 10));
  const X = n => M.l + (Math.log10(n) / L) * (W - M.l - M.r);
  const Y = v => M.t + (1 - (v - y0) / (y1 - y0)) * (H - M.t - M.b);
  for (let v = y0; v <= y1; v += 10) {
    el("line", {x1:M.l, x2:W - M.r, y1:Y(v), y2:Y(v), stroke: v === 0 ? "var(--axis)" : "var(--grid)", "stroke-width":1}, svg);
    el("text", {x:M.l - 8, y:Y(v) + 4, "text-anchor":"end", class:"tick"}, svg).textContent = (v > 0 ? "+" : "") + v;
  }
  for (let p = 0; Math.pow(10, p) <= xmax; p++) {
    const n = Math.pow(10, p);
    el("line", {x1:X(n), x2:X(n), y1:M.t, y2:H - M.b, stroke:"var(--grid)", "stroke-width":1}, svg);
    el("text", {x:X(n), y:H - M.b + 18, "text-anchor":"middle", class:"tick"}, svg).textContent = n.toLocaleString("fr-FR");
  }
  el("text", {x:(M.l + W - M.r) / 2, y:H - 6, "text-anchor":"middle", class:"lab"}, svg).textContent = "lézards testés (évaluations)";
  const cy = (M.t + H - M.b) / 2;
  el("text", {x:14, y:cy, "text-anchor":"middle", class:"lab", transform:`rotate(-90 14 ${cy})`}, svg).textContent = "meilleure hauteur accrochée (m)";
  for (const [n, txt] of D.reperes) {
    if (n > xmax) continue;
    el("line", {x1:X(n), x2:X(n), y1:M.t, y2:H - M.b, stroke:"var(--axis)", "stroke-width":1}, svg);
    el("text", {x:X(n) + 4, y:M.t + 12, class:"tick"}, svg).textContent = txt;
  }
  const stairs = (s, key) => s.n.map((n, i) => i === 0 ? `M${X(n).toFixed(1)} ${Y(s[key][0]).toFixed(1)}`
                                                         : `H${X(n).toFixed(1)}V${Y(s[key][i]).toFixed(1)}`).join("");
  const ends = [];
  for (const s of f.series) {
    const last = s.n.length - 1;
    let band = stairs(s, "max");
    for (let i = last; i >= 0; i--) band += `L${X(s.n[i]).toFixed(1)} ${Y(s.min[i]).toFixed(1)}` + (i > 0 ? `L${X(s.n[i]).toFixed(1)} ${Y(s.min[i - 1]).toFixed(1)}` : "");
    el("path", {d:band + "Z", fill:`var(${s.var})`, opacity:0.16}, svg);
    el("path", {d:stairs(s, "moy"), fill:"none", stroke:`var(${s.var})`, "stroke-width":2, "stroke-linejoin":"round"}, svg);
    ends.push({s, x:X(s.n[last]), yv:Y(s.moy[last]), y:Y(s.moy[last])});
  }
  ends.sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 15) ends[i].y = ends[i - 1].y + 15;
  for (const e of ends) {
    el("circle", {cx:e.x, cy:e.yv, r:4, fill:`var(${e.s.var})`, stroke:"var(--surface-1)", "stroke-width":2}, svg);
    el("text", {x:e.x + 8, y:e.y + 4, class:"lab"}, svg).textContent = `${short(e.s)} ${fmt(e.s.moy[e.s.moy.length - 1])} m`;
  }
  const cross = el("line", {y1:M.t, y2:H - M.b, stroke:"var(--muted)", "stroke-width":1, visibility:"hidden"}, svg);
  const tip = document.createElement("div");
  tip.className = "tip";
  box.appendChild(tip);
  const hit = el("rect", {x:M.l, y:M.t, width:W - M.l - M.r, height:H - M.t - M.b, fill:"transparent"}, svg);
  hit.addEventListener("mousemove", ev => {
    const r = svg.getBoundingClientRect();
    const px = (ev.clientX - r.left) * W / r.width;
    const n = Math.max(1, Math.round(Math.pow(10, (px - M.l) / (W - M.l - M.r) * L)));
    cross.setAttribute("x1", X(n)); cross.setAttribute("x2", X(n)); cross.setAttribute("visibility", "visible");
    let html = `<div class="muted">${n.toLocaleString("fr-FR")} lézards testés</div>`;
    for (const s of f.series) {
      const i = at(s, n);
      if (i === null) continue;
      html += `<div><span class="sw" style="background:var(${s.var})"></span>${short(s)} : <b>${fmt(s.moy[i])} m</b> <span class="muted">(${fmt(s.min[i])} à ${fmt(s.max[i])})</span></div>`;
    }
    tip.innerHTML = html;
    tip.style.display = "block";
    const bx = box.getBoundingClientRect();
    let left = ev.clientX - bx.left + 14;
    if (left + tip.offsetWidth > bx.width) left = ev.clientX - bx.left - tip.offsetWidth - 14;
    tip.style.left = left + "px";
    tip.style.top = (ev.clientY - bx.top + 10) + "px";
  });
  hit.addEventListener("mouseleave", () => { tip.style.display = "none"; cross.setAttribute("visibility", "hidden"); });
  const det = document.createElement("details");
  det.open = true;
  let t = `<summary>Tableau des valeurs (moyenne, et du minimum au maximum)</summary><table><tr><th>Lézards testés</th>${f.series.map(s => `<th>${short(s)}</th>`).join("")}</tr>`;
  for (const n of D.table) {
    if (n > xmax) continue;
    t += `<tr><td>${n.toLocaleString("fr-FR")}</td>` + f.series.map(s => {
      const i = at(s, n);
      return i === null ? "<td>—</td>" : `<td>${fmt(s.moy[i])} <span class="muted">(${fmt(s.min[i])} à ${fmt(s.max[i])})</span></td>`;
    }).join("") + "</tr>";
  }
  t += `<tr><td>Fin de chaque courbe</td>` + f.series.map(s => `<td>${s.finales.map(fmt).join(" / ")}</td>`).join("") + "</tr></table>";
  det.innerHTML = t;
  sec.appendChild(det);
  document.getElementById("figs").appendChild(sec);
}
</script></body></html>
"""
