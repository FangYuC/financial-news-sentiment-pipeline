# stage2_llm_filter.py

import asyncio
import argparse
import yaml
import re
import pandas as pd

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from tqdm.asyncio import tqdm_asyncio
from pathlib import Path


# =========================================================
# Stage 2 Schema
# =========================================================

class Stage2FilterSchema(BaseModel):

    relevance_score: float = Field(
        ...,
        description="新聞與目標資產的相關性分數，0~1"
    )

    reasoning: str = Field(
        ...,
        description="一句話簡短推理"
    )


# =========================================================
# 單筆新聞分析
# =========================================================

async def filter_news(
    semaphore,
    sentence,
    aclient,
    config
):

    async with semaphore:

        try:

            system_prompt = f"""
            你是一個專業金融事件篩選器。
            
            請判斷以下新聞是否可能對
            {config['name']} ({config['ticker']})
            產生直接或間接影響。

            請評估以下面向：

            - 營運
            - 供應鏈
            - 市場情緒
            - 波動率
            - 資金流向
            - 產業鏈

            即使新聞沒有直接提到公司名稱，
            若涉及相關供應鏈、宏觀事件、
            利率、關稅、AI資本支出、
            消費需求、半導體產業等，
            也可能具有高度相關性。

            # 核心關注領域
            {", ".join(config.get("core_topics", []))}

            # 供應鏈
            {", ".join(config.get("supply_chain", []))}

            # 宏觀敏感因子
            {", ".join(config.get("macro_factors", []))}
            
            請輸出：

            - 一句話
            - 不可換行
            - 不可列點
            """

            completion = await aclient.beta.chat.completions.parse(

                model="llama3.1:8b",

                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"新聞內容：{sentence}"
                    }
                ],

                response_format=Stage2FilterSchema,

                timeout=15.0
            )

            res = completion.choices[0].message.parsed
            reasoning = re.sub(r"\s+", " ", res.reasoning)

            if not res:
                return {
                    "score": 0.0,
                    "reasoning": "parse_failed"
                }

            return {
                "score": float(res.relevance_score),
                "reasoning": reasoning
            }

        except Exception as e:

            print(f"[Stage2 Error] {e}")

            return {
                "score": 0.0,
                "reasoning": "exception"
            }


# =========================================================
# Main
# =========================================================

async def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--ticker",
        type=str,
        required=True
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=0.35
    )

    args = parser.parse_args()

    # =====================================================
    # 載入 YAML
    # =====================================================

    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    
    config_path = PROJECT_ROOT / "config" / "tickers" / f"{args.ticker.upper()}.yaml"
    
    with open(
        config_path,
        "r",
        encoding="utf-8"
    ) as f:

        config = yaml.safe_load(f)

    # =====================================================
    # 載入 Stage1
    # =====================================================

    input_filename = PROJECT_ROOT / "data" / "processed" / "stage1" / f"{args.ticker.upper()}.csv"


    df = pd.read_csv(input_filename)

    print(f"\n[Stage 2] 載入 Stage1 資料: {len(df)} 筆")

    if len(df) == 0:

        print("[Stage 2] ⚠️ Stage1 為空")

        return

    # =====================================================
    # Ollama Client
    # =====================================================

    aclient = AsyncOpenAI(
        api_key="ollama",
        base_url="http://localhost:11434/v1"
    )

    # =====================================================
    # Async Tasks
    # =====================================================

    semaphore = asyncio.Semaphore(10)

    tasks = [

        filter_news(
            semaphore,
            row['sentence'],
            aclient,
            config
        )

        for _, row in df.iterrows()
    ]

    results = await tqdm_asyncio.gather(
        *tasks,
        desc="Stage2 Filtering"
    )

    # =====================================================
    # Merge Results
    # =====================================================

    df["relevance_score"] = [
        r["score"] for r in results
    ]

    df["stage2_reasoning"] = [
        r["reasoning"] for r in results
    ]

    # =====================================================
    # Soft Threshold
    # =====================================================

    df_filtered = df[
        df["relevance_score"] >= args.threshold
    ].reset_index(drop=True)

    # =====================================================
    # Save
    # =====================================================

    output_path = PROJECT_ROOT / "data" / "processed" / "stage2" / f"{args.ticker.upper()}.csv"

    df_filtered.to_csv(
        output_path,
        index=False,
        encoding="utf-8"
    )

    print("\n====================================")
    print(f"[Stage 2] 完成")
    print(f"Threshold: {args.threshold}")
    print(f"保留新聞數: {len(df_filtered)}")
    print(f"輸出檔案: {output_path}")
    print("====================================\n")


# =========================================================
# Entry
# =========================================================

if __name__ == "__main__":

    asyncio.run(main())
