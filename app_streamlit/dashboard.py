import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# ==========================================
# 0. 網頁基本配置與美化
# ==========================================
st.set_page_config(
    page_title="Agent+BERT Multi-Asset Dashboard", layout="wide")
st.title("🤖 AI Agent + BERT 雙模型多標的量化情緒看板")

# ==========================================
# 1. 側邊欄控制項 (Sidebar Options)
# ==========================================
st.sidebar.header("⚙️ 標的與模型參數設定")

# 【核心功能】：讓使用者挑選想要觀看的股票標的
selected_ticker = st.sidebar.selectbox(
    "📈 請選擇目標股票標的：",
    ["AAPL", "NVDA"]
)

# ==========================================
# 2. 動態資料讀取 (依據選定的 Ticker 載入對應 CSV)
# ==========================================


@st.cache_data
def load_ticker_data(ticker):
    file_name = f"{ticker.lower()}_merged.csv"

    # 檢查檔案是否存在，若存在則讀取真實資料
    if os.path.exists(file_name):
        df = pd.read_csv(file_name)
        df['Date'] = pd.to_datetime(df['Date'])
        return df
    else:
        # 💡 防禦性機制：如果使用者還沒產生該股票的 CSV，自動生成模擬資料供介面測試
        st.sidebar.warning(f"找不到 {file_name}，目前顯示為模擬測試數據。")
        date_range = pd.date_range(
            start="2008-02-12", end="2025-04-30", freq="12H")
        n = len(date_range)
        np.random.seed(hash(ticker) % 1000)

        close_prices = 100 + np.cumsum(np.random.normal(0.05, 1.5, n))
        intensities = np.zeros(n)
        bert_pos = np.zeros(n)
        bert_neg = np.zeros(n)
        sentences = [""] * n

        # 隨機塞入 5 筆重磅新聞
        news_idx = [50, 180, 300, 450, 620]
        for i, idx in enumerate(news_idx):
            intensities[idx] = np.random.uniform(0.7, 0.95)
            if i % 2 == 0:
                bert_pos[idx], bert_neg[idx] = np.random.uniform(0.6, 0.9), 0.1
                sentences[idx] = f"【利多】外資調升 {ticker} 目標價，市場預期需求大爆發。"
            else:
                bert_pos[idx], bert_neg[idx] = 0.1, np.random.uniform(0.6, 0.9)
                sentences[idx] = f"【利空】{ticker} 面臨供應鏈關鍵組件短缺風險。"

        df_dummy = pd.DataFrame({
            'Date': date_range, 'Open': close_prices, 'High': close_prices*1.01, 'Low': close_prices*0.99,
            'Close': close_prices, 'Volume': np.random.randint(1000, 5000, n), 'Symbol': ticker,
            'sentence': sentences, 'bert_prob_pos': bert_pos, 'bert_prob_neg': bert_neg,
            'sentiment_intensity': intensities
        })
        # 補齊方向標籤
        df_dummy['direction'] = "無新聞"
        df_dummy.loc[(df_dummy['sentiment_intensity'] > 0) & (
            df_dummy['bert_prob_pos'] > df_dummy['bert_prob_neg']), 'direction'] = "利多 (Bullish)"
        df_dummy.loc[(df_dummy['sentiment_intensity'] > 0) & (
            df_dummy['bert_prob_neg'] > df_dummy['bert_prob_pos']), 'direction'] = "利空 (Bearish)"
        return df_dummy


# 載入當前選定標的的數據
df_ticker = load_ticker_data(selected_ticker)

# ==========================================
# 3. 互動時間與門檻過濾 (連動當前股票時間軸)
# ==========================================
min_date = df_ticker['Date'].min().to_pydatetime()
max_date = df_ticker['Date'].max().to_pydatetime()

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
    df_filtered = df_ticker[(df_ticker['Date'] >= pd.to_datetime(start_date)) & (
        df_ticker['Date'] <= pd.to_datetime(end_date))].copy()
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
        x=df_filtered['Date'],
        y=df_filtered['Close'],
        name=f"{selected_ticker} Close Price",
        line=dict(color='#cbd5e1', width=2)
    ),
    secondary_y=False
)

# 軌道二：利多新聞點 (紅色朝上三角形)
df_pos = df_news_active[df_news_active['direction'] == "利多 (Bullish)"]
fig.add_trace(
    go.Scatter(
        x=df_pos['Date'],
        y=df_pos['sentiment_intensity'],
        name="BERT 利多 + Agent",
        mode='markers',
        marker=dict(size=14, color='#d62728', symbol='triangle-up',
                    line=dict(width=1, color='black')),
        hovertemplate="<b>時間:</b> %{x}<br>" +
                      "<b>Agent 強度:</b> %{y}<br>" +
                      "<b>BERT 利多機率:</b> %{text}<br>",
        text=df_pos['bert_prob_pos'].round(2).astype(str),
        customdata=df_pos['sentence']
    ), secondary_y=True
)

# 軌道三：利空新聞點 (綠色朝下三角形)
df_neg = df_news_active[df_news_active['direction'] == "利空 (Bearish)"]
fig.add_trace(
    go.Scatter(
        x=df_neg['Date'],
        y=df_neg['sentiment_intensity'],
        name="BERT 利空 + Agent",
        mode='markers',
        marker=dict(size=14, color='#2ca02c', symbol='triangle-down',
                    line=dict(width=1, color='black')),
        hovertemplate="<b>時間:</b> %{x}<br>" +
                      "<b>Agent 強度:</b> %{y}<br>" +
                      "<b>BERT 利空機率:</b> %{text}<br>",
        text=df_neg['bert_prob_neg'].round(2).astype(str),
        customdata=df_neg['sentence']
    ), secondary_y=True
)

fig.update_layout(
    title=f"📈 {selected_ticker} ｜新聞情緒與股價互動分析",
    xaxis_title="時間軸 (Date)",
    hovermode="x unified",
    legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)")
)

fig.update_yaxes(title_text="<b>股價 (USD)</b>", secondary_y=False)
fig.update_yaxes(
    title_text="<b>Agent 情緒強度 (sentiment_intensity)</b>", secondary_y=True)

st.plotly_chart(fig, width='stretch')

# ==========================================
# 5. 網頁下方：動態更新的特徵細節審查面板
# ==========================================
st.subheader(f"📰 {selected_ticker} 雙模型情緒特徵細節")
df_table = df_news_active[df_news_active['sentiment_intensity'] > 0]

if len(df_table) == 0:
    st.info(f"當前篩選條件下，{selected_ticker} 無觸發任何新聞事件。")
else:
    display_df = df_table[['Date', 'direction', 'sentiment_intensity',
                           'bert_prob_pos', 'bert_prob_neg', 'sentence', 'reasoning']].copy()
    display_df.columns = ['時間', 'BERT 判定方向', 'Agent 衝擊強度',
                          'BERT 利多機率', 'BERT 利空機率', '新聞原始文本', 'Agent 推理邏輯']
    st.dataframe(display_df.sort_values(
        '時間', ascending=False), width='stretch')
