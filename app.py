import streamlit as st
import yfinance as yf
from openai import OpenAI
import json
import plotly.graph_objects as go
from newsapi import NewsApiClient
from datetime import datetime 

# Graceful import for Supabase
try:
    from supabase import create_client
except ImportError:
    st.error("Please add 'supabase' to your requirements.txt file.")

# --- 1. Page Config & State Initialization ---

st.set_page_config(page_title="Stock-R", layout="wide", page_icon="Stock-R.png") 

if "page" not in st.session_state: st.session_state.page = "home"
if "ticker" not in st.session_state: st.session_state.ticker = ""
if "timeframe" not in st.session_state: st.session_state.timeframe = "1Y"
if "is_guest" not in st.session_state: st.session_state.is_guest = False
if "ai_weights" not in st.session_state:
    st.session_state.ai_weights = {"tech": 50, "fund": 50, "sent": 50, "macro": 50}

def go_to_analysis(ticker_val, timeframe_val, weights=None):
    st.session_state.ticker = ticker_val.upper()
    st.session_state.timeframe = timeframe_val
    if weights: st.session_state.ai_weights = weights
    st.session_state.page = "analysis"

def go_home():
    st.session_state.page = "home"
    st.session_state.ticker = ""

# --- 2. CSS Styling (TRUE LIQUID GLASS) ---
st.markdown("""
<style>
    /* TRUE APPLE LIQUID GLASS EFFECT */
    .glass-panel {
        background: linear-gradient(135deg, rgba(255,255,255,0.45) 0%, rgba(255,255,255,0.15) 100%);
        backdrop-filter: blur(24px); 
        -webkit-backdrop-filter: blur(24px);
        /* Specular highlights on top/left to simulate thick glass edges */
        border-top: 1px solid rgba(255, 255, 255, 0.8);
        border-left: 1px solid rgba(255, 255, 255, 0.8);
        border-right: 1px solid rgba(255, 255, 255, 0.2);
        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 24px;
        box-shadow: 0 12px 40px 0 rgba(31, 38, 135, 0.15);
    }

    /* Apply glass to Sidebar natively */
    [data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.2) !important;
        backdrop-filter: blur(30px) !important;
        -webkit-backdrop-filter: blur(30px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.6) !important;
    }

    /* Clean Top Bar */
    [data-testid="stHeader"] { background-color: transparent !important; }

    /* Card Layouts */
    .verdict-card { padding: 40px 30px; text-align: center; height: 100%; }
    .insight-card { padding: 25px; margin-bottom: 20px; }
    
    /* Typography */
    .verdict-text-GREEN { color: #10b981 !important; font-size: 80px !important; font-weight: 900 !important; margin: 0; padding: 0; line-height: 1; letter-spacing: -2px; text-shadow: 0 4px 12px rgba(16, 185, 129, 0.2); }
    .verdict-text-YELLOW { color: #eab308 !important; font-size: 80px !important; font-weight: 900 !important; margin: 0; padding: 0; line-height: 1; letter-spacing: -2px; text-shadow: 0 4px 12px rgba(234, 179, 8, 0.2); }
    .verdict-text-RED { color: #ef4444 !important; font-size: 80px !important; font-weight: 900 !important; margin: 0; padding: 0; line-height: 1; letter-spacing: -2px; text-shadow: 0 4px 12px rgba(239, 68, 68, 0.2); }
    .thesis-text { font-size: 1.2rem; font-weight: 500; color: var(--text-color); margin-top: 20px; line-height: 1.6; }
    .bar-title { font-size: 13px; font-weight: 800; text-transform: uppercase; color: #64748b; margin-bottom: 15px; letter-spacing: 1px;}
    .footer-disclaimer { color: #94a3b8; font-size: 11px; text-align: center; margin-top: 50px; font-style: italic; }
</style>
""", unsafe_allow_html=True)

