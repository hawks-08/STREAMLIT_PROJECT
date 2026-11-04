from __future__ import annotations
 
import itertools
import math
 
import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
 
# ----------------------------------------------------------------------------
# 1. Constantes del modelo
# ----------------------------------------------------------------------------
EDGE_COLS = ["Origen", "Destino", "Retardo_ms", "Banda_Mbps", "Disponible"]
 
DEFAULT_NODES = ["H", "D", "A", "B", "E", "J", "C", "O", "N"]
DEFAULT_EDGES = [
    ("H", "D", 8, 100, True),
    ("D", "A", 9, 100, True),
    ("A", "B", 7, 100, True),
    ("H", "E", 5, 50, True),
    ("E", "J", 10, 50, True),
    ("J", "C", 8, 100, True),
    ("C", "B", 6, 100, True),
    ("H", "O", 7, 100, True),
    ("O", "N", 9, 50, True),
    ("N", "J", 9, 100, True),
]
# Posiciones de la guía para la disposición "Fijo (guía)"
DEFAULT_POS = {
    "H": (0.0, 0.0), "D": (1.3, 1.5), "A": (2.8, 1.5), "B": (4.3, 0.0),
    "E": (1.3, 0.0), "J": (2.3, 0.0), "C": (3.3, 0.0),
    "O": (1.3, -1.5), "N": (2.3, -1.5),
}
# Rutas preconfiguradas (selección estática del artículo), por prioridad
STATIC_PATHS = [
    ("PSRC", ["H", "D", "A", "B"]),
    ("SSRC", ["H", "E", "J", "C", "B"]),
    ("TSRC", ["H", "O", "N", "J", "C", "B"]),
]
 
OBJ_HOPS = "Johal: mínimo de saltos"
OBJ_DELAY = "Mínimo retardo"
OBJ_MULTI = "Multicriterio (α, β, γ)"
OBJETIVOS = [OBJ_HOPS, OBJ_DELAY, OBJ_MULTI]
DEFAULT_W = (0.5, 0.35, 0.15)
 
LAYOUTS = [
    "Fijo (guía)",
    "Resorte (spring)",
    "Circular",
    "Kamada-Kawai",
    "Capas hacia el destino",
    "Espectral",
]
 
THEMES = {
    "Clásico claro": dict(
        paper="#FFFFFF", text="#1F2937", muted="#6B7280", edge="#9CA3AF",
        down="#DC2626", static="#F59E0B", opt="#2563EB", node="#E5E7EB",
        src="#16A34A", dst="#7C3AED", accent="#2563EB", accent2="#7C3AED"),
    "Oscuro": dict(
        paper="#0F172A", text="#E2E8F0", muted="#94A3B8", edge="#475569",
        down="#F87171", static="#FBBF24", opt="#38BDF8", node="#1E293B",
        src="#22C55E", dst="#A78BFA", accent="#0EA5E9", accent2="#6366F1"),
    "Océano": dict(
        paper="#F0FDFA", text="#134E4A", muted="#0F766E", edge="#5EEAD4",
        down="#E11D48", static="#EA580C", opt="#0D9488", node="#CCFBF1",
        src="#15803D", dst="#9333EA", accent="#0D9488", accent2="#0891B2"),
}
 
EXPERIMENTOS = {
    "A": ("Réplica original",
          "Restablece la red y usa el mínimo de saltos.",
          "H(P1)=3, H(P2)=4, H(P3)=5 → se selecciona P1 (H–D–A–B)."),
    "B": ("Cambio de retardo",
          "H–D = 40 ms y objetivo de mínimo retardo.",
          "D(P1)=56, D(P2)=29, D(P3)=39 ms → mejor de las tres: P2. "
          "Registra también el óptimo recalculado."),
    "C": ("Fallo primario",
          "Marca H–D como no disponible (objetivo: saltos).",
          "La estática elige SSRC (P2); compárala con el óptimo recalculado."),
    "D": ("Doble fallo",
          "H–D y H–E caídos (objetivo: saltos).",
          "Solo queda TSRC (P3) si sus enlaces siguen activos."),
    "E": ("Cuello de botella",
          "Restablece y reduce E–J a 5 Mbps (objetivo multicriterio).",
          "B(P2)=min(50, 5, 100, 100)=5 Mbps; la penalización de E–J es "
          "b_ref/b = 20 (no es lo mismo que la capacidad)."),
}
PESOS_F = {
    "F1 (1, 0, 0)": (1.0, 0.0, 0.0),
    "F2 (0, 1, 0)": (0.0, 1.0, 0.0),
    "F3 (0, 0, 1)": (0.0, 0.0, 1.0),
    "F4 (0.5, 0.35, 0.15)": (0.5, 0.35, 0.15),
}
 
 
def _stretch_kwargs() -> dict:
    """Compatibilidad entre versiones de Streamlit (ancho completo)."""
    try:
        parts = st.__version__.split(".")
        ver = (int(parts[0]), int(parts[1]))
    except Exception:  # pragma: no cover
        ver = (0, 0)
    return {"width": "stretch"} if ver >= (1, 50) else {"use_container_width": True}
 
 
