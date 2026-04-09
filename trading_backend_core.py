from fastapi import FastAPI, HTTPException, Depends
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
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ==========================================
# 1. データベース設定
# ==========================================
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:W%26f4z5Di8h9q@db.ezasvrijqcpgroyaayxf.supabase.co:5432/postgres"

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
app = FastAPI(title="TradeMaster.AI API v8.0 (Winning Stocks Only)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ★勝つための厳選銘柄リスト
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
# 3. AI解析システム（勝つための戦略）
# ==========================================
REAL_RANKING_DATA = []

def add_technical_indicators(df):
    """テクニカル指標を計算"""
    df['SMA5'] = df['Close'].rolling(window=5).mean()
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    
    delta = df['Close'].diff()
    up, down = delta.clip(lower=0), -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=14, adjust=False).mean()
    ema_down = down.ewm(com=14, adjust=False).mean()
    df['RSI'] = 100 - (100 / (1 + ema_up / ema_down))
    
    # MACD計算
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    return df.dropna()

def predict_with_rf(df, future_steps=3):
    """ランダムフォレストで価格予測"""
    if len(df) < 20: 
        return float(df['Close'].iloc[-1])
    
    features = ['Close', 'SMA5', 'SMA20', 'RSI']
    X = df[features].values[:-future_steps] 
    y = df['Close'].values[future_steps:]
    
    if len(X) == 0: 
        return float(df['Close'].iloc[-1])
    
    model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1, max_depth=15)
    model.fit(X, y)
    return float(model.predict(df[features].values[-1].reshape(1, -1))[0])

def update_ranking_cache():
    """勝てる株を自動抽出するメインロジック"""
    global REAL_RANKING_DATA
    valid_stocks = []
    
    print("\n" + "="*60)
    print("実トレード対象『勝てる株の抽出』を開始します...")
    print("="*60)
    
    for ticker, name in TARGET_TICKERS.items():
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="3mo", interval="1d")
            
            if df is None or df.empty or len(df) < 25:
                continue
                
            df = add_technical_indicators(df)
            if len(df) < 5:
                continue
            
            current_price = float(df['Close'].iloc[-1])
            current_rsi = float(df['RSI'].iloc[-1])
            sma5 = float(df['SMA5'].iloc[-1])
            sma20 = float(df['SMA20'].iloc[-1])
            sma50 = float(df['SMA50'].iloc[-1])
            sma200 = float(df['SMA200'].iloc[-1])
            
            # 過去5日間の値動き
            price_5d_ago = float(df['Close'].iloc[-5])
            momentum_5d = ((current_price - price_5d_ago) / price_5d_ago) * 100
            
            # 過去20日間の値動き
            price_20d_ago = float(df['Close'].iloc[-20])
            momentum_20d = ((current_price - price_20d_ago) / price_20d_ago) * 100
            
            # ボリンジャーバンド計算
            bb_std = df['Close'].rolling(window=20).std().iloc[-1]
            bb_middle = sma20
            bb_upper = bb_middle + (bb_std * 2)
            bb_lower = bb_middle - (bb_std * 2)
            
            # ボリューム分析
            recent_vol = float(df['Volume'].iloc[-1])
            avg_vol = float(df['Volume'].tail(20).mean())
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
            
            # MACD分析
            current_macd = float(df['MACD'].iloc[-1])
            current_signal = float(df['Signal'].iloc[-1])
            macd_diff = current_macd - current_signal
            
            # ★本気の勝つための条件フィルター★
            winning_score = 0
            
            # 1. RSI判定（売られすぎ＝反発の可能性）
            if current_rsi < 30:
                winning_score += 25  # 売られすぎ状態
            elif 30 <= current_rsi <= 50:
                winning_score += 20  # 理想的な反発ゾーン
            elif 50 < current_rsi <= 70:
                winning_score += 15  # 中立
            # 70以上は買われすぎなので加点しない
            
            # 2. トレンド強度判定（短期 > 長期移動平均）
            if sma5 > sma20:
                winning_score += 25
                trend_strength = ((sma5 - sma20) / sma20) * 100
                if trend_strength > 2:
                    winning_score += 10
            elif sma5 > sma50:
                winning_score += 10  # 中期上昇
            
            # 3. 長期トレンド確認（SMA20 > SMA50 > SMA200）
            if sma20 > sma50 > sma200:
                winning_score += 15  # 強い上昇トレンド
            elif sma20 > sma50:
                winning_score += 8
            
            # 4. 5日間のモメンタム（直近の勢い）
            if 0 < momentum_5d <= 5:
                winning_score += 15
            elif momentum_5d > 5:
                winning_score += 12  # 急騰は売られる可能性
            
            # 5. 20日間のモメンタム（中期の流れ）
            if 0 < momentum_20d <= 10:
                winning_score += 10
            elif momentum_20d > 10:
                winning_score += 5
            
            # 6. ボリンジャーバンド下限付近（買い時シグナル）
            if current_price < bb_middle:
                distance_to_lower = ((current_price - bb_lower) / (bb_middle - bb_lower)) * 100 if (bb_middle - bb_lower) != 0 else 0
                if distance_to_lower < 20:
                    winning_score += 25  # 下限近い = 強い買いシグナル
                elif distance_to_lower < 40:
                    winning_score += 15
                elif distance_to_lower < 60:
                    winning_score += 8
            elif current_price > bb_middle and current_price < bb_upper:
                winning_score += 5  # 上昇中
            
            # 7. 直近のボリューム上昇（投資家の関心が高い）
            if vol_ratio > 1.5:
                winning_score += 18  # ボリューム急増
            elif vol_ratio > 1.2:
                winning_score += 12
            elif vol_ratio > 1.1:
                winning_score += 8
            
            # 8. MACD クロスシグナル（強い買いシグナル）
            if macd_diff > 0 and current_macd > 0:
                winning_score += 15  # MACD > Signal で上昇シグナル
            elif macd_diff > 0:
                winning_score += 8
            
            # ★スコアが65以上なら本気の勝てる株として追加★
            if winning_score >= 65:
                prediction = predict_with_rf(df)
                predicted_upside = ((prediction - current_price) / current_price) * 100 if current_price > 0 else 0
                
                valid_stocks.append({
                    "ticker": ticker,
                    "name": name,
                    "currentPrice": round(current_price, 2),
                    "action": "CALL" if predicted_upside > 0.5 else "WAIT",
                    "confidence": min(99, winning_score),
                    "momentum": round(momentum_5d, 2),
                    "rsi": round(current_rsi, 1),
                    "trend": "上昇" if sma5 > sma20 else "下降",
                    "predictedPrice": round(prediction, 2),
                    "upside": round(predicted_upside, 2)
                })
                print(f"✓ 買い候補: {ticker:10} ({name:15}) | スコア {winning_score:3}点 | RSI {current_rsi:6.1f} | モメンタム {momentum_5d:7.2f}% | 上値 {predicted_upside:6.2f}%")
        
        except Exception as e:
            print(f"✗ エラー: {ticker} - {str(e)[:30]}")
        
        time.sleep(0.8)
    
    print("\n" + "="*60)
    if valid_stocks:
        valid_stocks.sort(key=lambda x: x['confidence'], reverse=True)
        REAL_RANKING_DATA = valid_stocks[:10]
        print(f"✓ 勝てる銘柄の抽出完了: {len(REAL_RANKING_DATA)}社を特定しました！")
        for i, stock in enumerate(REAL_RANKING_DATA, 1):
            print(f"   {i}. {stock['ticker']:10} - {stock['name']:15} 信頼度 {stock['confidence']}%")
    else:
        print("⚠ 現在、買うべき銘柄がありません。市場をモニタリング中...")
    print("="*60 + "\n")

