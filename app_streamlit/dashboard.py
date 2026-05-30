import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from pathlib import Path
from plotly.subplots import make_subplots


# ==========================================
# 0. 網頁基本配置與
# ==========================================
st.set_page_config(
    page_title="Agent+BERT Multi-Asset Dashboard", layout="wide")
st.title("🤖 AI Agent + BERT 雙模型多標的量化情緒看板")

# ==========================================
# 1. 側邊欄控制項 (Sidebar Options)
# ==========================================
st.sidebar.header("⚙️ 標的與模型參數設定")

selected_ticker = st.sidebar.selectbox(
    "📈 請選擇目標股票標的：",
    ["AAPL", "NVDA", "INTC"]
)

# ==========================================
# 2. 動態資料讀取 (依據選定的 Ticker 載入對應 CSV)
# ==========================================


@st.cache_data
def load_ticker_data(ticker):
    project_root = Path(__file__).resolve().parents[1]
    file_name = project_root / "data" / "features" / "merged" / f"{ticker.lower()}_merged.csv"

    if not os.path.exists(file_name):
        raise FileNotFoundError(
            f"Missing dataset for {ticker}: {file_name}"
        )

    df = pd.read_csv(file_name)
    df['date'] = pd.to_datetime(df['date'])
    return df


# 載入當前選定標的的數據
df_ticker = load_ticker_data(selected_ticker)

# ==========================================
# 3. 互動時間與門檻過濾 (連動當前股票時間軸)
# ==========================================
min_date = df_ticker['date'].min().to_pydatetime()
max_date = df_ticker['date'].max().to_pydatetime()

# 日期範圍選擇器
date_range_selection = st.sidebar.date_input(
    "📅 指定時間範圍：",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Agent 情緒門檻拉桿
intensity_filter = st.sidebar.slider("🔥 Agent 最低情緒強度門檻：", 0.0, 1.0, 0.5)

# 執行動態時間與門檻遮罩過濾
if len(date_range_selection) == 2:
    start_date, end_date = date_range_selection
    df_filtered = df_ticker[(df_ticker['date'] >= pd.to_datetime(start_date)) & (
        df_ticker['date'] <= pd.to_datetime(end_date))].copy()
else:
    df_filtered = df_ticker.copy()

# 依據使用者選擇的時間跨度，動態調整圖表上的雜訊
time_delta = pd.to_datetime(end_date) - pd.to_datetime(start_date)

# 如果使用者看超過一年的全景圖，自動提高最低強度的天花板，防止點點塞爆網頁
if time_delta.days > 365:
    # 強制限制全景圖只看最重磅的新聞
    active_intensity_threshold = max(intensity_filter, 0.80)
else:
    active_intensity_threshold = intensity_filter

df_news_active = df_filtered[df_filtered['sentiment_intensity']
                             >= active_intensity_threshold]

# ==========================================
# 4. 建立 Plotly 雙 Y 軸互動圖表
# ==========================================
fig = make_subplots(specs=[[{"secondary_y": True}]])

# 軌道一：灰色股價收盤線 (左軸)
fig.add_trace(
    go.Scatter(
        x=df_filtered['date'],
        y=df_filtered['close'],
        name=f"{selected_ticker} Close Price",
        line=dict(color='#94a3b8', width=2)
    ),
    secondary_y=False
)

# 軌道二：利多新聞點 (紅色朝上三角形)
df_pos = df_news_active[df_news_active['direction'] == "利多 (Bullish)"]
df_pos["sentence_short"] = df_pos["sentence"].str.slice(0, 120) + "..."
fig.add_trace(
    go.Scatter(
        x=df_pos['date'],
        y=[df_filtered['close'].max()*1.02]*len(df_pos),
        name="Bullish News",
        mode='markers',
        marker=dict(size=12, color='#ef4444', symbol='triangle-up'),
        text=df_pos['sentence_short'],
        customdata=df_pos[['bert_prob_pos','agent_sentiment']],
        hovertemplate=
            "<b>Bullish News</b><br>" +
            "Time: %{x}<br>" +
            "BERT Pos: %{customdata[0]}<br>" +
            "Agent Sent: %{customdata[1]}<br>" +
            "%{text}<extra></extra>"
    ),
    secondary_y=False
)

# 軌道三：利空新聞點 (綠色朝下三角形)
df_neg = df_news_active[df_news_active['direction'] == "利空 (Bearish)"]
df_neg["sentence_short"] = df_neg["sentence"].str.slice(0, 120) + "..."

fig.add_trace(
    go.Scatter(
        x=df_neg['date'],
        y=[df_filtered['close'].min()*0.98]*len(df_neg),
        name="Bearish News",
        mode='markers',
        marker=dict(size=12, color='#22c55e', symbol='triangle-down'),
        text=df_neg['sentence_short'],
        customdata=df_neg[['bert_prob_neg','agent_sentiment']],
        hovertemplate=
            "<b>Bearish News</b><br>" +
            "Time: %{x}<br>" +
            "BERT Neg: %{customdata[0]}<br>" +
            "Agent Sent: %{customdata[1]}<br>" +
            "%{text}<extra></extra>"
    ),
    secondary_y=False
)

fig.update_layout(
    title=f"{selected_ticker} - Price vs News Events",
    xaxis_title="Date",
    hovermode="x unified",
    template="plotly_white",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)

fig.update_yaxes(title_text="<b>股價 (USD)</b>", secondary_y=False)
fig.update_yaxes(
    title_text="<b>Agent 情緒強度 (sentiment_intensity)</b>",
    range=[0,1],
    secondary_y=True)

st.plotly_chart(fig, width='stretch')

# ==========================================
# 5. 網頁下方：動態更新的特徵細節審查面板
# ==========================================
st.subheader(f"📰 {selected_ticker} 雙模型情緒特徵細節")
df_table = df_news_active[df_news_active['sentiment_intensity'] > 0]

if len(df_table) == 0:
    st.info(f"當前篩選條件下，{selected_ticker} 無觸發任何新聞事件。")
else:
    display_df = df_table[['date', 'direction', 'sentiment_intensity',
                           'bert_prob_pos', 'bert_prob_neg', 'sentence', 'reasoning']].copy()
    display_df.columns = ['時間', 'BERT 判定方向', 'Agent 衝擊強度',
                          'BERT 利多機率', 'BERT 利空機率', '新聞原始文本', 'Agent 推理邏輯']
    st.dataframe(display_df.sort_values(
        '時間', ascending=False), width='stretch')
