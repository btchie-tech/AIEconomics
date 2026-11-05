import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred

# 頁面基本配置
st.set_page_config(
    page_title="總體經濟與金融即時儀表板",
    page_icon="🌐",
    layout="wide"
)

st.title("🌐 全球總體經濟與金融指標即時儀表板")

# 側邊欄設定
st.sidebar.header("⚙️ 設定與金鑰")

# 自動判定 API Key 來源
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 Secrets 中的 API Key！")
else:
    fred_key = st.sidebar.text_input("請輸入你的 FRED API Key:", type="password")

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()
    st.sidebar.info("快取已清除，數據將重新載入。")

# 1. 抓取 FRED 數據 (加入日本 10 年期國債殖利率)
@st.cache_data(ttl=3600)
def get_fred_data(api_key):
    fred = Fred(api_key=api_key)
    series_dict = {
        "CPI 物價指數": "CPIAUCSL",
        "10年期美債殖利率": "DGS10",
        "美國失業率": "UNRATE",
        "聯邦基金利率": "FEDFUNDS",
        "日本10年期國債殖利率": "IRLTLT01JPM156N"  # 新增：日本10年期國債殖利率
    }
    
    data = {}
    for name, code in series_dict.items():
        try:
            data[name] = fred.get_series(code)
        except Exception:
            pass
        
    df = pd.DataFrame(data).ffill().tail(365)
    return df

# 2. 抓取 yfinance 市場數據 (加入黃金現貨)
@st.cache_data(ttl=600)
def get_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "台灣加權指數": "^TWII",
        "布蘭特原油": "BZ=F",
        "黃金現貨": "GC=F",      # 新增：黃金現貨
        "美元/台幣匯率": "TWD=X"
    }
    
    df_raw = yf.download(list(tickers.values()), period="1y")["Close"]
    
    # 處理 MultiIndex 欄位平坦化
    if isinstance(df_raw.columns, pd.MultiIndex):
        df_raw.columns = df_raw.columns.get_level_values(-1)
        
    df = df_raw.rename(columns={v: k for k, v in tickers.items()})
    return df

# 頁面渲染邏輯
if fred_key:
    try:
        macro_df = get_fred_data(fred_key)
        market_df = get_market_data()

        # 第一區塊：核心 KPI 卡片 (採用 5 欄平均分佈)
        st.subheader("📊 關鍵總體經濟指標 (FRED)")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        # 1. CPI
        if "CPI 物價指數" in macro_df.columns:
            cpi_series = macro_df["CPI 物價指數"].dropna()
            if not cpi_series.empty:
                col1.metric("CPI 物價指數", f"{cpi_series.iloc[-1]:.1f}")
        
        # 2. 10年期美債殖利率
        if "10年期美債殖利率" in macro_df.columns:
            rate_series = macro_df["10年期美債殖利率"].dropna()
            if len(rate_series) >= 2:
                latest_rate = rate_series.iloc[-1]
                rate_prev = rate_series.iloc[-2]
                col2.metric("10年美債殖利率", f"{latest_rate:.2f}%", f"{latest_rate - rate_prev:+.2f}%")
        
        # 3. 美國失業率
        if "美國失業率" in macro_df.columns:
            unemp_series = macro_df["美國失業率"].dropna()
            if not unemp_series.empty:
                col3.metric("美國失業率", f"{unemp_series.iloc[-1]:.1f}%")
            
        # 4. 聯邦基金利率
        if "聯邦基金利率" in macro_df.columns:
            fed_series = macro_df["聯邦基金利率"].dropna()
            if not fed_series.empty:
                col4.metric("聯邦基金利率", f"{fed_series.iloc[-1]:.2f}%")

        # 5. 日本10年期國債殖利率
        if "日本10年期國債殖利率" in macro_df.columns:
            jgb_series = macro_df["日本10年期國債殖利率"].dropna()
            if not jgb_series.empty:
                col5.metric("日本10年國債殖利率", f"{jgb_series.iloc[-1]:.2f}%")

        # 第二區塊：互動式圖表
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

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板")
