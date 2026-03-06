"""
generate_mindmap.py
Usage:  python generate_mindmap.py <path-to-insight-json>
Output: mindmap-variation1-YYYYMMDD.html  (cwd)

Microfrontend-ready:
  - All markup lives inside #it-root  (fills 100% of host container)
  - No 100vh / viewport-unit assumptions
  - CSS scoped to #it-root to avoid shell style leakage
  - Right panel with Details + Filters tabs (no floating overlays)
  - Horizontal collapsible D3 tree, light professional theme
"""

import json, re, os, sys
from pathlib import Path


# ── helpers ───────────────────────────────────────────────────────

def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def date_from_name(p):
    m = re.search(r"(\d{8})", Path(p).stem)
    return m.group(1) if m else "00000000"

def fmt_date(d):
    try:
        from datetime import datetime
        return datetime.strptime(d, "%Y%m%d").strftime("%b %d, %Y")
    except Exception:
        return d


# ── hierarchy builders ────────────────────────────────────────────

def agg(topics):
    scores = [t.get("priorityScore", 0) for t in topics]
    return {
        "topicCount":  len(topics),
        "escalations": sum(1 for t in topics if t.get("escalation")),
        "blockers":    sum(1 for t in topics if t.get("blockers")),
        "maxPriority": max(scores) if scores else 0,
    }

def topic_node(t):
    return {
        "id":            t.get("clusterId", ""),
        "name":          t.get("topicTitle", "Untitled"),
        "type":          "topic",
        "state":         t.get("state", ""),
        "summary":       t.get("summary", ""),
        "next":          t.get("next", ""),
        "owner":         t.get("owner", ""),
        "sentiment":     t.get("sentiment", ""),
        "escalation":    bool(t.get("escalation")),
        "blockers":      bool(t.get("blockers")),
        "priorityScore": t.get("priorityScore", 0),
        "timestamp":     t.get("timestamp", ""),
        "children":      [],
    }

def build_v1(data):
    root = {"id": "root", "name": "Daily Summary \u2014 " + fmt_date(data.get("date", "")), "type": "root", "children": []}
    for ck, cv in data.get("clients", {}).items():
        all_t = []
        cn = {"id": "c-" + ck, "name": ck, "type": "client", "children": []}
        for pk, pv in cv.get("projects", {}).items():
            ts = pv.get("topics", [])
            all_t.extend(ts)
            cn["children"].append({"id": "p-" + ck + "-" + pk, "name": pk, "type": "project", "agg": agg(ts), "children": [topic_node(t) for t in ts]})
        cn["agg"] = agg(all_t)
        root["children"].append(cn)
    return root

def build_v2(data):
    by_proj = {}
    for ck, cv in data.get("clients", {}).items():
        for pk, pv in cv.get("projects", {}).items():
            by_proj.setdefault(pk, {}).setdefault(ck, []).extend(pv.get("topics", []))
    root = {"id": "root", "name": "Daily Summary \u2014 " + fmt_date(data.get("date", "")), "type": "root", "children": []}
    for pk, cm in by_proj.items():
        all_t = [t for ts in cm.values() for t in ts]
        pn = {"id": "p2-" + pk, "name": pk, "type": "project", "agg": agg(all_t), "children": []}
        for ck, ts in cm.items():
            pn["children"].append({"id": "c2-" + pk + "-" + ck, "name": ck, "type": "client", "agg": agg(ts), "children": [topic_node(t) for t in ts]})
        root["children"].append(pn)
    return root


# ── HTML ──────────────────────────────────────────────────────────

def make_html(h1, h2, date_str):
    dd = fmt_date(date_str)
    j1 = json.dumps(h1)
    j2 = json.dumps(h2)

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>InsightTree &mdash; """ + dd + """</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=DM+Serif+Display&display=swap" rel="stylesheet"/>
<style>
/* ── Scoped reset: only affects #it-root descendants ── */
#it-root,#it-root *,#it-root *::before,#it-root *::after{
  box-sizing:border-box; margin:0; padding:0;
}
/* Host shell sets the container's dimensions.
   html/body rules are minimal so the component works
   both in an iframe and mounted directly into a div.   */
html,body{ height:100%; }

/* ═══════════════════════════════════════════════════════
   ROOT CONTAINER  — fills whatever host gives it
   ═══════════════════════════════════════════════════════ */
