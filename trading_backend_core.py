from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import datetime
import uvicorn

# ==========================================
# シンプルなインメモリDB
# ==========================================
USERS_DATA = {}

def get_user_data(user_id: str):
    if user_id not in USERS_DATA:
        USERS_DATA[user_id] = {"balance": 3000000.0, "portfolio": [], "history": []}
    return USERS_DATA[user_id]

# ==========================================
# FastAPI アプリ
# ==========================================
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ★勝つための10社ランキング（ハードコード）
RANKING = [
    {"ticker": "NVDA", "name": "NVIDIA", "currentPrice": 890.50, "confidence": 78, "action": "CALL", "rsi": 45, "trend": "上昇", "momentum": 2.5, "predictedPrice": 915.00, "upside": 3.2},
    {"ticker": "TSLA", "name": "Tesla", "currentPrice": 245.30, "confidence": 72, "action": "CALL", "rsi": 48, "trend": "上昇", "momentum": 1.8, "predictedPrice": 252.00, "upside": 2.8},
    {"ticker": "AMD", "name": "AMD", "currentPrice": 165.20, "confidence": 70, "action": "CALL", "rsi": 42, "trend": "上昇", "momentum": 3.1, "predictedPrice": 171.00, "upside": 3.5},
    {"ticker": "MSFT", "name": "Microsoft", "currentPrice": 420.80, "confidence": 68, "action": "CALL", "rsi": 50, "trend": "上昇", "momentum": 1.2, "predictedPrice": 429.00, "upside": 2.1},
    {"ticker": "AAPL", "name": "Apple", "currentPrice": 189.95, "confidence": 65, "action": "CALL", "rsi": 52, "trend": "上昇", "momentum": 0.8, "predictedPrice": 193.50, "upside": 1.9},
    {"ticker": "META", "name": "Meta", "currentPrice": 520.50, "confidence": 62, "action": "CALL", "rsi": 46, "trend": "上昇", "momentum": 2.2, "predictedPrice": 535.00, "upside": 2.6},
    {"ticker": "NFLX", "name": "Netflix", "currentPrice": 580.25, "confidence": 60, "action": "CALL", "rsi": 44, "trend": "上昇", "momentum": 2.8, "predictedPrice": 597.50, "upside": 3.0},
    {"ticker": "7203.T", "name": "トヨタ自動車", "currentPrice": 2850.00, "confidence": 58, "action": "CALL", "rsi": 48, "trend": "上昇", "momentum": 1.5, "predictedPrice": 2912.00, "upside": 2.2},
    {"ticker": "8306.T", "name": "三菱UFJ", "currentPrice": 920.50, "confidence": 56, "action": "CALL", "rsi": 50, "trend": "上昇", "momentum": 1.1, "predictedPrice": 936.00, "upside": 1.8},
    {"ticker": "9984.T", "name": "ソフトバンクG", "currentPrice": 4580.00, "confidence": 54, "action": "CALL", "rsi": 49, "trend": "上昇", "momentum": 0.9, "predictedPrice": 4656.00, "upside": 1.6},
]

TICKERS = {
    "NVDA": "NVIDIA", "TSLA": "Tesla", "AAPL": "Apple", "MSFT": "Microsoft", "AMZN": "Amazon",
    "META": "Meta", "GOOGL": "Google", "NFLX": "Netflix", "AMD": "AMD", "INTC": "Intel",
    "8306.T": "三菱UFJ", "8316.T": "三井住友", "8411.T": "みずほ", "7203.T": "トヨタ自動車",
    "7267.T": "ホンダ", "7269.T": "スズキ", "8035.T": "東京エレクトロン", "6920.T": "レーザーテック",
    "6857.T": "アドバンテスト", "6146.T": "ディスコ", "9984.T": "ソフトバンクG", "9432.T": "NTT",
    "9433.T": "KDDI", "9983.T": "ファーストリテイリング", "8058.T": "三菱商事", "8031.T": "三井物産",
    "8001.T": "伊藤忠", "6758.T": "ソニーG", "6861.T": "キーエンス", "7974.T": "任天堂",
    "9766.T": "コナミG", "9101.T": "日本郵船", "9104.T": "商船三井", "9107.T": "川崎汽船",
    "5401.T": "日本製鉄", "7011.T": "三菱重工", "4385.T": "メルカリ", "6098.T": "リクルート"
}

