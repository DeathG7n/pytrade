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

count = 0
closes = []
symbols = ["BOOM1000","BOOM900", "BOOM500", "BOOM600", "BOOM300"]
previous_candles = [0] * len(symbols)


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

def detect_ema_crossover(candles):
    global closes

    closes = [c["close"] for c in candles["candles"]]
    opens = [c["open"] for c in candles["candles"]]
    length = len(closes)
    curr_index = length - 1
    prev_index = length - 2

    crossed_up = bullish(prev_index)
 
    return {"crossedUp": crossed_up}

async def sample_calls(symbol, i):
    global count
    global previous_candles
    try:
        api = DerivAPI(app_id=app_id)
        response = await api.ping({'ping': 1})
        authorize = await api.authorize(api_token)
        
        # Get Candles
        period = getTicksRequest(symbol, 10000000000000000000 , getTimeFrame(1, "mins"))
        candles = await api.ticks_history(period)
        result = detect_ema_crossover(candles)

        length = len(closes)
        prev_index = length - 2

        if(previous_candles[i] != closes[prev_index]):
            if result["crossedUp"]:
                send_message(f"BOOM on {symbol}")
                print(f"BOOM on {symbol}")
                previous_candles[i] = closes[prev_index]
        
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
    for index, symbol in enumerate(symbols):
        asyncio.run(sample_calls(symbol, index))
    # time.sleep(1)