import sys
import asyncio
import os
from deriv_api import DerivAPI
from deriv_api import ResponseError
from deriv_api import APIError
import requests
import time

app_id = 36807
api_token = 'IxcmbIEL0Mb4fvQ'
BOT_TOKEN = '8033524186:AAFp1cMBr1oRVUgCa2vwKPgroSw_i6M-qEQ'
CHAT_ID = '8068534792'
close_prices = []
open_positions = []
position = None
position_type = None
position_id = None
count = 0

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
    proposal = {
        "proposal": 1, 
        "amount": 1,
        "basis": "stake",
        "contract_type": direction,
        "currency": "USD", 
        "symbol": "R_75",
        "multiplier": 100,
    }
    return proposal

def detect_ema_crossover(prices):
    length = len(prices)
    curr_index = length - 1
    prev_index = length - 2

    ema14 = calculate_ema(prices, 14)
    ema21 = calculate_ema(prices, 21)

    ema14_now = ema14[curr_index]
    ema21_now = ema21[curr_index]
    ema14_prev = ema14[prev_index]
    ema21_prev = ema21[prev_index]

    crossed_up = ema14_prev < ema21_prev and ema14_now > ema21_now
    crossed_down = ema14_prev > ema21_prev and ema14_now < ema21_now

    return {"crossedUp": crossed_up, "crossedDown": crossed_down}

async def sample_calls():
    global count
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
        period = getTicksRequest("R_75", 1000 , getTimeFrame(5, "mins"))
        candles = await api.ticks_history(period)
        close_prices = [c["close"] for c in candles["candles"]]
        result = detect_ema_crossover(close_prices)

        if(len(open_positions) > 0):
            poc = await api.proposal_open_contract({
                "proposal_open_contract": 1, 
                "contract_id": open_positions[0]["contract_id"]
            })
            position = poc['proposal_open_contract']
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
            if result["crossedUp"]:
                proposal = await api.proposal(getProposal("MULTUP"))
                buy = await api.buy({"buy": proposal.get('proposal').get('id'), "price": 1})
                send_message(f"{proposal.get('echo_req').get('contract_type')} position entered")
                print(f"🟢 Entered {proposal.get('echo_req').get('contract_type')} position")
            
            if result["crossedDown"]:
                proposal = await api.proposal(getProposal("MULTDOWN"))
                buy = await api.buy({"buy": proposal.get('proposal').get('id'), "price": 1})
                send_message(f"{proposal.get('echo_req').get('contract_type')} position entered")
                print(f"🟢 Entered {proposal.get('echo_req').get('contract_type')} position")
        
        await api.clear()
        count = count + 1
        print(count)
    except ResponseError as err:
        print("error!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(err)


while True:
    asyncio.run(sample_calls())
    time.sleep(5)