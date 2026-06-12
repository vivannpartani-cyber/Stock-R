import streamlit as st
import yfinance as yf
from openai import OpenAI
import json
import plotly.express as px
from newsapi import NewsApiClient # Make sure you ran: pip install newsapi-python

# --- 1. Page Config ---
st.set_page_config(page_title="Stock-R", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #f7faff !important; color: #18181b !important; font-family: sans-serif; }
    header { visibility: hidden; }
    .verdict-card { background: #ffffff; border: 1px solid #e0e7ff; border-radius: 24px; padding: 30px; box-shadow: 0 10px 40px rgba(59, 130, 246, 0.05); text-align: center; }
    .verdict-text-GREEN { color: #10b981 !important; font-size: 48px !important; font-weight: 800 !important; }
    .verdict-text-YELLOW { color: #eab308 !important; font-size: 48px !important; font-weight: 800 !important; }
    .verdict-text-RED { color: #ef4444 !important; font-size: 48px !important; font-weight: 800 !important; }
    .bar-title { font-size: 12px; font-weight: 700; text-transform: uppercase; color: #94a3b8; margin: 20px 0 10px 0; }
    .footer-disclaimer { color: #94a3b8; font-size: 11px; text-align: center; margin-top: 50px; font-style: italic; }
</style>
""", unsafe_allow_html=True)

# --- 2. Client Setup ---
client = OpenAI(api_key=st.secrets["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
newsapi = NewsApiClient(api_key=st.secrets["NEWSAPI_KEY"])

# --- 3. Analysis Logic ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_analysis(ticker, timeframe):
    stock = yf.Ticker(ticker)
    info = stock.info
    prompt = f"Analyze {info.get('shortName', ticker)} ({ticker}) for {timeframe}. Return ONLY JSON: {{\"verdict\": \"GREEN|YELLOW|RED\", \"thesis\": \"...\", \"bull_case\": [\"...\"], \"bear_case\": [\"...\"]}}"
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": "You are a ruthless analyst. Output only raw JSON."}, {"role": "user", "content": prompt}]
    )
    text = response.choices[0].message.content.strip()
    try:
        return json.loads(text[text.find('{'):text.rfind('}')+1])
    except:
        return {"verdict": "RED", "thesis": "Analysis error.", "bull_case": [], "bear_case": []}

@st.cache_data(ttl=3600, show_spinner=False)
def get_market_pulse(ticker):
    try:
        # Fetch top news for the ticker
        news = newsapi.get_everything(
            q=f"{ticker} stock", 
            language='en', 
            sort_by='relevancy', 
            page_size=5
        )
        headlines = [a['title'] for a in news.get('articles', [])]
        
        # If no news, don't waste AI tokens
        if not headlines:
            return "No recent news headlines found for this ticker."

        # Ask AI to summarize sentiment
        prompt = f"Analyze the sentiment for {ticker} based on these headlines: {headlines}. Keep it to 2 sentences and include a 1-5 star sentiment rating."
        
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": "You are a ruthless, world-class market analyst."}, 
                      {"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Could not fetch news pulse: {str(e)}"

# --- 4. Main UI Layout ---
if "ticker" not in st.session_state: st.session_state.ticker = ""

# Header
st.markdown("""<div style="text-align: center; margin-top: -50px;">
    <h1 style="font-weight: 900; font-size: 4rem; letter-spacing: -1.5px;">
        <span style="color: #3b82f6;">Sto</span><span style="color: #09090b;">ck-R</span>
    </h1>
    <p style="color: #64748b; font-size: 1.1rem; margin-top: -10px;">the world's best ai stock market predictor</p>
</div>""", unsafe_allow_html=True)

# Legend
st.markdown("<div style='display: flex; justify-content: center; gap: 20px; font-size: 12px; font-weight: 600;'> <span style='color: #10b981;'>● GREEN: Good</span> <span style='color: #eab308;'>● YELLOW: Cautious</span> <span style='color: #ef4444;'>● RED: Bad</span></div>", unsafe_allow_html=True)

# Inputs
st.markdown("<div class='bar-title'>Trending Assets</div>", unsafe_allow_html=True)
pill_cols = st.columns(6)
trending = ["AAPL", "SBUX", "TSLA", "NVDA", "MSFT", "AMZN"]
for idx, sym in enumerate(trending):
    if pill_cols[idx].button(sym): st.session_state.ticker = sym

# Side-by-side inputs
input_cols = st.columns([2, 1])
with input_cols[0]:
    ticker_input = st.text_input("Asset Ticker", value=st.session_state.ticker).upper()
with input_cols[1]:
    timeframe = st.selectbox("Investment Horizon", ["1D", "1M", "1Y", "2Y", "5Y", "ALL"], index=2)

if ticker_input:
    res = get_analysis(ticker_input, timeframe)
    
    # Organize into Tabs to fix the "disappearing" elements issue
    tab1, tab2 = st.tabs(["Verdict & Analysis", "Detailed Pro/Con"])
    
    with tab1:
        # 1. The Verdict Card
        style_class = f"verdict-text-{res['verdict'].upper()}"
        st.markdown(f"<div class='verdict-card'><h1 class='{style_class}'>{res['verdict']}</h1><p>{res['thesis']}</p></div>", unsafe_allow_html=True)
        
        # 2. Market Pulse (News)
        st.markdown(f"<div class='bar-title'>Market Pulse</div>", unsafe_allow_html=True)
        with st.spinner("Analyzing news sentiment..."):
            pulse = get_market_pulse(ticker_input)
            st.info(pulse)
            
        # 3. Price History Title
        st.markdown(f"<div class='bar-title'>{ticker_input} Price History ({timeframe})</div>", unsafe_allow_html=True)
        stock = yf.Ticker(ticker_input)
        period_map = {"1D": "1d", "1M": "1mo", "1Y": "1y", "2Y": "2y", "5Y": "5y", "ALL": "max"}
        interval_map = {"1D": "1m", "1M": "1h"}
        hist = stock.history(period=period_map.get(timeframe, "1mo"), interval=interval_map.get(timeframe, "1d"))

        if not hist.empty:
            fig = px.line(hist, x=hist.index, y='Close', template="plotly_white")
            fig.update_traces(line_shape='spline', line=dict(width=2))
            fig.update_layout(margin=dict(l=0, r=0, t=20, b=20), height=300, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)


    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Pros")
            for point in res.get("bull_case", []): st.write(f"- {point}")
        with col2:
            st.subheader("Cons")
            for point in res.get("bear_case", []): st.write(f"- {point}")

st.markdown("<p class='footer-disclaimer'>Disclaimer: Stock-R is an AI-driven tool. All outputs are generated by AI and may contain errors or inaccuracies. Not financial advice.</p>", unsafe_allow_html=True)
