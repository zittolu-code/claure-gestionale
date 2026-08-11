"""
portfolio_manager.py
---------------------
Gestisce la struttura dati dei portafogli (sub-portafogli + posizioni),
la persistenza su file JSON locale e le operazioni CRUD di base.
"""

import json
import os
import pandas as pd

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "portfolios.json")

DEFAULT_CATEGORIES = ["Azioni Singole", "ETF", "Crypto", "Cash"]
DEFAULT_SECTORS = [
    "Tech", "Semiconductors", "Neocloud", "Financial Services",
    "Healthcare", "Energy", "Consumer", "Industrial", "Cash / Liquidità", "Altro",
]

HOLDING_COLUMNS = [
    "ticker", "name", "category", "sector", "quantity",
    "avg_price", "currency", "target_pct",
]


def _seed_data() -> dict:
    """Dataset di esempio mostrato al primo avvio, così l'app non parte vuota."""
    return {
        "Azioni Singole": [
            {"ticker": "AAPL", "name": "Apple Inc.", "category": "Azioni Singole",
             "sector": "Tech", "quantity": 10, "avg_price": 150.0,
             "currency": "USD", "target_pct": 8.0},
            {"ticker": "NVDA", "name": "NVIDIA Corp.", "category": "Azioni Singole",
             "sector": "Semiconductors", "quantity": 15, "avg_price": 90.0,
             "currency": "USD", "target_pct": 10.0},
        ],
        "ETF": [
            {"ticker": "SWDA.MI", "name": "iShares Core MSCI World", "category": "ETF",
             "sector": "Diversificato", "quantity": 100, "avg_price": 75.0,
             "currency": "EUR", "target_pct": 40.0},
        ],
        "Crypto": [
            {"ticker": "BTC-EUR", "name": "Bitcoin", "category": "Crypto",
             "sector": "Crypto", "quantity": 0.15, "avg_price": 40000.0,
             "currency": "EUR", "target_pct": 15.0},
        ],
        "Cash": [
            {"ticker": "CASH", "name": "Liquidità EUR", "category": "Cash",
             "sector": "Cash / Liquidità", "quantity": 1, "avg_price": 5000.0,
             "currency": "EUR", "target_pct": 27.0},
        ],
    }


def load_data() -> dict:
    """Carica i portafogli da disco, creando un dataset di esempio se assente."""
    if not os.path.exists(DATA_PATH):
        data = _seed_data()
        save_data(data)
        return data
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        data = _seed_data()
        save_data(data)
        return data


def save_data(data: dict) -> None:
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def to_dataframe(data: dict) -> pd.DataFrame:
    """Appiattisce la struttura {portafoglio: [holding, ...]} in un unico DataFrame."""
    rows = []
    for portfolio_name, holdings in data.items():
        for h in holdings:
            row = dict(h)
            row["portfolio"] = portfolio_name
            rows.append(row)
    if not rows:
        return pd.DataFrame(columns=["portfolio"] + HOLDING_COLUMNS)
    df = pd.DataFrame(rows)
    for col in HOLDING_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df


def from_dataframe(df: pd.DataFrame) -> dict:
    """Ricostruisce la struttura {portafoglio: [holding, ...]} da un DataFrame piatto."""
    data = {}
    for portfolio_name, group in df.groupby("portfolio"):
        holdings = group[HOLDING_COLUMNS].to_dict(orient="records")
        data[portfolio_name] = holdings
    return data


def add_portfolio(data: dict, name: str) -> dict:
    if name and name not in data:
        data[name] = []
    return data


def delete_portfolio(data: dict, name: str) -> dict:
    data.pop(name, None)
    return data


def add_holding(data: dict, portfolio_name: str, holding: dict) -> dict:
    data.setdefault(portfolio_name, [])
    data[portfolio_name].append(holding)
    return data
