import os
import sqlite3
import bcrypt
import pandas as pd
import streamlit as st

DB_FILE = "journal_saas.db"

st.set_page_config(page_title="Quant Journal SaaS", layout="wide")

# ==========================================
# DATABASE LAYER (SQLite Secure Automation)
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Create Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT)''')
    # Create Trades table mapped to user_id
    c.execute('''CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ticker TEXT,
                    direction TEXT,
                    entry REAL,
                    sl REAL,
                    tp REAL,
                    lot_size REAL,
                    strategy TEXT,
                    emotion TEXT,
                    pnl REAL,
                    r_multiple REAL,
                    is_win INTEGER,
                    FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.commit()
    conn.close()

def create_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False  # Username already exists
    conn.close()
    return success

def verify_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    if result:
        user_id, hashed_val = result
        if bcrypt.checkpw(password.encode('utf-8'), hashed_val.encode('utf-8')):
            return user_id
    return None

def load_user_trades(user_id):
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT ticker, direction, entry, sl, tp, lot_size, strategy, emotion, pnl, r_multiple, is_win FROM trades WHERE user_id = ?"
    df = pd.read_sql_query(query, conn, params=(user_id,))
    conn.close()
    # Convert integer mapping back to boolean for compatibility
    if not df.empty:
        df['is_win'] = df['is_win'].astype(bool)
    return df

def save_manual_trade(user_id, trade_dict):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO trades (user_id, ticker, direction, entry, sl, tp, lot_size, strategy, emotion, pnl, r_multiple, is_win)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, trade_dict['ticker'], trade_dict['direction'], trade_dict['entry'], trade_dict['sl'], 
               trade_dict['tp'], trade_dict['lot_size'], trade_dict['strategy'], trade_dict['emotion'], 
               trade_dict['pnl'], trade_dict['r_multiple'], int(trade_dict['is_win'])))
    conn.commit()
    conn.close()

# Start up Database automatically
init_db()

# ==========================================
# AUTHENTICATION SESSION STATE MANAGEMENT
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = ""

# ------------------------------------------
# GATEWAY SCREEN: LOGIN / SIGNUP PORTAL
# ------------------------------------------
if not st.session_state['logged_in']:
    st.title("🔐 Quant Trading Portal Login")
    auth_mode = st.radio("Access Action:", ["Sign In to Account", "Create New Account"])
    
    with st.form("auth_form"):
        user_input = st.text_input("Username / Email").strip().lower()
        pass_input = st.text_input("Password", type="password")
        action_btn = st.form_submit_button("Submit Credentials")
        
    if action_btn:
        if not user_input or not pass_input:
            st.error("Fields cannot be left blank.")
        elif auth_mode == "Create New Account":
            if create_user(user_input, pass_input):
                st.success("Account setup successful! Switch to 'Sign In to Account' to access dashboard.")
            else:
                st.error("That username/email is already registered. Try another or Sign In.")
        elif auth_mode == "Sign In to Account":
            uid = verify_user(user_input, pass_input)
            if uid:
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = uid
                st.session_state['username'] = user_input
                st.success("Access Granted! Loading system dashboard...")
                st.rerun()
            else:
                st.error("Invalid Username or Password combination.")
    st.stop() # Freeze execution here if not logged in

# ==========================================
# INSIDE PORTAL SYSTEM (POST-LOGIN SCREEN)
# ==========================================
st.sidebar.title(f"👤 Account: {st.session_state['username'].upper()}")
if st.sidebar.button("Log Out / Disconnect"):
    st.session_state['logged_in'] = False
    st.session_state['user_id'] = None
    st.session_state['username'] = ""
    st.rerun()

menu_choice = st.sidebar.radio("Go To:", ["Dashboard & Analytics", "Manual Entry", "Bulk CSV Import"])

