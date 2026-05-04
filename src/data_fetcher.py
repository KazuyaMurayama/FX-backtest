"""
data_fetcher.py — FX価格・金利データ取得モジュール

データソース（全てAPIキー不要）:
  - FRED: 直接CSV URL方式（1971年〜, 55年分）
  - Frankfurter API: バックアップ（1999年〜）
  - yfinance: 補完用（2000年頃〜）

SPEC.md §3 準拠。
"""
from __future__ import annotations

import time
import logging
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ─── 定数 ────────────────────────────────────────────────────────────────────

CACHE_DIR = Path(__file__).parent.parent / "data" / "raw"
FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRANKFURTER_BASE = "https://api.frankfurter.dev/v1"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; fx-backtest/1.0)"}

# 通貨ペア → FREDシリーズID
FX_SERIES: dict[str, str] = {
    "USDJPY": "DEXJPUS",
    "GBPUSD": "DEXUSUK",
    "EURUSD": "DEXUSEU",
    "AUDUSD": "DEXUSAL",
    "NZDUSD": "DEXUSNZ",
    "USDCHF": "DEXSZUS",
    "USDCAD": "DEXCAUS",
}

# 金利データ → FREDシリーズID
RATE_SERIES: dict[str, str] = {
    "USD_FEDFUNDS": "FEDFUNDS",
    "JPY_CALLRATE": "IRSTCI01JPM156N",
    "AUD_RBA":      "IRSTCI01AUM156N",
    "EUR_ECB":      "ECBDFR",
    "GBP_BOE":      "IUDSOIA",
    "NZD_RBNZ":     "IRSTCI01NZM156N",
}

# ─── FRED 直接URL取得 ──────────────────────────────────────────────────────────

def _fetch_fred_raw(series_id: str, max_retries: int = 4) -> pd.DataFrame:
    """FREDからCSVを直接取得。指数バックオフ付きリトライ。"""
    url = f"{FRED_BASE}?id={series_id}"
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            df = pd.read_csv(
                StringIO(resp.text),
                index_col=0,
                parse_dates=True,
                na_values=".",
            )
            df.index.name = "date"
            df.columns = [series_id]
            return df
        except (requests.Timeout, requests.ConnectionError) as e:
            wait = 2 ** attempt
            logger.warning(f"FRED {series_id} attempt {attempt+1} failed: {e}. Retry in {wait}s")
            time.sleep(wait)
        except requests.HTTPError as e:
            logger.error(f"FRED {series_id} HTTP error: {e}")
            raise
    raise RuntimeError(f"FRED {series_id}: {max_retries}回リトライ後も取得失敗")


def _fetch_frankfurter(base: str, quote: str, start: str = "1999-01-04") -> pd.DataFrame:
    """Frankfurter APIでバックアップ取得（1999年〜）。"""
    end = pd.Timestamp.today().strftime("%Y-%m-%d")
    url = f"{FRANKFURTER_BASE}/{start}..{end}?from={base}&to={quote}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    records = {pd.Timestamp(d): v[quote] for d, v in data["rates"].items()}
    df = pd.DataFrame.from_dict(records, orient="index", columns=[f"{base}{quote}"])
    df.index.name = "date"
    return df.sort_index()


# ─── キャッシュ付き取得 ───────────────────────────────────────────────────────

def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{name}.csv"


def _load_cache(name: str) -> pd.DataFrame | None:
    path = _cache_path(name)
    if path.exists():
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.index.name = "date"
        logger.info(f"Cache hit: {name} ({len(df)} rows)")
        return df
    return None


def _save_cache(df: pd.DataFrame, name: str) -> None:
    df.to_csv(_cache_path(name))
    logger.info(f"Cache saved: {name} ({len(df)} rows)")


# ─── 公開API ─────────────────────────────────────────────────────────────────