STRETCH = _stretch_kwargs()
 
 
# ----------------------------------------------------------------------------
# 2. Lógica del modelo (sin Streamlit, fácil de probar)
# ----------------------------------------------------------------------------
def typed(df: pd.DataFrame) -> pd.DataFrame:
    """Fuerza los tipos de la tabla de enlaces."""
    df = df.copy()
    for c in EDGE_COLS:
        if c not in df.columns:
            df[c] = None
    for c in ("Origen", "Destino"):
        df[c] = df[c].astype(object)
    for c in ("Retardo_ms", "Banda_Mbps"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    df["Disponible"] = df["Disponible"].map(lambda v: True if pd.isna(v) else bool(v))
    return df[EDGE_COLS].reset_index(drop=True)
 
 
def default_edges_df() -> pd.DataFrame:
    return typed(pd.DataFrame(DEFAULT_EDGES, columns=EDGE_COLS))
 
 
def clean_edges(df: pd.DataFrame, nodes: list[str]):
    """Valida la tabla editada. Devuelve (tabla limpia, advertencias)."""
    warns: list[str] = []
    seen: dict = {}
    node_set = set(nodes)
    for _, r in df.iterrows():
        o, d = r.get("Origen"), r.get("Destino")
        if pd.isna(o) or pd.isna(d):
            continue  # fila incompleta (en edición)
        if o not in node_set or d not in node_set:
            warns.append(f"Enlace {o}–{d} ignorado: algún router no existe.")
            continue
        if o == d:
            warns.append(f"Enlace {o}–{d} ignorado: un router no puede unirse consigo mismo.")
            continue
        try:
            dl, bw = float(r["Retardo_ms"]), float(r["Banda_Mbps"])
        except (TypeError, ValueError):
            continue
        if math.isnan(dl) or math.isnan(bw):
            continue
        if dl < 0 or bw < 0:
            warns.append(f"Enlace {o}–{d} ignorado: retardo y capacidad no pueden ser negativos.")
            continue
        disp = True if pd.isna(r.get("Disponible")) else bool(r["Disponible"])
        key = frozenset((o, d))
        if key in seen:
            warns.append(f"Enlace {o}–{d} duplicado: se usa la última fila.")
        seen[key] = (o, d, dl, bw, disp)
    out = pd.DataFrame(list(seen.values()), columns=EDGE_COLS)
    return typed(out), warns
 
 
def is_up(disponible: bool, banda: float) -> bool:
    return bool(disponible) and banda > 0
 
 
def scales(edges: pd.DataFrame):
    """d_ref y b_ref: máximos positivos de la tabla de enlaces actual."""
    dpos = [x for x in edges["Retardo_ms"] if x > 0]
    bpos = [x for x in edges["Banda_Mbps"] if x > 0]
    return (max(dpos) if dpos else 1.0), (max(bpos) if bpos else 1.0)
 
 
def normalize_weights(a: float, b: float, g: float):
    s = a + b + g
    if s <= 0:
        return 1 / 3, 1 / 3, 1 / 3, True
    return a / s, b / s, g / s, False
 
 
def edge_terms(d, b, alpha, beta, gamma, dref, bref):
    """Tres sumandos del costo multicriterio de una arista."""
    return alpha, beta * d / dref, gamma * bref / b
 
 
def edge_weight(d, b, obj, w, dref, bref) -> float:
    if obj == OBJ_HOPS:
        return 1.0
    if obj == OBJ_DELAY:
        return float(d)
    return float(sum(edge_terms(d, b, *w, dref, bref)))
 
 
def edge_lookup(edges: pd.DataFrame) -> dict:
    return {
        frozenset((r.Origen, r.Destino)): (r.Retardo_ms, r.Banda_Mbps,
                                           is_up(r.Disponible, r.Banda_Mbps))
        for r in edges.itertuples(index=False)
    }
 
 
def build_graph(edges: pd.DataFrame, nodes: list[str]) -> nx.Graph:
    """Grafo solo con enlaces disponibles."""
    G = nx.Graph()
    G.add_nodes_from(nodes)
    for r in edges.itertuples(index=False):
        if is_up(r.Disponible, r.Banda_Mbps):
            G.add_edge(r.Origen, r.Destino, d=r.Retardo_ms, b=r.Banda_Mbps)
    return G
 
 
def set_weights(G: nx.Graph, obj, w, dref, bref):
    for _, _, dat in G.edges(data=True):
        dat["w"] = edge_weight(dat["d"], dat["b"], obj, w, dref, bref)
 
 
def fmt_path(path) -> str:
    return "–".join(path)
 
 
def path_status(path, lookup) -> str:
    for u, v in zip(path[:-1], path[1:]):
        key = frozenset((u, v))
        if key not in lookup:
            return f"Enlace inexistente {u}–{v}"
        if not lookup[key][2]:
            return f"Enlace caído {u}–{v}"
    return "Disponible"
 
 
def path_metrics(path, lookup, w, dref, bref) -> dict:
    hops = len(path) - 1
    D, Bmin, C = 0.0, math.inf, 0.0
    for u, v in zip(path[:-1], path[1:]):
        d, b, _ = lookup[frozenset((u, v))]
        D += d
        Bmin = min(Bmin, b)
        C += sum(edge_terms(d, b, *w, dref, bref))
    return {"H": hops, "D": D, "B": (Bmin if hops else float("nan")), "C": C}
 
 
def objective_value(m: dict, obj) -> float:
    return m["H"] if obj == OBJ_HOPS else (m["D"] if obj == OBJ_DELAY else m["C"])
 
 
def make_row(label, path, lookup, obj, w, dref, bref, status=None) -> dict:
    status = status or path_status(path, lookup)
    row = {"Etiqueta": label, "Ruta": fmt_path(path), "Estado": status,
           "H(P) saltos": None, "D(P) ms": None, "B(P) Mbps": None,
           "C(P)": None, "Valor del objetivo": None}
    if status == "Disponible":
        m = path_metrics(path, lookup, w, dref, bref)
        row.update({"H(P) saltos": m["H"], "D(P) ms": round(m["D"], 4),
                    "B(P) Mbps": round(m["B"], 4), "C(P)": round(m["C"], 4),
                    "Valor del objetivo": round(objective_value(m, obj), 4)})
    return row
 
 
def sink_tree(G, dst, nodes, lookup, obj, w, dref, bref):
    """Árbol de siguientes saltos hacia dst. Devuelve (filas, {nodo: siguiente})."""
    if dst not in G:
        return [], {}
    dist, paths = nx.single_source_dijkstra(G, dst, weight="w")
    rows, tree = [], {}
    for n in nodes:
        if n == dst:
            rows.append({"Nodo": n, "Siguiente salto": "— (destino)", "Ruta hacia el destino": n,
                         "Saltos": 0, "Retardo (ms)": 0.0, "Costo del objetivo": 0.0,
                         "Observación": "Destino"})
            continue
        if n not in paths:
            rows.append({"Nodo": n, "Siguiente salto": "sin ruta", "Ruta hacia el destino": "—",
                         "Saltos": None, "Retardo (ms)": None, "Costo del objetivo": None,
                         "Observación": "Inalcanzable con los enlaces activos"})
            continue
        p = list(reversed(paths[n]))
        tree[n] = p[1]
        m = path_metrics(p, lookup, w, dref, bref)
        cands = [v for v in G[n]
                 if v in dist and math.isclose(G[n][v]["w"] + dist[v], dist[n],
                                               rel_tol=1e-9, abs_tol=1e-9)]
        obs = ("Empate con: " + ", ".join(sorted(cands))) if len(cands) > 1 else ""
        rows.append({"Nodo": n, "Siguiente salto": p[1], "Ruta hacia el destino": fmt_path(p),
                     "Saltos": m["H"], "Retardo (ms)": round(m["D"], 4),
                     "Costo del objetivo": round(dist[n], 4), "Observación": obs})
    return rows, tree
 
 
def analyze(nodes, edges_raw, src, dst, obj, w_raw, max_paths=500) -> dict:
    """Calcula todo lo que muestra la app."""
    edges, warns = clean_edges(edges_raw, nodes)
    dref, bref = scales(edges)
    a, b, g, zero = normalize_weights(*w_raw)
    w = (a, b, g)
    G = build_graph(edges, nodes)
    set_weights(G, obj, w, dref, bref)
    lookup = edge_lookup(edges)
 
    applies = (src == "H" and dst == "B")
    static_rows, static_sel = [], None
    for label, path in STATIC_PATHS:
        status = None if applies else "No aplica (la estática es H → B)"
        static_rows.append(make_row(label, path, lookup, obj, w, dref, bref, status))
    if applies:
        for (label, path), row in zip(STATIC_PATHS, static_rows):
            if row["Estado"] == "Disponible":
                static_sel = (label, path)
                break
 
    opt, opt_row, simple_rows, truncated = None, None, [], False
    if src in G and dst in G and src != dst:
        try:
            opt = nx.dijkstra_path(G, src, dst, weight="w")
        except nx.NetworkXNoPath:
            opt = None
    if opt:
        opt_row = make_row("Óptima (Dijkstra)", opt, lookup, obj, w, dref, bref)
        found = list(itertools.islice(nx.all_simple_paths(G, src, dst), max_paths + 1))
        truncated = len(found) > max_paths
        found = found[:max_paths]
        rows = [make_row("", p, lookup, obj, w, dref, bref) for p in found]
        rows.sort(key=lambda r: (r["Valor del objetivo"], r["H(P) saltos"]))
        for i, r in enumerate(rows, 1):
            r["Etiqueta"] = f"R{i}" + (" ★" if r["Ruta"] == fmt_path(opt) else "")
        simple_rows = rows
 
    tree_rows, tree = sink_tree(G, dst, nodes, lookup, obj, w, dref, bref)
    unreachable = [r["Nodo"] for r in tree_rows if r["Siguiente salto"] == "sin ruta"]
    return dict(nodes=nodes, edges=edges, warns=warns, dref=dref, bref=bref, w=w,
                zero_weights=zero, G=G, lookup=lookup, src=src, dst=dst, obj=obj,
                static_rows=static_rows, static_sel=static_sel, opt=opt, opt_row=opt_row,
                simple_rows=simple_rows, truncated=truncated, tree_rows=tree_rows,
                tree=tree, unreachable=unreachable)
 
 
def manual_table(path, lookup, w, dref, bref) -> pd.DataFrame:
    """Desarrollo manual de C(P) arista por arista."""
    rows = []
    tot = dict(h=0, d=0.0, c=0.0, bmin=math.inf, t1=0.0, t2=0.0, t3=0.0)
    for u, v in zip(path[:-1], path[1:]):
        d, b, _ = lookup[frozenset((u, v))]
        t1, t2, t3 = edge_terms(d, b, *w, dref, bref)
        c = t1 + t2 + t3
        rows.append({"Enlace": f"{u}–{v}", "d_ij (ms)": d, "b_ij (Mbps)": b, "h_ij": 1,
                     "α·h": round(t1, 4), "β·d/d_ref": round(t2, 4),
                     "γ·b_ref/b": round(t3, 4), "C_ij": round(c, 4)})
        tot["h"] += 1; tot["d"] += d; tot["c"] += c; tot["bmin"] = min(tot["bmin"], b)
        tot["t1"] += t1; tot["t2"] += t2; tot["t3"] += t3
    rows.append({"Enlace": "TOTAL del camino", "d_ij (ms)": tot["d"],
                 "b_ij (Mbps)": tot["bmin"], "h_ij": tot["h"], "α·h": round(tot["t1"], 4),
                 "β·d/d_ref": round(tot["t2"], 4), "γ·b_ref/b": round(tot["t3"], 4),
                 "C_ij": round(tot["c"], 4)})
    return pd.DataFrame(rows)
 
 
# ----------------------------------------------------------------------------
# 3. Disposición y gráficos
# ----------------------------------------------------------------------------
def compute_pos(nodes, edges, layout, seed, dst):
    G = nx.Graph()
    G.add_nodes_from(nodes)
    G.add_edges_from((r.Origen, r.Destino) for r in edges.itertuples(index=False))
    try:
        if layout == "Fijo (guía)":
            fixed = {n: p for n, p in DEFAULT_POS.items() if n in G}
            if len(fixed) == len(G):
                return fixed
            if fixed:
                return nx.spring_layout(G, pos=fixed, fixed=list(fixed), seed=seed)
            return nx.spring_layout(G, seed=seed)
        if layout == "Circular":
            return nx.circular_layout(G)
        if layout == "Kamada-Kawai":
            return nx.kamada_kawai_layout(G)
        if layout == "Espectral":
            return nx.spectral_layout(G)
        if layout == "Capas hacia el destino":
            if dst in G:
                dist = nx.single_source_shortest_path_length(G, dst)
                layers = {}
                for n in G:
                    layers.setdefault(dist.get(n, max(dist.values(), default=0) + 1), []).append(n)
                return nx.shell_layout(G, nlist=[layers[k] for k in sorted(layers)])
        return nx.spring_layout(G, seed=seed)
    except Exception:
        return nx.spring_layout(G, seed=seed)
 
 
def graph_figure(nodes, edges, pos, src, dst, theme, show_labels=True, node_size=34,
                 title="", opt=None, static=None, tree=None, unreachable=()):
    th = THEMES[theme]
    fig = go.Figure()
    if not nodes:
        return fig
 
    up = [(r.Origen, r.Destino) for r in edges.itertuples(index=False)
          if is_up(r.Disponible, r.Banda_Mbps)]
    down = [(r.Origen, r.Destino) for r in edges.itertuples(index=False)
            if not is_up(r.Disponible, r.Banda_Mbps)]
 
    def add_lines(pairs, name, color, width, dash="solid", opacity=1.0):
        if not pairs:
            return
        xs, ys = [], []
        for u, v in pairs:
            xs += [pos[u][0], pos[v][0], None]
            ys += [pos[u][1], pos[v][1], None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=name, hoverinfo="skip",
                                 opacity=opacity, line=dict(color=color, width=width, dash=dash)))
 
    add_lines(down, "Enlace caído", th["down"], 2, "dash")
    add_lines(up, "Enlace activo", th["edge"], 2, opacity=0.35 if tree is not None else 1.0)
    if static:
        add_lines(list(zip(static[:-1], static[1:])), "Ruta estática (Johal)",
                  th["static"], 11, opacity=0.5)
    if opt:
        add_lines(list(zip(opt[:-1], opt[1:])), "Ruta óptima recalculada", th["opt"], 4)
 
    if show_labels and len(edges):
        mx, my, tx, hv = [], [], [], []
        for r in edges.itertuples(index=False):
            mx.append((pos[r.Origen][0] + pos[r.Destino][0]) / 2)
            my.append((pos[r.Origen][1] + pos[r.Destino][1]) / 2)
            txt = f"{r.Retardo_ms:g} ms · {r.Banda_Mbps:g} Mbps"
            ok = is_up(r.Disponible, r.Banda_Mbps)
            tx.append(txt if ok else "✕ " + txt)
            hv.append(f"{r.Origen}–{r.Destino}<br>Retardo: {r.Retardo_ms:g} ms"
                      f"<br>Capacidad: {r.Banda_Mbps:g} Mbps<br>{'Activo' if ok else 'Caído'}")
        fig.add_trace(go.Scatter(x=mx, y=my, mode="markers+text", text=tx,
                                 textposition="top center", hovertext=hv, hoverinfo="text",
                                 textfont=dict(size=11, color=th["muted"]),
                                 marker=dict(size=16, opacity=0), showlegend=False))
 
    fills, tcols, hov = [], [], []
    for n in nodes:
        if n == src:
            c, t, role = th["src"], "#FFFFFF", "origen"
        elif n == dst:
            c, t, role = th["dst"], "#FFFFFF", "destino"
        elif n in unreachable:
            c, t, role = th["down"], "#FFFFFF", "sin ruta al destino"
        else:
            c, t, role = th["node"], th["text"], "router"
        fills.append(c)
        tcols.append(t)
        hov.append(f"{n} ({role})")
    fig.add_trace(go.Scatter(
        x=[pos[n][0] for n in nodes], y=[pos[n][1] for n in nodes], mode="markers+text",
        text=nodes, textfont=dict(size=14, color=tcols), hovertext=hov, hoverinfo="text",
        marker=dict(size=node_size, color=fills, line=dict(width=2, color=th["edge"])),
        showlegend=False))
 
    if tree:
        off = int(node_size // 2 + 3)
        for n, nh in tree.items():
            fig.add_annotation(x=pos[nh][0], y=pos[nh][1], ax=pos[n][0], ay=pos[n][1],
                               xref="x", yref="y", axref="x", ayref="y", text="",
                               showarrow=True, arrowhead=3, arrowsize=1.3, arrowwidth=3,
                               arrowcolor=th["opt"], standoff=off, startstandoff=off)
 
    xs = [pos[n][0] for n in nodes]
    ys = [pos[n][1] for n in nodes]
    padx = (max(xs) - min(xs) or 1.0) * 0.12 + 0.3
    pady = (max(ys) - min(ys) or 1.0) * 0.12 + 0.4
    fig.update_layout(
        title=dict(text=title, x=0.01), paper_bgcolor=th["paper"], plot_bgcolor=th["paper"],
        font=dict(color=th["text"]), height=520,
        margin=dict(l=10, r=10, t=50 if title else 10, b=10),
        legend=dict(orientation="h", y=-0.02, yanchor="top"),
        xaxis=dict(visible=False, range=[min(xs) - padx, max(xs) + padx], constrain="domain"),
        yaxis=dict(visible=False, range=[min(ys) - pady, max(ys) + pady],
                   scaleanchor="x", scaleratio=1))
    return fig
 
 
def to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")
 
 
# ----------------------------------------------------------------------------
# 4. Estado de sesión y callbacks
# ----------------------------------------------------------------------------
def init_state():
    ss = st.session_state
    if "nodes" not in ss:
        ss.nodes = list(DEFAULT_NODES)
    if "edges_base" not in ss:
        ss.edges_base = default_edges_df()
    ss.setdefault("edges_cur", ss.edges_base.copy())
    ss.setdefault("ed_ver", 0)
    ss.setdefault("objetivo", OBJ_HOPS)
    ss.setdefault("w_a", DEFAULT_W[0])
    ss.setdefault("w_b", DEFAULT_W[1])
    ss.setdefault("w_g", DEFAULT_W[2])
    ss.setdefault("origen", "H")
    ss.setdefault("destino", "B")
    ss.setdefault("log", [])
    ss.setdefault("new_node_links", [])
    ss.setdefault("del_nodes", [])
    ss.setdefault("del_edges", [])
 
 
def sanitize_state():
    """Evita valores huérfanos en los widgets tras eliminar o renombrar nodos."""
    ss = st.session_state
    nodes = ss.nodes
    if ss.get("origen") not in nodes:
        ss.origen = nodes[0]
    if ss.get("destino") not in nodes:
        ss.destino = nodes[-1]
    for key, pos in (("ren_old", 0), ("ae_o", 0), ("ae_d", -1)):
        if ss.get(key) not in nodes and key in ss:
            ss[key] = nodes[pos]
    ss.new_node_links = [n for n in ss.get("new_node_links", []) if n in nodes]
    ss.del_nodes = [n for n in ss.get("del_nodes", []) if n in nodes]
 
 
def flash(kind: str, msg: str):
    st.session_state.flash = (kind, msg)
 
 
def _current_edges() -> pd.DataFrame:
    ss = st.session_state
    return clean_edges(ss.edges_cur, ss.nodes)[0]
 
 
def _set_edges(df: pd.DataFrame):
    ss = st.session_state
    ss.edges_base = typed(df)
    ss.edges_cur = ss.edges_base.copy()
    ss.ed_ver += 1  # nueva clave para reiniciar el editor
 
 
def cb_add_node():
    ss = st.session_state
    name = (ss.get("new_node_name") or "").strip()
    if not name:
        return flash("error", "Escribe un nombre para el nuevo nodo.")
    if name in ss.nodes:
        return flash("error", f"Ya existe un nodo llamado «{name}».")
    if len(name) > 12:
        return flash("error", "Usa un nombre de máximo 12 caracteres.")
    links = [n for n in ss.get("new_node_links", []) if n in ss.nodes]
    cur = _current_edges()
    rows = [{"Origen": name, "Destino": n, "Retardo_ms": float(ss.new_node_d),
             "Banda_Mbps": float(ss.new_node_b), "Disponible": True} for n in links]
    ss.nodes = ss.nodes + [name]
    if rows:
        cur = pd.concat([cur, pd.DataFrame(rows, columns=EDGE_COLS)], ignore_index=True)
    _set_edges(cur)
    ss.new_node_name = ""
    ss.new_node_links = []
    flash("success", f"Nodo «{name}» agregado con {len(rows)} enlace(s).")
 
 
def cb_remove_nodes():
    ss = st.session_state
    sel = [n for n in ss.get("del_nodes", []) if n in ss.nodes]
    if not sel:
        return flash("warning", "Selecciona al menos un nodo para eliminar.")
    if len(ss.nodes) - len(sel) < 2:
        return flash("error", "Deben quedar al menos 2 nodos en la red.")
    cur = _current_edges()
    keep = ~cur["Origen"].isin(sel) & ~cur["Destino"].isin(sel)
    removed = int((~keep).sum())
    ss.nodes = [n for n in ss.nodes if n not in sel]
    _set_edges(cur[keep])
    ss.del_nodes = []
    ss.new_node_links = []
    flash("success", f"Se eliminaron {len(sel)} nodo(s) y {removed} enlace(s) asociados.")
 
 
def cb_rename_node():
    ss = st.session_state
    old = ss.get("ren_old")
    new = (ss.get("ren_new") or "").strip()
    if old not in ss.nodes or not new:
        return flash("error", "Elige el nodo y escribe el nuevo nombre.")
    if new in ss.nodes:
        return flash("error", f"Ya existe un nodo llamado «{new}».")
    if len(new) > 12:
        return flash("error", "Usa un nombre de máximo 12 caracteres.")
    cur = _current_edges()
    cur["Origen"] = cur["Origen"].replace({old: new})
    cur["Destino"] = cur["Destino"].replace({old: new})
    ss.nodes = [new if n == old else n for n in ss.nodes]
    if ss.get("origen") == old:
        ss.origen = new
    if ss.get("destino") == old:
        ss.destino = new
    _set_edges(cur)
    ss.ren_new = ""
    extra = " Las rutas estáticas del artículo usan los nombres originales." \
        if old in {n for _, p in STATIC_PATHS for n in p} else ""
    flash("success", f"«{old}» ahora se llama «{new}».{extra}")
 
 
def cb_add_edge():
    ss = st.session_state
    o, d = ss.get("ae_o"), ss.get("ae_d")
    if o == d:
        return flash("error", "Origen y destino del enlace deben ser distintos.")
    cur = _current_edges()
    mask = ((cur["Origen"] == o) & (cur["Destino"] == d)) | \
           ((cur["Origen"] == d) & (cur["Destino"] == o))
    if mask.any():
        cur.loc[mask, ["Retardo_ms", "Banda_Mbps", "Disponible"]] = \
            [float(ss.ae_ms), float(ss.ae_mbps), True]
        _set_edges(cur)
        return flash("success", f"Se actualizó el enlace {o}–{d}.")
    row = pd.DataFrame([{"Origen": o, "Destino": d, "Retardo_ms": float(ss.ae_ms),
                         "Banda_Mbps": float(ss.ae_mbps), "Disponible": True}])
    _set_edges(pd.concat([cur, row], ignore_index=True) if len(cur) else row)
    flash("success", f"Enlace {o}–{d} agregado.")
