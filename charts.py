"""
charts.py
----------
Funzioni per la generazione dei grafici Plotly usati nella dashboard.
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

COLOR_SEQUENCE = px.colors.qualitative.Set3


def donut_chart(df: pd.DataFrame, names_col: str, values_col: str, title: str) -> go.Figure:
    if df.empty or df[values_col].sum() == 0:
        fig = go.Figure()
        fig.update_layout(title=title, annotations=[dict(text="Nessun dato", showarrow=False)])
        return fig

    fig = px.pie(
        df, names=names_col, values=values_col, hole=0.55,
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(
        title=title,
        showlegend=True,
        margin=dict(t=50, b=10, l=10, r=10),
        legend=dict(orientation="v"),
    )
    return fig


def target_vs_actual_bar(df: pd.DataFrame, label_col: str) -> go.Figure:
    """Barre affiancate Target % vs Effettiva % per titolo/settore."""
    if df.empty:
        fig = go.Figure()
        fig.update_layout(annotations=[dict(text="Nessun dato", showarrow=False)])
        return fig

    df_sorted = df.sort_values("effective_pct", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df_sorted[label_col], x=df_sorted["target_pct"],
        name="Target %", orientation="h", marker_color="#3D8BFD",
    ))
    fig.add_trace(go.Bar(
        y=df_sorted[label_col], x=df_sorted["effective_pct"],
        name="Effettiva %", orientation="h", marker_color="#F5A623",
    ))
    fig.update_layout(
        barmode="group",
        title="Target % vs Effettiva %",
        xaxis_title="%",
        margin=dict(t=50, b=10, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=max(300, 32 * len(df_sorted)),
    )
    return fig


def performance_gauge(total_gl_pct: float) -> go.Figure:
    """Piccolo indicatore a gauge per la performance complessiva del portafoglio."""
    color = "#2ECC71" if total_gl_pct >= 0 else "#E74C3C"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=total_gl_pct,
        number={"suffix": "%"},
        gauge={
            "axis": {"range": [-30, 30]},
            "bar": {"color": color},
            "steps": [
                {"range": [-30, 0], "color": "rgba(231,76,60,0.2)"},
                {"range": [0, 30], "color": "rgba(46,204,113,0.2)"},
            ],
        },
        title={"text": "Performance Totale"},
    ))
    fig.update_layout(margin=dict(t=40, b=10, l=20, r=20), height=250)
    return fig
