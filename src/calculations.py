"""
calculations.py
-----------------
Logica di business: calcolo valori di mercato, profitto/perdita,
percentuali effettive vs target e importi di rebalancing.
"""

import pandas as pd
from src.data_fetcher import get_prices_batch, get_fx_rate


def enrich_with_market_data(df: pd.DataFrame, base_currency: str = "EUR") -> pd.DataFrame:
    """
    Arricchisce il DataFrame delle posizioni con:
    - last_price (prezzo corrente nella valuta nativa; per Cash = avg_price)
    - market_value (quantity * last_price, valuta nativa)
    - market_value_base (convertito in valuta base, es. EUR)
    - cost_basis, cost_basis_base
    - gain_loss_base, gain_loss_pct
    - day_change_pct
    """
    if df.empty:
        for col in ["last_price", "market_value", "market_value_base", "cost_basis",
                    "cost_basis_base", "gain_loss_base", "gain_loss_pct", "day_change_pct"]:
            df[col] = []
        return df

    df = df.copy()
    tickers = tuple(sorted(set(df.loc[df["category"] != "Cash", "ticker"].dropna())))
    prices_df = get_prices_batch(tickers)

    last_prices = []
    day_changes = []
    for _, row in df.iterrows():
        if row["category"] == "Cash" or row["ticker"] == "CASH":
            last_prices.append(row["avg_price"])  # per il cash il "prezzo" è il valore stesso
            day_changes.append(0.0)
        else:
            if row["ticker"] in prices_df.index and prices_df.loc[row["ticker"], "price"]:
                last_prices.append(prices_df.loc[row["ticker"], "price"])
                day_changes.append(prices_df.loc[row["ticker"], "day_change_pct"] or 0.0)
            else:
                # fallback: se il prezzo non è disponibile, usa il prezzo medio di carico
                last_prices.append(row["avg_price"])
                day_changes.append(0.0)

    df["last_price"] = last_prices
    df["day_change_pct"] = day_changes

    df["market_value"] = df["quantity"] * df["last_price"]
    df["cost_basis"] = df["quantity"] * df["avg_price"]

    # conversione valuta -> base
    fx_cache = {}
    def _fx(ccy):
        if ccy not in fx_cache:
            fx_cache[ccy] = get_fx_rate(ccy, base_currency)
        return fx_cache[ccy]

    df["fx_rate"] = df["currency"].apply(_fx)
    df["market_value_base"] = df["market_value"] * df["fx_rate"]
    df["cost_basis_base"] = df["cost_basis"] * df["fx_rate"]

    df["gain_loss_base"] = df["market_value_base"] - df["cost_basis_base"]
    df["gain_loss_pct"] = df.apply(
        lambda r: (r["gain_loss_base"] / r["cost_basis_base"] * 100) if r["cost_basis_base"] else 0.0,
        axis=1,
    )
    return df


def compute_allocation(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Aggrega il valore di mercato (base) per una colonna di raggruppamento."""
    if df.empty:
        return pd.DataFrame(columns=[group_col, "market_value_base", "pct"])
    agg = df.groupby(group_col, as_index=False)["market_value_base"].sum()
    total = agg["market_value_base"].sum()
    agg["pct"] = agg["market_value_base"] / total * 100 if total else 0.0
    return agg.sort_values("market_value_base", ascending=False)


def compute_rebalance(df: pd.DataFrame, base_currency: str = "EUR") -> pd.DataFrame:
    """
    Calcola, per ogni posizione:
    - effective_pct: peso attuale sul totale complessivo
    - target_pct: peso desiderato (inserito dall'utente)
    - delta_pct: scostamento (effective - target)
    - rebalance_amount_base: importo da comprare (+) o vendere (-) in valuta base
    - rebalance_amount_native: stesso importo convertito nella valuta nativa del titolo
    - rebalance_shares: quantità approssimativa di unità/azioni da comprare o vendere
    """
    if df.empty:
        return df

    df = df.copy()
    total_value = df["market_value_base"].sum()
    df["effective_pct"] = df["market_value_base"] / total_value * 100 if total_value else 0.0
    df["target_pct"] = pd.to_numeric(df["target_pct"], errors="coerce").fillna(0.0)
    df["delta_pct"] = df["effective_pct"] - df["target_pct"]

    # importo (in valuta base) necessario per riportare la posizione al target
    df["rebalance_amount_base"] = (df["target_pct"] / 100 * total_value) - df["market_value_base"]
    df["rebalance_amount_native"] = df["rebalance_amount_base"] / df["fx_rate"]

    df["rebalance_shares"] = df.apply(
        lambda r: (r["rebalance_amount_native"] / r["last_price"]) if r["last_price"] else 0.0,
        axis=1,
    )
    return df


def portfolio_summary(df: pd.DataFrame) -> dict:
    """Ritorna KPI aggregati: valore totale, P&L totale, P&L %, N° posizioni."""
    if df.empty:
        return {"total_value": 0.0, "total_gain_loss": 0.0, "total_gain_loss_pct": 0.0, "n_positions": 0}
    total_value = df["market_value_base"].sum()
    total_cost = df["cost_basis_base"].sum()
    total_gl = total_value - total_cost
    total_gl_pct = (total_gl / total_cost * 100) if total_cost else 0.0
    return {
        "total_value": total_value,
        "total_gain_loss": total_gl,
        "total_gain_loss_pct": total_gl_pct,
        "n_positions": len(df),
    }