#it-root{
  /* design tokens */
  --bg:      #f2f4f8;
  --surf:    #ffffff;
  --surf2:   #eef0f5;
  --surf3:   #e5e8f0;
  --bdr:     #dde1ea;
  --bdr2:    #c3cad8;
  --txt:     #1a202c;
  --txt2:    #4a5568;
  --muted:   #8896aa;
  --accent:  #2563eb;
  --acc-bg:  #eff6ff;
  --p5:      #e74c3c;
  --p4:      #e67e22;
  --p3:      #c9940f;
  --p2:      #27ae60;
  --pw:      300px;       /* right panel width */
  --hd:      'DM Serif Display', Georgia, serif;
  --bd:      'DM Sans', sans-serif;

  width:100%; height:100%;
  display:flex; flex-direction:column;
  font-family:var(--bd);
  color:var(--txt);
  background:var(--bg);
  overflow:hidden;
  min-height:300px; min-width:480px;
}

/* ── Header ─────────────────────────────────────────── */
#it-hd{
  display:flex; align-items:center; gap:12px;
  padding:0 16px; height:50px; flex-shrink:0;
  background:var(--surf); border-bottom:1px solid var(--bdr);
  box-shadow:0 1px 4px rgba(0,0,0,.06); z-index:20;
}
.it-logo{ font-family:var(--hd); font-size:19px; letter-spacing:-.3px; white-space:nowrap; }
.it-logo em{ color:var(--accent); font-style:normal; }
.it-date{
  font-size:11px; font-weight:500; color:var(--muted);
  background:var(--surf2); border:1px solid var(--bdr);
  border-radius:20px; padding:2px 10px;
}
.it-seg{
  display:flex; border:1px solid var(--bdr); border-radius:7px;
  overflow:hidden; margin-left:auto; flex-shrink:0;
}
.it-seg-btn{
  padding:5px 12px; font-size:11px; font-weight:500;
  font-family:var(--bd); background:var(--surf); border:none;
  cursor:pointer; color:var(--muted); transition:all .16s; white-space:nowrap;
}
.it-seg-btn:not(:last-child){ border-right:1px solid var(--bdr); }
.it-seg-btn.on{ background:var(--accent); color:#fff; }

/* ── Hint bar ───────────────────────────────────────── */
#it-hints{
  display:flex; align-items:center; gap:16px;
  padding:3px 16px; background:var(--surf2);
  border-bottom:1px solid var(--bdr);
  font-size:10px; color:var(--muted); flex-shrink:0;
}
#it-hints span{ display:flex; align-items:center; gap:4px; }
.it-kbd{
  background:var(--surf); border:1px solid var(--bdr2);
  border-radius:3px; padding:0 5px;
  font-size:9.5px; color:var(--txt2); font-family:monospace; line-height:1.7;
}

/* ── Body row ───────────────────────────────────────── */
#it-body{ flex:1; display:flex; overflow:hidden; }

/* ═══════════════════════════════════════════════════════
   CANVAS
   ═══════════════════════════════════════════════════════ */
#it-cv{
  flex:1; overflow:hidden; position:relative;
  background:var(--bg);
  background-image:radial-gradient(circle,#bcc3d0 1px,transparent 1px);
  background-size:26px 26px;
}
#it-cv svg{ width:100%; height:100%; }

