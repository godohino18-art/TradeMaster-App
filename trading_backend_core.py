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
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1489169956129214496/axw4OI8cP43aHkrUootqZ828vqa2w9krDOBQyZybg9tdQHxxmzbuoUQG5kZQ4-aA3iNk"

# ==========================================
# 1. データベース設定 (Supabase クラウドDB)
# ==========================================
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:W%26f4z5Di8h9q@db.ezasvrijqcpgroyaayxf.supabase.co:5432/postgres"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserWallet(Base):
    __tablename__ = "user_wallet_v1"
    user_id = Column(String, primary_key=True, index=True)
    balance = Column(Float, default=3000000.0) 

# ★ 100円などの少額投資（小数点株数）に対応するため、テーブルを「v3」に進化
class PortfolioItem(Base):
    __tablename__ = "portfolio_v3"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    ticker = Column(String, index=True)
    name = Column(String)
    shares = Column(Float) # ★ Integer(整数)からFloat(小数)に変更！
    avg_price = Column(Float)
    purchased_at = Column(DateTime, default=datetime.datetime.utcnow)

class TradeHistory(Base):
    __tablename__ = "trade_history_v3"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
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

def get_user_wallet(db: Session, user_id: str):
    wallet = db.query(UserWallet).filter(UserWallet.user_id == user_id).first()
    if not wallet:
        wallet = UserWallet(user_id=user_id, balance=3000000.0)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    return wallet

# ==========================================
# 2. FastAPI 初期化
# ==========================================
app = FastAPI(title="TradeMaster.AI API v3.4 (Pro AI & Micro Investment)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ★ 監視銘柄を大幅に拡大！（ボラティリティが高いもの中心）
TARGET_TICKERS = {
    "8306.T": "三菱UFJ", "8316.T": "三井住友", "8411.T": "みずほ",
    "7203.T": "トヨタ自動車", "7267.T": "ホンダ", "7269.T": "スズキ",
    "8035.T": "東京エレクトロン", "6920.T": "レーザーテック", "6857.T": "アドバンテスト", "6146.T": "ディスコ",
    "9984.T": "ソフトバンクG", "9432.T": "NTT", "9433.T": "KDDI",
    "9983.T": "ファーストリテイリング", "8058.T": "三菱商事", "8031.T": "三井物産", "8001.T": "伊藤忠",
    "6758.T": "ソニーG", "6861.T": "キーエンス", "7974.T": "任天堂", "9766.T": "コナミG",
    "9101.T": "日本郵船", "9104.T": "商船三井", "9107.T": "川崎汽船",
    "5401.T": "日本製鉄", "7011.T": "三菱重工", "4385.T": "メルカリ", "6098.T": "リクルート"
}

def send_discord_notification(message):
    if not DISCORD_WEBHOOK_URL: return
    try: requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e: print(f"通知エラー: {e}")

# ==========================================
# 3. AIエンジン & 本物チャート抽出
# ==========================================
ANALYSIS_CACHE = {}
CACHE_DURATION = 60 * 3 

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
    current_time = time.time()
    if ticker in ANALYSIS_CACHE:
        cached_data, cached_time = ANALYSIS_CACHE[ticker]
        if current_time - cached_time < CACHE_DURATION:
            return cached_data
            
    try:
        # ★ エラー回避のため 5d に戻して十分なデータを確保
        df = fetch_stock_data(ticker, period="5d", interval="5m")
        if df is None or len(df) < 30: return None
        df = add_technical_indicators(df)
        if len(df) < 5: return None
        
        current_price = float(df['Close'].iloc[-1])
        prediction = predict_with_rf(df)
        
        # ★ プロの視点：RSIと出来高をより重視する
        current_rsi = float(df['RSI'].iloc[-1])
        recent_vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].tail(20).mean())
        
        # 1. 押し目買いスコア（RSIが40以下なら強いプラス評価）
        dip_score = 0
        if current_rsi < 40:
            dip_score = (40 - current_rsi) * 2.0
            
        # 2. 出来高ブースト（投資家の勢い）
        momentum = 1.0
        if avg_vol > 0 and recent_vol > avg_vol:
            momentum = min(2.0, recent_vol / avg_vol)
            
        # 3. AI予測上昇率
        diff_percent = (prediction - current_price) / current_price
        ai_growth = diff_percent * 5000 
        
        # 下落タイミング＆出来高でスコアが跳ねる計算式
        raw_score = (ai_growth + dip_score + 10) * momentum 
        confidence = max(5, min(99, int(raw_score)))
        
        action = "CALL" if confidence >= 60 else "WAIT"

        recent_df = df.tail(40)
        chart_data = []
        for idx, row in recent_df.iterrows():
            time_str = idx.strftime("%H:%M") if hasattr(idx, 'strftime') else str(idx)
            chart_data.append({
                "time": time_str,
                "price": round(float(row['Close']), 1),
                "predictedPrice": None
            })

        result = {
            "ticker": ticker, "name": name, "currentPrice": round(current_price, 1),
            "predictedPrice": round(prediction, 1), "action": action, "confidence": confidence,
            "indicators": {"rsi": round(current_rsi, 1)},
            "chartData": chart_data
        }
        
        ANALYSIS_CACHE[ticker] = (result, current_time)
        return result
    except Exception as e: return None

