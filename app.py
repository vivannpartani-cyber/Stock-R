import streamlit as st
import yfinance as yf
from openai import OpenAI
import json
import plotly.graph_objects as go
from newsapi import NewsApiClient
from datetime import datetime # <-- Put this at the very top of your app.py

# Graceful import for Supabase
try:
    from supabase import create_client
except ImportError:
    st.error("Please add 'supabase' to your requirements.txt file.")

# --- 1. Page Config & State Initialization ---
st.set_page_config(page_title="Stock-R", layout="wide", page_icon="logo.png") # Switched to WIDE layout for the dashboard

# Initialize our "Page Router" and data states
if "page" not in st.session_state:
    st.session_state.page = "home"
if "ticker" not in st.session_state:
    st.session_state.ticker = ""
if "timeframe" not in st.session_state:
    st.session_state.timeframe = "1Y"
if "is_guest" not in st.session_state:
    st.session_state.is_guest = False

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

# --- 3. Authentication Wall ---
# Only show the wall if they aren't logged in AND haven't clicked guest
if not st.user.is_logged_in and not st.session_state.is_guest:
    st.markdown("""
    <div style="text-align: center; margin-top: 80px; margin-bottom: 30px;">
        <h1 style="font-weight: 900; font-size: 4.5rem; letter-spacing: -1.5px; margin-bottom: 0;">
            <span style="color: #3b82f6;">Sto</span><span style="color: var(--text-color);">ck-R</span>
        </h1>
        <p style="color: #64748b; font-size: 1.2rem;">Log in to save favorites and track history, or explore as a guest.</p>
    </div>""", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("Log in with Google", use_container_width=True, type="primary"):
            st.login("google")
        if st.button("Continue as Guest", use_container_width=True):
            st.session_state.is_guest = True
            st.rerun()
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

# Handle user identity based on login vs guest status
if st.session_state.is_guest:
    user_email = "Guest"
    display_name = "Guest User"
else:
    user_email = st.user.email
    display_name = getattr(st.user, "name", user_email) or user_email

def log_search(ticker):
    # Only log to Supabase if they are a real logged-in user
    if supabase and not st.session_state.is_guest:
        try: supabase.table("search_history").insert({"user_email": user_email, "ticker": ticker}).execute()
        except Exception: pass

def add_favorite(ticker):
    # Block guests from saving and tell them why
    if st.session_state.is_guest:
        st.toast("⚠️ Guests cannot save favorites. Please log in!")
        return
        
    print(f"Attempting to save {ticker} for {user_email}")
    try:
        response = supabase.table("user_favorites").insert({"user_email": user_email, "ticker": ticker}).execute()
        print("Supabase Response:", response)
        st.toast(f"Saved {ticker}!")
    except Exception as e:
        print("DATABASE ERROR:", e)
        st.error(f"Save failed: {e}")

# --- 5. Sidebar Navigation ---
st.sidebar.markdown(f"### 👤 {display_name}")

# Smart Logout/Exit button
if st.sidebar.button("Logout / Exit", use_container_width=True):
    if st.session_state.is_guest:
        st.session_state.is_guest = False
        st.rerun()
    else:
        st.logout()

st.sidebar.markdown("---")

# If they are a guest, show a promo to log in instead of empty DB queries
if st.session_state.is_guest:
    st.sidebar.info("🔒 **Log in with Google** to save your favorite assets and track your search history across devices.")
else:
    # --- Real User Sidebar Logic ---
    st.sidebar.markdown("### ⭐ Favorites")
    if supabase:
        try:
            response = supabase.table("user_favorites").select("ticker").eq("user_email", user_email).execute()
            unique_favs = list(set([row['ticker'] for row in response.data]))
            
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
    st.sidebar.markdown("### 🕒 Recent Searches")
    if supabase:
        try:
            response = supabase.table("search_history").select("ticker").eq("user_email", user_email).execute()
            unique_hist = list(dict.fromkeys([row['ticker'] for row in response.data]))
            
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

# --- 6. Analysis Logic ---
@st.cache_data(ttl=3600)
def get_analysis(ticker, timeframe):
    stock = yf.Ticker(ticker)
    info = stock.info
    current_price = info.get('currentPrice', info.get('regularMarketPrice', 0.0))
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""
    Today is {current_date}. The current trading price for {ticker} is ${current_price}.
    
    Provide a forward-looking investment analysis for {ticker} projecting over the next {timeframe}. 
    You must output your response strictly as a JSON object.
    
    Expected JSON Structure:
    {{
        "verdict": "GREEN", 
        "thesis": "2-3 sentences justifying the verdict.", 
        "bull_case": ["Point 1", "Point 2"], 
        "bear_case": ["Point 1", "Point 2"],
        "options_play": "Write ONE conversational paragraph explaining exactly what options strategy to use and WHY. Include realistic strike prices (based on current price ${current_price}) and expiration dates. Do NOT use any internal double quotes inside this paragraph."
    }}
    """
    
    try:
        # We added response_format={"type": "json_object"} to force absolute JSON compliance at the server level
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=[
                {"role": "system", "content": "You are a financial AI. You must output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}  # <--- THE NUCLEAR OPTION
        )
        
        # Because we forced JSON mode, we don't need any messy string slicing anymore!
        return json.loads(res.choices[0].message.content)
        
    except Exception as e:
        print(f"\n--- LLM API ERROR for {ticker} ---")
        print(f"Python Error: {e}")
        print(f"Raw AI Output: {res.choices[0].message.content if 'res' in locals() else 'None'}\n-----------------------------------\n")
        
        return {
            "verdict": "RED", 
            "thesis": f"Error generating analysis for {timeframe}. The AI failed to respond properly.", 
            "bull_case": ["N/A"], 
            "bear_case": ["N/A"], 
            "options_play": "N/A"
        }

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
        st.markdown("<div class='insight-card' style='height: 100%;'>", unsafe_allow_html=True)
        st.markdown("<div class='bar-title'>Live Market Pulse</div>", unsafe_allow_html=True)
        with st.spinner("Analyzing news..."):
            st.write(get_market_pulse(ticker))
        st.markdown("</div>", unsafe_allow_html=True)
        
    # ROW 1.5: Full-Width Options Play
    st.markdown("<div class='insight-card'>", unsafe_allow_html=True)
    st.markdown("<div class='bar-title'>Strategic Options Play</div>", unsafe_allow_html=True)
    
    # Grab the text and render it natively so the font matches perfectly
    opt_text = res.get("options_play", "Hold equity. No clear options edge detected.")
    st.markdown(f"<p style='font-size: 1.1rem; color: var(--text-color); line-height: 1.6; margin: 0;'>{opt_text}</p>", unsafe_allow_html=True)
    
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
