import streamlit as st
import yfinance as yf
from openai import OpenAI
import json
import plotly.graph_objects as go
from newsapi import NewsApiClient

# Graceful import for Supabase
try:
    from supabase import create_client
except ImportError:
    st.error("Please add 'supabase' to your requirements.txt file.")

# --- 1. Page Config & State Initialization ---
st.set_page_config(page_title="Stock-R", layout="wide", page_icon="Stock-R.png") # Switched to WIDE layout for the dashboard

# Initialize our "Page Router" and data states
if "page" not in st.session_state:
    st.session_state.page = "home"
if "ticker" not in st.session_state:
    st.session_state.ticker = ""
if "timeframe" not in st.session_state:
    st.session_state.timeframe = "1Y"

# Navigation Helper Functions
def go_to_analysis(ticker_val, timeframe_val):
    st.session_state.ticker = ticker_val.upper()
    st.session_state.timeframe = timeframe_val
    st.session_state.page = "analysis"

def go_home():
    st.session_state.page = "home"
    st.session_state.ticker = ""

# --- 2. CSS Styling ---
st.markdown("""
<style>
    /* Global Layout Tweaks */
    .verdict-card { background: var(--secondary-background-color); border: 1px solid #e0e7ff; border-radius: 16px; padding: 40px 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); text-align: center; height: 100%;}
    .verdict-text-GREEN { color: #10b981 !important; font-size: 80px !important; font-weight: 900 !important; margin: 0; padding: 0; line-height: 1; letter-spacing: -2px; }
    .verdict-text-YELLOW { color: #eab308 !important; font-size: 80px !important; font-weight: 900 !important; margin: 0; padding: 0; line-height: 1; letter-spacing: -2px;}
    .verdict-text-RED { color: #ef4444 !important; font-size: 80px !important; font-weight: 900 !important; margin: 0; padding: 0; line-height: 1; letter-spacing: -2px;}
    .thesis-text { font-size: 1.2rem; font-weight: 500; color: var(--text-color); margin-top: 20px; line-height: 1.6; }
    
    .insight-card { background: var(--secondary-background-color); border-radius: 12px; padding: 20px; border: 1px solid #f1f5f9; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);}
    .bar-title { font-size: 12px; font-weight: 800; text-transform: uppercase; color: #64748b; margin-bottom: 10px; letter-spacing: 1px;}
    .footer-disclaimer { color: #94a3b8; font-size: 11px; text-align: center; margin-top: 50px; font-style: italic; }
    
    /* Clean Top Bar */
    [data-testid="stHeader"] { background-color: transparent !important; }
</style>
""", unsafe_allow_html=True)

