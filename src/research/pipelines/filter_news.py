import os
import yaml
import asyncio
import argparse
import pandas as pd
from typing import Literal
from jinja2 import Template
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from typing import Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from tqdm.asyncio import tqdm_asyncio

'''
[19 萬筆 股票新聞]
       │
       ▼  (Phase 1: 高速、嚴格的 AND 邏輯初篩)
[約 2~3 萬筆 潛在 Apple 新聞]
       │
       ▼  (Phase 2: Llama 3.3 + MCP Context Tool 結構化精準過濾)
[純度 100% 的 Apple 重大事件]
       │
       ▼  (Phase 3: 雙模型共識 / 特徵打分提取)
[產出：可用於波動率策略的 final_score 與 intensity]
'''

'''
┌─────────────────┐                 ┌────────────────┐
│  Refined News   │                 │  MySQL Market  │
│  (非結構化文本)  │                 │  (結構化數值)  │
└────────┬────────┘                 └───────┬────────┘
         │                                  │
         │         ┌───────────────┐        │
         └────────►│  MCP Server   │◄───────┘
                   │ (Data Bridge) │
                   └───────┬───────┘
                           │ 封裝成標準工具 (call_tool)
                           ▼
                   ┌───────────────┐
                   │ Local LLM 8B  │ (做出二階波動打分)
                   └───────────────┘
'''


# 1. 初始化非同步客戶端
aclient = AsyncOpenAI(
    api_key="ollama",
    base_url="http://localhost:11434/v1"
)

# 2. 定義結構化輸出 Pydantic 模型


class NewsFilterSchema(BaseModel):
    chain_of_thought: str = Field(..., description="簡短推理該新聞如何影響目標資產")
    is_target_relevant: bool = Field(..., description="新聞是否對目標資產具交易相關性")
    intensity_score: float = Field(..., description="情緒與事件衝擊強度，範圍 0~1")
    direction: Literal["positive", "negative", "neutral"]

# 3. 核心處理管道 (移除重複的 YAML 讀取，並修正為真正的結構化解析)


async def process_single_news(semaphore, news_id, sentence, timestamp, mcp_server, aclient, config, ticker="AAPL") -> Optional[dict]:
    async with semaphore:  # 這裡控制真正的併發限制
        try:
            # 向本地 MCP 服務器動態請求市場環境
            mcp_response = await mcp_server.call_tool(
                "get_market_context",
                arguments={"ticker": ticker, "timestamp_str": str(timestamp)}
            )
            market_context = mcp_response.content[0].text

            template_str = """ 
            你是一位資深金融分析師。 
            請評估新聞對 {{ name }} ({{ ticker }}) 的影響。 

            # === 市場環境 === 
            {{ market_context }} 

            # === 新聞內容 === 
            {{ sentence }} 

            # === 核心關注領域 === 
            {% for item in core_topics %}- {{ item }}{% endfor %} 

            # === 供應鏈 / 相關產業 === 
            {% for item in supply_chain %}- {{ item }}{% endfor %} 

            # === 宏觀敏感因子 === 
            {% for item in macro_factors %}- {{ item }}{% endfor %} 

            # === 推理規則 === 
            {% for rule in reasoning_rules %}- {{ rule }}{% endfor %} 
            """

            template = Template(template_str)
            prompt = template.render(
                name=config["name"],
                ticker=config["ticker"],
                market_context=market_context,
                sentence=sentence,
                core_topics=config.get("core_topics", []),
                supply_chain=config.get("supply_chain", []),
                macro_factors=config.get("macro_factors", []),
                reasoning_rules=config.get("reasoning_rules", [])
            )

            # 正確使用 Pydantic 結構化輸出功能
            completion = await aclient.beta.chat.completions.parse(
                model="llama3.1:8b",
                messages=[
                    {"role": "system", "content": "你是一個精準的 AI 交易員，必須遵循 schema 輸出。"},
                    {"role": "user", "content": prompt}
                ],
                response_format=NewsFilterSchema,  # 讓模型直接對齊 Pydantic
                timeout=45.0
            )

            # 透過 .parsed_match 直接取得強型別物件
            res_obj: NewsFilterSchema = completion.choices[0].message.parsed_match
            if not res_obj or not res_obj.is_target_relevant:
                return None

            direction = res_obj.direction
            raw_intensity = res_obj.intensity_score

            if direction == "positive":
                p_pos, p_neg, p_neu = raw_intensity, 0.0, max(
                    0.0, 1.0 - raw_intensity)
            elif direction == "negative":
                p_pos, p_neg, p_neu = 0.0, raw_intensity, max(
                    0.0, 1.0 - raw_intensity)
            else:
                p_pos, p_neg, p_neu = 0.0, 0.0, 1.0
                raw_intensity = 0.0

            return {
                "aligned_time": timestamp,
                "Sentence": sentence,
                "Prob_Pos": p_pos,
                "Prob_Neg": p_neg,
                "Prob_Neu": p_neu,
                "sentiment_intensity": raw_intensity,
                "reasoning": res_obj.chain_of_thought
            }

        except Exception as e:
            print(f"Error processing news ID {news_id}: {str(e)}")
            return None

