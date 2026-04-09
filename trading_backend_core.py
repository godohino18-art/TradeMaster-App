from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import uvicorn
import threading
import time
from sklearn.ensemble import RandomForestRegressor
import warnings
warnings.filterwarnings('ignore')

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
app = FastAPI(title="TradeMaster.AI v11.0")
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

REAL_RANKING_DATA = []

# ==========================================
# 3. テクニカル指標
# ==========================================
def add_technical_indicators(df):
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    
    delta = df['Close'].diff()
    up, down = delta.clip(lower=0), -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=14, adjust=False).mean()
    ema_down = down.ewm(com=14, adjust=False).mean()
    rs = ema_up / ema_down
    df['RSI'] = 100 - (100 / (1 + rs))
    df['RSI'] = df['RSI'].fillna(50)
    
    return df.dropna()

def predict_with_rf(df):
    try:
        if len(df) < 20:
            return float(df['Close'].iloc[-1])
        
        features = ['Close', 'SMA5', 'SMA20', 'RSI']
        df_clean = df[features].dropna()
        
        if len(df_clean) < 10:
            return float(df['Close'].iloc[-1])
        
        X = df_clean[:-3].values
        y = df['Close'].iloc[-len(X):].values if len(X) > 0 else []
        
        if len(X) == 0 or len(y) == 0 or len(X) != len(y):
            return float(df['Close'].iloc[-1])
        
        model = RandomForestRegressor(n_estimators=20, random_state=42, n_jobs=1, max_depth=5)
        model.fit(X, y)
        
        last_features = df_clean[features].iloc[-1].values.reshape(1, -1)
        return float(model.predict(last_features)[0])
    except:
        return float(df['Close'].iloc[-1])

# ==========================================
# 4. 勝つための銘柄抽出
# ==========================================
def update_ranking_cache():
    """勝てる株を自動抽出"""
    global REAL_RANKING_DATA
    valid_stocks = []
    
    print("\n" + "="*80)
    print("🚀 勝てる株の抽出を開始します...")
    print("="*80 + "\n")
    
    for i, (ticker, name) in enumerate(TARGET_TICKERS.items(), 1):
        try:
            print(f"[{i:2d}/{len(TARGET_TICKERS)}] {ticker:8} | {name:15}", end=" | ", flush=True)
            
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo", interval="1d")
            
            if df is None or df.empty or len(df) < 30:
                print("✗ データ不足")
                continue
            
            df = add_technical_indicators(df)
            if len(df) < 20:
                print("✗ インジケーター失敗")
                continue
            
            current_price = float(df['Close'].iloc[-1])
            current_rsi = float(df['RSI'].iloc[-1])
            sma5 = float(df['SMA5'].iloc[-1])
            sma20 = float(df['SMA20'].iloc[-1])
            sma50 = float(df['SMA50'].iloc[-1])
            sma200 = float(df['SMA200'].iloc[-1])
            
            price_5d_ago = float(df['Close'].iloc[-5]) if len(df) >= 5 else current_price
            momentum_5d = ((current_price - price_5d_ago) / price_5d_ago * 100) if price_5d_ago > 0 else 0
            
            bb_std = df['Close'].rolling(window=20).std().iloc[-1]
            bb_middle = sma20
            bb_lower = bb_middle - (bb_std * 2) if bb_std > 0 else bb_middle * 0.95
            
            recent_vol = float(df['Volume'].iloc[-1])
            avg_vol = float(df['Volume'].tail(20).mean())
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
            
            # ★スコア計算（シンプル化）
            score = 0
            
            # RSI
            if current_rsi < 30:
                score += 30
            elif 30 <= current_rsi <= 50:
                score += 25
            elif 50 < current_rsi <= 70:
                score += 15
            
            # トレンド
            if sma5 > sma20:
                score += 30
                if ((sma5 - sma20) / sma20 * 100) > 2:
                    score += 15
            elif sma20 > sma50:
                score += 15
            
            if sma20 > sma50 > sma200:
                score += 20
            
            # モメンタム
            if 0 < momentum_5d <= 5:
                score += 15
            elif momentum_5d > 5:
                score += 10
            
            # ボリューム
            if vol_ratio > 1.5:
                score += 20
            elif vol_ratio > 1.2:
                score += 12
            
            # ボリンジャーバンド
            if current_price < bb_middle:
                distance = ((current_price - bb_lower) / (bb_middle - bb_lower) * 100) if (bb_middle - bb_lower) != 0 else 50
                if distance < 30:
                    score += 25
                elif distance < 50:
                    score += 15
            
            if score >= 60:
                prediction = predict_with_rf(df)
                upside = ((prediction - current_price) / current_price * 100) if current_price > 0 else 0
                
                valid_stocks.append({
                    "ticker": ticker,
                    "name": name,
                    "currentPrice": round(current_price, 2),
                    "confidence": min(99, score),
                    "action": "CALL" if upside > 0.5 else "WAIT",
                    "rsi": round(current_rsi, 1),
                    "trend": "上昇" if sma5 > sma20 else "下降",
                    "momentum": round(momentum_5d, 2),
                    "predictedPrice": round(prediction, 2),
                    "upside": round(upside, 2)
                })
                print(f"✓ スコア {score}")
            else:
                print(f"✗ スコア {score}")
        
        except Exception as e:
            print(f"✗ エラー")
        
        time.sleep(0.3)
    
    print("\n" + "="*80)
    if valid_stocks:
        valid_stocks.sort(key=lambda x: x['confidence'], reverse=True)
        REAL_RANKING_DATA = valid_stocks[:10]
        print(f"✅ 成功: {len(REAL_RANKING_DATA)}社の買い候補を抽出しました！\n")
        for i, s in enumerate(REAL_RANKING_DATA, 1):
            print(f"   {i}. {s['ticker']:8} {s['name']:15} スコア{s['confidence']:3d}% 上値{s['upside']:+.2f}%")
    else:
        print("⚠️ 条件を満たす銘柄がありません")
    print("="*80 + "\n")

