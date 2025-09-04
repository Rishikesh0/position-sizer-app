#!/usr/bin/env python3
"""
Streamlit Position Sizer App
Run with: streamlit run position_sizer.py
"""

import math
import streamlit as st
import yfinance as yf
import pandas as pd

# ---------------- Core class ----------------
class PositionSizer:
    def __init__(self, account_balance, commission_per_trade=0.0, slippage_per_share=0.0):
        self.account_balance = float(account_balance)
        self.commission_per_trade = float(commission_per_trade)
        self.slippage_per_share = float(slippage_per_share)

    def risk_amount(self, risk_pct):
        return self.account_balance * float(risk_pct)

    def fixed_risk_by_stop(self, entry_price, stop_price, risk_pct):
        trade_risk = abs(entry_price - stop_price) + self.slippage_per_share
        risk_amt = self.risk_amount(risk_pct)
        qty = math.floor((risk_amt - self.commission_per_trade) / trade_risk)
        qty = max(qty, 0)
        cost = qty * entry_price + self.commission_per_trade
        return qty, cost, risk_amt, trade_risk

    def percent_of_portfolio(self, entry_price, allocation_pct):
        position_value = self.account_balance * allocation_pct
        qty = math.floor((position_value - self.commission_per_trade) / entry_price)
        qty = max(qty, 0)
        cost = qty * entry_price + self.commission_per_trade
        return qty, cost, position_value

    def atr_position_size(self, atr, atr_multiplier, risk_pct):
        trade_risk = atr * atr_multiplier + self.slippage_per_share
        risk_amt = self.risk_amount(risk_pct)
        qty = math.floor((risk_amt - self.commission_per_trade) / trade_risk)
        qty = max(qty, 0)
        return qty, risk_amt, trade_risk

    def kelly_position_size(self, entry_price, win_rate, win_loss_ratio, fraction_of_kelly=0.25):
        W, R = win_rate, win_loss_ratio
        raw_kelly = W - (1 - W) / R
        kelly_used = max(raw_kelly, 0.0) * fraction_of_kelly
        position_value = self.account_balance * kelly_used
        qty = math.floor((position_value - self.commission_per_trade) / entry_price)
        qty = max(qty, 0)
        return qty, raw_kelly, kelly_used, position_value

    @staticmethod
    def fetch_price_and_atr(ticker, period="90d", atr_period=14):
        df = yf.download(ticker, period=period, progress=False)
        if df.empty:
            return None, None
        high, low, close = df["High"], df["Low"], df["Close"]
        prev_close = close.shift(1)
        tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=atr_period, min_periods=1).mean().iloc[-1]
        last_close = close.iloc[-1]
        return float(last_close), float(atr)


# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="📊 Position Sizer", layout="wide")

st.title("📊 Automated Position Sizer")
st.markdown("Calculate how many shares to buy based on risk, portfolio %, ATR, or Kelly.")

col1, col2 = st.columns(2)

with col1:
    account_balance = st.number_input("💰 Account Balance", min_value=1000.0, value=10000.0, step=100.0)
    commission = st.number_input("📉 Commission per Trade", min_value=0.0, value=0.0, step=1.0)
    slippage = st.number_input("🔀 Slippage per Share", min_value=0.0, value=0.0, step=0.01)
    ticker = st.text_input("📈 Stock Ticker (Yahoo Finance)", value="AAPL")
    fetch = st.button("Fetch Price & ATR")

with col2:
    method = st.selectbox("📌 Choose Sizing Method", 
                          ["Fixed Risk by Stop", "Percent of Portfolio", "ATR-based", "Kelly"])

# Fetch data
entry_price, atr_val = None, None
if fetch:
    price, atr = PositionSizer.fetch_price_and_atr(ticker)
    if price is None:
        st.error("Could not fetch data for ticker.")
    else:
        entry_price, atr_val = price, atr
        st.success(f"Fetched {ticker}: Last Close = {entry_price:.2f}, ATR(14) = {atr_val:.2f}")

# Instantiate sizer
sizer = PositionSizer(account_balance, commission, slippage)

st.markdown("---")
st.header("⚙️ Parameters")

if method == "Fixed Risk by Stop":
    entry = st.number_input("Entry Price", value=entry_price if entry_price else 100.0)
    stop = st.number_input("Stop-Loss Price", value=95.0)
    risk_pct = st.slider("Risk % of Account", 0.5, 5.0, 2.0) / 100
    if st.button("Calculate Fixed Risk Size"):
        qty, cost, risk_amt, risk_per_share = sizer.fixed_risk_by_stop(entry, stop, risk_pct)
        st.success(f"Buy **{qty} shares** (Cost ≈ {cost:.2f}, Risk per share = {risk_per_share:.2f}, Total risk = {risk_amt:.2f})")

elif method == "Percent of Portfolio":
    entry = st.number_input("Entry Price", value=entry_price if entry_price else 100.0)
    alloc_pct = st.slider("Allocation % of Account", 1, 100, 10) / 100
    if st.button("Calculate Portfolio % Size"):
        qty, cost, target_value = sizer.percent_of_portfolio(entry, alloc_pct)
        st.success(f"Buy **{qty} shares** (Target Value = {target_value:.2f}, Cost ≈ {cost:.2f})")

elif method == "ATR-based":
    atr = st.number_input("ATR Value", value=atr_val if atr_val else 2.0)
    atr_mult = st.slider("ATR Multiplier", 0.5, 5.0, 1.0)
    risk_pct = st.slider("Risk % of Account", 0.5, 5.0, 2.0) / 100
    if st.button("Calculate ATR Size"):
        qty, risk_amt, risk_per_unit = sizer.atr_position_size(atr, atr_mult, risk_pct)
        st.success(f"Buy **{qty} shares** (Risk per unit = {risk_per_unit:.2f}, Total risk = {risk_amt:.2f})")

elif method == "Kelly":
    entry = st.number_input("Entry Price", value=entry_price if entry_price else 100.0)
    win_rate = st.slider("Win Rate %", 10, 90, 55) / 100
    win_loss_ratio = st.number_input("Win/Loss Ratio", value=1.5, step=0.1)
    frac_kelly = st.slider("Fraction of Kelly", 0.1, 1.0, 0.25)
    if st.button("Calculate Kelly Size"):
        qty, raw_k, used_k, pos_val = sizer.kelly_position_size(entry, win_rate, win_loss_ratio, frac_kelly)
        st.success(f"Buy **{qty} shares** (Raw Kelly={raw_k:.2f}, Used Kelly={used_k:.2f}, Position Value={pos_val:.2f})")
