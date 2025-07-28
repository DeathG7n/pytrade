import sys
import asyncio
import os
from deriv_api import DerivAPI
from deriv_api import ResponseError
from deriv_api import APIError
import requests
import time
import subprocess
import pandas as pd

app_id = 36807
api_token = 'IxcmbIEL0Mb4fvQ'
BOT_TOKEN = '8033524186:AAFp1cMBr1oRVUgCa2vwKPgroSw_i6M-qEQ'
CHAT_ID = '8068534792'
close_prices = []
open_prices = []
open_positions = []
position = None
position_type = None
position_id = None
count = 0
amount = 1
stop_loss = -1000
symbol = "R_75"

def compute_heikin_ashi(df):
    ha_df = df.copy()

    ha_df['HA_Close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    ha_df['HA_Open'] = 0.0
    ha_df['HA_High'] = 0.0
    ha_df['HA_Low'] = 0.0

    # Initialize the first HA_Open as the real candle's open
    ha_df.loc[0, 'HA_Open'] = df.loc[0, 'open']

    # Loop through the DataFrame to calculate the rest
    for i in range(1, len(df)):
        ha_df.loc[i, 'HA_Open'] = (ha_df.loc[i-1, 'HA_Open'] + ha_df.loc[i-1, 'HA_Close']) / 2
        ha_df.loc[i, 'HA_High'] = max(df.loc[i, 'high'], ha_df.loc[i, 'HA_Open'], ha_df.loc[i, 'HA_Close'])
        ha_df.loc[i, 'HA_Low']  = min(df.loc[i, 'low'],  ha_df.loc[i, 'HA_Open'], ha_df.loc[i, 'HA_Close'])

    # Handle the first row (optional, not always needed)
    ha_df.loc[0, 'HA_High'] = max(df.loc[0, 'high'], ha_df.loc[0, 'HA_Open'], ha_df.loc[0, 'HA_Close'])
    ha_df.loc[0, 'HA_Low']  = min(df.loc[0, 'low'],  ha_df.loc[0, 'HA_Open'], ha_df.loc[0, 'HA_Close'])

    return ha_df[['HA_Open', 'HA_High', 'HA_Low', 'HA_Close']]

def calculate_ema(prices, period):
    ema = [prices[0]]
    k = 2 / (period + 1)
    for price in prices[1:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema


def send_message(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Telegram Error:", e)

def bullish(open, close, i):
    return close[i] > open[i]

def bearish(open, close, i):
    return open[i] > close[i]

def getTimeFrame(count, time):
    if(time == "mins"):
      return count * 60
    
    if(time == "hrs"):
      return count * 3600
    
  
def getTicksRequest(symbol, count, timeframe):
    ticks_history_request = {
      "ticks_history": symbol,
      "count": count,
      "end": 'latest',
      "style": 'candles',
      "granularity": timeframe,
    }
    return ticks_history_request

def getProposal(direction):
    global amount
    proposal = {
        "proposal": 1, 
        "amount": amount,
        "basis": "stake",
        "contract_type": direction,
        "currency": "USD", 
        "symbol": symbol,
        "multiplier": 100,
    }
    return proposal

def detect_ema_crossover(candles, candles5):
    global closes

    closes = [c["close"] for c in candles["candles"]]
    opens = [c["open"] for c in candles["candles"]]
    length = len(closes)
    curr_index = length - 1
    prev_index = length - 2

    ema21 = calculate_ema(closes, 21)
    ema50 = calculate_ema(closes, 50)

    ema21_now = ema21[curr_index]
    ema50_now = ema50[curr_index]
    ema21_prev = ema21[prev_index]
    ema50_prev = ema50[prev_index]

    closes5 = [c["close"] for c in candles5["candles"]]

    ema14_5 = calculate_ema(closes5, 14)
    ema21_5 = calculate_ema(closes5, 21)

    ema14_5_now = ema14_5[curr_index]
    ema21_5_now = ema21_5[curr_index]

    trend = ema21_now > ema50_now
    higher_trend = ema14_5_now > ema21_5_now

    crossed_up = higher_trend and trend and bullish(opens, closes, prev_index) and ((closes[prev_index] > ema21_prev and opens[prev_index] < ema21_prev) or (closes[prev_index] > ema50_prev and opens[prev_index] < ema50_prev))
    crossed_down = not higher_trend and not trend and bearish(opens, closes, prev_index) and ((opens[prev_index] > ema21_prev and closes[prev_index] < ema21_prev) or (opens[prev_index] > ema50_prev and closes[prev_index] < ema50_prev))
 
    return {"crossedUp": crossed_up, "crossedDown": crossed_down}

async def sample_calls():
    global count
    global stop_loss
    global amount
    try:
        api = DerivAPI(app_id=app_id)
        response = await api.ping({'ping': 1})
        authorize = await api.authorize(api_token)

        # Get Open Positions
        porfolio = await api.portfolio({"portfolio": 1})
        open_positions = porfolio['portfolio']["contracts"]
        if(len(open_positions) > 0):
            position_type = porfolio['portfolio']["contracts"][0]["contract_type"]
            position_id = porfolio['portfolio']["contracts"][0]["contract_id"]

        # Get Candles
        period = getTicksRequest(symbol, 10000000000000000000 , getTimeFrame(1, "mins"))
        candles = await api.ticks_history(period)
        period5 = getTicksRequest(symbol, 10000000000000000000 , getTimeFrame(5, "mins"))
        candles5 = await api.ticks_history(period5)
        result = detect_ema_crossover(candles, candles5)

        if(len(open_positions) > 0):
            poc = await api.proposal_open_contract({
                "proposal_open_contract": 1, 
                "contract_id": open_positions[0]["contract_id"]
            })
            position = poc['proposal_open_contract']
            type = position["contract_type"]
            entry_spot = position["entry_spot"]
            current_spot = position["current_spot"]
            if(type == "MULTUP"):
                pip = current_spot - entry_spot
            else:
                pip = entry_spot - current_spot

            profit = position["profit"]
            if(pip <= stop_loss):
                sell = await api.sell({"sell": position_id, "price" : 0})
                send_message(f"💸 Position closed at {sell['sell']['sold_for']} USD, because of stop loss hit")
                print(f"💸 Position closed at {sell['sell']['sold_for']} USD, because of stop loss hit")

            if(pip >= 500 and stop_loss == -1000):
                stop_loss = 100
            if(pip >= 2000 and stop_loss == 100):
                stop_loss = 1000
            if(pip >= 3000 and stop_loss == 1000):
                stop_loss = 2000
            if(pip >= 4000 and stop_loss == 2000):
                stop_loss = 3000
            if(pip >= 5000 and stop_loss == 3000):
                stop_loss = 4000

            print(amount, profit, stop_loss, pip)

            if result["crossedUp"]:
                if position_type == "MULTDOWN":
                    sell = await api.sell({"sell": position_id, "price" : 0})
                    send_message(f"💸 Position closed at {sell['sell']['sold_for']} USD, because of opposing signal")
                    print(f"💸 Position closed at {sell['sell']['sold_for']} USD, because of opposing signal")
            
            if result["crossedDown"]:
                if position_type == "MULTUP":
                    sell = await api.sell({"sell": position_id, "price" : 0})
                    send_message(f"💸 Position closed at {sell['sell']['sold_for']} USD, because of opposing signal")
                    print(f"💸 Position closed at {sell['sell']['sold_for']} USD, because of opposing signal")

        if(len(open_positions) == 0):
            stop_loss  = -1000
            if result["crossedUp"]:
                proposal = await api.proposal(getProposal("MULTUP"))
                buy = await api.buy({"buy": proposal.get('proposal').get('id'), "price": 1})
                send_message(f"{proposal.get('echo_req').get('contract_type')} position entered on {proposal.get('echo_req').get('symbol')}")
                print(f"🟢 Entered {proposal.get('echo_req').get('contract_type')} position")
            
            if result["crossedDown"]:
                proposal = await api.proposal(getProposal("MULTDOWN"))
                buy = await api.buy({"buy": proposal.get('proposal').get('id'), "price": 1})
                send_message(f"{proposal.get('echo_req').get('contract_type')} position entered on {proposal.get('echo_req').get('symbol')}")
                print(f"🟢 Entered {proposal.get('echo_req').get('contract_type')} position")
        
        await api.clear()
        count = count + 1
        print(count)
        if(count > 1000):
            subprocess.run(["pm2", "restart", "all"], check=True)
    except ResponseError as err:
        print("error!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(err)
        subprocess.run(["pm2", "restart", "all"], check=True)


while True:
    asyncio.run(sample_calls())
    # time.sleep(1)