# ------------------------------------------
# INTERIOR CAPABILITIES: MANUAL ENTRY
# ------------------------------------------
if menu_choice == "Manual Entry":
    st.header("📥 Log a New Trade Manually")
    with st.form(key="trade_form", clear_on_submit=True):
        ticker = st.text_input("Asset / Pair Symbol", value="XAUUSD").upper().strip()
        direction = st.selectbox("Position Direction", ["LONG", "SHORT"])
        
        col1, col2 = st.columns(2)
        with col1:
            entry_price = st.number_input("Entry Price", value=4010.0, step=1.0)
            stop_loss = st.number_input("Stop Loss", value=4000.0, step=1.0)
        with col2:
            target_price = st.number_input("Target Price (TP)", value=4020.0, step=1.0)
            lot_size = st.number_input("Lot Size", value=0.01, format="%.2f", step=0.01)
            
        strategy = st.selectbox("Strategy Setup", ["Trend Continuation", "Reversal", "Breakout", "News Event"])
        emotion = st.selectbox("Primary Emotional State", ["Calm/Disciplined", "FOMO", "Revenge Trade", "Impulsive"])
        outcome = st.radio("Trade Outcome Match", ["Hit Target (TP)", "Hit Stop Loss (SL)"])
        
        submit_button = st.form_submit_button(label="Log Transaction to Ledger")

    if submit_button:
        multiplier = 100 if "XAUUSD" in ticker or "GOLD" in ticker else 1
        
        if direction == "LONG":
            potential_profit = (target_price - entry_price) * lot_size * multiplier
            potential_loss = (entry_price - stop_loss) * lot_size * multiplier
        else:
            potential_profit = (entry_price - target_price) * lot_size * multiplier
            potential_loss = (stop_loss - entry_price) * lot_size * multiplier
            
        p_loss = potential_loss if potential_loss > 0 else 0.01
        planned_rr = potential_profit / p_loss
        
        if outcome == "Hit Target (TP)":
            final_pnl = potential_profit
            r_multiple = planned_rr
            is_win = True
        else:
            final_pnl = -potential_loss
            r_multiple = -1.0
            is_win = False
            
        new_trade = {
            "ticker": ticker, "direction": direction, "entry": entry_price, "sl": stop_loss, 
            "tp": target_price, "lot_size": lot_size, "strategy": strategy, "emotion": emotion, 
            "pnl": round(final_pnl, 2), "r_multiple": round(r_multiple, 2), "is_win": is_win
        }
        
        save_manual_trade(st.session_state['user_id'], new_trade)
        st.success(f"Logged {ticker} successfully into your private secure database partition!")