def background_monitoring():
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
            
    # 全銘柄を期待度順にソートして返す
    all_recommendations = sorted(results, key=lambda x: x['confidence'], reverse=True)
    return {"recommendations": all_recommendations, "timestamp": datetime.datetime.now().isoformat()}

class WalletRequest(BaseModel):
    user_id: str
    amount: float

@app.post("/api/wallet/deposit")
def deposit_cash(req: WalletRequest, db: Session = Depends(get_db)):
    wallet = get_user_wallet(db, req.user_id)
    wallet.balance += req.amount
    db.commit()
    send_discord_notification(f"🏧 ユーザーが入金しました。額: ¥{int(req.amount):,} (残高: ¥{int(wallet.balance):,})")
    return {"status": "success", "balance": wallet.balance}

@app.post("/api/wallet/withdraw")
def withdraw_cash(req: WalletRequest, db: Session = Depends(get_db)):
    wallet = get_user_wallet(db, req.user_id)
    if wallet.balance < req.amount:
        raise HTTPException(status_code=400, detail="残高不足です。")
    wallet.balance -= req.amount
    db.commit()
    send_discord_notification(f"🏧 ユーザーが出金しました。額: ¥{int(req.amount):,} (残高: ¥{int(wallet.balance):,})")
    return {"status": "success", "balance": wallet.balance}

# ★ 100円などの小数点投資に対応するため float に変更
class BuyRequest(BaseModel):
    ticker: str
    shares: float 
    user_id: str

@app.post("/api/portfolio/buy")
def buy_stock(req: BuyRequest, db: Session = Depends(get_db)):
    name = TARGET_TICKERS.get(req.ticker, req.ticker)
    df = fetch_stock_data(req.ticker, period="5d", interval="5m")
    current_price = float(df['Close'].iloc[-1]) if df is not None else 0
    total_cost = current_price * req.shares

    wallet = get_user_wallet(db, req.user_id)
    if wallet.balance < total_cost:
        raise HTTPException(status_code=400, detail="残高不足です。")

    wallet.balance -= total_cost
    new_item = PortfolioItem(ticker=req.ticker, name=name, shares=req.shares, avg_price=current_price, user_id=req.user_id)
    db.add(new_item)
    history = TradeHistory(action="BUY", ticker=req.ticker, name=name, profit=0, user_id=req.user_id)
    db.add(history)
    db.commit()
    
    send_discord_notification(f"🛒 購入: {name} (約{req.shares:.4f}株) ¥{int(total_cost):,}")
    return {"status": "success"}

@app.get("/api/portfolio")
def get_portfolio(user_id: str, db: Session = Depends(get_db)):
    wallet = get_user_wallet(db, user_id)
    items = db.query(PortfolioItem).filter(PortfolioItem.user_id == user_id).all()
    history = db.query(TradeHistory).filter(TradeHistory.user_id == user_id).order_by(TradeHistory.created_at.desc()).limit(10).all()
    return {
        "cash": wallet.balance,
        "portfolio": [{"id": i.id, "ticker": i.ticker, "name": i.name, "shares": i.shares, "avgPrice": i.avg_price} for i in items],
        "history": [{"date": h.created_at.strftime("%m/%d %H:%M"), "action": h.action, "name": h.name, "profit": h.profit} for h in history]
    }

@app.post("/api/portfolio/sell/{item_id}")
def sell_stock(item_id: int, user_id: str, db: Session = Depends(get_db)):
    item = db.query(PortfolioItem).filter(PortfolioItem.id == item_id, PortfolioItem.user_id == user_id).first()
    if not item: raise HTTPException(status_code=404, detail="Item not found")
    
    df = fetch_stock_data(item.ticker, period="5d", interval="5m")
    current_price = float(df['Close'].iloc[-1]) if df is not None else item.avg_price
    profit = (current_price - item.avg_price) * item.shares
    total_revenue = current_price * item.shares

    wallet = get_user_wallet(db, user_id)
    wallet.balance += total_revenue
    
    history = TradeHistory(action="SELL", ticker=item.ticker, name=item.name, profit=profit, user_id=user_id)
    db.add(history)
    db.delete(item)
    db.commit()
    
    send_discord_notification(f"💰 利確: {item.name} (+¥{int(profit):,})")
    return {"status": "success", "profit": profit}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)