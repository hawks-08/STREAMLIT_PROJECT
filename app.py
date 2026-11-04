import streamlit as st # Creación interfaz web
import networkx as nx # Generación de grafos y algoritmos de rutas
import pandas as pd # Generación de tablas
import plotly.graph_objects as go # Dibujado de grafos

 # Generación de títulos y descripción de la aplicación
st.set_page_config(page_title="Laboratorio Johal - Sink Tree", layout="wide")
 
st.title("Laboratorio de Redes: Optimalidad y Sink Tree")
st.write(
    "Simulador educativo de rutas entre el router de origen H y el destino B. "
    "Puedes cambiar retardos, capacidades y disponibilidad de los enlaces."
)
 
# Datos iniciales de los enlaces. Los retardos y capacidades son los valores didácticos del laboratorio.
ENLACES_INICIALES = [
    {"Origen": "H", "Destino": "D", "Retardo_ms": 8, "Banda_Mbps": 100, "Disponible": True},
    {"Origen": "D", "Destino": "A", "Retardo_ms": 9, "Banda_Mbps": 100, "Disponible": True},
    {"Origen": "A", "Destino": "B", "Retardo_ms": 7, "Banda_Mbps": 100, "Disponible": True},
    {"Origen": "H", "Destino": "E", "Retardo_ms": 5, "Banda_Mbps": 50, "Disponible": True},
    {"Origen": "E", "Destino": "J", "Retardo_ms": 10, "Banda_Mbps": 50, "Disponible": True},
    {"Origen": "J", "Destino": "C", "Retardo_ms": 8, "Banda_Mbps": 100, "Disponible": True},
    {"Origen": "C", "Destino": "B", "Retardo_ms": 6, "Banda_Mbps": 100, "Disponible": True},
    {"Origen": "H", "Destino": "O", "Retardo_ms": 7, "Banda_Mbps": 50, "Disponible": True},
    {"Origen": "O", "Destino": "N", "Retardo_ms": 9, "Banda_Mbps": 50, "Disponible": True},
    {"Origen": "N", "Destino": "J", "Retardo_ms": 9, "Banda_Mbps": 50, "Disponible": True},
]

# Estado de la sesión y botón para restablecer a los datos iniciales
if "enlaces" not in st.session_state:
    st.session_state.enlaces = pd.DataFrame(ENLACES_INICIALES)
 
if st.sidebar.button("Restablecer datos iniciales"):
    st.session_state.enlaces = pd.DataFrame(ENLACES_INICIALES)
    # Borra también las ediciones guardadas por el editor de la tabla.
    st.session_state.pop("editor_enlaces", None)

 # Función objetivo y pesos para el costo multicriterio:
st.sidebar.header("Configuración")
#Elección entre criterios de optimización: mínimo de saltos, mínimo retardo o costo multicriterio.
objetivo = st.sidebar.selectbox(
    "Función objetivo",
    ["Mínimo de saltos (Johal)", "Mínimo retardo", "Costo multicriterio"]
)

 # Pesos del costo multicriterio: α para saltos, β para retardo y γ para capacidad. Se normalizan a 1.
st.sidebar.write("Pesos del costo multicriterio")
alpha = st.sidebar.number_input("α: saltos", min_value=0.0, max_value=1.0, value=0.5, step=0.05)
beta = st.sidebar.number_input("β: retardo", min_value=0.0, max_value=1.0, value=0.35, step=0.05)
gamma = st.sidebar.number_input("γ: capacidad", min_value=0.0, max_value=1.0, value=0.15, step=0.05)
suma_pesos = alpha + beta + gamma
# Normalización de pesos y validación de que no sean todos cero.
if suma_pesos == 0:
    st.sidebar.error("La suma de los pesos no puede ser cero. Ajusta al menos uno.")
    st.stop()
else:
    alpha, beta, gamma = alpha / suma_pesos, beta / suma_pesos, gamma / suma_pesos
    st.sidebar.caption(f"Pesos normalizados: α={alpha:.3f}, β={beta:.3f}, γ={gamma:.3f}")

 # Generación de la tabla editable de enlaces
