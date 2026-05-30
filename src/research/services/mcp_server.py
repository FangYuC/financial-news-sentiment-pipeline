import sys
import logging

import pandas as pd
from pathlib import Path
from src.research.services.db_service import load_data_from_sql
from mcp.server.fastmcp import FastMCP

# 建立一個名為市場上下文的 MCP 服務
app = FastMCP("MarketContextServer")

logger = logging.getLogger(__name__)

logger.info("SERVER STARTED")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))
GLOBAL_MARKET_DF = load_data_from_sql(table_name="market")

GLOBAL_MARKET_DF = None

def get_market_df():
    global GLOBAL_MARKET_DF
    if GLOBAL_MARKET_DF is None:
        GLOBAL_MARKET_DF = load_data_from_sql(table_name="market")
    return GLOBAL_MARKET_DF

@app.tool()
def get_market_context(ticker: str, timestamp_str: str) -> str:
    """
    根據傳入的時間戳，動態計算當前的市場上下文（5日ATR與財報季狀態）。
    """
    try:
        target_time = pd.to_datetime(timestamp_str)
        
        df_all = get_market_df()
        df_prices = df_all[df_all['Symbol'] == ticker].copy()

        if df_prices is None or df_prices.empty:
            return f"Error: 數據庫中找不到股票 {ticker} 的資料"

        # 2. 確保 timestamp 欄位名稱是 MySQL 欄位 'Date'，並設為 Index
        if 'Date' in df_prices.columns:
            df_prices['Date'] = pd.to_datetime(df_prices['Date'])
            df_prices = df_prices.set_index('Date').sort_index()

        # 尋找最接近該時間點的歷史數據
        idx = df_prices.index.get_indexer([target_time], method='pad')[0]

        if idx == -1:
            return f"Error: 找不到該股票 {ticker} 在時間點 {timestamp_str} 之前的歷史數據"

        # 動態計算過去 70 根 K 線（約 5 個交易日）的 ATR
        sub_df = df_prices.iloc[max(0, idx-70):idx+1].copy()
        sub_df['range'] = sub_df['High'] - sub_df['Low']
        current_atr = sub_df['range'].mean()

        # 簡單判斷是否為財報季 (4, 7, 10, 1月)
        is_earnings = target_time.month in [1, 4, 7, 10]
        regime = "Earnings Season" if is_earnings else "Normal Trading"

        return f"Ticker: {ticker}, Dynamic_5D_ATR: {current_atr:.4f}, Regime: {regime}"
    except Exception as e:
        return f"Error fetching context: {str(e)}"


if __name__ == "__main__":
    # 啟動 MCP 伺服器 (預設透過 stdio 通訊)
    app.run()
