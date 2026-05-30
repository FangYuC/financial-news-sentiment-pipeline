import pandas as pd


def add_sentiment(news: pd.DataFrame) -> pd.DataFrame:
    """
    Create sentiment from probability outputs.
    Must be executed BEFORE aggregation.
    """

    news = news.copy()

    # safety check
    if "bert_prob_pos" not in news.columns or "bert_prob_neg" not in news.columns:
        raise ValueError("Missing prob_pos or prob_neg columns")

    news["bert_prob_pos"] = news["bert_prob_pos"].fillna(0.0)
    news["bert_prob_neg"] = news["bert_prob_neg"].fillna(0.0)
    news["agent_prob_pos"] = news["agent_prob_pos"].fillna(0.0)
    news["agent_prob_neg"] = news["agent_prob_neg"].fillna(0.0)

    # core feature
    news["bert_sentiment"] = news["bert_prob_pos"] - news["bert_prob_neg"]
    news["agent_sentiment"] = news["agent_prob_pos"] - news["agent_prob_neg"]
    
    news["sentiment"] = (
        news["bert_sentiment"] * 0.6 + news["agent_sentiment"] * 0.4
    )
    
    news["sentiment_divergence"] = abs(
        news["bert_sentiment"] - news["agent_sentiment"]
    )

    return news