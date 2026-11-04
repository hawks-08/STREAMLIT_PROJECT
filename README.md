# 🌐 Laboratorio de redes · Optimalidad y Sink Tree

Aplicación interactiva en **Streamlit** para estudiar el principio de optimalidad y el *Sink Tree* con topología dinámica. Está basada en el estudio de Hartinder Singh Johal (2008) y permite modificar nodos, enlaces, retardos, capacidades, fallas y pesos, para ver cómo cambian las rutas óptimas hacia un destino.

> Los valores en ms y Mbps y la función multicriterio son construcciones de este laboratorio. **No** son resultados experimentales reportados por Johal.

---

## Características

- **Nodos dinámicos:** agregar (con sus enlaces), renombrar y eliminar routers.
- **Aristas dinámicas:** tabla editable (añadir y borrar filas, marcar enlaces como caídos) y formularios rápidos.
- **Origen y destino configurables** (la red original usa H → B).
- **Tres funciones objetivo:** mínimo de saltos (Johal), mínimo retardo y multicriterio (α, β, γ).
- **Comparación** entre la selección estática del artículo y la ruta recalculada con Dijkstra.
- **Sink Tree** con flechas hacia el destino y tabla de siguientes saltos (marca los empates).
- **Desarrollo manual de C(P)** arista por arista, útil para el informe.
- **Experimentos A–F** con un clic y **registro de evidencia** exportable.
- **Diseño personalizable:** 3 estilos visuales y 6 disposiciones del grafo.

---

## Requisitos

- Python 3.10 o superior
- Librerías (ver `requirements.txt`): `streamlit>=1.36`, `networkx>=3.0`, `plotly>=5.18`, `pandas>=2.0`, `scipy>=1.10`

## Instalación y ejecución (Windows)

1. Coloca `app.py` y `requirements.txt` en la misma carpeta.
2. Abre CMD en esa carpeta: en el Explorador, haz clic en la barra de direcciones, escribe `cmd` y pulsa Enter. Si no funciona, abre CMD y usa `cd /d "RUTA_DE_TU_CARPETA"`.
3. Instala las dependencias:
   ```
   python -m pip install -r requirements.txt
   ```
4. Ejecuta la aplicación:
   ```
   python -m streamlit run app.py
   ```
5. Abre <http://localhost:8501> si el navegador no se abre solo. Mantén CMD abierta mientras uses la app.

---

## Estructura del proyecto

```
.
├── app.py             # Aplicación completa (lógica del modelo + interfaz)
├── requirements.txt   # Dependencias
└── README.md
```

---

## Guía de uso

### Barra lateral
- **Estilo y disposición:** estilo visual, disposición del grafo, semilla, etiquetas de enlaces y tamaño de nodos.
- **Origen y destino:** routers `s` y `t`.
- **Función objetivo:** saltos, retardo o multicriterio. Los sliders α, β y γ solo se activan en multicriterio y se **normalizan** dividiendo cada uno entre la suma. Si los tres son 0, se usan pesos iguales (1/3).
- **Restablecer red original:** vuelve a la topología de la guía.

### Pestañas
| Pestaña | Qué hace |
|---|---|
| **1 · Red y enlaces** | Gestiona nodos y enlaces, y muestra la topología actual. |
| **2 · Rutas óptimas** | Fórmulas, ruta estática frente a ruta óptima, tabla de rutas, todas las rutas simples y desarrollo manual de C(P). |
| **3 · Sink Tree** | Árbol de siguientes saltos hacia el destino y tabla con ruta, saltos, retardo y costo de cada nodo. |
| **4 · Experimentos** | Botones A–F, resultados esperados y registro de evidencia. |
| **5 · Variables y exportación** | Tabla de variables del modelo con valores actuales y descargas en CSV. |

---

## Modelo matemático

Red: grafo no dirigido `G = (V, E)`, con origen `s` y destino `t`. Solo se usan enlaces disponibles (`f_ij = 1`, capacidad > 0).

- **Saltos (modelo original):** `H(P) = Σ h_ij`, con `h_ij = 1`
- **Retardo:** `D(P) = Σ d_ij`
- **Capacidad del camino:** `B(P) = min b_ij`
- **Multicriterio:**

  `C(P) = Σ [ α + β · d_ij / d_ref + γ · b_ref / b_ij ]`, con `α + β + γ = 1`

  `d_ref` y `b_ref` son los máximos positivos de la tabla de enlaces actual. Cambiarlos modifica la escala, así que **registra siempre ambos valores** al comparar experimentos.

