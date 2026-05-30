# stage3_mcp_analyzer.py
import sys
import argparse
import asyncio
import yaml
import os
import re
import pandas as pd
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from jinja2 import Template
from tqdm.asyncio import tqdm_asyncio
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))


def format_bert_output(bert_df: pd.DataFrame) -> pd.DataFrame:
    bert_df = bert_df.copy()

    bert_df = bert_df.rename(columns={
        "pred_label": "bert_pred_label",
        "prob_neu": "bert_prob_neu",
        "prob_pos": "bert_prob_pos",
        "prob_neg": "bert_prob_neg",
    })

    return bert_df


class Stage3AnalysisSchema(BaseModel):
    chain_of_thought: str = Field(...,
                                  description="結合推理規則與市場環境，分析該新聞如何影響目標資產，不超過50字")
    intensity_score: float = Field(..., description="情緒與事件衝擊強度，範圍 0~1")
    direction: Literal["positive", "negative", "neutral"]


async def run_stage3_deep_analysis(semaphore, row, mcp_server, aclient, config) -> dict:
    async with semaphore:
        try:
            # 1. 透過 MCP 取得動態上下文
            mcp_response = await mcp_server.call_tool(
                "get_market_context",
                arguments={
                    "ticker": config["ticker"],
                    "timestamp_str": str(row['date'])
                }
            )
            market_context = mcp_response.content[0].text

            # 2. 建立 Prompt
            template_str = """ 
            你是一位資深金融分析師。請評估新聞對 {{ name }} ({{ ticker }}) 的影響。 

            # 市場環境
            {{ market_context }}

            # 新聞
            {{ sentence }}

            # 分析規則
            {% for rule in reasoning_rules %}
            - {{ rule }}
            {% endfor %}

            # 核心要求
            請只輸出 JSON，不要任何額外文字。

            chain_of_thought 必須：
            - 1~2句
            - ≤40繁體中文字
            - 不可條列
            - 只描述「原因 → 結論」

            intensity_score：
            - 0~1 浮點數

            direction：
            - positive / negative / neutral
            """

            template = Template(template_str)
            prompt = template.render(
                name=config["name"],
                ticker=config["ticker"],
                market_context=market_context,
                sentence=row['sentence'],
                core_topics=config.get("core_topics", []),
                supply_chain=config.get("supply_chain", []),
                macro_factors=config.get("macro_factors", []),
                reasoning_rules=config.get("reasoning_rules", [])
            )

            # 3. 呼叫 LLM 並解析
            completion = await aclient.beta.chat.completions.parse(
                model="llama3.1:8b",
                messages=[{"role": "user", "content": prompt}],
                response_format=Stage3AnalysisSchema,
                timeout=30.0
            )

            res = completion.choices[0].message.parsed
            reasoning = re.sub(r"\s+", " ", res.chain_of_thought) if res else ""
            if not res:
                return None

            p_pos, p_neg, p_neu = 0.0, 0.0, 0.0
            if res.direction == "positive":
                p_pos = res.intensity_score
                p_neu = max(0.0, 1.0 - p_pos)
            elif res.direction == "negative":
                p_neg = res.intensity_score
                p_neu = max(0.0, 1.0 - p_neg)
            else:
                p_neu = 1.0

            return {
                "date": row['date'],
                "sentence": row['sentence'],

                # ===== BERT =====
                "bert_pred_label": row.get("bert_pred_label"),
                "bert_prob_pos": row.get("bert_prob_pos"),
                "bert_prob_neg": row.get("bert_prob_neg"),
                "bert_prob_neu": row.get("bert_prob_neu"),

                # ===== Agent =====
                "agent_prob_pos": p_pos,
                "agent_prob_neg": p_neg,
                "agent_prob_neu": p_neu,

                # ===== Intensity =====
                "agent_intensity": res.intensity_score if res.direction != "neutral" else 0.0,

                "reasoning": reasoning
            }
        except Exception as e:
            print(f"[Stage3 Error] 處理新聞失敗: {e}")
            return None


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str, required=True)
    args = parser.parse_args()

    # === 定義 project root ===
    PROJECT_ROOT = Path(__file__).resolve().parents[3]

    # === config 路徑 ===
    config_path = PROJECT_ROOT / "config" / "tickers" / f"{args.ticker.upper()}.yaml"

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # === input data 路徑 ===
    input_filename = PROJECT_ROOT / "data" / "processed" / "stage2" / f"{args.ticker.upper()}.csv"

    if not input_filename.exists():
        print(f"[Stage 3] 錯誤：找不到上游檔案 {input_filename}")
        return

    df = pd.read_csv(input_filename)
    df = format_bert_output(df)

    # === output ===
    output_filename = PROJECT_ROOT / "data" / "features" / f"{args.ticker.lower()}_high_freq_ai_features.csv"
    print(f"[Stage 3] 開始掛載 MCP 對 {len(df)} 筆新聞進行量化打分...")
    aclient = AsyncOpenAI(
        api_key="ollama", base_url="http://localhost:11434/v1")
    stage3_semaphore = asyncio.Semaphore(5)
    CHUNK_SIZE = 10

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "src.research.services.mcp_server"],
        env={"PYTHONPATH": "D:/research_project/src"})

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            for start_idx in range(0, len(df), CHUNK_SIZE):
                end_idx = min(start_idx + CHUNK_SIZE, len(df))
                df_chunk = df.iloc[start_idx:end_idx]

                tasks = [run_stage3_deep_analysis(
                    stage3_semaphore, row, session, aclient, config) for _, row in df_chunk.iterrows()]
                results = await tqdm_asyncio.gather(*tasks, desc=f"Analyzing {start_idx}-{end_idx}")

                clean_res = [r for r in results if r is not None]
                if clean_res:
                    pd.DataFrame(clean_res).to_csv(
                        output_filename,
                        mode='a',
                        index=False,
                        header=not os.path.exists(output_filename),
                        encoding='utf-8'
                    )

if __name__ == "__main__":
    asyncio.run(main())