st.header("1. Tabla de enlaces")
st.write("Edita el retardo, la banda y la disponibilidad directamente en la tabla.")
editado = st.data_editor(
    st.session_state.enlaces,
    width="stretch",
    hide_index=True,
    column_config={
        "Origen": st.column_config.TextColumn(disabled=True),
        "Destino": st.column_config.TextColumn(disabled=True),
        "Retardo_ms": st.column_config.NumberColumn(min_value=1, max_value=10000, step=1),
        "Banda_Mbps": st.column_config.NumberColumn(min_value=1, max_value=100000, step=1),
        "Disponible": st.column_config.CheckboxColumn(),
    },
    key="editor_enlaces",
)
st.session_state.enlaces = editado.copy()
 
# Generación del grafo a partir de la tabla editada. Se añaden todos los enlaces disponibles y se crean nodos para los routers aunque no tengan enlaces activos, para reflejar desconexiones.
G = nx.Graph()
for _, fila in editado.iterrows():
    if bool(fila["Disponible"]):
        G.add_edge(
            fila["Origen"],
            fila["Destino"],
            retardo=float(fila["Retardo_ms"]),
            banda=float(fila["Banda_Mbps"]),
        )
 
# Añadir nodos aunque todos sus enlaces estén caídos ayuda a informar desconexiones.
for nodo in ["H", "D", "A", "B", "E", "J", "C", "O", "N"]:
    G.add_node(nodo)

# Funcion de peso para el cálculo de la ruta óptima según el criterio seleccionado.
if objetivo == "Mínimo de saltos (Johal)":
    peso = lambda u, v, datos: 1
elif objetivo == "Mínimo retardo":
    peso = "retardo"
else:
    # NetworkX puede utilizar una función de costo que recibe u, v y datos de la arista.
    peso = lambda u, v, datos: (
        alpha
        + beta * (datos["retardo"] / max(
            [float(x) for x in editado["Retardo_ms"] if float(x) > 0] or [1]
        ))
        + gamma * (
            max([float(x) for x in editado["Banda_Mbps"] if float(x) > 0] or [1])
            / datos["banda"]
        )
    )
 
st.header("2. Grafo y ruta óptima")
# Grafo dibujado con Plotly
pos = {
    "H": (0, 1), "D": (1, 2), "A": (2, 2), "B": (3, 1),
    "E": (1, 1), "J": (2, 0), "C": (2.6, 1),
    "O": (1, -1), "N": (2, -1),
}
fig = go.Figure()
# Dibujar todos los enlaces; los caídos se muestran discontinuos.
for _, fila in editado.iterrows():
    u, v = fila["Origen"], fila["Destino"]
    x0, y0 = pos[u]
    x1, y1 = pos[v]
    activo = bool(fila["Disponible"])
    fig.add_trace(go.Scatter(
        x=[x0, x1], y=[y0, y1], mode="lines",
        line=dict(width=3 if activo else 1, dash="solid" if activo else "dash"),
        hovertemplate=f"{u}–{v}<br>Retardo: {fila['Retardo_ms']} ms"
                     f"<br>Banda: {fila['Banda_Mbps']} Mbps"
                     f"<br>Disponible: {activo}<extra></extra>",
        showlegend=False,
    ))
for nodo, (x, y) in pos.items():
    fig.add_trace(go.Scatter(
        x=[x], y=[y], mode="markers+text", text=[nodo], textposition="top center",
        marker=dict(size=28), showlegend=False, hoverinfo="text", hovertext=f"Router {nodo}"
    ))
fig.update_layout(height=450, margin=dict(l=20, r=20, t=20, b=20),
                  xaxis=dict(visible=False), yaxis=dict(visible=False))
st.plotly_chart(fig, width="stretch")

 # Calcular la ruta óptima según el criterio seleccionado y mostrar métricas.