# 4. 批次控制器


async def run_phase2_pipeline(df_refined_news, mcp_server, groq_async_client, config):
    semaphore = asyncio.Semaphore(3)

    tasks = []
    for idx, row in df_refined_news.iterrows():
        task = asyncio.create_task(
            process_single_news(
                semaphore=semaphore,
                news_id=idx,
                sentence=row['sentence'],
                timestamp=row['effective_trade_time'],
                mcp_server=mcp_server,
                aclient=groq_async_client,
                config=config
            )
        )
        tasks.append(task)

    results = await tqdm_asyncio.gather(*tasks, desc="LLM Processing")
    return pd.DataFrame([r for r in results if r is not None])


async def main(ticker: str, input_file: str):

    yaml_filename = f'{ticker.lower()}.yaml'
    output_filename = f"{ticker.lower()}_high_freq_ai_features.csv"

    print(f"正在處理標的: {ticker}")
    print(f"讀取新聞檔案: {input_file}")
    print(f"讀取設定檔案: {yaml_filename}")

    try:
        df_all_news = pd.read_csv(input_file)
    except FileNotFoundError:
        print(f" 錯誤：找不到新聞檔案 {input_file}")
        return

    try:
        with open(yaml_filename, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
    except FileNotFoundError:
        print(f" 錯誤：找不到設定檔案 {yaml_filename}")
        return

    keywords = [config['name'], config['ticker']] + \
        config.get("core_topics", [])
    pattern = '|'.join([str(k) for k in keywords if k])

    print(f"原始數據總量: {len(df_all_news)} 筆")
    df_filtered = df_all_news[df_all_news['sentence'].str.contains(
        pattern, case=False, na=False)].reset_index(drop=True)
    total_rows = len(df_filtered)
    print(f"經關鍵字初篩後剩餘: {total_rows} 筆 (已過濾掉不相關新聞)")

    CHUNK_SIZE = 100
    output_filename = f"{ticker.lower()}_high_freq_ai_features.csv"

    server_params = StdioServerParameters(
        command="python", args=["mcp_server.py"])

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("MCP 伺服器連線成功！")

            for start_idx in range(0, total_rows, CHUNK_SIZE):
                end_idx = min(start_idx + CHUNK_SIZE, total_rows)
                print(f"\n [批次進度] 正在處理第 {start_idx} 到 {end_idx} 筆新聞...")

                df_chunk = df_filtered.iloc[start_idx:end_idx]

                df_chunk_features = await run_phase2_pipeline(
                    df_refined_news=df_chunk,
                    mcp_server=session,
                    groq_async_client=aclient,
                    config=config
                )

                if not df_chunk_features.empty:
                    file_exists = os.path.exists(output_filename)
                    df_chunk_features.to_csv(
                        output_filename, mode='a', index=False,
                        header=not file_exists, encoding='utf-8'
                    )
                print(f" [自動存檔] 第 {start_idx} ~ {end_idx} 筆處理完畢。")

            print(f"\n 數據清洗完畢！最終特徵庫：{output_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="量化新聞特徵提取流水線")

    # 添加參數 (required=True 代表一定要輸入)
    parser.add_argument("--ticker", type=str, required=True,
                        help="股票代碼 (例如: AAPL, TSLA)")
    parser.add_argument("--input", type=str, required=True,
                        help="輸入的新聞 CSV 檔案路徑")

    args = parser.parse_args()

    # 執行主程式並傳入參數
    asyncio.run(main(ticker=args.ticker.upper(), input_file=args.input))
