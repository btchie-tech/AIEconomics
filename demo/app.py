import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
from google import genai

# 頁面基本配置
st.set_page_config(
    page_title="總體經濟與金融即時儀表板",
    page_icon="🌐",
    layout="wide"
)

st.title("🌐 全球總體經濟與金融指標即時儀表板")

# 側邊欄設定：輸入 API Key 與刷新控制
st.sidebar.header("⚙️ 設定與金鑰")

# 1. FRED API Key 讀取
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 Secrets 中的 FRED API Key！")
else:
    fred_key = st.sidebar.text_input("請輸入你的 FRED API Key:", type="password")

# 2. Gemini API Key 讀取
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("已自動讀取 Secrets 中的 Gemini API Key！")
else:
    gemini_key = st.sidebar.text_input("請輸入你的 Gemini API Key:", type="password")

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()
    st.sidebar.info("快取已清除，數據將重新載入。")


# 抓取 FRED 數據
@st.cache_data(ttl=3600)
def get_fred_data(api_key):
    fred = Fred(api_key=api_key)
    series_dict = {
        "CPI 物價指數": "CPIAUCSL",
        "10年期美債殖利率": "DGS10",
        "美國失業率": "UNRATE",
        "聯邦基金利率": "FEDFUNDS",
        "日本10年期國債殖利率": "IRLTLT01JPM156N"
    }
    
    data = {}
    for name, code in series_dict.items():
        try:
            data[name] = fred.get_series(code)
        except Exception:
            pass
        
    df = pd.DataFrame(data).ffill().tail(365)
    return df


# 抓取 yfinance 市場數據
@st.cache_data(ttl=600)
def get_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "台灣加權指數": "^TWII",
        "布蘭特原油": "BZ=F",
        "黃金現貨": "GC=F",
        "美元/台幣匯率": "TWD=X"
    }
    
    df_raw = yf.download(list(tickers.values()), period="1y")["Close"]
    
    if isinstance(df_raw.columns, pd.MultiIndex):
        df_raw.columns = df_raw.columns.get_level_values(-1)
        
    df = df_raw.rename(columns={v: k for k, v in tickers.items()})
    return df


# 呼叫 Gemini 產出分析短評
def generate_macro_summary(api_key, context_data):
    # 初始化最新版 google-genai Client
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    你是一位專業的總體經濟分析師。請根據以下最新的關鍵總體經濟與市場數據，撰寫一份約 200 字繁體中文的專業短評，分析當前的經濟環境與潛在影響：

    數據資料庫（最新紀錄）：
    - 美國 CPI 物價指數: {context_data.get('cpi', 'N/A')}
    - 美國失業率: {context_data.get('unemp', 'N/A')}%
    - 聯邦基金利率: {context_data.get('fed_rate', 'N/A')}%
    - 10 年期美債殖利率: {context_data.get('us10y', 'N/A')}%
    - 日本 10 年期國債殖利率: {context_data.get('jp10y', 'N/A')}%

    請直接輸出分析短評，條理清晰，觀點切中要害。
    """
    
    response = client.models.generate_content(
        model='gemini-3.8-flash',
        contents=prompt
    )
    return response.text


# 主頁面渲染邏輯
if fred_key:
    try:
        macro_df = get_fred_data(fred_key)
        market_df = get_market_data()

        # 第一區塊：核心 KPI 卡片
        st.subheader("📊 關鍵總體經濟指標 (FRED)")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        # 紀錄最新數據供 AI 提示詞使用
        latest_values = {}

        if "CPI 物價指數" in macro_df.columns:
            cpi_series = macro_df["CPI 物價指數"].dropna()
            if not cpi_series.empty:
                val = cpi_series.iloc[-1]
                latest_values['cpi'] = f"{val:.1f}"
                col1.metric("CPI 物價指數", f"{val:.1f}")
        
        if "10年期美債殖利率" in macro_df.columns:
            rate_series = macro_df["10年期美債殖利率"].dropna()
            if len(rate_series) >= 2:
                latest_rate = rate_series.iloc[-1]
                rate_prev = rate_series.iloc[-2]
                latest_values['us10y'] = f"{latest_rate:.2f}"
                col2.metric("10年美債殖利率", f"{latest_rate:.2f}%", f"{latest_rate - rate_prev:+.2f}%")
        
        if "美國失業率" in macro_df.columns:
            unemp_series = macro_df["美國失業率"].dropna()
            if not unemp_series.empty:
                val = unemp_series.iloc[-1]
                latest_values['unemp'] = f"{val:.1f}"
                col3.metric("美國失業率", f"{val:.1f}%")
            
        if "聯邦基金利率" in macro_df.columns:
            fed_series = macro_df["聯邦基金利率"].dropna()
            if not fed_series.empty:
                val = fed_series.iloc[-1]
                latest_values['fed_rate'] = f"{val:.2f}"
                col4.metric("聯邦基金利率", f"{val:.2f}%")

        if "日本10年期國債殖利率" in macro_df.columns:
            jgb_series = macro_df["日本10年期國債殖利率"].dropna()
            if not jgb_series.empty:
                val = jgb_series.iloc[-1]
                latest_values['jp10y'] = f"{val:.2f}"
                col5.metric("日本10年國債殖利率", f"{val:.2f}%")

        # 第二區塊：圖表
        st.divider()
        st.subheader("📈 市場走勢與總體指標折線圖")
        
        tab1, tab2 = st.tabs(["金融市場走勢 (yfinance)", "總體經濟趨勢 (FRED)"])
        
        with tab1:
            market_choice = st.selectbox("選擇金融市場標的：", market_df.columns)
            fig1 = px.line(
                market_df, 
                y=market_choice, 
                title=f"{market_choice} 近一年走勢",
                labels={"index": "日期", market_choice: "價格/指數"}
            )
            st.plotly_chart(fig1, use_container_width=True)
            
        with tab2:
            macro_choice = st.selectbox("選擇總體經濟指標：", macro_df.columns)
            fig2 = px.line(
                macro_df, 
                y=macro_choice, 
                title=f"{macro_choice} 近一年走勢",
                labels={"index": "日期", macro_choice: "數值"}
            )
            st.plotly_chart(fig2, use_container_width=True)

        # 第三區塊：AI 總體經濟短評生成按鈕
        st.divider()
        st.subheader("🤖 AI 總體經濟即時短評")

        if st.button("✨ 產生 AI 總體經濟摘要", type="primary"):
            if not gemini_key:
                st.warning("請先在左側邊欄輸入 Gemini API Key！")
            else:
                with st.spinner("AI 正在分析最新經濟數據中..."):
                    try:
                        summary = generate_macro_summary(gemini_key, latest_values)
                        st.success("分析完成！")
                        st.markdown(summary)
                    except Exception as e:
                        st.error(f"AI 生成失敗: {e}")

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板")
