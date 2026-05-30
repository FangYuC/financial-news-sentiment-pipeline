# mcp_server.py

import asyncio
import json
from datetime import datetime

from mcp.server.fastmcp import FastMCP


# =========================================================
# 建立 MCP Server
# =========================================================

mcp = FastMCP("MarketContextServer")


# =========================================================
# Tool:
# get_market_context
# =========================================================

@mcp.tool()
async def get_market_context(
    ticker: str,
    timestamp_str: str
) -> str:
    """
    回傳指定時間點的市場環境資訊
    """

    try:

        # =================================================
        # 時間解析
        # =================================================

        ts = datetime.fromisoformat(
            timestamp_str.replace("Z", "")
        )

        # =================================================
        # Mock 市場環境
        # =================================================

        # 🔥 之後這裡可以改成：
        # - MySQL
        # - DuckDB
        # - Polygon
        # - AlphaVantage
        # - 自建 volatility features

        market_context = {

            "ticker": ticker,

            "timestamp": str(ts),

            "market_regime": "normal",

            "vix_level": 22.5,

            "atr_14": 3.2,

            "volume_ratio": 1.4,

            "macro_environment": "rate_cut_expectation",

            "risk_level": "medium",

            "event_risk": [
                "fed_policy",
                "china_supply_chain"
            ]
        }

        return json.dumps(
            market_context,
            ensure_ascii=False
        )

    except Exception as e:

        return json.dumps({
            "error": str(e)
        })


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    try:

        print("🚀 MCP Market Context Server Started")

        # stdio transport
        mcp.run(transport="stdio")

    except Exception as e:

        import traceback

        print(traceback.format_exc())

        input("MCP Server Crashed...")
