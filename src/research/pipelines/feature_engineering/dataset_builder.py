import argparse
import pandas as pd

from app.core.paths import PathManager
from src.research.services.db_service import load_data_from_sql
from src.research.services.preprocess_service import add_sentiment
from src.research.pipelines.feature_engineering.time_alignment import MarketCalendarAligner
from src.research.pipelines.feature_engineering.news_aggregation import aggregate_news_features


def merge_stock_news(df_stock: pd.DataFrame, df_news: pd.DataFrame) -> pd.DataFrame:
    """
    Merge stock and news features on aligned time.
    """

    df_stock = df_stock.copy()    
    df_news = df_news.copy()
    df_news = df_news.rename(columns={"date": "news_date"})
    
    df_stock.columns = df_stock.columns.str.lower()

    df_stock["date"] = pd.to_datetime(df_stock["date"])
    df_news["aligned_time"] = pd.to_datetime(df_news["aligned_time"])

    df_merged = pd.merge(
        df_stock,
        df_news,
        left_on="date",
        right_on="aligned_time",
        how="left"
    )
    df_merged.drop(columns=["aligned_time", "news_date"], inplace=True, errors="ignore")
    
    return df_merged


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Final feature engineering layer (lightweight).

    Only:
    - fill missing values
    - derive simple signals
    - compute returns
    """

    df = df.copy()
    print("build_features", df.columns)

    # 1. Handle missing values
    fill_zero_cols = [
        "bert_prob_pos",
        "bert_prob_neg",
        "bert_prob_neu",
        "bert_sentiment",
        "agent_prob_pos",
        "agent_prob_neg",
        "agent_prob_neu",
        "agent_sentiment",
        "sentiment",
        "sentiment_divergence"
    ]

    for col in fill_zero_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0.0)

    df["direction"] = "無"
    
    # Agent 判定有衝擊強度 (強度 > 0) 且 BERT 語意利多機率 > 利空機率
    pos_condition = (df['bert_sentiment'] > 0) & (df['agent_sentiment'] > 0)
    df.loc[pos_condition, 'direction'] = "利多 (Bullish)"
    
    # Agent 判定有衝擊強度 (強度 > 0) 且 BERT 語意利空機率 > 利多機率
    neg_condition = (df['bert_sentiment'] < 0) & (df['agent_sentiment'] < 0)
    df.loc[neg_condition, 'direction'] = "利空 (Bearish)"
    
    df["return"] = df["close"].pct_change() * 100
    df["return"] = df["return"].fillna(0.0)

    return df


def build_dataset(
    df_stock: pd.DataFrame,
    df_news: pd.DataFrame,
    schedule: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Full pipeline:
    stock + news → aligned + aggregated → merged → final dataset
    """

    # -------------------------
    # 1. Align news time
    # -------------------------
    aligner = MarketCalendarAligner()
    schedule = aligner.get_schedule(
    start_date="2008-01-01"
    )

    df_news["aligned_time"] = df_news["date"].apply(
        lambda x: aligner.align(x, schedule)
    )
    
    df_news = add_sentiment(df_news)
    print("build_dataset", df_news.columns)

    # -------------------------
    # 2. Aggregate news features
    # -------------------------

    market_features = aggregate_news_features(df_news)
        
    df_news = df_news.merge(market_features, on="aligned_time", how="left")

    # -------------------------
    # 3. Merge stock + news
    # -------------------------
    df_merged = merge_stock_news(df_stock, df_news)

    # -------------------------
    # 4. Final feature engineering
    # -------------------------
    df_final = build_features(df_merged)

    return df_final


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--market_symbol", type=str,
                        required=False, default="AAPL")
    args = parser.parse_args()
    
    paths = PathManager(ticker=args.market_symbol.upper())

    stock = load_data_from_sql(table_name="market")
    
    df_stock = stock[stock['Symbol'] == f'{args.market_symbol.upper()}']
    df_news = pd.read_csv(
        paths.stage3 / f"{args.market_symbol.lower()}_high_freq_ai_features.csv"
        )
    
    df_final = build_dataset(df_stock, df_news)
    
    output_path = paths.merged / f"{args.market_symbol.lower()}_merged.csv"
    df_final.to_csv(output_path, index=False)
    # print(df_final.head())
