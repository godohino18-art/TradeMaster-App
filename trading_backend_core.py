from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np
import datetime
import uvicorn
import threading
import time
import urllib.parse
import requests
import io
from sklearn.ensemble import RandomForestRegressor
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ==========================================
# 1. データベース設定 (前回の成功URLを維持)
# ==========================================
RAW_SUPABASE_URL = "postgresql://postgres.ezasvrijqcpgroyaayxf:[YOUR-PASSWORD]@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres"

DB_PASSWORD = urllib.parse.quote_plus("W&f4z5Di8h9q")
if "[YOUR-PASSWORD]" in RAW_SUPABASE_URL:
    SQLALCHEMY_DATABASE_URL = RAW_SUPABASE_URL.replace("[YOUR-PASSWORD]", DB_PASSWORD)
else:
    SQLALCHEMY_DATABASE_URL = RAW_SUPABASE_URL

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserWallet(Base):
    __tablename__ = "user_wallet_v1"
    user_id = Column(String, primary_key=True, index=True)
    balance = Column(Float, default=3000000.0) 

class PortfolioItem(Base):
    __tablename__ = "portfolio_v3"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    ticker = Column(String, index=True)
    name = Column(String)
    shares = Column(Float) 
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
# 2. FastAPI 初期化 & ターゲット銘柄
# ==========================================
app = FastAPI(title="TradeMaster.AI API v8.1 (Stooq Direct Fetch)")
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

# ==========================================
# 3. 確実なデータ取得システム (Stooq直結ベース)
# ==========================================
REAL_RANKING_DATA = []

def fetch_stooq_data(ticker):
    """ライブラリエラーを回避し、Stooqから直接CSVを抜き出す最も堅牢な取得関数"""
    stooq_ticker = ticker.replace('.T', '.JP') if '.T' in ticker else ticker + '.US'
    url = f"https://stooq.com/q/d/l/?s={stooq_ticker}&i=d"
    try:
        # ブラウザからのアクセスに見せかけてブロックを防ぐ
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            # CSVデータをPandasの表形式に直接変換
            df = pd.read_csv(io.StringIO(res.text), index_col='Date', parse_dates=True)
            if not df.empty and 'Close' in df.columns:
                df = df.sort_index() # 古い順に並び替え
                return df
    except Exception as e:
        print(f"Stooq Direct Fetch Error for {ticker}: {e}")
    return None

def add_technical_indicators(df):
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    delta = df['Close'].diff()
    up, down = delta.clip(lower=0), -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=14, adjust=False).mean()
    ema_down = down.ewm(com=14, adjust=False).mean()
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

def update_ranking_cache():
    global REAL_RANKING_DATA
    valid_stocks = []
    
    print("本物データ(Stooq直結)のランキング更新を開始します...")
    
    for ticker, name in TARGET_TICKERS.items():
        df = fetch_stooq_data(ticker)
        if df is not None and not df.empty and len(df) >= 25:
            df = add_technical_indicators(df)
            if len(df) >= 5:
                current_price = float(df['Close'].iloc[-1])
                current_rsi = float(df['RSI'].iloc[-1])
                sma20 = float(df['SMA20'].iloc[-1])
                deviation = ((current_price - sma20) / sma20) * 100
                
                # 勝つための厳格な底値判定スコア
                rsi_score = max(0, (40 - current_rsi) * 2.5)
                dev_score = max(0, -deviation) * 3.0
                raw_score = rsi_score + dev_score + 15
                confidence = max(5, min(99, int(raw_score)))
                
                # 期待度60%以上の勝負銘柄のみリストアップ
                if confidence >= 60:
                    valid_stocks.append({
                        "ticker": ticker,
                        "name": name,
                        "currentPrice": round(current_price, 1),
                        "action": "CALL",
                        "confidence": confidence
                    })
        time.sleep(0.5) # サーバー負荷を掛けないための休止
                
    if valid_stocks:
        valid_stocks.sort(key=lambda x: x['confidence'], reverse=True)
        REAL_RANKING_DATA = valid_stocks
        print(f"ランキング更新完了: 期待度60%以上の {len(valid_stocks)} 社を抽出しました！")