def analyze_single_ticker(ticker, name):
    """個別銘柄の詳細解析"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="5d", interval="5m")
        is_daily = False
        
        # 5分足がダメなら日足で確実に返す
        if df is None or df.empty or len(df) < 30:
            df = stock.history(period="3mo", interval="1d")
            is_daily = True
            
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
    """バックグラ��ンドで定期的にランキングを更新"""
    update_ranking_cache() 
    counter = 0
    while True:
        time.sleep(60) 
        counter += 1
        if counter % 15 == 0:  # 15分ごとに更新
            update_ranking_cache()

@app.on_event("startup")
def startup_event():
    """サーバー起動時にバックグラウンドタスクを開始"""
    threading.Thread(target=background_monitoring, daemon=True).start()

# ==========================================
# 4. API エンドポイント
# ==========================================

@app.get("/api/analyze/{ticker}")
def get_analysis(ticker: str):
    """個別銘柄の詳細解析を返す"""
    name = TARGET_TICKERS.get(ticker, ticker)
    result = analyze_single_ticker(ticker, name)
    result["timestamp"] = datetime.datetime.now().isoformat()
    return result

@app.get("/api/recommend")
def get_recommendations():
    """勝てる銘柄トップ10を返す"""
    top_10 = REAL_RANKING_DATA[:10]
    return {"recommendations": top_10, "timestamp": datetime.datetime.now().isoformat()}

# ==========================================
# 5. ウォレット関連API
# ==========================================

class WalletRequest(BaseModel):
    user_id: str
    amount: float

@app.post("/api/wallet/deposit")
def deposit_cash(req: WalletRequest, db: Session = Depends(get_db)):
    """資金を入金"""
    wallet = get_user_wallet(db, req.user_id)
    wallet.balance += req.amount
    db.commit()
    return {"status": "success", "balance": wallet.balance}

@app.post("/api/wallet/withdraw")
def withdraw_cash(req: WalletRequest, db: Session = Depends(get_db)):
    """資金を出金"""
    wallet = get_user_wallet(db, req.user_id)
    if wallet.balance < req.amount:
        raise HTTPException(status_code=400, detail="残高不足")
    wallet.balance -= req.amount
    db.commit()
    return {"status": "success", "balance": wallet.balance}

# ==========================================
# 6. ポートフォリオ関連API
# ==========================================

class BuyRequest(BaseModel):
    ticker: str
    shares: float 
    user_id: str

@app.post("/api/portfolio/buy")
def buy_stock(req: BuyRequest, db: Session = Depends(get_db)):
    """株を購入"""
    name = TARGET_TICKERS.get(req.ticker, req.ticker)
    
    stock_df = yf.Ticker(req.ticker).history(period="5d", interval="1d")
    if stock_df is None or stock_df.empty:
        raise HTTPException(status_code=400, detail="現在の株価が取得できませんでした")
        
    current_price = float(stock_df['Close'].iloc[-1])
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
    """ポートフォリオ情報を取得"""
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
    """株を売却"""
    item = db.query(PortfolioItem).filter(PortfolioItem.id == item_id, PortfolioItem.user_id == user_id).first()
    if not item: 
        raise HTTPException(status_code=404, detail="Item not found")
    
    stock_df = yf.Ticker(item.ticker).history(period="5d", interval="1d")
    current_price = float(stock_df['Close'].iloc[-1]) if stock_df is not None and not stock_df.empty else item.avg_price
    
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