def analyze_single_ticker(ticker, name):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="5d", interval="5m")
        is_daily = False
        
        if df is None or df.empty or len(df) < 30:
            df = stock.history(period="3mo", interval="1d")
            is_daily = True
        
        if df is None or df.empty or len(df) < 30:
            raise Exception("データ取得失敗")
        
        df = add_technical_indicators(df)
        if len(df) < 5:
            raise Exception("インジケーター失敗")
        
        current_price = float(df['Close'].iloc[-1])
        prediction = predict_with_rf(df)
        current_rsi = float(df['RSI'].iloc[-1])
        
        diff_percent = (prediction - current_price) / current_price if current_price > 0 else 0
        action = "CALL" if diff_percent > 0.003 else "WAIT"

        recent_df = df.tail(40)
        chart_data = []
        for idx, row in recent_df.iterrows():
            time_str = idx.strftime("%m/%d") if is_daily else idx.strftime("%H:%M")
            chart_data.append({
                "time": time_str,
                "price": round(float(row['Close']), 1),
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
            "currentPrice": round(current_price, 1),
            "predictedPrice": round(prediction, 1),
            "action": action,
            "confidence": current_confidence,
            "indicators": {"rsi": round(current_rsi, 1)},
            "chartData": chart_data
        }
    except Exception as e:
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

# ==========================================
# 5. バックグラウンドタスク
# ==========================================
def background_update_loop():
    """定期更新ループ"""
    counter = 0
    while True:
        time.sleep(300)  # 5分ごと
        counter += 1
        print(f"\n🔄 定期更新 #{counter}")
        try:
            update_ranking_cache()
        except Exception as e:
            print(f"更新エラー: {e}")

@app.on_event("startup")
def startup_event():
    print("\n✨ サーバー起動中...\n")
    # 起動時に同期的に実行
    update_ranking_cache()
    # バックグラウンドタスクを開始
    threading.Thread(target=background_update_loop, daemon=True).start()

# ==========================================
# 6. API エンドポイント
# ==========================================

@app.get("/")
def root():
    return {"status": "Running", "stocks": len(REAL_RANKING_DATA)}

@app.get("/api/analyze/{ticker}")
def get_analysis(ticker: str):
    name = TARGET_TICKERS.get(ticker, ticker)
    result = analyze_single_ticker(ticker, name)
    result["timestamp"] = datetime.datetime.now().isoformat()
    return result

@app.get("/api/recommend")
def get_recommendations():
    return {"recommendations": REAL_RANKING_DATA[:10], "timestamp": datetime.datetime.now().isoformat()}

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
    
    stock_df = yf.Ticker(req.ticker).history(period="5d", interval="1d")
    if stock_df is None or stock_df.empty:
        raise HTTPException(status_code=400, detail="株価取得失敗")
    
    current_price = float(stock_df['Close'].iloc[-1])
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
    
    stock_df = yf.Ticker(item["ticker"]).history(period="5d", interval="1d")
    current_price = float(stock_df['Close'].iloc[-1]) if stock_df is not None and not stock_df.empty else item["avgPrice"]
    
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