# Dynamic Background (Applied to ALL pages)
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(-45deg, #ffffff, #e6f0ff, #d6e8ff, #ffffff);
        background-size: 400% 400%;
        animation: floatingClouds 25s ease infinite;
    }
    @keyframes floatingClouds { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
    .home-container { max-width: 850px; margin: 0 auto; padding-top: 1vh; }
</style>
""", unsafe_allow_html=True)

# --- 3. Authentication Wall ---
# Safely check if st.user has 'is_logged_in' configured by Render. If not, it defaults to False.
is_logged_in_via_streamlit = getattr(st.user, "is_logged_in", False)

if not is_logged_in_via_streamlit and not st.session_state.is_guest:
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

if st.session_state.is_guest:
    user_email = "Guest"
    display_name = "Guest User"
else:
    # Safely pull attributes without letting Python throw an error if they don't exist
    user_email = getattr(st.user, "email", "Unknown Email")
    user_name = getattr(st.user, "name", None)
    display_name = user_name or user_email
    
def log_search(ticker):
    if supabase and not st.session_state.is_guest:
        try: supabase.table("search_history").insert({"user_email": user_email, "ticker": ticker}).execute()
        except Exception: pass

def add_favorite(ticker):
    if st.session_state.is_guest:
        st.toast("⚠️ Guests cannot save favorites. Please log in!")
        return
    try:
        supabase.table("user_favorites").insert({"user_email": user_email, "ticker": ticker}).execute()
        st.toast(f"Saved {ticker}!")
    except Exception as e:
        st.error(f"Save failed: {e}")

# --- 5. Sidebar Navigation ---
st.sidebar.markdown(f"### {display_name}")
if st.sidebar.button("Logout / Exit", use_container_width=True):
    if st.session_state.is_guest:
        st.session_state.is_guest = False
        st.rerun()
    else: st.logout()

st.sidebar.markdown("---")

if st.session_state.is_guest:
    st.sidebar.info("**Log in with Google** to save your favorite assets and track your search history across devices.")
else:
    st.sidebar.markdown("### Favorites")
    if supabase:
        try:
            response = supabase.table("user_favorites").select("ticker").eq("user_email", user_email).execute()
            unique_favs = list(set([row['ticker'] for row in response.data]))
            if not unique_favs: st.sidebar.caption("No favorites saved yet.")
            else:
                for f in unique_favs:
                    if st.sidebar.button(f" {f}", key=f"side_fav_{f}", use_container_width=True): go_to_analysis(f, "1Y"); st.rerun()
        except Exception as e: st.sidebar.error(f"DB Error: {e}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Recent Searches")
    if supabase:
        try:
            response = supabase.table("search_history").select("ticker").eq("user_email", user_email).execute()
            unique_hist = list(dict.fromkeys([row['ticker'] for row in response.data]))
            if not unique_hist: st.sidebar.caption("No history yet.")
            else:
                for h in unique_hist:
                    if st.sidebar.button(f" {h}", key=f"side_hist_{h}", use_container_width=True): go_to_analysis(h, "1Y"); st.rerun()
        except Exception as e: st.sidebar.error(f"DB Error: {e}")
    
    # Only show Quick Jump if the user is on the analysis page
    if st.session_state.page == "analysis":
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Quick Jump")
        for sym in ["TSLA", "GOOG", "NVDA", "AAPL", "MSFT", "AMZN", "META", "AMD", "NFLX", "PLTR"]:
            if st.sidebar.button(f"{sym}", key=f"q_{sym}", use_container_width=True): 
                go_to_analysis(sym, "1Y")
                st.rerun()

# --- 6. Analysis Logic ---
@st.cache_data(ttl=3600)
def get_analysis(ticker, timeframe, weights):
    stock = yf.Ticker(ticker)
    info = stock.info
    current_price = info.get('currentPrice', info.get('regularMarketPrice', 0.0))
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""
    Today is {current_date}. The current trading price for {ticker} is ${current_price}.
    
    Provide a forward-looking investment analysis for {ticker} projecting over the next {timeframe}. 
    
    CRITICAL INSTRUCTION: You must base your final verdict on the user's custom priority weighting below (0-100 scale):
    - Technical Analysis & Momentum: {weights['tech']}/100
    - Fundamental Data & Valuation: {weights['fund']}/100
    - News & Market Sentiment: {weights['sent']}/100
    - Macroeconomic Factors: {weights['macro']}/100
    
    You must output your response strictly as a JSON object.
    
    Expected JSON Structure:
    {{
        "verdict": "GREEN", 
        "thesis": "2-3 sentences justifying the verdict, specifically mentioning the highest-weighted factors from the prompt.", 
        "bull_case": ["Point 1", "Point 2"], 
        "bear_case": ["Point 1", "Point 2"],
        "options_play": "Write ONE conversational paragraph explaining exactly what options strategy to use and WHY. Include realistic strike prices (based on current price ${current_price}) and expiration dates. Do NOT use any internal double quotes inside this paragraph."
    }}
    """
    
    try:
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=[
                {"role": "system", "content": "You are an elite quantitative AI. You must output valid JSON only and obey user weightings strictly."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(res.choices[0].message.content)
    except Exception as e:
        return {"verdict": "RED", "thesis": f"Error generating analysis. The AI failed to respond properly.", "bull_case": ["N/A"], "bear_case": ["N/A"], "options_play": "N/A"}

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
    
    # --- UI UPGRADE 1: Background & Ambient Candlestick Animations ---
    st.markdown("""
    <style>
        /* NUKE STREAMLIT'S DEFAULT TOP PADDING */
        [data-testid="block-container"] {
            padding-top: 0rem !important;
        }

        /* The Aurora Background */
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(-45deg, #ffffff, #e0e7ff, #f3e8ff, #ffedd5);
            background-size: 400% 400%;
            animation: floatingClouds 25s ease infinite;
        }
        @keyframes floatingClouds { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
        
        /* Reduced padding-top from 5vh to 1vh to pull everything up! */
        .home-container { max-width: 850px; margin: 0 auto; padding-top: 1vh; position: relative; z-index: 10; }

        /* The Ambient Floating Candlesticks */
        .floating-stocks {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100vh;
            pointer-events: none;
            z-index: 1; 
            overflow: hidden;
        }
        .candle {
            position: absolute; bottom: -200px; 
            width: 4px; 
            height: 100px; 
            border-radius: 2px; opacity: 0; animation: float-up linear infinite;
        }
        .candle::after {
            content: ''; position: absolute; top: 25px; left: -6px;
            width: 16px; 
            height: 50px; 
            border-radius: 4px;
        }
        .c-green { background: rgba(16, 185, 129, 0.4); }
        .c-green::after { background: rgba(16, 185, 129, 0.6); box-shadow: 0 0 20px rgba(16, 185, 129, 0.4); }
        
        .c-red { background: rgba(239, 68, 68, 0.4); }
        .c-red::after { background: rgba(239, 68, 68, 0.6); box-shadow: 0 0 20px rgba(239, 68, 68, 0.4); }

        @keyframes float-up {
            0% { transform: translateY(0) scale(0.8); opacity: 0; }
            5% { opacity: 1; }
            90% { opacity: 1; }
            100% { transform: translateY(-110vh) scale(1.2); opacity: 0; }
        }
    </style>

    <div class="floating-stocks">
        <div class="candle c-green" style="left: 10%; animation-duration: 20s; animation-delay: 0s;"></div>
        <div class="candle c-red" style="left: 30%; animation-duration: 25s; animation-delay: 3s;"></div>
        <div class="candle c-green" style="left: 70%; animation-duration: 18s; animation-delay: 1s;"></div>
        <div class="candle c-red" style="left: 85%; animation-duration: 28s; animation-delay: 6s;"></div>
        <div class="candle c-green" style="left: 50%; animation-duration: 35s; animation-delay: 10s;"></div>
        <div class="candle c-red" style="left: 20%; animation-duration: 22s; animation-delay: 12s;"></div>
    </div>
    """, unsafe_allow_html=True)

    # --- UI UPGRADE 2: Bulletproof Static Title ---
    st.markdown("""
    <style>
        .title-wrapper {
            text-align: center;
            margin-bottom: -10px; /* Reduced this slightly too so the glass panel moves up */
            position: relative;
            z-index: 10;
        }
        
        .static-title {
            font-weight: 900 !important;
            font-size: 9vw !important; /* MASSIVE, edge-to-edge scaling */
            letter-spacing: -10px !important;
            margin: 0px !important;
            display: inline-block !important;
            line-height: 1.2 !important;
            
            background: linear-gradient(to right, #0f172a, #334155) !important;
            -webkit-background-clip: text !important;
            -webkit-text-fill-color: transparent !important;
            color: transparent !important;
        }
        
        .static-title .blue-text { 
            background: linear-gradient(to right, #2563eb, #3b82f6) !important;
            -webkit-background-clip: text !important;
            -webkit-text-fill-color: transparent !important;
            color: transparent !important;
        }
        
        .sub-text { 
            color: #64748b !important; 
            font-size: 1.1rem !important; 
            margin-top: -15px !important; 
            font-weight: 700 !important; 
            text-transform: uppercase !important; 
            letter-spacing: 6px !important; 
        }
    </style>

    <div class='home-container'>
        <div class='title-wrapper'>
            <h1 class="static-title"><span class="blue-text">Stock-</span>R</h1>
            <p class="sub-text">The World's Best AI Market Predictor</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ---------------------------------------------------------
    # (Your with st.container(): glass panel code stays safely right below this!)
    
    # ---------------------------------------------------------
    # (Your with st.container(): glass panel code stays safely right below this!)
    
    # ---------------------------------------------------------
    # (Keep all your with st.container(): glass panel code below here)

    # ... Your existing CSS for the Glass Panel goes here ...

    # 1. Inject the CSS (You can put this at the top of your app)
    st.markdown("""
<style>
div[data-testid="stVerticalBlock"]:has(> .element-container .glass-marker) {
    /* Your Glass Styling */
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-radius: 15px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    padding: 35px;
    margin-bottom: 30px;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    
    /* THE NUCLEAR WIDTH FIX */
    width:75vw !important; /* Stretches it to 95% of your total screen */
    max-width: none !important; /* Destroys Streamlit's built-in limits */
    position: relative !important;
    left: 50% !important; /* Pushes it right to the middle of the screen */
    transform: translateX(-50%) !important; /* Pulls it perfectly dead-center */
}
</style>
""", unsafe_allow_html=True)

    # 2. Create a standard Streamlit container
    with st.container():
        # 3. Drop the invisible marker so our CSS knows which container to target!
        st.markdown("<div class='glass-marker'></div>", unsafe_allow_html=True)
        
        # 4. Add your title
        st.markdown("<div class='bar-title' style='text-align: center; margin-bottom: 20px;'>Trending Assets</div>", unsafe_allow_html=True)
        
        # 5. Render your columns and buttons natively inside the container
        pill_cols = st.columns(12)
        for idx, sym in enumerate(["AAPL", "SBUX", "TSLA", "NVDA", "MSFT", "AMZN", "GOOG", "META", "NFLX", "AMD", "INTC", "PYPL"]):
            if pill_cols[idx].button(sym, key=f"trend_{sym}", use_container_width=True): 
                go_to_analysis(sym, "1Y", st.session_state.ai_weights)
                st.rerun()
    

    
        # 1. Open the standard Streamlit container
    with st.container():
        # 2. Drop the exact same invisible marker! (Your existing CSS will automatically find this)
        st.markdown("<div class='glass-marker'></div>", unsafe_allow_html=True)
        
        # 3. Paste all your native Streamlit code
        input_cols = st.columns([2, 1])
        with input_cols[0]:
            temp_ticker = st.text_input("Asset Ticker", placeholder="e.g. AAPL", label_visibility="collapsed").upper()
        with input_cols[1]:
            temp_timeframe = st.selectbox("Investment Horizon", ["1D", "1M", "1Y", "2Y", "5Y", "ALL"], index=2, label_visibility="collapsed")
        
        # --- EXPERT MODE: Weightage Sliders ---
        with st.expander("Advanced AI Weighting (Pro Mode - You choose the weightage)"):
            st.caption("Customize how the AI calculates its final conviction verdict.")
            cw1, cw2 = st.columns(2)
            with cw1:
                w_tech = st.slider("Technical Price Action", 0, 100, st.session_state.ai_weights['tech'])
                w_fund = st.slider("Fundamental Value", 0, 100, st.session_state.ai_weights['fund'])
            with cw2:
                w_sent = st.slider("News Sentiment", 0, 100, st.session_state.ai_weights['sent'])
                w_macro = st.slider("Macro Environment", 0, 100, st.session_state.ai_weights['macro'])
                
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("Analyze Asset", use_container_width=True, type="primary"):
            if temp_ticker:
                custom_weights = {"tech": w_tech, "fund": w_fund, "sent": w_sent, "macro": w_macro}
                go_to_analysis(temp_ticker, temp_timeframe, custom_weights)
                st.rerun()

# ==========================================
# --- 7B. VIEW: FULL SCREEN DASHBOARD ---
# ==========================================
elif st.session_state.page == "analysis":
    
    # 1. CLEAN COLUMN-SAFE GLASS CSS & BULLETPROOF CENTERING
    st.markdown("""
    <style>
    /* 1. The Glass Panel */
    div[data-testid="stVerticalBlock"]:has(> .element-container .analysis-glass) {
        background: linear-gradient(135deg, rgba(255,255,255,0.45) 0%, rgba(255,255,255,0.15) 100%);
        backdrop-filter: blur(24px); 
        -webkit-backdrop-filter: blur(24px);
        border-top: 1px solid rgba(255, 255, 255, 0.8);
        border-left: 1px solid rgba(255, 255, 255, 0.8);
        border-right: 1px solid rgba(255, 255, 255, 0.2);
        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 24px;
        box-shadow: 0 12px 40px 0 rgba(31, 38, 135, 0.15);
        padding: 30px;
        margin-bottom: 20px;
    }
    
    /* 2. THE CENTERING OVERRIDE: Forces Streamlit's invisible boxes to stretch to the edges */
    div[data-testid="stVerticalBlock"]:has(> .element-container .analysis-glass) > div.element-container {
        width: 100% !important;
        display: flex !important;
        justify-content: center !important;
    }
    div[data-testid="stVerticalBlock"]:has(> .element-container .analysis-glass) .stMarkdown {
        width: 100% !important;
        display: flex !important;
        justify-content: center !important;
    }

    /* 3. MISSING NEUTRAL STYLE: Adds styling for when the AI is unsure */
    .verdict-text-NEUTRAL { 
        color: #94a3b8 !important; /* Cool slate gray */
        font-size: 80px !important; 
        font-weight: 900 !important; 
        margin: 0; padding: 0; line-height: 1; 
        letter-spacing: -2px; 
        text-shadow: 0 4px 12px rgba(148, 163, 184, 0.2); 
    }
    </style>
    """, unsafe_allow_html=True)

    ticker = st.session_state.ticker
    timeframe = st.session_state.timeframe
    weights = st.session_state.ai_weights
    
    top_cols = st.columns([1, 8, 1])
    with top_cols[0]:
        if st.button("← Home"): go_home(); st.rerun()
    with top_cols[1]:
        st.markdown(f"<h3 style='text-align: center; margin-top: 0;'>Terminal: {ticker} ({timeframe})</h3>", unsafe_allow_html=True)
    with top_cols[2]:
        if st.button("Favorite", use_container_width=True): add_favorite(ticker); st.rerun() 

    log_search(ticker)
    stock = yf.Ticker(ticker)
    info = stock.info
    
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
    res = get_analysis(ticker, timeframe, weights)

    # ROW 1: AI Analysis & Insights
    col1, col2 = st.columns([4, 3])
    
    with col1:
        # Glass Panel 1: AI Conviction (MANUALLY CENTERED)
        with st.container():
            st.markdown("<div class='analysis-glass'></div>", unsafe_allow_html=True)
            style_class = f"verdict-text-{res.get('verdict', 'YELLOW').upper()}"
            
            st.markdown(f"""
            <div style='text-align: center; width: 100%;'>
                <div class='bar-title'>AI Conviction</div>
                <h1 class='{style_class}' style='margin: 10px 0px;'>{res.get('verdict', 'YELLOW')}</h1>
                <p class='thesis-text'>{res.get('thesis', 'No thesis generated.')}</p>
            </div>
            """, unsafe_allow_html=True)
        
    with col2:
        # Glass Panel 2: Market Pulse (MANUALLY CENTERED)
        with st.container():
            st.markdown("<div class='analysis-glass'></div>", unsafe_allow_html=True)
            
            with st.spinner("Analyzing news..."): 
                pulse_text = get_market_pulse(ticker)
            
            st.markdown(f"""
            <div style='text-align: center; width: 100%;'>
                <div class='bar-title'>Live Market Pulse</div>
                <p style='font-size: 1.1rem; color: var(--text-color); line-height: 1.6; margin: 0;'>{pulse_text}</p>
            </div>
            """, unsafe_allow_html=True)
        
    # ROW 1.5: Full-Width Options Play
    # Glass Panel 3: Options (MANUALLY CENTERED)
    with st.container():
        st.markdown("<div class='analysis-glass'></div>", unsafe_allow_html=True)
        opt_text = res.get("options_play", "Hold equity. No clear options edge detected.")
        
        st.markdown(f"""
        <div style='text-align: center; width: 100%;'>
            <div class='bar-title'>Strategic Options Play</div>
            <p style='font-size: 1.1rem; color: var(--text-color); line-height: 1.6; margin: 0;'>{opt_text}</p>
        </div>
        """, unsafe_allow_html=True)

    # ROW 2: Pro Candlestick Chart
    # Glass Panel 4: Chart (MANUALLY CENTERED TITLE)
    with st.container():
        st.markdown("<div class='analysis-glass'></div>", unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style='text-align: center; width: 100%; margin-bottom: 10px;'>
            <div class='bar-title'>Price Action & Volatility ({timeframe})</div>
        </div>
        """, unsafe_allow_html=True)
        
        period_map = {"1D": "1d", "1M": "1mo", "1Y": "1y", "2Y": "2y", "5Y": "5y", "ALL": "max"}
        interval_map = {"1D": "1m", "1M": "1h"}
        hist = stock.history(period=period_map.get(timeframe, "1mo"), interval=interval_map.get(timeframe, "1d"))

        if not hist.empty:
            fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], increasing_line_color='#10b981', decreasing_line_color='#ef4444')])
            fig.update_layout(margin=dict(l=0, r=0, t=10, b=10), height=400, template="plotly_white", xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

    # ROW 3: Bull vs Bear Breakdown
    col_bull, col_bear = st.columns(2)
    with col_bull:
        st.success("### Pros")
        for point in res.get("bull_case", []): st.write(f"**✓** {point}")
    with col_bear:
        st.error("### Cons")
        for point in res.get("bear_case", []): st.write(f"**✗** {point}")

    st.markdown("<p class='footer-disclaimer' style='text-align: center;'>Disclaimer: Stock-R is an AI-driven tool. Not financial advice.</p>", unsafe_allow_html=True)
