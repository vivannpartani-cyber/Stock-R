import streamlit as st
import yfinance as yf
from openai import OpenAI
from newsapi import NewsApiClient
from supabase import create_client
import json
import plotly.express as px

# --- 1. CONFIG & CLIENTS ---
st.set_page_config(page_title="Stock-R", layout="centered")

# Initialize Clients
client = OpenAI(api_key=st.secrets["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
newsapi = NewsApiClient(api_key=st.secrets["NEWSAPI_KEY"])
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- 2. AUTHENTICATION FLOW ---
if not st.user.is_logged_in:
    st.markdown("<h1 style='text-align: center;'>Welcome to Stock-R</h1>", unsafe_allow_html=True)
    if st.button("Log in with Google"):
        st.login("google")
    st.stop()

# --- 3. DATA FUNCTIONS ---
@st.cache_data(ttl=3600)
def get_analysis(ticker, timeframe):
    stock = yf.Ticker(ticker)
    info = stock.info
    prompt = f"""Analyze {ticker} ({info.get('shortName', ticker)}) for {timeframe}.
    Consider macro themes: Apple Intelligence, Oil/Energy crisis, US-China trade.
    Return ONLY JSON: {{"verdict": "GREEN|YELLOW|RED", "thesis": "...", "bull_case": ["..."], "bear_case": ["..."]}}"""
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": "You are a ruthless market analyst."}, {"role": "user", "content": prompt}]
    )
    return json.loads(response.choices[0].message.content)

@st.cache_data(ttl=3600)
def get_market_pulse(ticker):
    news = newsapi.get_everything(q=f"{ticker} stock", language='en', page_size=5)
    headlines = [a['title'] for a in news.get('articles', [])]
    prompt = f"Analyze sentiment for {ticker} based on: {headlines}. Max 2 sentences + 1-5 star rating."
    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": "You are an analyst."}, {"role": "user", "content": prompt}]
    )
    return resp.choices[0].message.content

# --- 4. SIDEBAR & DATABASE LOGIC ---
st.sidebar.markdown(f"## 👋 {st.user.name}")
if st.sidebar.button("Logout"): st.logout()

def save_search(ticker):
    supabase.table("search_history").insert({"user_email": st.user.email, "ticker": ticker}).execute()

# --- 5. MAIN UI ---
st.markdown("<h1 style='text-align: center;'>Stock-R</h1>", unsafe_allow_html=True)
ticker_input = st.text_input("Enter Ticker (e.g., AAPL)").upper()

if ticker_input:
    save_search(ticker_input) # Save to Supabase
    res = get_analysis(ticker_input, "1Y")
    
    tab1, tab2 = st.tabs(["Verdict & News", "Bull/Bear"])
    with tab1:
        st.subheader(res['verdict'])
        st.info(get_market_pulse(ticker_input))
        
    with tab2:
        col1, col2 = st.columns(2)
        col1.write(res['bull_case'])
        col2.write(res['bear_case'])

# Sidebar History Display
st.sidebar.subheader("Recent Searches")
history = supabase.table("search_history").select("ticker").eq("user_email", st.user.email).execute()
for item in history.data[:10]: st.sidebar.text(item['ticker'])