# stage1_keyword_filter.py
import sys
import argparse
import yaml
import re
import pandas as pd
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str, required=True)
    parser.add_argument("--input", type=str, required=True)
    args = parser.parse_args()
    
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    config_path = PROJECT_ROOT / "config" / "tickers" / f"{args.ticker.upper()}.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    print(f"[Stage 1] 正在載入原始數據...")
    df = pd.read_csv(args.input)

    # 提取 YAML 內的所有關鍵字實體
    keywords = [config['ticker'], config['name']] + config.get(
        'core_business', []) + config.get('supply_chain', []) + config.get('competitors', [])
    clean_keywords = [re.sub(r'\(.*\)', '', str(k)).strip() for k in keywords if k]
    pattern = '|'.join([re.escape(k) for k in clean_keywords])

    print(f"[Stage 1] 開始關鍵字正則過濾...")
    df_filtered = df[df['sentence'].str.contains(
        pattern, case=False, na=False)].reset_index(drop=True)

    output_path =  PROJECT_ROOT / "data" / "processed" / "stage1" / f"{args.ticker.upper()}.csv"
    df_filtered.to_csv(output_path, index=False, encoding='utf-8')
    print(
        f"[Stage 1] 完成！數據從 {len(df)} 筆減至 {len(df_filtered)} 筆，已存至 {output_path}")


if __name__ == "__main__":
    main()