def analyze_single_ticker(ticker, name):
    try:
        df = fetch_stooq_data(ticker)
        
        if df is None or df.empty or len(df) < 30: 
            raise Exception("データ取得失敗")
            
        df = add_technical_indicators(df)
        if len(df) < 5: 
            raise Exception("インジケーター計算失敗")
        
        current_price = float(df['Close'].iloc[-1])
        prediction = predict_with_rf(df) 
        current_rsi = float(df['RSI'].iloc[-1])
        
        diff_percent = (prediction - current_price) / current_price
        action = "CALL" if diff_percent > 0.003 else "WAIT"

        # チャート用に直近40日分を抽出
        recent_df = df.tail(40)
        chart_data = []
        for idx, row in recent_df.iterrows():
            time_str = idx.strftime("%m/%d") 
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
            "ticker": ticker, "name": name, "currentPrice": round(current_price, 1),
            "predictedPrice": round(prediction, 1), "action": action, 
            "confidence": current_confidence, 
            "indicators": {"rsi": round(current_rsi, 1)},
            "chartData": chart_data
        }
    except Exception as e:
        return {
            "ticker": ticker, "name": name, "currentPrice": 0,
            "predictedPrice": 0, "action": "WAIT", "confidence": 0,
            "indicators": {"rsi": 50}, "chartData": []
        }

def background_monitoring():
    update_ranking_cache() 
    counter = 0
    while True:
        time.sleep(60) 
        counter += 1
        if counter % 15 == 0: 
            update_ranking_cache()

@app.on_event("startup")
def startup_event():
    threading.Thread(target=background_monitoring, daemon=True).start()

# ==========================================
# 4. API エンドポイント
# ==========================================
@app.get("/api/analyze/{ticker}")
def get_analysis(ticker: str):
    name = TARGET_TICKERS.get(ticker, ticker)
    result = analyze_single_ticker(ticker, name)
    result["timestamp"] = datetime.datetime.now().isoformat()
    return result

@app.get("/api/recommend")
def get_recommendations():
    top_10 = REAL_RANKING_DATA[:10]
    return {"recommendations": top_10, "timestamp": datetime.datetime.now().isoformat()}

class WalletRequest(BaseModel):
    user_id: str
    amount: float

@app.post("/api/wallet/deposit")
def deposit_cash(req: WalletRequest, db: Session = Depends(get_db)):
    wallet = get_user_wallet(db, req.user_id)
    wallet.balance += req.amount
    db.commit()
    return {"status": "success", "balance": wallet.balance}

@app.post("/api/wallet/withdraw")
def withdraw_cash(req: WalletRequest, db: Session = Depends(get_db)):
    wallet = get_user_wallet(db, req.user_id)
    if wallet.balance < req.amount:
        raise HTTPException(status_code=400, detail="残高不足")
    wallet.balance -= req.amount
    db.commit()
    return {"status": "success", "balance": wallet.balance}

class BuyRequest(BaseModel):
    ticker: str
    shares: float 
    user_id: str

@app.post("/api/portfolio/buy")
def buy_stock(req: BuyRequest, db: Session = Depends(get_db)):
    name = TARGET_TICKERS.get(req.ticker, req.ticker)
    
    df = fetch_stooq_data(req.ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=400, detail="現在の株価が取得できませんでした")
        
    current_price = float(df['Close'].iloc[-1])
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
    
    df = fetch_stooq_data(item.ticker)
    current_price = float(df['Close'].iloc[-1]) if df is not None and not df.empty else item.avg_price
    
    profit = (current_price - item.avg_price) * item.shares
    total_revenue = current_price * item.shares

    wallet = get_user_wallet(db, user_id)
    wallet.balance += total_revenue
    
    history = TradeHistory(action="SELL", ticker=item.ticker, name=item.name, profit=profit, user_id=user_id)
    db.add(history)
    db.delete(item)
    db.commit()
    return {"status": "success", "profit": profit}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)