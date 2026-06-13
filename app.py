import os
os.environ["STREAMLIT_URL"] = "https://stock-r.streamlit.app"
import streamlit as st
import yfinance as yf
from openai import OpenAI
import json
import plotly.express as px
from newsapi import NewsApiClient

# Graceful import for Supabase
try:
    from supabase import create_client
except ImportError:
    st.error("Please add 'supabase' to your requirements.txt file.")

# --- 1. Page Config & CSS ---
st.set_page_config(page_title="Stock-R", layout="centered", page_icon="Stock-R.png")

st.markdown("""
<style>
    /* Clean layout tweaks */
    /* Removed the header/toolbar hiding CSS to guarantee the sidebar button is always visible */
    
    .verdict-card { background: var(--secondary-background-color); border: 1px solid #e0e7ff; border-radius: 16px; padding: 30px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); text-align: center; margin-bottom: 20px;}
    .verdict-text-GREEN { color: #10b981 !important; font-size: 56px !important; font-weight: 900 !important; margin: 0; padding: 0; line-height: 1.2; }
    .verdict-text-YELLOW { color: #eab308 !important; font-size: 56px !important; font-weight: 900 !important; margin: 0; padding: 0; line-height: 1.2;}
    .verdict-text-RED { color: #ef4444 !important; font-size: 56px !important; font-weight: 900 !important; margin: 0; padding: 0; line-height: 1.2;}
    .thesis-text { font-size: 1.15rem; font-weight: 500; color: var(--text-color); margin-top: 15px; line-height: 1.6; }
    .bar-title { font-size: 13px; font-weight: 700; text-transform: uppercase; color: #94a3b8; margin: 25px 0 15px 0; }
    .footer-disclaimer { color: #94a3b8; font-size: 11px; text-align: center; margin-top: 50px; font-style: italic; }
</style>
""", unsafe_allow_html=True)

# --- 2. Google Authentication Wall ---
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

