import pandas as pd

def merge_stock_news(df_stock, df_news_features):

    df_stock = df_stock.copy()
    df_news = df_news_features.copy()

    df_stock["Date"] = pd.to_datetime(df_stock["Date"])
    df_news["aligned_time"] = pd.to_datetime(df_news["aligned_time"])

    df_merged = pd.merge(
        df_stock,
        df_news,
        left_on="Date",
        right_on="aligned_time",
        how="left"
    )

    return df_merged