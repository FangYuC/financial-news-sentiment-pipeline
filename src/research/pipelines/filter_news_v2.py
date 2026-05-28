import subprocess
import argparse


"""
XXX0k news
   ↓
[Phase 1]
  Section routing
  Keyword filter
  Embedding filter
   ↓
20k candidates
   ↓
[Phase 2]
  LLM scoring (no hard reject)
   ↓
5k scored news
   ↓
[Phase 3]
  MCP + deep reasoning
   ↓
final alpha signals
"""


def main():
   parser = argparse.ArgumentParser(description="量化新聞篩選")
   parser.add_argument("--ticker", type=str, required=True, help="例如: AAPL")
   parser.add_argument("--input", type=str,
                        required=True, help="原始19萬筆新聞 CSV")
   args = parser.parse_args()

   ticker = args.ticker.lower()

   # 1. 執行階段一 (CPU 粗篩)
   print("\n=== ▶️ 啟動 Stage 1: 關鍵字過濾 ===")
   subprocess.run([
      "python", "-m",
      "research.pipelines.keyword_filter",
      "--ticker", ticker,
      "--input", args.input
], check=True)

   # 2. 執行階段二 (LLM 相關性過濾)
   print("\n=== ▶️ 啟動 Stage 2: LLM 相關性過濾 ===")
   subprocess.run([
      "python", "-m",
      "research.pipelines.llm_filter",
      "--ticker", ticker
], check=True)

   # 3. 執行階段三 (MCP 深度分析)
   print("\n=== ▶️ 啟動 Stage 3: MCP 深度特徵提取 ===")
   subprocess.run([
      "python", "-m",
      "research.pipelines.mcp_analyzer",
      "--ticker", ticker
], check=True)

   print(f"\n 所有階段執行完畢！最終成果已存至: {ticker}_high_freq_ai_features.csv")


if __name__ == "__main__":
   main()
