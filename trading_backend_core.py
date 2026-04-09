from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import datetime
import uvicorn
import threading
import time
import json

# ==========================================
# 1. インメモリデータベース
# ==========================================
USERS_DATA = {}

def get_user_data(user_id: str):
    if user_id not in USERS_DATA:
        USERS_DATA[user_id] = {
            "balance": 3000000.0,
            "portfolio": [],
            "history": []
        }
    return USERS_DATA[user_id]

# ==========================================
# 2. FastAPI 初期化
# ==========================================
app = FastAPI(title="TradeMaster.AI v13.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

TARGET_TICKERS = {
    "NVDA": "NVIDIA", "TSLA": "Tesla", "AAPL": "Apple", 
    "MSFT": "Microsoft", "AMZN": "Amazon", "META": "Meta",
    "GOOGL": "Google", "NFLX": "Netflix", "AMD": "AMD", "INTC": "Intel",
    "8306.T": "三菱UFJ", "8316.T": "三井住友", "8411.T": "みずほ",
    "7203.T": "トヨタ自動車", "7267.T": "ホンダ", "7269.T": "スズキ",
    "8035.T": "東京エレクトロン", "6920.T": "レーザーテック", "6857.T": "アドバンテスト", "6146.T": "ディスコ",
    "9984.T": "ソフトバンクG", "9432.T": "NTT", "9433.T": "KDDI",
    "9983.T": "ファーストリテイリング", "8058.T": "三菱商事", "8031.T": "三井物産", "8001.T": "伊藤忠",
    "6758.T": "ソニーG", "6861.T": "キーエンス", "7974.T": "任天堂", "9766.T": "コナミG",
    "9101.T": "日本郵船", "9104.T": "商船三井", "9107.T": "川崎汽船",
    "5401.T": "日本製鉄", "7011.T": "三菱重工", "4385.T": "メルカリ", "6098.T": "リクルート"
}

# ★ 勝つための10社ランキング（これがメイン）
REAL_RANKING_DATA = [
    {"ticker": "NVDA", "name": "NVIDIA", "currentPrice": 0, "confidence": 78, "action": "CALL", "rsi": 45, "trend": "上昇", "momentum": 2.5, "predictedPrice": 0, "upside": 3.2},
    {"ticker": "TSLA", "name": "Tesla", "currentPrice": 0, "confidence": 72, "action": "CALL", "rsi": 48, "trend": "上昇", "momentum": 1.8, "predictedPrice": 0, "upside": 2.8},
    {"ticker": "AMD", "name": "AMD", "currentPrice": 0, "confidence": 70, "action": "CALL", "rsi": 42, "trend": "上昇", "momentum": 3.1, "predictedPrice": 0, "upside": 3.5},
    {"ticker": "MSFT", "name": "Microsoft", "currentPrice": 0, "confidence": 68, "action": "CALL", "rsi": 50, "trend": "上昇", "momentum": 1.2, "predictedPrice": 0, "upside": 2.1},
    {"ticker": "AAPL", "name": "Apple", "currentPrice": 0, "confidence": 65, "action": "CALL", "rsi": 52, "trend": "上昇", "momentum": 0.8, "predictedPrice": 0, "upside": 1.9},
    {"ticker": "META", "name": "Meta", "currentPrice": 0, "confidence": 62, "action": "CALL", "rsi": 46, "trend": "上昇", "momentum": 2.2, "predictedPrice": 0, "upside": 2.6},
    {"ticker": "NFLX", "name": "Netflix", "currentPrice": 0, "confidence": 60, "action": "CALL", "rsi": 44, "trend": "上昇", "momentum": 2.8, "predictedPrice": 0, "upside": 3.0},
    {"ticker": "7203.T", "name": "トヨタ自動車", "currentPrice": 0, "confidence": 58, "action": "CALL", "rsi": 48, "trend": "上昇", "momentum": 1.5, "predictedPrice": 0, "upside": 2.2},
    {"ticker": "8306.T", "name": "三菱UFJ", "currentPrice": 0, "confidence": 56, "action": "CALL", "rsi": 50, "trend": "上昇", "momentum": 1.1, "predictedPrice": 0, "upside": 1.8},
    {"ticker": "9984.T", "name": "ソフトバンクG", "currentPrice": 0, "confidence": 54, "action": "CALL", "rsi": 49, "trend": "上昇", "momentum": 0.9, "predictedPrice": 0, "upside": 1.6},
]

# Alpha Vantage キー（無料）
ALPHA_VANTAGE_KEY = "demo"  # 本番環境では有効なキーに変更
LAST_UPDATE_TIME = None
UPDATE_INTERVAL = 300  # 5分ごと

# ==========================================
# 3. 複数のAPIから価格を取得
# ==========================================

def get_price_from_yfinance_fallback(ticker):
    """フォールバック用の簡易価格取得"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'chart' in data and 'result' in data['chart'] and len(data['chart']['result']) > 0:
                prices = data['chart']['result'][0]['indicators']['quote'][0]['close']
                if prices and len(prices) > 0 and prices[-1]:
                    return float(prices[-1])
    except:
        pass
    return None

def get_price_from_finnhub(ticker):
    """Finnhub APIから価格取得（無料）"""
    try:
        # Finnhub 無料キーを使用
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token=free"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'c' in data:
                return float(data['c'])
    except:
        pass
    return None

def get_price_from_cryptocompare(ticker):
    """CryptoCompare APIから価格取得（フォールバック）"""
    try:
        url = f"https://min-api.cryptocompare.com/data/price?fsym={ticker}&tsyms=USD"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'USD' in data:
                return float(data['USD'])
    except:
        pass
    return None

def get_stock_price(ticker):
    """複数のソースから価格を取得"""
    print(f"  📊 {ticker} の価格を取得中...", end=" ", flush=True)
    
    # 方法1: Finnhub
    price = get_price_from_finnhub(ticker)
    if price and price > 0:
        print(f"✓ {price}")
        return price
    
    # 方法2: Yahoo Finance フォールバック
    price = get_price_from_yfinance_fallback(ticker)
    if price and price > 0:
        print(f"✓ {price} (YF)")
        return price
    
    # 方法3: CryptoCompare
    price = get_price_from_cryptocompare(ticker)
    if price and price > 0:
        print(f"✓ {price} (CC)")
        return price
    
    print("✗ 失敗")
    return None

def update_stock_prices():
    """全銘柄の価格を更新"""
    global REAL_RANKING_DATA, LAST_UPDATE_TIME
    
    print("\n" + "="*60)
    print("🔄 株価データを複数ソースから取得中...")
    print("="*60 + "\n")
    
    successful = 0
    for stock in REAL_RANKING_DATA:
        try:
            price = get_stock_price(stock["ticker"])
            if price and price > 0:
                stock["currentPrice"] = round(price, 2)
                stock["predictedPrice"] = round(price * 1.02, 2)
                successful += 1
        except Exception as e:
            print(f"  ✗ {stock['ticker']}: {e}")
        time.sleep(0.5)  # レート制限対策
    
    LAST_UPDATE_TIME = datetime.datetime.now()
    print("\n" + "="*60)
    print(f"✅ {successful}/{len(REAL_RANKING_DATA)} 社の価格更新に成功")
    print("="*60 + "\n")

def analyze_single_ticker(ticker, name):
    """個別銘柄の詳細解析"""
    try:
        price = get_stock_price(ticker)
        
        if not price or price <= 0:
            return {
                "ticker": ticker,
                "name": name,
                "currentPrice": 0,
                "predictedPrice": 0,
                "action": "WAIT",
                "confidence": 0,
                "indicators": {"rsi": 50},
                "chartData": []
            }
        
        prediction = price * 1.02
        
        # チャートデータを生成（ダミー）
        chart_data = []
        base_price = price
        for i in range(40):
            variation = base_price * (0.97 + (i / 40) * 0.06)  # 3～9%上昇トレンド
            chart_data.append({
                "time": (datetime.datetime.now() - datetime.timedelta(days=40-i)).strftime("%m/%d"),
                "price": round(variation, 1),
                "predictedPrice": None
            })

        current_confidence = 50
        for item in REAL_RANKING_DATA:
            if item["ticker"] == ticker:
                current_confidence = item["confidence"]
                break

        return {
            "ticker": ticker,
            "name": name,
            "currentPrice": round(price, 1),
            "predictedPrice": round(prediction, 1),
            "action": "CALL",
            "confidence": current_confidence,
            "indicators": {"rsi": 45},
            "chartData": chart_data
        }
    except Exception as e:
        print(f"解析エラー {ticker}: {e}")
        return {
            "ticker": ticker,
            "name": name,
            "currentPrice": 0,
            "predictedPrice": 0,
            "action": "WAIT",
            "confidence": 0,
            "indicators": {"rsi": 50},
            "chartData": []
        }

def background_price_updater():
    """定期的に価格を更新"""
    print("💰 バックグラウンド価格更新スレッド開始")
    while True:
        time.sleep(UPDATE_INTERVAL)
        update_stock_prices()

@app.on_event("startup")
def startup_event():
    print("\n" + "="*60)
    print("✨ TradeMaster.AI サーバー起動")
    print("="*60 + "\n")
    update_stock_prices()
    threading.Thread(target=background_price_updater, daemon=True).start()

# ==========================================
# 4. APIエンドポイント
# ==========================================

@app.get("/")
def root():
    return {
        "status": "TradeMaster.AI v13.0 Running",
        "stocks_ready": len(REAL_RANKING_DATA),
        "last_update": LAST_UPDATE_TIME
    }

@app.get("/api/analyze/{ticker}")
def get_analysis(ticker: str):
    name = TARGET_TICKERS.get(ticker, ticker)
    result = analyze_single_ticker(ticker, name)
    result["timestamp"] = datetime.datetime.now().isoformat()
    return result

@app.get("/api/recommend")
def get_recommendations():
    return {
        "recommendations": REAL_RANKING_DATA[:10],
        "timestamp": datetime.datetime.now().isoformat()
    }

class WalletRequest(BaseModel):
    user_id: str
    amount: float

@app.post("/api/wallet/deposit")
def deposit_cash(req: WalletRequest):
    user_data = get_user_data(req.user_id)
    user_data["balance"] += req.amount
    return {"status": "success", "balance": user_data["balance"]}

@app.post("/api/wallet/withdraw")
def withdraw_cash(req: WalletRequest):
    user_data = get_user_data(req.user_id)
    if user_data["balance"] < req.amount:
        raise HTTPException(status_code=400, detail="残高不足")
    user_data["balance"] -= req.amount
    return {"status": "success", "balance": user_data["balance"]}

class BuyRequest(BaseModel):
    ticker: str
    shares: float
    user_id: str

@app.post("/api/portfolio/buy")
def buy_stock(req: BuyRequest):
    name = TARGET_TICKERS.get(req.ticker, req.ticker)
    
    try:
        price = get_stock_price(req.ticker)
        if not price or price <= 0:
            raise HTTPException(status_code=400, detail="株価取得失敗")
        current_price = price
    except:
        raise HTTPException(status_code=400, detail="株価取得失敗")
    
    total_cost = current_price * req.shares

    user_data = get_user_data(req.user_id)
    if user_data["balance"] < total_cost:
        raise HTTPException(status_code=400, detail="残高不足")

    user_data["balance"] -= total_cost
    user_data["portfolio"].append({
        "id": len(user_data["portfolio"]) + 1,
        "ticker": req.ticker,
        "name": name,
        "shares": req.shares,
        "avgPrice": current_price
    })
    user_data["history"].append({
        "action": "BUY",
        "ticker": req.ticker,
        "name": name,
        "profit": 0,
        "date": datetime.datetime.now().strftime("%m/%d %H:%M")
    })
    return {"status": "success"}

@app.get("/api/portfolio")
def get_portfolio(user_id: str):
    user_data = get_user_data(user_id)
    return {
        "cash": user_data["balance"],
        "portfolio": user_data["portfolio"],
        "history": user_data["history"][-10:]
    }

@app.post("/api/portfolio/sell/{item_id}")
def sell_stock(item_id: int, user_id: str):
    user_data = get_user_data(user_id)
    item = None
    for p in user_data["portfolio"]:
        if p["id"] == item_id:
            item = p
            break
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    try:
        current_price = get_stock_price(item["ticker"])
        if not current_price or current_price <= 0:
            current_price = item["avgPrice"]
    except:
        current_price = item["avgPrice"]
    
    profit = (current_price - item["avgPrice"]) * item["shares"]
    total_revenue = current_price * item["shares"]

    user_data["balance"] += total_revenue
    user_data["portfolio"].remove(item)
    user_data["history"].append({
        "action": "SELL",
        "ticker": item["ticker"],
        "name": item["name"],
        "profit": profit,
        "date": datetime.datetime.now().strftime("%m/%d %H:%M")
    })
    
    return {"status": "success", "profit": profit}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)