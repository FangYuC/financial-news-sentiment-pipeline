# 🤖 AI Agent + BERT Financial Sentiment Dashboard

A production-style full-stack system for financial news sentiment analysis and multi-asset visualization, combining **NLP (FinBERT / ModernBERT)**, **AI agent signals**, and **interactive dashboards**.

---

## 📊 Overview

This project builds a **multi-asset sentiment analysis system** that:

- Extracts sentiment from financial news using BERT-based models
- Enhances signals with an AI agent-based scoring layer
- Aligns sentiment with stock price movement
- Provides an interactive dashboard for analysis

It is designed as a **modular system with separated frontend and backend architecture**.

---

## 🏗️ Architecture

Streamlit (UI)
   ↓
FastAPI (Backend API)
   ↓
Data Service Layer
   ↓
BERT / FinBERT Models
   ↓
Stock & News Dataset

---

## 📁 Project Structure

```

project/
│
├── app/                         # FastAPI app
│   ├── main.py
│   ├── api/
│   │   ├── news.py
│   │   ├── sentiment.py
│   │   ├── stocks.py
│   │   └── pipeline.py
│   │
│   ├── services/
│   │   ├── crawler_service.py
│   │   ├── preprocess_service.py
│   │   ├── sentiment_service.py
│   │   ├── stock_filter_service.py
│   │   └── merge_service.py
│   │
│   ├── models/
│   │   ├── finbert_model.py
│   │   ├── modernbert_model.py
│   │   └── ensemble_model.py
│   │
│   ├── schemas/
│   │   ├── news_schema.py
│   │   └── sentiment_schema.py
│   │
│   └── core/
│       ├── config.py
│       └── logging.py
|   
├── app_streamlit/          # Streamlit dashboard (UI layer)
│   └── dashboard.py
│
├── src/                    # Core ML / NLP logic
│   └── research/
|
│        ├── api/
│        │   └── main.py
|        |
│        ├── pipelines/
|        |   ├── feature_engineering
|        |   |   ├── dataset_builder.py
|        |   | 
|        |   ├── news_filtering
|        |   |   ├── keyword_filter.py        # Stage 1
|        |   |   ├── llm_filter.py            # Stage 2
|        |   |   ├── mcp_analyzer.py          # Stage 3
|        |   |  
|        |   ├── orchestration/
|        |   ├── processing/
|        |   ├── sentiment/

|        |
│        ├── data_pipeline/
|        |   ├── ingestion/
|        |   |   ├──sources/
│        │   |      ├── nyt.py
│        │   |      ├── wsj.py
│        │   |      ├── cnbc.py
|        |   |
|        |   ├── news_crawler_main.py
|        |
│        ├── models/
│
├── orchestration/                 # PIPELINE CONTROLLER
│   ├── filter_news.py
│
│
├── data/                    # Stock & sentiment datasets
│   ├── raw/
│   ├── processed/
|   |   ├── stage1/
│   |   ├── stage2/
│   |   ├── stage3/
|   |
│   |
│   └── features/
│       ├── merged/
|
├── config/
│   ├── setting.json
│   └── tickers/
│       ├── nvda.yaml
│       ├── intc.yaml
│       └── aapl.yaml
│
├── requirements.txt
└── README.md
```
## 🚀 Features
- Multi-asset stock sentiment tracking (AAPL, NVDA, etc.)
- Sentiment intensity scoring (AI Agent layer)
- Bullish / Bearish event detection
- Interactive Streamlit dashboard
- Time-based filtering of financial events


## 🧠 NLP Models
- FinBERT / ModernBERT for financial sentiment classification
- Probabilistic sentiment outputs
- Support for unlabeled data inference


## 🤖 AI Agent Layer
- Aggregates sentiment signals into intensity score
- Filters high-impact news events dynamically

### News Filtering Pipeline

This system adopts a 3-stage hierarchical filtering architecture:

1. Keyword Filter  
   - Fast rule-based filtering  
   - Removes irrelevant noise

2. LLM Filter  
   - Semantic relevance classification  
   - Ensures financial context alignment

3. MCP Analyzer  
   - Deep reasoning layer  
   - Generates sentiment and impact score


## 📊 Interactive Dashboard
- Built with Streamlit + Plotly
- Dual-axis visualization:
- Stock price
- Sentiment intensity
- Time range filtering
- Event-level inspection


## How to Run

### 1. Install dependencies
pip install -r requirements.txt