ruta = None
try:
    if nx.has_path(G, "H", "B"):
        ruta = nx.shortest_path(G, "H", "B", weight=peso)
        saltos = len(ruta) - 1
        retardo_total = sum(G[u][v]["retardo"] for u, v in zip(ruta[:-1], ruta[1:]))
        capacidad = min(G[u][v]["banda"] for u, v in zip(ruta[:-1], ruta[1:]))
        if objetivo == "Mínimo de saltos (Johal)":
            costo = saltos
        elif objetivo == "Mínimo retardo":
            costo = retardo_total
        else:
            costo = sum(peso(u, v, G[u][v]) for u, v in zip(ruta[:-1], ruta[1:]))
        st.success("Ruta óptima recalculada: " + " → ".join(ruta))
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Saltos", saltos)
        col2.metric("Retardo total", f"{retardo_total:g} ms")
        col3.metric("Capacidad de ruta", f"{capacidad:g} Mbps")
        col4.metric("Costo según objetivo", f"{costo:.3f}" if isinstance(costo, float) else costo)
    else:
        st.error("No existe una ruta disponible entre H y B con la configuración actual.")
except (nx.NetworkXNoPath, nx.NodeNotFound):
    st.error("No existe una ruta disponible entre H y B con la configuración actual.")

 # Aplicación principio de optimalidad: mostrar los siguientes saltos hacia B desde cada router en la ruta óptima.
st.header("3. Sink Tree: siguientes saltos hacia B")
if ruta:
    arbol = nx.Graph()
    arbol.add_edges_from(zip(ruta[:-1], ruta[1:]))
    tabla_saltos = []
    for i, nodo in enumerate(ruta):
        siguiente = ruta[i + 1] if i + 1 < len(ruta) else "Destino (B)"
        tabla_saltos.append({"Router": nodo, "Siguiente salto hacia B": siguiente})
    st.dataframe(pd.DataFrame(tabla_saltos), hide_index=True, width="stretch")
    st.caption("Esta tabla muestra los siguientes saltos de la ruta óptima actual, no todas las rutas de respaldo.")
else:
    st.info("El Sink Tree no puede calcularse porque no hay una ruta disponible.")

 # Comparación de las tres rutas de la guía: PSRC, SSRC y TSRC. Se muestran métricas de disponibilidad, saltos, retardo y capacidad mínima.
st.header("4. Comparación de las tres rutas de la guía")
rutas_referencia = {
    "PSRC": ["H", "D", "A", "B"],
    "SSRC": ["H", "E", "J", "C", "B"],
    "TSRC": ["H", "O", "N", "J", "C", "B"],
}
# Calcular métricas para cada ruta de referencia y mostrar en una tabla.
resultados = []
for nombre, nodos in rutas_referencia.items():
    enlaces_ruta = list(zip(nodos[:-1], nodos[1:]))
    filas_por_enlace = []
    posible = True
    for u, v in enlaces_ruta:
        coincidencia = editado[
            (((editado["Origen"] == u) & (editado["Destino"] == v)) |
             ((editado["Origen"] == v) & (editado["Destino"] == u)))
        ]
        if coincidencia.empty or not bool(coincidencia.iloc[0]["Disponible"]):
            posible = False
            break
        filas_por_enlace.append(coincidencia.iloc[0])
    if posible:
        retardos = sum(float(f["Retardo_ms"]) for f in filas_por_enlace)
        bandas = min(float(f["Banda_Mbps"]) for f in filas_por_enlace)
        resultados.append({
            "Ruta": nombre, "Recorrido": " → ".join(nodos), "Disponible": "Sí",
            "Saltos": len(enlaces_ruta), "Retardo_ms": retardos, "Banda_min_Mbps": bandas
        })
    else:
        resultados.append({
            "Ruta": nombre, "Recorrido": " → ".join(nodos), "Disponible": "No",
            "Saltos": len(enlaces_ruta), "Retardo_ms": "—", "Banda_min_Mbps": "—"
        })
tabla_rutas = pd.DataFrame(resultados)
st.dataframe(tabla_rutas, hide_index=True, width="stretch")

 # Exportación de resultados a CSV para análisis posterior.
st.header("5. Exportar resultados")
csv = tabla_rutas.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Descargar resultados de rutas en CSV",
    data=csv,
    file_name="resultados_laboratorio_johal.csv",
    mime="text/csv",
)
st.caption(
    "Los retardos y capacidades son datos didácticos del laboratorio. "
    "El costo multicriterio es una extensión propuesta para esta práctica."
)