# ==========================================
# API エンドポイント
# ==========================================

@app.get("/")
def root():
    return {"status": "TradeMaster.AI Running", "version": "14.0"}

@app.get("/api/recommend")
def get_recommendations():
    return {
        "recommendations": RANKING,
        "timestamp": datetime.datetime.now().isoformat()
    }

@app.get("/api/analyze/{ticker}")
def get_analysis(ticker: str):
    name = TICKERS.get(ticker, ticker)
    
    # ランキングから該当銘柄を探す
    stock_info = None
    for s in RANKING:
        if s["ticker"] == ticker:
            stock_info = s
            break
    
    if not stock_info:
        stock_info = {
            "ticker": ticker,
            "name": name,
            "currentPrice": 0,
            "confidence": 0,
            "action": "WAIT"
        }
    
    # チャートデータを生成
    chart_data = []
    for i in range(40):
        days_ago = 40 - i
        price = stock_info.get("currentPrice", 100) * (0.97 + (i / 40) * 0.06)
        chart_data.append({
            "time": (datetime.datetime.now() - datetime.timedelta(days=days_ago)).strftime("%m/%d"),
            "price": round(price, 1),
            "predictedPrice": None
        })
    
    return {
        "ticker": ticker,
        "name": name,
        "currentPrice": stock_info.get("currentPrice", 0),
        "predictedPrice": stock_info.get("predictedPrice", 0),
        "action": stock_info.get("action", "WAIT"),
        "confidence": stock_info.get("confidence", 0),
        "indicators": {"rsi": stock_info.get("rsi", 50)},
        "chartData": chart_data,
        "timestamp": datetime.datetime.now().isoformat()
    }

class WalletRequest(BaseModel):
    user_id: str
    amount: float

@app.post("/api/wallet/deposit")
def deposit_cash(req: WalletRequest):
    user = get_user_data(req.user_id)
    user["balance"] += req.amount
    return {"status": "success", "balance": user["balance"]}

@app.post("/api/wallet/withdraw")
def withdraw_cash(req: WalletRequest):
    user = get_user_data(req.user_id)
    if user["balance"] < req.amount:
        raise HTTPException(status_code=400, detail="残高不足")
    user["balance"] -= req.amount
    return {"status": "success", "balance": user["balance"]}

class BuyRequest(BaseModel):
    ticker: str
    shares: float
    user_id: str

@app.post("/api/portfolio/buy")
def buy_stock(req: BuyRequest):
    user = get_user_data(req.user_id)
    name = TICKERS.get(req.ticker, req.ticker)
    
    # ランキングから価格を取得
    price = 100.0
    for s in RANKING:
        if s["ticker"] == req.ticker:
            price = s["currentPrice"]
            break
    
    total = price * req.shares
    if user["balance"] < total:
        raise HTTPException(status_code=400, detail="残高不足")
    
    user["balance"] -= total
    user["portfolio"].append({
        "id": len(user["portfolio"]) + 1,
        "ticker": req.ticker,
        "name": name,
        "shares": req.shares,
        "avgPrice": price
    })
    user["history"].append({
        "action": "BUY",
        "ticker": req.ticker,
        "name": name,
        "profit": 0,
        "date": datetime.datetime.now().strftime("%m/%d %H:%M")
    })
    return {"status": "success"}

@app.get("/api/portfolio")
def get_portfolio(user_id: str):
    user = get_user_data(user_id)
    return {
        "cash": user["balance"],
        "portfolio": user["portfolio"],
        "history": user["history"][-10:]
    }

@app.post("/api/portfolio/sell/{item_id}")
def sell_stock(item_id: int, user_id: str):
    user = get_user_data(user_id)
    item = None
    for p in user["portfolio"]:
        if p["id"] == item_id:
            item = p
            break
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # ランキングから現在価格を取得
    current_price = item["avgPrice"]
    for s in RANKING:
        if s["ticker"] == item["ticker"]:
            current_price = s["currentPrice"]
            break
    
    profit = (current_price - item["avgPrice"]) * item["shares"]
    revenue = current_price * item["shares"]
    
    user["balance"] += revenue
    user["portfolio"].remove(item)
    user["history"].append({
        "action": "SELL",
        "ticker": item["ticker"],
        "name": item["name"],
        "profit": profit,
        "date": datetime.datetime.now().strftime("%m/%d %H:%M")
    })
    
    return {"status": "success", "profit": profit}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)