def fetch_fx(pair: str, use_cache: bool = True) -> pd.DataFrame:
    """
    FX日足データを取得（キャッシュ優先）。

    Parameters
    ----------
    pair : str
        通貨ペア名。例: 'USDJPY', 'EURUSD'
    use_cache : bool
        Trueならdata/raw/にCSVキャッシュを使用

    Returns
    -------
    pd.DataFrame
        columns=['close'], index=DatetimeIndex, 欠損補完済み
    """
    pair = pair.upper()
    cache_name = f"fx_{pair}"

    if use_cache:
        cached = _load_cache(cache_name)
        if cached is not None:
            return cached

    if pair not in FX_SERIES:
        raise ValueError(f"未対応通貨ペア: {pair}. 対応: {list(FX_SERIES.keys())}")

    series_id = FX_SERIES[pair]
    logger.info(f"Fetching {pair} from FRED ({series_id})...")

    try:
        df = _fetch_fred_raw(series_id)
    except RuntimeError:
        logger.warning(f"FRED失敗。Frankfurterにフォールバック: {pair}")
        base, quote = pair[:3], pair[3:]
        df = _fetch_frankfurter(base, quote)

    # 前方補完（土日・祝日欠損）→ 欠損行除去
    df = df.ffill().dropna()
    df.columns = ["close"]

    # FRED は USD基軸で逆方向になる場合がある (例: USD/CHF → CHF/USD)
    # DEXSZUS は CHF per USD → USDCHF として逆数をとる必要はない（1 USD = N CHF）
    # ただし DEXUSUK は USD per GBP → GBPUSDとして正しい
    # DEXJPUS は JPY per USD → USDJPYとして正しい
    # DEXUSAL は USD per AUD → AUDUSDとして正しい
    # DEXCAUS は CAD per USD → USDCADとして正しい
    # DEXSZUS は CHF per USD → USDCHFとして正しい

    if use_cache:
        _save_cache(df, cache_name)

    return df


def fetch_rate(name: str, use_cache: bool = True) -> pd.DataFrame:
    """
    政策金利・短期金利データを取得（月次）。

    Parameters
    ----------
    name : str
        金利名。例: 'USD_FEDFUNDS', 'JPY_CALLRATE'

    Returns
    -------
    pd.DataFrame
        columns=['rate'], index=DatetimeIndex (月次)
    """
    cache_name = f"rate_{name}"

    if use_cache:
        cached = _load_cache(cache_name)
        if cached is not None:
            return cached

    if name not in RATE_SERIES:
        raise ValueError(f"未対応金利: {name}. 対応: {list(RATE_SERIES.keys())}")

    series_id = RATE_SERIES[name]
    logger.info(f"Fetching rate {name} from FRED ({series_id})...")

    df = _fetch_fred_raw(series_id)
    df = df.dropna()
    df.columns = ["rate"]

    if use_cache:
        _save_cache(df, cache_name)

    return df


def fetch_all_fx(pairs: list[str] | None = None, use_cache: bool = True) -> dict[str, pd.DataFrame]:
    """全通貨ペアを取得してdictで返す。"""
    if pairs is None:
        pairs = list(FX_SERIES.keys())

    result = {}
    for pair in pairs:
        try:
            result[pair] = fetch_fx(pair, use_cache=use_cache)
            logger.info(f"  {pair}: OK ({len(result[pair])}行)")
        except Exception as e:
            logger.error(f"  {pair}: FAILED - {e}")
    return result


def fetch_all_rates(use_cache: bool = True) -> dict[str, pd.DataFrame]:
    """全金利データを取得してdictで返す。"""
    result = {}
    for name in RATE_SERIES:
        try:
            result[name] = fetch_rate(name, use_cache=use_cache)
            logger.info(f"  {name}: OK ({len(result[name])}行)")
        except Exception as e:
            logger.error(f"  {name}: FAILED - {e}")
    return result


# ─── データ概要レポート ───────────────────────────────────────────────────────

def data_summary(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """取得データのサマリーDataFrameを返す。"""
    rows = []
    for name, df in data.items():
        rows.append({
            "name": name,
            "rows": len(df),
            "start": df.index.min().date(),
            "end": df.index.max().date(),
            "years": round((df.index.max() - df.index.min()).days / 365.25, 1),
            "missing_pct": round(df.isnull().mean().iloc[0] * 100, 2),
        })
    return pd.DataFrame(rows).set_index("name")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    print("=" * 60)
    print("FX データ取得テスト")
    print("=" * 60)

    # 全FXデータ取得
    print("\n--- FX 価格データ ---")
    fx_data = fetch_all_fx()
    print(data_summary(fx_data).to_string())

    # 全金利データ取得
    print("\n--- 政策金利データ ---")
    rate_data = fetch_all_rates()
    print(data_summary(rate_data).to_string())

    print("\n✅ 全データ取得完了。data/raw/ にキャッシュ保存済み。")