# ------------------------------------------
# INTERIOR CAPABILITIES: BULK CSV IMPORT
# ------------------------------------------
elif menu_choice == "Bulk CSV Import":
    st.header("🤖 Automated Broker CSV Import")
    uploaded_file = st.file_uploader("Choose your broker CSV file", type=["csv"])
    
    if uploaded_file is not None:
        try:
            uploaded_df = pd.read_csv(uploaded_file)
            st.markdown("### Previewing Uploaded File Data:")
            st.dataframe(uploaded_df.head(3))
            
            col_mapping = {}
            for col in uploaded_df.columns:
                col_lower = col.lower()
                if 'symbol' in col_lower or 'ticker' in col_lower or 'item' in col_lower:
                    col_mapping['ticker'] = col
                elif 'type' in col_lower or 'direction' in col_lower or 'side' in col_lower:
                    col_mapping['direction'] = col
                elif 'lot' in col_lower or 'volume' in col_lower or 'qty' in col_lower or 'size' in col_lower:
                    col_mapping['lot_size'] = col
                elif 'profit' in col_lower or 'pnl' in col_lower or 'amount' in col_lower:
                    col_mapping['pnl'] = col

            if len(col_mapping) >= 3: 
                if st.button("Confirm and Import Automatically"):
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    imported_count = 0
                    for _, row in uploaded_df.iterrows():
                        raw_ticker = str(row[col_mapping['ticker']]).upper()
                        raw_dir = str(row[col_mapping['direction']]).upper()
                        
                        final_dir = "LONG" if ("BUY" in raw_dir or "LONG" in raw_dir) else "SHORT"
                        final_lot = float(row[col_mapping['lot_size']]) if 'lot_size' in col_mapping else 0.01
                        final_pnl = float(row[col_mapping['pnl']])
                        final_win = final_pnl > 0
                        r_mult = 2.0 if final_win else -1.0 
                        
                        c.execute('''INSERT INTO trades (user_id, ticker, direction, entry, sl, tp, lot_size, strategy, emotion, pnl, r_multiple, is_win)
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                  (st.session_state['user_id'], raw_ticker, final_dir, 0.0, 0.0, 0.0, final_lot, 
                                   "Bulk CSV Import", "Neutral/Automated", round(final_pnl, 2), r_mult, int(final_win)))
                        imported_count += 1
                    conn.commit()
                    conn.close()
                    st.success(f"Successfully auto-parsed and isolated {imported_count} trades into your secure profile data store!")
            else:
                st.error("Could not auto-match column headers. Ensure your CSV has clear column headers specifying Symbol, Type, Lots, and Profit.")
        except Exception as e:
            st.error(f"Error parsing file: {e}")

# ------------------------------------------
# INTERIOR CAPABILITIES: PERSONAL DASHBOARD
# ------------------------------------------
elif menu_choice == "Dashboard & Analytics":
    df = load_user_trades(st.session_state['user_id'])
    
    if df.empty:
        st.info("👋 Welcome to the platform! Your database workspace is currently empty. Head to 'Manual Entry' or 'Bulk CSV Import' to feed logs into your tracking core.")
    else:
        total_trades = len(df)
        wins = df[df['is_win'] == True]
        losses = df[df['is_win'] == False]
        win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
        total_pnl = df['pnl'].sum()
        avg_r = df['r_multiple'].mean()
        
        avg_win_usd = wins['pnl'].mean() if not wins.empty else 0
        avg_loss_usd = abs(losses['pnl'].mean()) if not losses.empty else 0
        expectancy = ((win_rate / 100) * avg_win_usd) - ((1 - (win_rate / 100)) * avg_loss_usd)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Executed Trades", f"{total_trades}")
        m2.metric("Win Rate Metric", f"{win_rate:.1f}%")
        m3.metric("Net Account Balance", f"${total_pnl:,.2f} USD")
        m4.metric("Avg Risk Return", f"{avg_r:+.2f}R")
        
        if expectancy > 0:
            st.success(f"💡 **Trading Expectancy Edge Verdict:** Positive Mathematical Advantage (${expectancy:.2f} expected net return per setup).")
        else:
            st.error(f"⚠️ **Trading Expectancy Edge Verdict:** Negative Mathematical Variance (${expectancy:.2f} decay per execution). System parameters need adjustment.")
            
        st.markdown("### 📈 Cumulative Account Balance Growth Curve")
        df['Equity Curve'] = 10000 + df['pnl'].cumsum()
        st.line_chart(df['Equity Curve'])
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown("### ⚡ Strategy Performance Ledger")
            strat_df = df.groupby('strategy').agg(
                Trades=('pnl', 'count'),
                Total_PnL=('pnl', 'sum'),
                Avg_R=('r_multiple', 'mean')
            ).reset_index()
            st.dataframe(strat_df, width='stretch')
            
        with col_right:
            st.markdown("### 🧠 Emotional Capital Drain Analysis")
            emotion_df = df.groupby('emotion').agg(
                Trades=('pnl', 'count'),
                Net_PnL=('pnl', 'sum')
            ).reset_index()
            st.dataframe(emotion_df, width='stretch')

        st.markdown("### 📑 Full Historical Transaction Logs")
        st.dataframe(df[['ticker', 'direction', 'entry', 'sl', 'tp', 'lot_size', 'strategy', 'emotion', 'pnl', 'r_multiple']], width='stretch')