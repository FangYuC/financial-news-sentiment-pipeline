"""
News Feature Aggregation

將已完成時間對齊(aligned_time)的新聞資料聚合成市場時間窗特徵。

Input:
    News DataFrame

Required Columns:
    aligned_time
    sentiment
    prob_pos
    prob_neg

Output:
    Feature DataFrame
"""

from __future__ import annotations

import pandas as pd


def aggregate_news_features(
    news_df: pd.DataFrame,
    min_news_threshold: int = 2,
) -> pd.DataFrame:
    """
    Aggregate news sentiment features by aligned_time.

    Parameters
    ----------
    news_df : pd.DataFrame
        News dataframe after time alignment.

    min_news_threshold : int, default=2
        Minimum news count required to keep full signal strength.

    Returns
    -------
    pd.DataFrame
        Aggregated sentiment features.
    """

    required_cols = {
        "aligned_time",
        "sentiment",
        "bert_prob_pos",
        "bert_prob_neg",
    }

    missing_cols = required_cols - set(news_df.columns)

    if missing_cols:
        raise ValueError(
            f"Missing required columns: {missing_cols}"
        )

    sentiment_features = (
        news_df
        .groupby("aligned_time")
        .agg(
            avg_sentiment=("sentiment", "mean"),
            std_sentiment=("sentiment", "std"),
            
            avg_pos=("bert_prob_pos", "mean"),
            avg_neg=("bert_prob_neg", "mean"),
            
            max_pos=("bert_prob_pos", "max"),
            max_neg=("bert_prob_neg", "max"),
            
            news_count=("sentiment", "count"),
        )
        .reset_index()
    )

    sentiment_features["net_sentiment"] = (
        sentiment_features["avg_pos"]
        - sentiment_features["avg_neg"]
    )

    # 新聞數量不足時降低權重
    low_volume_mask = (
        sentiment_features["news_count"]
        < min_news_threshold
    )

    sentiment_features.loc[
        low_volume_mask,
        "net_sentiment"
    ] *= 0.5

    return sentiment_features