# Dynamic Background: Only apply the animated clouds on the Home page
if st.session_state.page == "home":
    st.markdown("""
    <style>
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(-45deg, #ffffff, #f0f6ff, #e0eeff, #ffffff);
            background-size: 400% 400%;
            animation: floatingClouds 20s ease infinite;
        }
        @keyframes floatingClouds {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        /* Center content on home page since layout is wide */
        .home-container { max-width: 800px; margin: 0 auto; padding-top: 10vh; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. Google Authentication Wall ---
if not st.user.is_logged_in:
    st.markdown("""
    <div style="text-align: center; margin-top: 80px; margin-bottom: 30px;">
        <h1 style="font-weight: 900; font-size: 4.5rem; letter-spacing: -1.5px; margin-bottom: 0;">
            <span style="color: #3b82f6;">Sto</span><span style="color: var(--text-color);">ck-R</span>
        </h1>
        <p style="color: #64748b; font-size: 1.2rem;">Please log in to access AI predictions, save favorites, and track history.</p>
    </div>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("Log in with Google", use_container_width=True):
            st.login("google")
    st.stop()

# --- 4. Client & Database Initialization ---
client = OpenAI(api_key=st.secrets["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
newsapi = NewsApiClient(api_key=st.secrets["NEWSAPI_KEY"])

@st.cache_resource
def init_supabase():
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    return None

supabase = init_supabase()
user_email = st.user.email

def log_search(ticker):
    if supabase:
        try: supabase.table("search_history").insert({"user_email": user_email, "ticker": ticker}).execute()
        except Exception: pass

def add_favorite(ticker):
    print(f"Attempting to save {ticker} for {user_email}")
    try:
        response = supabase.table("user_favorites").insert({"user_email": user_email, "ticker": ticker}).execute()
        print("Supabase Response:", response)
        st.toast(f"Saved {ticker}!")
    except Exception as e:
        print("DATABASE ERROR:", e)
        st.error(f"Save failed: {e}")

# --- 5. Sidebar Navigation ---
# Safely grab the Google profile name, but fallback to email just in case it's blank
display_name = getattr(st.user, "name", user_email) or user_email
st.sidebar.markdown(f"### {display_name}")
if st.sidebar.button("Logout", use_container_width=True):
    st.logout()

st.sidebar.markdown("---")
st.sidebar.markdown("### Favorites")
if supabase:
    # We use a forced refresh by not caching this call
    try:
        # Fetch directly from the table
        response = supabase.table("user_favorites").select("ticker").eq("user_email", user_email).execute()
        # Extract tickers
        fav_list = [row['ticker'] for row in response.data]
        unique_favs = list(set(fav_list))
        
        if not unique_favs:
            st.sidebar.caption("No favorites saved yet.")
        else:
            for f in unique_favs:
                if st.sidebar.button(f" {f}", key=f"side_fav_{f}", use_container_width=True):
                    st.session_state.ticker = f
                    st.session_state.page = "analysis"
                    st.rerun()
    except Exception as e:
        st.sidebar.error(f"DB Error: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("### Recent Searches")
if supabase:
    try:
        # Fetch directly from the table
        response = supabase.table("search_history").select("ticker").eq("user_email", user_email).execute()
        hist_list = [row['ticker'] for row in response.data]
        unique_hist = list(dict.fromkeys(hist_list))
        
        if not unique_hist:
            st.sidebar.caption("No history yet.")
        else:
            for h in unique_hist:
                if st.sidebar.button(f" {h}", key=f"side_hist_{h}", use_container_width=True):
                    st.session_state.ticker = h
                    st.session_state.page = "analysis"
                    st.rerun()
    except Exception as e:
        st.sidebar.error(f"DB Error: {e}")

# Inject "Quick Jump" only on the analysis page
if st.session_state.page == "analysis":
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Quick Jump")
    for sym in ["TSLA", "GOOG", "NVDA", "AAPL", "MSFT", "AMZN"]:
        if st.sidebar.button(f" {sym}", key=f"quick_{sym}", use_container_width=True):
            go_to_analysis(sym, st.session_state.timeframe)
            st.rerun()

# --- 6. Analysis Logic ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_analysis(ticker, timeframe):
    stock = yf.Ticker(ticker)
    info = stock.info
    prompt = f"""
    Provide a forward-looking investment analysis for {info.get('shortName', ticker)} ({ticker}) projecting over the next {timeframe}. 
    Return ONLY a raw JSON object: 
    {{
        "verdict": "GREEN", 
        "thesis": "2-3 sentences justifying the verdict.", 
        "bull_case": ["Point 1", "Point 2"], 
        "bear_case": ["Point 1", "Point 2"],
        "options_play": "Suggest a specific options strategy (e.g., short put, call spread) that aligns with your verdict."
    }}
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": "You are an elite financial analyst. Output ONLY valid JSON."}, {"role": "user", "content": prompt}]
        )
        raw_text = response.choices[0].message.content.strip()
        return json.loads(raw_text[raw_text.find('{'):raw_text.rfind('}')+1])
    except Exception as e:
        return {"verdict": "RED", "thesis": "Error generating analysis.", "bull_case": ["N/A"], "bear_case": ["N/A"], "options_play": "N/A"}

@st.cache_data(ttl=3600, show_spinner=False)
def get_market_pulse(ticker):
    try:
        news = newsapi.get_everything(q=f"{ticker} stock", language='en', sort_by='relevancy', page_size=5)
        headlines = [a['title'] for a in news.get('articles', [])]
        if not headlines: return "No recent news headlines found."
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": "You are a ruthless market analyst."}, {"role": "user", "content": f"Analyze sentiment for {ticker} based on these headlines: {headlines}. Keep it to exactly 2 sentences."}]
        )
        return response.choices[0].message.content
    except Exception: return "Could not fetch news pulse."

def format_large_number(num):
    if not num: return "N/A"
    if num >= 1_000_000_000_000: return f"${num/1_000_000_000_000:.2f}T"
    if num >= 1_000_000_000: return f"${num/1_000_000_000:.2f}B"
    if num >= 1_000_000: return f"${num/1_000_000:.2f}M"
    return f"${num}"


# ==========================================
# --- 7A. VIEW: HOME PAGE ---
# ==========================================
if st.session_state.page == "home":
    st.markdown("<div class='home-container'>", unsafe_allow_html=True)
    st.markdown("""
    <div style="text-align: center; margin-bottom: 40px;">
        <h1 style="font-weight: 900; font-size: 6rem; letter-spacing: -3px; margin-bottom: 0px;">
            <span style="color: #3b82f6;">Sto</span><span style="color: var(--text-color);">ck-R</span>
        </h1>
        <p style="color: #64748b; font-size: 1.3rem; margin-top: -10px; font-weight: 500;">the world's best ai stock market predictor</p>
    </div>
    """, unsafe_allow_html=True)

    # Trending Assets trigger immediate routing
    st.markdown("<div class='bar-title' style='text-align: center;'>Trending Assets</div>", unsafe_allow_html=True)
    pill_cols = st.columns(6)
    trending = ["AAPL", "SBUX", "TSLA", "NVDA", "MSFT", "AMZN"]
    for idx, sym in enumerate(trending):
        if pill_cols[idx].button(sym, key=f"trend_{sym}", use_container_width=True): 
            go_to_analysis(sym, "1Y")
            st.rerun()

    st.markdown("<br><div class='bar-title' style='text-align: center;'>New Analysis</div>", unsafe_allow_html=True)
    
    # Input Form
    with st.container():
        input_cols = st.columns([2, 1])
        with input_cols[0]:
            temp_ticker = st.text_input("Asset Ticker", placeholder="e.g. AAPL").upper()
        with input_cols[1]:
            temp_timeframe = st.selectbox("Investment Horizon", ["1D", "1M", "1Y", "2Y", "5Y", "ALL"], index=2)
        
        if st.button("Analyze Asset", use_container_width=True, type="primary"):
            if temp_ticker:
                go_to_analysis(temp_ticker, temp_timeframe)
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ==========================================
# --- 7B. VIEW: FULL SCREEN DASHBOARD ---
# ==========================================
elif st.session_state.page == "analysis":
    ticker = st.session_state.ticker
    timeframe = st.session_state.timeframe
    
   # Top Action Bar
    top_cols = st.columns([1, 8, 1])
    with top_cols[0]:
        if st.button("← Home"):
            go_home()
            st.rerun()
    with top_cols[1]:
        st.markdown(f"<h3 style='text-align: center; margin-top: 0;'>Terminal: {ticker} ({timeframe})</h3>", unsafe_allow_html=True)
    with top_cols[2]:
        if st.button("⭐ Save", use_container_width=True):
            add_favorite(ticker)
            st.rerun()  # <--- THIS IS THE MISSING KEY

    # Execute DB logging & Fetch Info
    log_search(ticker)
    stock = yf.Ticker(ticker)
    info = stock.info
    
    # KPI Row
    st.markdown("---")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    current_price = info.get('currentPrice', info.get('regularMarketPrice', 0.0))
    prev_close = info.get('previousClose', 0.0)
    change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0.0
    
    kpi1.metric("Current Price", f"${current_price:,.2f}", f"{change_pct:.2f}%")
    kpi2.metric("Market Cap", format_large_number(info.get('marketCap')))
    kpi3.metric("P/E Ratio", info.get('trailingPE', 'N/A'))
    kpi4.metric("52W Range", f"${info.get('fiftyTwoWeekLow', 0):.1f} - ${info.get('fiftyTwoWeekHigh', 0):.1f}")
    st.markdown("---")

    # Fetch AI Data
    res = get_analysis(ticker, timeframe)

    # ROW 1: AI Analysis & Insights
    col1, col2 = st.columns([4, 3])
    
    with col1:
        # Giant Verdict Card
        style_class = f"verdict-text-{res.get('verdict', 'YELLOW').upper()}"
        st.markdown(f"""
        <div class='verdict-card'>
            <div class='bar-title'>AI Conviction</div>
            <h1 class='{style_class}'>{res.get('verdict', 'YELLOW')}</h1>
            <p class='thesis-text'>{res.get('thesis', 'No thesis generated. Try again.')}</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        # Live Market Pulse Box
        st.markdown("<div class='insight-card'>", unsafe_allow_html=True)
        st.markdown("<div class='bar-title'>Live Market Pulse</div>", unsafe_allow_html=True)
        with st.spinner("Analyzing news..."):
            st.write(get_market_pulse(ticker))
        st.markdown("</div>", unsafe_allow_html=True)
        
        # New Feature: Options & Volatility Play
        st.markdown("<div class='insight-card'>", unsafe_allow_html=True)
        st.markdown("<div class='bar-title'>Strategic Options Play</div>", unsafe_allow_html=True)
        st.info(res.get("options_play", "Hold equity. No clear options edge detected."))
        st.markdown("</div>", unsafe_allow_html=True)

    # ROW 2: Pro Candlestick Chart
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"<div class='bar-title'>Price Action & Volatility ({timeframe})</div>", unsafe_allow_html=True)
    period_map = {"1D": "1d", "1M": "1mo", "1Y": "1y", "2Y": "2y", "5Y": "5y", "ALL": "max"}
    interval_map = {"1D": "1m", "1M": "1h"}
    hist = stock.history(period=period_map.get(timeframe, "1mo"), interval=interval_map.get(timeframe, "1d"))

    if not hist.empty:
        fig = go.Figure(data=[go.Candlestick(x=hist.index,
                        open=hist['Open'], high=hist['High'],
                        low=hist['Low'], close=hist['Close'],
                        increasing_line_color='#10b981', decreasing_line_color='#ef4444')])
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=10), height=400, template="plotly_white", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    # ROW 3: Bull vs Bear Breakdown
    st.markdown("<br>", unsafe_allow_html=True)
    col_bull, col_bear = st.columns(2)
    with col_bull:
        st.success("### Pros")
        for point in res.get("bull_case", []): st.write(f"**✓** {point}")
    with col_bear:
        st.error("### Cons")
        for point in res.get("bear_case", []): st.write(f"**✗** {point}")

    st.markdown("<p class='footer-disclaimer'>Disclaimer: Stock-R is an AI-driven tool. Not financial advice.</p>", unsafe_allow_html=True)