# --- 3. Client & Database Initialization ---
client = OpenAI(api_key=st.secrets["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
newsapi = NewsApiClient(api_key=st.secrets["NEWSAPI_KEY"])

@st.cache_resource
def init_supabase():
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    return None

supabase = init_supabase()
user_email = st.user.email

# --- 4. Database Mutations ---
def log_search(ticker):
    if supabase:
        try:
            supabase.table("search_history").insert({"user_email": user_email, "ticker": ticker}).execute()
        except Exception as e:
            pass

def add_favorite(ticker):
    if supabase:
        try:
            supabase.table("user_favorites").insert({"user_email": user_email, "ticker": ticker}).execute()
            st.toast(f"Added {ticker} to Favorites!")
        except Exception:
            st.toast(f"{ticker} is already in your favorites.")

# --- 5. Sidebar Navigation ---
st.sidebar.markdown(f"### 👤 {user_email}")
if st.sidebar.button("Logout", use_container_width=True):
    st.logout()

st.sidebar.markdown("---")
st.sidebar.markdown("### Favorites")
if supabase:
    try:
        fav_data = supabase.table("user_favorites").select("ticker").eq("user_email", user_email).execute()
        unique_favs = list(set([row['ticker'] for row in fav_data.data]))
        if not unique_favs:
            st.sidebar.caption("No favorites saved yet.")
        for f in unique_favs:
            if st.sidebar.button(f" {f}", key=f"side_fav_{f}", use_container_width=True):
                st.session_state.ticker = f
                st.rerun()
    except Exception as e:
        st.sidebar.error(f"Could not load favorites.")

st.sidebar.markdown("---")
st.sidebar.markdown("### Recent Searches")
if supabase:
    try:
        hist_data = supabase.table("search_history").select("ticker").eq("user_email", user_email).order('created_at', desc=True).limit(10).execute()
        unique_hist = list(dict.fromkeys([row['ticker'] for row in hist_data.data]))
        if not unique_hist:
            st.sidebar.caption("No history yet.")
        for h in unique_hist:
            if st.sidebar.button(f" {h}", key=f"side_hist_{h}", use_container_width=True):
                st.session_state.ticker = h
                st.rerun()
    except Exception as e:
        st.sidebar.error(f"Could not load history.")

# --- 6. Analysis Logic ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_analysis(ticker, timeframe):
    stock = yf.Ticker(ticker)
    info = stock.info
    
    # REVISED PROMPT: Forces forward-looking investment advice and explanations.
    prompt = f"""
    Provide a forward-looking investment analysis for {info.get('shortName', ticker)} ({ticker}) projecting over the next {timeframe}. 
    Focus entirely on WHY someone should or shouldn't invest for this specific future horizon. Do not just list past performance.
    Return ONLY a raw JSON object with this exact structure:
    {{
        "verdict": "GREEN", (Must be exactly GREEN, YELLOW, or RED)
        "thesis": "A detailed 2-3 sentence explanation justifying your verdict and future outlook.",
        "bull_case": ["Strong future growth catalyst 1", "Catalyst 2", "Catalyst 3"],
        "bear_case": ["Future risk 1", "Risk 2", "Risk 3"]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are an elite, forward-looking financial analyst. Output ONLY valid JSON."}, 
                {"role": "user", "content": prompt}
            ]
        )
        raw_text = response.choices[0].message.content.strip()
        clean_json = raw_text[raw_text.find('{'):raw_text.rfind('}')+1]
        return json.loads(clean_json)
    except Exception as e:
        return {"verdict": "RED", "thesis": f"Error generating analysis: {str(e)}", "bull_case": ["N/A"], "bear_case": ["N/A"]}

@st.cache_data(ttl=3600, show_spinner=False)
def get_market_pulse(ticker):
    try:
        news = newsapi.get_everything(q=f"{ticker} stock", language='en', sort_by='relevancy', page_size=5)
        headlines = [a['title'] for a in news.get('articles', [])]
        
        if not headlines:
            return "No recent news headlines found for this ticker."

        prompt = f"Analyze the sentiment for {ticker} based on these headlines: {headlines}. Keep it to exactly 2 sentences and include a 1-5 star sentiment rating."
        
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": "You are a ruthless, world-class market analyst."}, 
                      {"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Could not fetch news pulse."

# --- 7. Main UI Layout ---
if "ticker" not in st.session_state: 
    st.session_state.ticker = ""

# Header - Uses var(--text-color) to adapt to light/dark mode seamlessly
st.markdown("""
<div style="text-align: center; margin-top: -20px; padding-bottom: 10px;">
    <h1 style="font-weight: 900; font-size: 4.5rem; letter-spacing: -2px; margin-bottom: 0px;">
        <span style="color: #3b82f6;">Sto</span><span style="color: var(--text-color);">ck-R</span>
    </h1>
    <p style="color: #64748b; font-size: 1.1rem; margin-top: -5px; font-weight: 500;">the world's best ai stock market predictor</p>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='display: flex; justify-content: center; gap: 20px; font-size: 12px; font-weight: 700;'> <span style='color: #10b981;'>● GREEN: Good</span> <span style='color: #eab308;'>● YELLOW: Cautious</span> <span style='color: #ef4444;'>● RED: Bad</span></div>", unsafe_allow_html=True)

# Trending Assets
st.markdown("<div class='bar-title'>Trending Assets</div>", unsafe_allow_html=True)
pill_cols = st.columns(6)
trending = ["AAPL", "SBUX", "TSLA", "NVDA", "MSFT", "AMZN"]
for idx, sym in enumerate(trending):
    if pill_cols[idx].button(sym, key=f"trend_{sym}", use_container_width=True): 
        st.session_state.ticker = sym
        st.rerun()

# Side-by-side inputs (Fixed proportions)
st.markdown("<div class='bar-title'>New Analysis</div>", unsafe_allow_html=True)
input_cols = st.columns([1, 1]) # Exactly 50/50 split for perfect alignment
with input_cols[0]:
    ticker_input = st.text_input("Asset Ticker", value=st.session_state.ticker, placeholder="e.g. AAPL").upper()
with input_cols[1]:
    timeframe = st.selectbox("Investment Horizon", ["1D", "1M", "1Y", "2Y", "5Y", "ALL"], index=2)

# Main Dashboard Execution
if ticker_input:
    log_search(ticker_input) 
    
    # Action Row
    action_cols = st.columns([4, 1])
    with action_cols[1]:
        if st.button("⭐ Favorite", use_container_width=True):
            add_favorite(ticker_input)

    res = get_analysis(ticker_input, timeframe)
    tab1, tab2 = st.tabs(["Verdict & Analysis", "Detailed Pro/Con"])
    
    with tab1:
        # Verdict Card with integrated thesis
        style_class = f"verdict-text-{res.get('verdict', 'YELLOW').upper()}"
        st.markdown(f"""
        <div class='verdict-card'>
            <h1 class='{style_class}'>{res.get('verdict', 'YELLOW')}</h1>
            <p class='thesis-text'>{res.get('thesis', 'No thesis generated. Try again.')}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"<div class='bar-title'>Market Pulse</div>", unsafe_allow_html=True)
        with st.spinner("Analyzing news sentiment..."):
            pulse = get_market_pulse(ticker_input)
            st.info(pulse)
            
        st.markdown(f"<div class='bar-title'>{ticker_input} Price History ({timeframe})</div>", unsafe_allow_html=True)
        stock = yf.Ticker(ticker_input)
        period_map = {"1D": "1d", "1M": "1mo", "1Y": "1y", "2Y": "2y", "5Y": "5y", "ALL": "max"}
        interval_map = {"1D": "1m", "1M": "1h"}
        hist = stock.history(period=period_map.get(timeframe, "1mo"), interval=interval_map.get(timeframe, "1d"))

        if not hist.empty:
            fig = px.line(hist, x=hist.index, y='Close', template="plotly_white")
            fig.update_traces(line_shape='spline', line=dict(width=2, color="#3b82f6"))
            fig.update_layout(margin=dict(l=0, r=0, t=20, b=20), height=300, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        # Fixed Bull/Bear UI using Streamlit's native colored boxes
        col_bull, col_bear = st.columns(2)
        with col_bull:
            st.success("### 🟢 The Bull Case")
            for point in res.get("bull_case", []): 
                st.write(f"**✓** {point}")
        with col_bear:
            st.error("### 🔴 The Bear Case")
            for point in res.get("bear_case", []): 
                st.write(f"**✗** {point}")

st.markdown("<p class='footer-disclaimer'>Disclaimer: Stock-R is an AI-driven tool. All outputs are generated by AI and may contain errors or inaccuracies. Not financial advice.</p>", unsafe_allow_html=True)