La penalización `b_ref / b_ij` permite usar Dijkstra, pero **no equivale** a la capacidad del camino, que es `B(P) = min b_ij`.

**Principio de optimalidad:** si una ruta minimiza una función aditiva de costos no negativos, cada subcamino también es óptimo desde su propio router. El **Sink Tree** fija un solo siguiente salto por nodo hacia el destino: no incluye rutas de respaldo ni todas las aristas.

---

## Topología y datos iniciales

Enlaces de la guía (retardo en ms, capacidad en Mbps):

| Enlace | ms | Mbps | Enlace | ms | Mbps |
|---|---|---|---|---|---|
| H–D | 8 | 100 | J–C | 8 | 100 |
| D–A | 9 | 100 | C–B | 6 | 100 |
| A–B | 7 | 100 | H–O | 7 | 100* |
| H–E | 5 | 50 | O–N | 9 | 50* |
| E–J | 10 | 50 | N–J | 9 | 100* |

\* La guía no especifica las capacidades de H–O, O–N y N–J; solo indica B(P3) = 50 Mbps. Se asumieron estos valores, que cumplen esa condición. Puedes editarlos en la tabla.

Rutas preconfiguradas del artículo (selección estática, por prioridad):

| Etiqueta | Ruta | Saltos |
|---|---|---|
| PSRC | H–D–A–B | 3 |
| SSRC | H–E–J–C–B | 4 |
| TSRC | H–O–N–J–C–B | 5 |

La selección estática toma la primera de estas rutas con todos sus enlaces disponibles y solo aplica cuando origen = H y destino = B. Si renombras o eliminas nodos de estas rutas, quedan como no disponibles.

---

## Experimentos

| Prueba | Acción | Evidencia esperada |
|---|---|---|
| **A** Réplica original | Red original, mínimo de saltos | H = 3, 4, 5 → se selecciona P1 |
| **B** Cambio de retardo | H–D = 40 ms, mínimo retardo | D(P1) = 56, D(P2) = 29, D(P3) = 39 ms → mejor de las tres: P2 |
| **C** Fallo primario | H–D caído | La estática elige SSRC; compárala con el óptimo recalculado |
| **D** Doble fallo | H–D y H–E caídos | Solo queda TSRC (P3) |
| **E** Cuello de botella | E–J = 5 Mbps (multicriterio) | B(P2) = 5 Mbps; penalización de E–J = 20 |
| **F** Cambio de pesos | (1,0,0), (0,1,0), (0,0,1), (0.5,0.35,0.15) | Calcular C(P) a mano y contrastar |

Con los 10 enlaces de la guía solo existen esas tres rutas simples de H a B. La advertencia de la prueba B (el óptimo del grafo completo puede diferir del mejor entre las tres) importa cuando agregas enlaces o nodos.

---

## Exportaciones

- `resultados_rutas.csv`: rutas, métricas y parámetros (objetivo, α, β, γ, d_ref, b_ref).
- `sink_tree.csv`: siguiente salto, ruta, saltos, retardo y costo por nodo.
- `enlaces.csv`: tabla de enlaces actual.
- `registro_experimentos.csv`: registro de evidencia acumulado en la sesión.

Los CSV usan codificación UTF-8 con BOM para abrirse bien en Excel.

---

## Notas y limitaciones

- El estado vive en la sesión del navegador: al recargar la página se pierde. Descarga los CSV antes de cerrar.
- En los empates del Sink Tree, el algoritmo elige uno de los siguientes saltos equivalentes. La columna *Observación* lo indica.
- Las rutas simples se limitan a 500 para no ralentizar la app en redes densas.
- Para desplegar este procedimiento en routers reales faltarían detección de fallos, instalación de rutas y temporización.

---

## Referencia

Johal, H. S. (2008). *Optimality Principle Based Sink Tree Methodology for Adaptive Static Routing Using Multiple Route Configuration Scheme*. Advances in Electrical and Electronics Engineering / WCECS 2008. DOI: [10.1109/WCECS.2008.21](https://doi.org/10.1109/WCECS.2008.21)
