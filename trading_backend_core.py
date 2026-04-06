from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import uvicorn
import concurrent.futures
import threading
import time
import requests
from sklearn.ensemble import RandomForestRegressor
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ==========================================
# 設定：Discord Webhook URL
# ==========================================
DISCORD_WEBHOOK_URL = "[https://discord.com/api/webhooks/1489169956129214496/axw4OI8cP43aHkrUootqZ828vqa2w9krDOBQyZybg9tdQHxxmzbuoUQG5kZQ4-aA3iNk](https://discord.com/api/webhooks/1489169956129214496/axw4OI8cP43aHkrUootqZ828vqa2w9krDOBQyZybg9tdQHxxmzbuoUQG5kZQ4-aA3iNk)"

# ==========================================
# 1. データベース設定 (Supabase クラウドDB)
# ==========================================
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:W%26f4z5Di8h9q@db.ezasvrijqcpgroyaayxf.supabase.co:5432/postgres"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# マルチユーザー化に伴い、テーブル名を_v2にして新しく作成します（カラム追加エラー回避のため）
class PortfolioItem(Base):
    __tablename__ = "portfolio_v2"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True) # ★追加：誰の株か
    ticker = Column(String, index=True)
    name = Column(String)
    shares = Column(Integer)
    avg_price = Column(Float)
    purchased_at = Column(DateTime, default=datetime.datetime.utcnow)

class TradeHistory(Base):
    __tablename__ = "trade_history_v2"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True) # ★追加：誰の取引か
    action = Column(String) 
    ticker = Column(String)
    name = Column(String)
    profit = Column(Float) 
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# ==========================================
# 2. FastAPI 初期化
# ==========================================
app = FastAPI(title="TradeMaster.AI API v2.0 (Multi-User)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

TARGET_TICKERS = {
    "7203.T": "トヨタ自動車", "9984.T": "ソフトバンクG", "8306.T": "三菱UFJ", 
    "6920.T": "レーザーテック", "9432.T": "NTT", "8035.T": "東京エレクトロン",
    "9983.T": "ファーストリテイリング", "6758.T": "ソニーG", "6861.T": "キーエンス", "8058.T": "三菱商事"
}

def send_discord_notification(message):
    if not DISCORD_WEBHOOK_URL: return
    try: requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e: print(f"通知エラー: {e}")

# ==========================================
# 3. AIエンジン
# ==========================================
def fetch_stock_data(ticker, period="5d", interval="5m"): 
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval)
    if df.empty: return None
    return df[['Close', 'Volume']]

def add_technical_indicators(df):
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    delta = df['Close'].diff()
    up, down = delta.clip(lower=0), -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + ema_up / ema_down))
    return df.dropna()

def predict_with_rf(df, future_steps=3):
    if len(df) < 20: return float(df['Close'].iloc[-1])
    features = ['Close', 'SMA5', 'SMA20', 'RSI']
    X = df[features].values[:-future_steps] 
    y = df['Close'].values[future_steps:]
    if len(X) == 0: return float(df['Close'].iloc[-1])
    model = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
    model.fit(X, y)
    return float(model.predict(df[features].values[-1].reshape(1, -1))[0])

def analyze_single_ticker(ticker, name):
    try:
        df = fetch_stock_data(ticker)
        if df is None: return None
        df = add_technical_indicators(df)
        current_price = float(df['Close'].iloc[-1])
        prediction = predict_with_rf(df)
        confidence = 0
        action = "WAIT"
        diff_percent = (prediction - current_price) / current_price
        if diff_percent > 0.003: 
            action = "CALL"
            confidence = min(99, int(diff_percent * 8000))
        return {
            "ticker": ticker, "name": name, "currentPrice": round(current_price, 1),
            "predictedPrice": round(prediction, 1), "action": action, "confidence": confidence,
            "indicators": {"rsi": round(float(df['RSI'].iloc[-1]), 1)}
        }
    except Exception as e: return None

# ==========================================
# 4. バックグラウンド監視
# ==========================================
def background_monitoring():
    print("バックグラウンド監視スレッド開始...")
    while True:
        time.sleep(60) 
        try:
            db = SessionLocal()
            portfolio_items = db.query(PortfolioItem).all()
            for item in portfolio_items:
                df = fetch_stock_data(item.ticker, period="1d", interval="5m")
                if df is not None and not df.empty:
                    current_price = float(df['Close'].iloc[-1])
                    profit = (current_price - item.avg_price) * item.shares
                    if profit >= 5000: 
                        msg = f"💸 **【利確チャンス】**\n『{item.name}』を今すぐ売却すれば、**＋{int(profit):,}円** の利益が確定します！"
                        send_discord_notification(msg)
                        time.sleep(5) 
            db.close()
        except Exception as e: pass

