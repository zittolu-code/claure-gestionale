"""
data_fetcher.py
----------------
Wrapper attorno a yfinance per il recupero di prezzi, valute e metadati
dei titoli, con caching per evitare chiamate ripetute e limiti di rate.
"""

import streamlit as st
import yfinance as yf
import pandas as pd


# ---------------------------------------------------------------------------
# PREZZI TITOLI
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def get_last_price(ticker: str) -> dict:
    """
    Recupera l'ultimo prezzo disponibile per un ticker, la valuta nativa,
    il nome esteso e la variazione giornaliera %.
    Ritorna un dizionario con valori di default (None / 0) in caso di errore,
    così l'app non si blocca se un ticker non è valido o Yahoo è irraggiungibile.
    """
    result = {
        "price": None,
        "currency": "USD",
        "name": ticker,
        "day_change_pct": 0.0,
        "error": None,
    }
    try:
        tk = yf.Ticker(ticker)
        # fast_info è molto più leggero di .info e sufficiente per prezzo/valuta
        fast = tk.fast_info
        price = fast.get("lastPrice") or fast.get("last_price")
        prev_close = fast.get("previousClose") or fast.get("previous_close")
        currency = fast.get("currency") or "USD"

        if price is None:
            # fallback: ultimo giorno di storico
            hist = tk.history(period="5d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                if prev_close is None and len(hist) > 1:
                    prev_close = float(hist["Close"].iloc[-2])

        if price is None:
            result["error"] = "Prezzo non disponibile"
            return result

        day_change_pct = 0.0
        if prev_close:
            day_change_pct = (price - prev_close) / prev_close * 100

        # nome esteso: tentativo leggero, non blocca se fallisce
        try:
            name = tk.info.get("shortName") or tk.info.get("longName") or ticker
        except Exception:
            name = ticker

        result.update(
            price=float(price),
            currency=currency,
            name=name,
            day_change_pct=float(day_change_pct),
        )
        return result
    except Exception as e:
        result["error"] = str(e)
        return result


@st.cache_data(ttl=300, show_spinner=False)
def get_prices_batch(tickers: tuple) -> pd.DataFrame:
    """
    Recupera i prezzi per una lista di ticker in un'unica chiamata batch
    (più efficiente di N chiamate singole). Ritorna un DataFrame indicizzato
    per ticker con colonne: price, currency, day_change_pct, error.
    """
    tickers = [t for t in tickers if t and t.upper() != "CASH"]
    if not tickers:
        return pd.DataFrame(columns=["price", "currency", "day_change_pct", "error"])

    rows = {}
    try:
        data = yf.download(
            tickers=tickers,
            period="5d",
            group_by="ticker",
            progress=False,
            threads=True,
            auto_adjust=False,
        )
    except Exception:
        data = None

    for t in tickers:
        info = get_last_price(t)
        rows[t] = {
            "price": info["price"],
            "currency": info["currency"],
            "day_change_pct": info["day_change_pct"],
            "name": info["name"],
            "error": info["error"],
        }

    return pd.DataFrame.from_dict(rows, orient="index")


# ---------------------------------------------------------------------------
# CAMBI VALUTA
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def get_fx_rate(from_ccy: str, to_ccy: str = "EUR") -> float:
    """
    Ritorna il tasso di cambio per convertire 1 unità di from_ccy in to_ccy.
    Usa i ticker Yahoo Finance del tipo 'EURUSD=X'.
    Se from_ccy == to_ccy, ritorna 1.0.
    """
    if from_ccy == to_ccy:
        return 1.0

    pair = f"{from_ccy}{to_ccy}=X"
    try:
        tk = yf.Ticker(pair)
        fast = tk.fast_info
        rate = fast.get("lastPrice") or fast.get("last_price")
        if rate is None:
            hist = tk.history(period="5d")
            if not hist.empty:
                rate = float(hist["Close"].iloc[-1])
        if rate:
            return float(rate)
    except Exception:
        pass

    # fallback: prova la coppia inversa e inverti
    try:
        inv_pair = f"{to_ccy}{from_ccy}=X"
        tk = yf.Ticker(inv_pair)
        hist = tk.history(period="5d")
        if not hist.empty:
            inv_rate = float(hist["Close"].iloc[-1])
            if inv_rate:
                return 1.0 / inv_rate
    except Exception:
        pass

    return 1.0  # ultima spiaggia: nessuna conversione


def convert_to_base(amount: float, currency: str, base_currency: str = "EUR") -> float:
    """Converte un importo dalla sua valuta nativa alla valuta base scelta."""
    rate = get_fx_rate(currency, base_currency)
    return amount * rate