/* links */
.it-link{ fill:none; stroke:#c0c7d6; stroke-width:1.8px; }

/* node foreignObject */
.it-fo{ overflow:visible; }

/* node card */
.it-card{
  background:var(--surf); border:1.5px solid var(--bdr); border-radius:9px;
  display:flex; align-items:stretch; cursor:pointer;
  transition:box-shadow .18s, border-color .18s, transform .14s;
  box-shadow:0 1px 4px rgba(0,0,0,.07);
  overflow:hidden; user-select:none; font-family:var(--bd);
}
.it-card:hover{ box-shadow:0 5px 18px rgba(0,0,0,.13); border-color:var(--accent); transform:translateY(-1px); }
.it-card.root-c{ background:var(--accent); border-color:var(--accent); }
.it-card.sel{ border-color:var(--accent); box-shadow:0 0 0 3px rgba(37,99,235,.2); }
.it-card.dim{ opacity:.18; pointer-events:none; }
.it-link.dim{ opacity:.07; }

/* card parts */
.it-bar{ width:4px; flex-shrink:0; background:var(--bdr2); }
.it-bar.p5{ background:var(--p5); }
.it-bar.p4{ background:var(--p4); }
.it-bar.p3{ background:var(--p3); }
.it-bar.p2,.it-bar.p1{ background:var(--p2); }
.it-bar.client{ background:#7c3aed; }
.it-bar.project{ background:#0284c7; }
.it-bar.root{ background:rgba(255,255,255,.35); }

.it-ico{ width:34px; flex-shrink:0; display:flex; align-items:center; justify-content:center; }
.it-ico svg{ width:16px; height:16px; }

.it-cb{ flex:1; padding:6px 6px 6px 2px; min-width:0; display:flex; flex-direction:column; justify-content:center; gap:2px; }
.it-cn{ font-size:11.5px; font-weight:600; color:var(--txt); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; line-height:1.3; }
.root-c .it-cn{ color:#fff; font-size:12px; }
.it-cs{ font-size:9.5px; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:flex; align-items:center; gap:4px; }
.it-badge{ display:inline-flex; align-items:center; gap:2px; font-size:8.5px; font-weight:700; padding:1px 5px; border-radius:3px; }
.it-badge.e{ background:#fef2f2; color:#dc2626; }
.it-badge.b{ background:#fff7ed; color:#c2410c; }
.it-chev{ width:20px; flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:12px; color:var(--muted); }

/* ── Hover tooltip (client/project only) ──────────────── */
#it-tt{
  position:absolute; background:var(--surf);
  border:1px solid var(--bdr); border-radius:9px;
  padding:12px 14px; max-width:260px; min-width:200px;
  font-size:11.5px; line-height:1.55;
  pointer-events:none; opacity:0;
  transform:translateY(6px) scale(.98);
  transition:opacity .16s,transform .16s;
  z-index:100; box-shadow:0 8px 28px rgba(0,0,0,.13);
}
#it-tt.show{ opacity:1; transform:translateY(0) scale(1); }
.tt-title{ font-family:var(--hd); font-size:13px; color:var(--txt); margin-bottom:8px; line-height:1.3; }
.tt-grid{ display:grid; grid-template-columns:repeat(3,1fr); gap:5px; margin-bottom:6px; }
.tt-cell{ background:var(--surf2); border-radius:6px; padding:6px 7px; text-align:center; }
.tt-num{ font-size:17px; font-weight:700; font-family:var(--hd); color:var(--txt); line-height:1; }
.tt-lbl{ font-size:8.5px; color:var(--muted); margin-top:2px; font-weight:500; text-transform:uppercase; letter-spacing:.04em; }

/* ── Zoom controls ────────────────────────────────────── */
.it-zc{ position:absolute; bottom:14px; left:14px; display:flex; flex-direction:column; gap:4px; z-index:10; }
.it-zb{ width:30px; height:30px; background:var(--surf); border:1px solid var(--bdr); border-radius:6px; display:flex; align-items:center; justify-content:center; cursor:pointer; font-size:15px; color:var(--txt2); box-shadow:0 1px 4px rgba(0,0,0,.07); transition:all .14s; font-family:monospace; }
.it-zb:hover{ background:var(--acc-bg); color:var(--accent); border-color:var(--accent); }

/* ═══════════════════════════════════════════════════════
   RIGHT PANEL
   ═══════════════════════════════════════════════════════ */
#it-panel{
  width:var(--pw); flex-shrink:0;
  display:flex; flex-direction:column;
  background:var(--surf);
  border-left:1px solid var(--bdr);
}

/* tab bar */
#it-tabs{
  display:flex; border-bottom:1px solid var(--bdr);
  background:var(--surf2); flex-shrink:0;
}
.it-tab{
  flex:1; padding:10px 0; font-size:11.5px; font-weight:500;
  font-family:var(--bd); background:transparent; border:none;
  cursor:pointer; color:var(--muted); transition:all .16s;
  border-bottom:2px solid transparent; position:relative; top:1px;
  display:flex; align-items:center; justify-content:center; gap:6px;
}
.it-tab svg{ width:13px; height:13px; opacity:.7; }
.it-tab.on{ color:var(--accent); border-bottom-color:var(--accent); background:var(--surf); }
.it-tab:hover:not(.on){ color:var(--txt2); }

/* tab panes */
.it-pane{ display:none; flex:1; flex-direction:column; overflow:hidden; }
.it-pane.on{ display:flex; }

/* ── Details pane ─────────────────────────────────────── */
#it-det{ overflow-y:auto; padding:16px; gap:0; }

/* empty state */
.it-empty{
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  flex:1; gap:10px; padding:32px 16px; text-align:center;
  color:var(--muted);
}
.it-empty svg{ width:36px; height:36px; opacity:.3; }
.it-empty p{ font-size:12px; line-height:1.5; }

/* detail content */
.det-title{
  font-family:var(--hd); font-size:14.5px; color:var(--txt);
  line-height:1.35; margin-bottom:10px;
}
.det-div{ height:1px; background:var(--bdr); margin:10px 0; }
.det-row{ display:flex; gap:8px; margin-bottom:6px; align-items:flex-start; }
.det-key{ font-size:10.5px; color:var(--muted); min-width:58px; flex-shrink:0; padding-top:2px; font-weight:500; }
.det-val{ font-size:11.5px; color:var(--txt2); line-height:1.45; }
.det-stars span{ font-size:13px; }
.det-star-on{ color:#f59e0b; }
.det-star-off{ color:var(--bdr2); }
.det-flags{ display:flex; gap:6px; flex-wrap:wrap; }
.det-flag{ display:inline-flex; align-items:center; gap:4px; font-size:10px; font-weight:600; padding:3px 9px; border-radius:5px; letter-spacing:.03em; }
.det-flag.esc{ background:#fef2f2; color:#dc2626; border:1px solid #fecaca; }
.det-flag.blk{ background:#fff7ed; color:#c2410c; border:1px solid #fed7aa; }
.det-flag.ok{ background:#f0fdf4; color:#16a34a; border:1px solid #bbf7d0; }
.det-summary{
  font-size:11px; color:var(--txt2); line-height:1.65;
  background:var(--surf2); border-radius:7px; padding:9px 11px;
  margin-top:2px; border-left:3px solid var(--accent);
}
.det-pbar-wrap{ height:5px; background:var(--surf3); border-radius:3px; overflow:hidden; margin-top:4px; }
.det-pbar{ height:100%; border-radius:3px; transition:width .4s; }

/* ── Filters pane ─────────────────────────────────────── */
#it-flt{ overflow-y:auto; padding:16px; gap:0; }

.flt-section-title{
  font-size:10px; font-weight:600; color:var(--muted);
  text-transform:uppercase; letter-spacing:.07em; margin-bottom:10px;
  display:flex; align-items:center; gap:6px;
}
.flt-section-title svg{ width:12px; height:12px; }
.flt-row{
  display:flex; align-items:center; gap:10px;
  padding:8px 10px; border-radius:7px; cursor:pointer;
  transition:background .14s; margin-bottom:4px;
  border:1px solid transparent;
}
.flt-row:hover{ background:var(--surf2); border-color:var(--bdr); }
.flt-dot{ width:11px; height:11px; border-radius:3px; flex-shrink:0; }
.flt-label{ font-size:12px; color:var(--txt2); flex:1; }
.flt-sub{ font-size:10px; color:var(--muted); }
.flt-cnt{ font-size:10px; font-weight:600; color:var(--muted); background:var(--surf2); border-radius:10px; padding:1px 8px; border:1px solid var(--bdr); }
#it-root input[type="checkbox"]{ width:14px; height:14px; accent-color:var(--accent); cursor:pointer; flex-shrink:0; }
.flt-div{ height:1px; background:var(--bdr); margin:12px 0; }
.flt-action{ font-size:11px; color:var(--accent); cursor:pointer; text-align:center; padding:6px 0; border-radius:6px; transition:background .14s; }
.flt-action:hover{ background:var(--acc-bg); }

/* ── Legend (inside panel footer) ────────────────────── */
#it-legend{
  border-top:1px solid var(--bdr); padding:12px 16px;
  background:var(--surf2); flex-shrink:0;
}
.lg-title{ font-size:9.5px; font-weight:600; color:var(--muted); text-transform:uppercase; letter-spacing:.07em; margin-bottom:8px; }
.lg-grid{ display:grid; grid-template-columns:1fr 1fr; gap:4px 12px; }
.lg-row{ display:flex; align-items:center; gap:6px; }
.lg-sw{ width:11px; height:11px; border-radius:2px; flex-shrink:0; }
.lg-txt{ font-size:10px; color:var(--txt2); }
.lg-div{ height:1px; background:var(--bdr); margin:7px 0; }
.lg-row-full{ display:flex; align-items:center; gap:6px; margin-bottom:3px; }
</style>
</head>
<body>

<!-- ═══ ROOT ═══════════════════════════════════════════════════════ -->
<div id="it-root">

  <!-- Header -->
  <div id="it-hd">
    <div class="it-logo">Insight<em>Tree</em></div>
    <div class="it-date">""" + dd + """</div>
    <div class="it-seg">
      <button class="it-seg-btn on" id="btn-v1" onclick="switchV(1)">Client &rarr; Project &rarr; Topic</button>
      <button class="it-seg-btn"    id="btn-v2" onclick="switchV(2)">Project &rarr; Client &rarr; Topic</button>
    </div>
  </div>

  <!-- Hint bar -->
  <div id="it-hints">
    <span><span class="it-kbd">Click</span> expand / collapse</span>
    <span><span class="it-kbd">Leaf click</span> open details &rarr;</span>
    <span><span class="it-kbd">Scroll</span> zoom</span>
    <span><span class="it-kbd">Drag</span> pan</span>
  </div>

  <!-- Body -->
  <div id="it-body">

    <!-- Canvas -->
    <div id="it-cv">
      <svg id="it-svg"></svg>
      <!-- hover tooltip for client/project nodes -->
      <div id="it-tt"></div>
      <!-- zoom buttons -->
      <div class="it-zc">
        <div class="it-zb" onclick="zBy(1.3)" title="Zoom in">+</div>
        <div class="it-zb" onclick="zBy(0.77)" title="Zoom out">&minus;</div>
        <div class="it-zb" onclick="fitV()" title="Fit">&#10548;</div>
      </div>
    </div>

    <!-- Right Panel -->
    <div id="it-panel">

      <!-- Tab bar -->
      <div id="it-tabs">
        <button class="it-tab on" id="tab-det" onclick="openTab('det')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          Details
        </button>
        <button class="it-tab" id="tab-flt" onclick="openTab('flt')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
          Filters
        </button>
      </div>

      <!-- Details pane -->
      <div class="it-pane on" id="it-det">
        <div class="it-empty" id="det-empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
          <p>Click a <strong>topic node</strong> in the tree to view its details here.</p>
        </div>
        <div id="det-content" style="display:none"></div>
      </div>

      <!-- Filters pane -->
      <div class="it-pane" id="it-flt">
        <div class="flt-section-title" style="padding-top:4px">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
          Show Priority
        </div>
        <label class="flt-row">
          <input type="checkbox" id="fp-p5" checked onchange="applyF()"/>
          <span class="flt-dot" style="background:var(--p5)"></span>
          <span class="flt-label">Priority 5 <span class="flt-sub">&mdash; Critical</span></span>
          <span class="flt-cnt" id="cnt-p5">0</span>
        </label>
        <label class="flt-row">
          <input type="checkbox" id="fp-p4" checked onchange="applyF()"/>
          <span class="flt-dot" style="background:var(--p4)"></span>
          <span class="flt-label">Priority 4 <span class="flt-sub">&mdash; High</span></span>
          <span class="flt-cnt" id="cnt-p4">0</span>
        </label>
        <label class="flt-row">
          <input type="checkbox" id="fp-p3" checked onchange="applyF()"/>
          <span class="flt-dot" style="background:var(--p3)"></span>
          <span class="flt-label">Priority 3 <span class="flt-sub">&mdash; Medium</span></span>
          <span class="flt-cnt" id="cnt-p3">0</span>
        </label>
        <label class="flt-row">
          <input type="checkbox" id="fp-p12" onchange="applyF()"/>
          <span class="flt-dot" style="background:var(--p2)"></span>
          <span class="flt-label">Priority 1&ndash;2 <span class="flt-sub">&mdash; Low</span></span>
          <span class="flt-cnt" id="cnt-p12">0</span>
        </label>
        <div class="flt-div"></div>
        <div class="flt-action" onclick="toggleAllF()">Toggle All</div>
      </div>

      <!-- Legend footer (always visible) -->
      <div id="it-legend">
        <div class="lg-title">Legend</div>
        <div class="lg-grid">
          <div class="lg-row"><div class="lg-sw" style="background:var(--p5)"></div><div class="lg-txt">P5 Critical</div></div>
          <div class="lg-row"><div class="lg-sw" style="background:var(--p4)"></div><div class="lg-txt">P4 High</div></div>
          <div class="lg-row"><div class="lg-sw" style="background:var(--p3)"></div><div class="lg-txt">P3 Medium</div></div>
          <div class="lg-row"><div class="lg-sw" style="background:var(--p2)"></div><div class="lg-txt">P1-2 Low</div></div>
        </div>
        <div class="lg-div"></div>
        <div class="lg-row-full">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>
          <div class="lg-txt">Client node</div>
        </div>
        <div class="lg-row-full">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#0284c7" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          <div class="lg-txt">Project node</div>
        </div>
        <div class="lg-row-full">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          <div class="lg-txt">Topic leaf</div>
        </div>
      </div>

    </div><!-- /right panel -->
  </div><!-- /body -->
</div><!-- /it-root -->

<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script>
// ═══ DATA ═══════════════════════════════════════════════════════
const DATA = { v1: """ + j1 + """, v2: """ + j2 + """ };

// ═══ CONSTANTS ══════════════════════════════════════════════════
const NW = 172, NH = 52, RW = 200, RH = 60;
const DX = 216, DY = 66;

// ═══ ICONS ══════════════════════════════════════════════════════
const ICO = {
  root:    '<svg viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,.88)" stroke-width="2" stroke-linecap="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/></svg>',
  client:  '<svg viewBox="0 0 24 24" fill="none" stroke="#7c3aed" stroke-width="2" stroke-linecap="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/><line x1="12" y1="12" x2="12" y2="16"/><line x1="10" y1="14" x2="14" y2="14"/></svg>',
  project: '<svg viewBox="0 0 24 24" fill="none" stroke="#0284c7" stroke-width="2" stroke-linecap="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
  topic:   '<svg viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
};

// ═══ COLOUR HELPERS ═════════════════════════════════════════════
function pColor(s){ return s>=5?'#e74c3c': s===4?'#e67e22': s===3?'#c9940f': '#27ae60'; }
function barCls(d){
  const t = d.data.type;
  if(t==='root')    return 'root';
  if(t==='client')  return 'client';
  if(t==='project') return 'project';
  const s = d.data.priorityScore||0;
  return s>=5?'p5': s===4?'p4': s===3?'p3': 'p2';
}

// ═══ SVG SETUP ══════════════════════════════════════════════════
const root_el = document.getElementById('it-root');
const svg  = d3.select('#it-svg');
const gM   = svg.append('g');
const gL   = gM.append('g');
const gN   = gM.append('g');

function CW(){ return document.getElementById('it-cv').clientWidth; }
function CH(){ return document.getElementById('it-cv').clientHeight; }

const zB = d3.zoom().scaleExtent([0.05,3]).on('zoom', e => gM.attr('transform', e.transform));
svg.call(zB).on('dblclick.zoom', null);

// ═══ STATE ══════════════════════════════════════════════════════
let curRoot = null, curV = 1, selNode = null;

// ═══ HIERARCHY ══════════════════════════════════════════════════
function mkRoot(v){
  const raw  = v===1 ? DATA.v1 : DATA.v2;
  const root = d3.hierarchy(raw, d => d.children&&d.children.length ? d.children : null);
  root.each(d => {
    if(d.depth>=2 && d.children){ d._ch = d.children; d.children = null; }
  });
  return root;
}

function doLayout(root){
  d3.tree().nodeSize([DY,DX]).separation((a,b) => a.parent===b.parent?1:1.25)(root);
}

// ═══ DRAW ═══════════════════════════════════════════════════════
function draw(root){
  curRoot = root;
  doLayout(root);
  const nodes = root.descendants();
  const links = root.links();

  // links
  gL.selectAll('.it-link')
    .data(links, d => d.target.data.id||d.target.data.name)
    .join(
      en => en.append('path').attr('class','it-link').attr('opacity',0)
              .call(s=>s.transition().duration(340).attr('opacity',1)),
      up => up.transition().duration(340),
      ex => ex.transition().duration(200).attr('opacity',0).remove()
    )
    .attr('d', d3.linkHorizontal().x(d=>d.y).y(d=>d.x));

  // nodes
  const nw = d => d.data.type==='root'?RW:NW;
  const nh = d => d.data.type==='root'?RH:NH;

  gN.selectAll('.it-ng')
    .data(nodes, d => d.data.id||d.data.name)
    .join(
      en => {
        const g = en.append('g').attr('class','it-ng')
          .attr('transform', d=>`translate(${d.y-nw(d)/2},${d.x-nh(d)/2})`)
          .attr('opacity',0);
        g.transition().duration(340).attr('opacity',1);
        g.append('foreignObject')
          .attr('class','it-fo')
          .attr('width',  d=>nw(d))
          .attr('height', d=>nh(d)+20)
          .append('xhtml:div')
          .attr('class', d=>cardCls(d))
          .html(d=>cardHTML(d))
          .on('click',     (ev,d)=>{ ev.stopPropagation(); onNodeClick(d); })
          .on('mouseover', (ev,d)=>{ if(d.data.type!=='topic'&&d.data.type!=='root') showTT(ev,d); })
          .on('mousemove', moveTT)
          .on('mouseout',  hideTT);
        return g;
      },
      up => {
        up.transition().duration(340)
          .attr('transform', d=>`translate(${d.y-nw(d)/2},${d.x-nh(d)/2})`);
        up.select('div')
          .attr('class', d=>cardCls(d))
          .html(d=>cardHTML(d));
        return up;
      },
      ex => ex.transition().duration(200).attr('opacity',0).remove()
    );

  applyF();
  updCounts();
}

function cardCls(d){
  let c='it-card';
  if(d.data.type==='root') c+=' root-c';
  if(!d.children&&d._ch)   c+=' collapsed';
  if(selNode && d.data.id===selNode.data.id) c+=' sel';
  return c;
}

function cardHTML(d){
  const t   = d.data;
  const ico = ICO[t.type]||ICO.topic;
  const has = !!(d.children||d._ch);
  const col = !d.children && d._ch;
  let sub = '';
  if(t.type==='client'||t.type==='project'){
    const a = t.agg||{};
    sub = (a.topicCount||0)+' topics';
    if(a.escalations) sub+=' &nbsp;<span class="it-badge e">&#9889;&nbsp;'+a.escalations+'</span>';
    if(a.blockers)    sub+=' &nbsp;<span class="it-badge b">&#9888;&nbsp;'+a.blockers+'</span>';
  } else if(t.type==='topic'){
    sub = esc(t.state||'');
  } else {
    sub = 'Click to expand';
  }
  const chev = has ? '<div class="it-chev">'+(col?'&#8250;':'&#8964;')+'</div>' : '';
  return '<div class="it-bar '+barCls(d)+'"></div>'
       + '<div class="it-ico">'+ico+'</div>'
       + '<div class="it-cb">'
       + '<div class="it-cn">'+esc(trunc(t.name, t.type==='root'?23:18))+'</div>'
       + (sub?'<div class="it-cs">'+sub+'</div>':'')
       + '</div>'
       + chev;
}

// ═══ NODE CLICK ═════════════════════════════════════════════════
function onNodeClick(d){
  if(d.data.type==='topic'){
    selNode = d;
    // data is bound to the <g class="it-ng">, not to the inner xhtml div —
    // iterate g nodes and push the updated class into each child div
    gN.selectAll('.it-ng').each(function(n){
      d3.select(this).select('div').attr('class', cardCls(n));
    });
    renderDetails(d.data);
    openTab('det');
  } else {
    // expand / collapse branch
    if(d.data.type==='root') return;
    if(d.children){ d._ch=d.children; d.children=null; }
    else if(d._ch){ d.children=d._ch; d._ch=null; }
    doLayout(curRoot);
    draw(curRoot);
  }
}

// ═══ DETAILS PANEL ══════════════════════════════════════════════
function stars(n,max=5){
  let s='';
  for(let i=1;i<=max;i++) s+='<span class="'+(i<=n?'det-star-on':'det-star-off')+'">&#9733;</span>';
  return '<span class="det-stars">'+s+'</span>';
}

function renderDetails(t){
  const empty   = document.getElementById('det-empty');
  const content = document.getElementById('det-content');
  empty.style.display   = 'none';
  content.style.display = 'block';

  const pct   = ((t.priorityScore||0)/5*100).toFixed(0);
  const pclr  = pColor(t.priorityScore||0);

  let flags = '';
  if(t.escalation) flags += '<span class="det-flag esc">&#9889; Escalation</span>';
  if(t.blockers)   flags += '<span class="det-flag blk">&#9888; Blocker</span>';
  if(!t.escalation&&!t.blockers) flags += '<span class="det-flag ok">&#10003; No Active Flags</span>';

  let h = '';
  h += '<div class="det-title">'+esc(t.name)+'</div>';
  h += '<div class="det-div"></div>';

  if(t.state)  h += '<div class="det-row"><span class="det-key">State</span><span class="det-val">'+esc(t.state)+'</span></div>';
  if(t.owner)  h += '<div class="det-row"><span class="det-key">Owner</span><span class="det-val">'+esc(t.owner)+'</span></div>';
  if(t.next)   h += '<div class="det-row"><span class="det-key">Next</span><span class="det-val">'+esc(t.next)+'</span></div>';

  h += '<div class="det-row"><span class="det-key">Priority</span>'
     + '<span class="det-val">'+stars(t.priorityScore||0)+' &nbsp;'+(t.priorityScore||0)+'/5'
     + '</span></div>';
  h += '<div class="det-pbar-wrap"><div class="det-pbar" style="width:'+pct+'%;background:'+pclr+'"></div></div>';

  h += '<div class="det-div"></div>';
  h += '<div class="det-flags">'+flags+'</div>';

  if(t.summary){
    h += '<div class="det-div"></div>';
    h += '<div class="det-row"><span class="det-key">Summary</span></div>';
    h += '<div class="det-summary">'+esc(t.summary)+'</div>';
  }

  if(t.timestamp){
    const ts = new Date(t.timestamp);
    const fmt = isNaN(ts)?t.timestamp:ts.toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'});
    h += '<div class="det-div"></div>';
    h += '<div class="det-row"><span class="det-key">Timestamp</span><span class="det-val" style="font-size:10.5px;color:var(--muted)">'+esc(fmt)+'</span></div>';
  }

  content.innerHTML = h;
}

// ═══ TABS ═══════════════════════════════════════════════════════
function openTab(id){
  document.querySelectorAll('#it-root .it-tab').forEach(b => b.classList.remove('on'));
  document.querySelectorAll('#it-root .it-pane').forEach(p => p.classList.remove('on'));
  document.getElementById('tab-'+id).classList.add('on');
  document.getElementById('it-'+id).classList.add('on');
}

// ═══ VARIANT SWITCH ═════════════════════════════════════════════
function switchV(v){
  curV=v; selNode=null;
  document.getElementById('det-empty').style.display   = '';
  document.getElementById('det-content').style.display = 'none';
  document.getElementById('btn-v1').classList.toggle('on', v===1);
  document.getElementById('btn-v2').classList.toggle('on', v===2);
  gL.selectAll('*').remove();
  gN.selectAll('*').remove();
  draw(mkRoot(v));
  setTimeout(fitV,420);
}

// ═══ FILTERS ════════════════════════════════════════════════════
function vis(d){
  if(d.data.type!=='topic') return true;
  const s=d.data.priorityScore||0;
  if(s>=5 && !document.getElementById('fp-p5').checked)  return false;
  if(s===4 && !document.getElementById('fp-p4').checked)  return false;
  if(s===3 && !document.getElementById('fp-p3').checked)  return false;
  if(s<=2 && !document.getElementById('fp-p12').checked)  return false;
  return true;
}
function applyF(){
  gN.selectAll('.it-ng').each(function(d){ d3.select(this).classed('dim',!vis(d)); });
  gL.selectAll('.it-link').each(function(d){ d3.select(this).classed('dim',!vis(d.target)); });
}
let _allOn=true;
function toggleAllF(){
  _allOn=!_allOn;
  ['fp-p5','fp-p4','fp-p3','fp-p12'].forEach(id=>{ document.getElementById(id).checked=_allOn; });
  applyF();
}
function updCounts(){
  if(!curRoot) return;
  const all = curRoot.descendants().filter(d=>d.data.type==='topic');
  document.getElementById('cnt-p5').textContent  = all.filter(d=>(d.data.priorityScore||0)>=5).length;
  document.getElementById('cnt-p4').textContent  = all.filter(d=>(d.data.priorityScore||0)===4).length;
  document.getElementById('cnt-p3').textContent  = all.filter(d=>(d.data.priorityScore||0)===3).length;
  document.getElementById('cnt-p12').textContent = all.filter(d=>(d.data.priorityScore||0)<=2).length;
}

// ═══ HOVER TOOLTIP (client / project only) ══════════════════════
const ttEl = document.getElementById('it-tt');
function showTT(ev,d){
  const t=d.data, a=t.agg||{};
  let h='<div class="tt-title">'+esc(t.name)+'</div>';
  h+='<div class="tt-grid">';
  h+=ttCell(a.topicCount||0,'Topics','');
  h+=ttCell(a.escalations||0,'Escalations',a.escalations>0?'#dc2626':'');
  h+=ttCell(a.maxPriority||0,'Max P',pColor(a.maxPriority||0));
  h+='</div>';
  ttEl.innerHTML=h; ttEl.classList.add('show'); moveTT(ev);
}
function ttCell(n,l,c){ return '<div class="tt-cell"><div class="tt-num"'+(c?' style="color:'+c+'"':'')+'>'+(n)+'</div><div class="tt-lbl">'+l+'</div></div>'; }
function moveTT(ev){
  const pad=12, rect=document.getElementById('it-cv').getBoundingClientRect();
  let x=ev.clientX-rect.left+pad, y=ev.clientY-rect.top+pad;
  const w=ttEl.offsetWidth, h=ttEl.offsetHeight;
  if(x+w+pad>rect.width)  x=ev.clientX-rect.left-w-pad;
  if(y+h+pad>rect.height) y=ev.clientY-rect.top-h-pad;
  ttEl.style.left=x+'px'; ttEl.style.top=y+'px';
}
function hideTT(){ ttEl.classList.remove('show'); }

// ═══ ZOOM ════════════════════════════════════════════════════════
function zBy(f){ svg.transition().duration(260).call(zB.scaleBy,f); }
function fitV(){
  const bb = gM.node().getBBox();
  if(!bb.width||!bb.height) return;
  const pad=60, cw=CW(), ch=CH();
  const sc = Math.min((cw-pad*2)/bb.width, (ch-pad*2)/bb.height, 1.4);
  const tx = (cw-bb.width*sc)/2 - bb.x*sc;
  const ty = (ch-bb.height*sc)/2 - bb.y*sc;
  svg.transition().duration(580).call(zB.transform, d3.zoomIdentity.translate(tx,ty).scale(sc));
}

// ═══ UTILS ═══════════════════════════════════════════════════════
function trunc(s,n){ return s&&s.length>n ? s.slice(0,n)+'\u2026' : (s||''); }
function esc(s){ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

// ═══ INIT ════════════════════════════════════════════════════════
draw(mkRoot(1));
setTimeout(fitV, 480);
window.addEventListener('resize', ()=>{ if(curRoot){ doLayout(curRoot); draw(curRoot); } });
</script>
</body>
</html>"""


# ── entry point ───────────────────────────────────────────────────

def main(filepath):
    if not os.path.exists(filepath):
        print(f"[ERROR] File not found: {filepath}")
        sys.exit(1)

    data     = load_json(filepath)
    date_str = date_from_name(filepath)
    out_name = f"mindmap-variation1-{date_str}.html"
    out_path = Path.cwd() / out_name

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(make_html(build_v1(data), build_v2(data), date_str))

    print(f"[OK] {out_path}")
    return str(out_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_mindmap.py <insight-json-path>")
        sys.exit(1)
    main(sys.argv[1])
