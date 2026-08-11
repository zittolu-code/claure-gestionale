"""
app.py
-------
Dashboard per la gestione e il ribilanciamento di portafogli finanziari
multi-categoria con dati in tempo reale da Yahoo Finance.

Esecuzione:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd

from src import portfolio_manager as pm
from src import calculations as calc
from src import charts

st.set_page_config(
    page_title="Portfolio Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_CURRENCY = "EUR"


# ---------------------------------------------------------------------------
# STATO / DATI
# ---------------------------------------------------------------------------

if "data" not in st.session_state:
    st.session_state.data = pm.load_data()

if "editor_key" not in st.session_state:
    st.session_state.editor_key = 0


def refresh_from_disk():
    st.session_state.data = pm.load_data()


def persist():
    pm.save_data(st.session_state.data)
    st.cache_data.clear()


# ---------------------------------------------------------------------------
# SIDEBAR - FILTRI E GESTIONE
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("📊 Portfolio Dashboard")
    st.caption("Gestione e ribilanciamento portafogli multi-asset")

    st.divider()
    st.subheader("🔍 Filtri")

    all_portfolios = list(st.session_state.data.keys())
    view_mode = st.radio(
        "Vista",
        options=["Consolidata (tutti)"] + all_portfolios,
        index=0,
    )

    st.divider()
    if st.button("🔄 Aggiorna prezzi", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("➕ Nuovo sub-portafoglio")
    with st.form("new_portfolio_form", clear_on_submit=True):
        new_pf_name = st.text_input("Nome portafoglio", placeholder="es. Obbligazioni")
        submitted_pf = st.form_submit_button("Crea", use_container_width=True)
        if submitted_pf and new_pf_name:
            pm.add_portfolio(st.session_state.data, new_pf_name)
            persist()
            st.success(f"Portafoglio '{new_pf_name}' creato.")
            st.rerun()

    st.subheader("➕ Nuova posizione")
    with st.form("new_holding_form", clear_on_submit=True):
        h_portfolio = st.selectbox("Sub-portafoglio", options=all_portfolios or ["Azioni Singole"])
        h_ticker = st.text_input("Ticker (Yahoo Finance)", placeholder="es. AAPL, BTC-EUR, CASH")
        h_name = st.text_input("Nome descrittivo", placeholder="es. Apple Inc.")
        h_category = st.selectbox("Categoria", options=pm.DEFAULT_CATEGORIES)
        h_sector = st.selectbox("Settore / Tipologia", options=pm.DEFAULT_SECTORS)
        h_qty = st.number_input("Quantità", min_value=0.0, value=0.0, step=1.0, format="%.6f")
        h_avg_price = st.number_input("Prezzo medio carico (valuta nativa)", min_value=0.0, value=0.0, step=1.0)
        h_currency = st.selectbox("Valuta", options=["EUR", "USD", "GBP", "CHF"])
        h_target = st.number_input("Target % (sul totale complessivo)", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
        submitted_h = st.form_submit_button("Aggiungi posizione", use_container_width=True)
        if submitted_h and h_ticker and h_qty > 0:
            new_holding = {
                "ticker": h_ticker.upper().strip(),
                "name": h_name or h_ticker.upper(),
                "category": h_category,
                "sector": h_sector,
                "quantity": h_qty,
                "avg_price": h_avg_price,
                "currency": h_currency,
                "target_pct": h_target,
            }
            pm.add_holding(st.session_state.data, h_portfolio, new_holding)
            persist()
            st.success(f"Posizione '{h_ticker.upper()}' aggiunta a {h_portfolio}.")
            st.rerun()


# ---------------------------------------------------------------------------
# PREPARAZIONE DATI
# ---------------------------------------------------------------------------

raw_df = pm.to_dataframe(st.session_state.data)

if view_mode != "Consolidata (tutti)":
    raw_df = raw_df[raw_df["portfolio"] == view_mode]

if raw_df.empty:
    st.info("Nessuna posizione presente. Aggiungine una dalla barra laterale per iniziare.")
    st.stop()

with st.spinner("Recupero prezzi da Yahoo Finance..."):
    enriched_df = calc.enrich_with_market_data(raw_df, base_currency=BASE_CURRENCY)
    enriched_df = calc.compute_rebalance(enriched_df, base_currency=BASE_CURRENCY)

summary = calc.portfolio_summary(enriched_df)


# ---------------------------------------------------------------------------
# HEADER KPI
# ---------------------------------------------------------------------------

st.title("Panoramica Portafoglio" if view_mode == "Consolidata (tutti)" else f"Portafoglio: {view_mode}")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Valore Totale", f"€ {summary['total_value']:,.2f}")
k2.metric(
    "Profitto / Perdita",
    f"€ {summary['total_gain_loss']:,.2f}",
    f"{summary['total_gain_loss_pct']:+.2f}%",
)
k3.metric("N° Posizioni", summary["n_positions"])
errors = enriched_df[enriched_df.get("error").notna()] if "error" in enriched_df.columns else pd.DataFrame()
k4.metric("Sub-portafogli attivi", raw_df["portfolio"].nunique())

st.divider()


# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------

tab_dashboard, tab_rebalance, tab_positions, tab_manage = st.tabs(
    ["📈 Dashboard", "⚖️ Rebalancing", "📋 Posizioni", "🛠️ Gestione"]
)

# --- TAB 1: DASHBOARD -------------------------------------------------------
with tab_dashboard:
    c1, c2, c3 = st.columns(3)
    with c1:
        alloc_cat = calc.compute_allocation(enriched_df, "category")
        st.plotly_chart(
            charts.donut_chart(alloc_cat, "category", "market_value_base", "Allocazione per Categoria"),
            use_container_width=True,
        )
    with c2:
        alloc_sector = calc.compute_allocation(enriched_df, "sector")
        st.plotly_chart(
            charts.donut_chart(alloc_sector, "sector", "market_value_base", "Allocazione per Settore"),
            use_container_width=True,
        )
    with c3:
        alloc_ticker = calc.compute_allocation(enriched_df, "ticker")
        st.plotly_chart(
            charts.donut_chart(alloc_ticker, "ticker", "market_value_base", "Allocazione per Titolo"),
            use_container_width=True,
        )

    if view_mode == "Consolidata (tutti)":
        st.plotly_chart(
            charts.donut_chart(
                calc.compute_allocation(enriched_df, "portfolio"),
                "portfolio", "market_value_base", "Allocazione per Sub-Portafoglio",
            ),
            use_container_width=True,
        )

# --- TAB 2: REBALANCING -----------------------------------------------------
with tab_rebalance:
    st.subheader("Target % vs Effettiva % per titolo")

    target_sum = enriched_df["target_pct"].sum()
    if abs(target_sum - 100) > 0.5:
        st.warning(
            f"⚠️ La somma dei target % nella vista corrente è **{target_sum:.1f}%** "
            f"(dovrebbe essere 100%). Aggiusta i target dal tab Gestione per un rebalancing corretto."
        )

    st.plotly_chart(charts.target_vs_actual_bar(enriched_df, "ticker"), use_container_width=True)

    st.subheader("💡 Importi da acquistare / vendere per riallineare al target")

    reb_df = enriched_df[[
        "ticker", "name", "portfolio", "category", "currency",
        "effective_pct", "target_pct", "delta_pct",
        "rebalance_amount_base", "rebalance_amount_native", "rebalance_shares",
    ]].copy()

    reb_df = reb_df.rename(columns={
        "ticker": "Ticker", "name": "Nome", "portfolio": "Portafoglio", "category": "Categoria",
        "currency": "Valuta", "effective_pct": "Effettiva %", "target_pct": "Target %",
        "delta_pct": "Scostamento %", "rebalance_amount_base": f"Importo ({BASE_CURRENCY})",
        "rebalance_amount_native": "Importo (valuta nativa)", "rebalance_shares": "Quantità stimata",
    })

    def _color_delta(val):
        if val > 0.3:
            return "color: #E74C3C"  # sovrappeso -> vendere
        elif val < -0.3:
            return "color: #2ECC71"  # sottopeso -> comprare
        return ""

    def _color_amount(val):
        if val > 0:
            return "color: #2ECC71"  # da comprare
        elif val < 0:
            return "color: #E74C3C"  # da vendere
        return ""

    styled_reb = (
        reb_df.style
        .format({
            "Effettiva %": "{:.2f}%", "Target %": "{:.2f}%", "Scostamento %": "{:+.2f}%",
            f"Importo ({BASE_CURRENCY})": "{:+,.2f}", "Importo (valuta nativa)": "{:+,.2f}",
            "Quantità stimata": "{:+.4f}",
        })
        .applymap(_color_delta, subset=["Scostamento %"])
        .applymap(_color_amount, subset=[f"Importo ({BASE_CURRENCY})", "Importo (valuta nativa)"])
    )
    st.dataframe(styled_reb, use_container_width=True, hide_index=True)
    st.caption(
        "🟢 Importo positivo = **da acquistare** per raggiungere il target · "
        "🔴 Importo negativo = **da vendere** (posizione sovrappesata)."
    )

# --- TAB 3: POSIZIONI --------------------------------------------------------
with tab_positions:
    st.subheader("Dettaglio posizioni con Profitto / Perdita")

    pos_df = enriched_df[[
        "ticker", "name", "portfolio", "category", "sector", "quantity",
        "avg_price", "last_price", "currency", "market_value_base",
        "gain_loss_base", "gain_loss_pct", "day_change_pct",
    ]].copy()

    pos_df = pos_df.rename(columns={
        "ticker": "Ticker", "name": "Nome", "portfolio": "Portafoglio", "category": "Categoria",
        "sector": "Settore", "quantity": "Quantità", "avg_price": "Prezzo Medio",
        "last_price": "Prezzo Attuale", "currency": "Valuta",
        "market_value_base": f"Valore ({BASE_CURRENCY})", "gain_loss_base": f"P&L ({BASE_CURRENCY})",
        "gain_loss_pct": "P&L %", "day_change_pct": "Var. Giorno %",
    })

    def _color_gl(val):
        return "color: #2ECC71" if val >= 0 else "color: #E74C3C"

    styled_pos = (
        pos_df.style
        .format({
            "Quantità": "{:.4f}", "Prezzo Medio": "{:.2f}", "Prezzo Attuale": "{:.2f}",
            f"Valore ({BASE_CURRENCY})": "{:,.2f}", f"P&L ({BASE_CURRENCY})": "{:+,.2f}",
            "P&L %": "{:+.2f}%", "Var. Giorno %": "{:+.2f}%",
        })
        .applymap(_color_gl, subset=[f"P&L ({BASE_CURRENCY})", "P&L %", "Var. Giorno %"])
    )
    st.dataframe(styled_pos, use_container_width=True, hide_index=True)

    if not errors.empty:
        with st.expander("⚠️ Ticker con errori di recupero dati"):
            st.dataframe(errors[["ticker", "error"]], hide_index=True)

# --- TAB 4: GESTIONE ----------------------------------------------------------
with tab_manage:
    st.subheader("Modifica posizioni esistenti")
    st.caption("Modifica direttamente le celle della tabella e premi 'Salva modifiche'.")

    full_df = pm.to_dataframe(st.session_state.data)
    edited_df = st.data_editor(
        full_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"editor_{st.session_state.editor_key}",
        column_config={
            "portfolio": st.column_config.SelectboxColumn("Portafoglio", options=list(st.session_state.data.keys())),
            "category": st.column_config.SelectboxColumn("Categoria", options=pm.DEFAULT_CATEGORIES),
            "sector": st.column_config.SelectboxColumn("Settore", options=pm.DEFAULT_SECTORS),
            "target_pct": st.column_config.NumberColumn("Target %", min_value=0.0, max_value=100.0, step=0.5),
            "quantity": st.column_config.NumberColumn("Quantità", min_value=0.0, step=0.01),
            "avg_price": st.column_config.NumberColumn("Prezzo medio", min_value=0.0, step=0.01),
        },
    )

    col_save, col_reload = st.columns(2)
    with col_save:
        if st.button("💾 Salva modifiche", use_container_width=True, type="primary"):
            try:
                st.session_state.data = pm.from_dataframe(edited_df)
                persist()
                st.session_state.editor_key += 1
                st.success("Modifiche salvate correttamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Errore nel salvataggio: {e}")
    with col_reload:
        if st.button("↩️ Annulla modifiche", use_container_width=True):
            refresh_from_disk()
            st.session_state.editor_key += 1
            st.rerun()

    st.divider()
    st.subheader("🗑️ Elimina sub-portafoglio")
    del_pf = st.selectbox("Seleziona portafoglio da eliminare", options=list(st.session_state.data.keys()))
    if st.button("Elimina definitivamente", type="secondary"):
        pm.delete_portfolio(st.session_state.data, del_pf)
        persist()
        st.success(f"Portafoglio '{del_pf}' eliminato.")
        st.rerun()

st.divider()
st.caption(
    "Dati di mercato forniti da Yahoo Finance tramite `yfinance` · "
    "I prezzi possono essere ritardati di 15-20 minuti · Uso personale, non consulenza finanziaria."
)