@app.on_event("startup")
def startup_event():
    threading.Thread(target=background_monitoring, daemon=True).start()

# ==========================================
# 5. API エンドポイント
# ==========================================
@app.get("/api/analyze/{ticker}")
def get_analysis(ticker: str):
    name = TARGET_TICKERS.get(ticker, ticker)
    result = analyze_single_ticker(ticker, name)
    if not result: raise HTTPException(status_code=404, detail="Data not found")
    result["timestamp"] = datetime.datetime.now().isoformat()
    return result

@app.get("/api/recommend")
def get_recommendations():
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(analyze_single_ticker, t, n) for t, n in TARGET_TICKERS.items()]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    call_recommendations = sorted([r for r in results if r['action'] == 'CALL'], key=lambda x: x['confidence'], reverse=True)
    if call_recommendations and call_recommendations[0]['confidence'] > 80:
        best = call_recommendations[0]
        send_discord_notification(f"🚀 **【買いシグナル発生】**\n『{best['name']}』に強い上昇トレンドが発生しています。(期待度: {best['confidence']}%)")
    return {"recommendations": call_recommendations, "timestamp": datetime.datetime.now().isoformat()}

# ★ 買いリクエストに user_id を追加
class BuyRequest(BaseModel):
    ticker: str
    shares: int
    user_id: str

@app.post("/api/portfolio/buy")
def buy_stock(req: BuyRequest, db: Session = Depends(get_db)):
    name = TARGET_TICKERS.get(req.ticker, req.ticker)
    df = fetch_stock_data(req.ticker, period="1d")
    current_price = float(df['Close'].iloc[-1]) if df is not None else 0

    # ★ 誰が買ったかを保存
    new_item = PortfolioItem(ticker=req.ticker, name=name, shares=req.shares, avg_price=current_price, user_id=req.user_id)
    db.add(new_item)
    history = TradeHistory(action="BUY", ticker=req.ticker, name=name, profit=0, user_id=req.user_id)
    db.add(history)
    db.commit()
    
    send_discord_notification(f"🛒 ユーザーが『{name}』を {req.shares}株 購入しました。(買値: {current_price}円)")
    return {"status": "success"}

# ★ GETの時に user_id を受け取り、その人だけのデータを返す
@app.get("/api/portfolio")
def get_portfolio(user_id: str, db: Session = Depends(get_db)):
    items = db.query(PortfolioItem).filter(PortfolioItem.user_id == user_id).all()
    history = db.query(TradeHistory).filter(TradeHistory.user_id == user_id).order_by(TradeHistory.created_at.desc()).limit(10).all()
    return {
        "portfolio": [{"id": i.id, "ticker": i.ticker, "name": i.name, "shares": i.shares, "avgPrice": i.avg_price} for i in items],
        "history": [{"date": h.created_at.strftime("%m/%d %H:%M"), "action": h.action, "name": h.name, "profit": h.profit} for h in history]
    }

# ★ 売却時に user_id を受け取り、本人の株か確認して売却
@app.post("/api/portfolio/sell/{item_id}")
def sell_stock(item_id: int, user_id: str, db: Session = Depends(get_db)):
    item = db.query(PortfolioItem).filter(PortfolioItem.id == item_id, PortfolioItem.user_id == user_id).first()
    if not item: raise HTTPException(status_code=404, detail="Item not found")
    
    df = fetch_stock_data(item.ticker, period="1d", interval="5m")
    current_price = float(df['Close'].iloc[-1]) if df is not None else item.avg_price
    profit = (current_price - item.avg_price) * item.shares
    
    history = TradeHistory(action="SELL", ticker=item.ticker, name=item.name, profit=profit, user_id=user_id)
    db.add(history)
    db.delete(item)
    db.commit()
    
    send_discord_notification(f"💰 **【利益確定】** ユーザーが『{item.name}』を売却し、**＋{int(profit):,}円** の利益を獲得しました！")
    return {"status": "success", "profit": profit}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)