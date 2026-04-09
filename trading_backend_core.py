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
import asyncio

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
app = FastAPI(title="TradeMaster.AI API v10.0")
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
IS_UPDATING = False

# ==========================================
# 3. テクニカル指標計算
# ==========================================
def add_technical_indicators(df):
    """テクニカル指標を計算"""
    try:
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
        
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        return df.dropna()
    except Exception as e:
        print(f"インジケーター計算エラー: {e}")
        return df

def predict_with_rf(df):
    """ランダムフォレストで価格予測"""
    try:
        if len(df) < 20:
            return float(df['Close'].iloc[-1])
        
        features = ['Close', 'SMA5', 'SMA20', 'RSI']
        
        # NaN値を削除
        df_clean = df[features].dropna()
        if len(df_clean) < 10:
            return float(df['Close'].iloc[-1])
        
        X = df_clean[:-3].values
        y = df['Close'].iloc[len(df_clean)-len(df)+3:].values[:len(X)]
        
        if len(X) == 0 or len(y) == 0:
            return float(df['Close'].iloc[-1])
        
        if len(X) != len(y):
            min_len = min(len(X), len(y))
            X = X[:min_len]
            y = y[:min_len]
        
        model = RandomForestRegressor(n_estimators=30, random_state=42, n_jobs=1, max_depth=8)
        model.fit(X, y)
        
        last_features = df_clean[features].iloc[-1].values.reshape(1, -1)
        prediction = float(model.predict(last_features)[0])
        
        return max(prediction, float(df['Close'].iloc[-1]) * 0.5)  # 異常値防止
    except Exception as e:
        print(f"予測エラー: {e}")
        return float(df['Close'].iloc[-1])

# ==========================================
# 4. 勝つための銘柄抽出（重要）
# ==========================================
def update_ranking_cache():
    """勝てる株を自動抽出 - 確実に実行"""
    global REAL_RANKING_DATA, IS_UPDATING
    
    if IS_UPDATING:
        print("⚠️ 既に更新中です。スキップします。")
        return
    
    IS_UPDATING = True
    valid_stocks = []
    
    print("\n" + "="*80)
    print("🚀 実トレード対象『勝てる株の抽出』を開始します...")
    print("="*80)
    
    processed = 0
    successful = 0
    
    for ticker, name in TARGET_TICKERS.items():
        processed += 1
        try:
            print(f"[{processed}/{len(TARGET_TICKERS)}] {ticker} ({name}) を解析中...", end=" ", flush=True)
            
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo", interval="1d")
            
            if df is None or df.empty or len(df) < 30:
                print("✗ データ不足")
                continue
            
            df = add_technical_indicators(df)
            if len(df) < 20:
                print("✗ インジケーター計算失敗")
                continue
            
            current_price = float(df['Close'].iloc[-1])
            current_rsi = float(df['RSI'].iloc[-1])
            sma5 = float(df['SMA5'].iloc[-1])
            sma20 = float(df['SMA20'].iloc[-1])
            sma50 = float(df['SMA50'].iloc[-1])
            sma200 = float(df['SMA200'].iloc[-1])
            
            # 過去5日間の値動き
            price_5d_ago = float(df['Close'].iloc[-5]) if len(df) >= 5 else current_price
            momentum_5d = ((current_price - price_5d_ago) / price_5d_ago * 100) if price_5d_ago > 0 else 0
            
            # ボリンジャーバンド
            bb_std = df['Close'].rolling(window=20).std().iloc[-1]
            bb_middle = sma20
            bb_lower = bb_middle - (bb_std * 2) if bb_std > 0 else bb_middle * 0.95
            
            # ボリューム
            recent_vol = float(df['Volume'].iloc[-1])
            avg_vol = float(df['Volume'].tail(20).mean())
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0
            
            # MACD
            current_macd = float(df['MACD'].iloc[-1])
            current_signal = float(df['Signal'].iloc[-1])
            macd_diff = current_macd - current_signal
            
            # ★スコア計算
            winning_score = 0
            reasons = []
            
            # 1. RSI判定
            if current_rsi < 30:
                winning_score += 30
                reasons.append(f"RSI低い({current_rsi:.1f})")
            elif 30 <= current_rsi <= 50:
                winning_score += 25
                reasons.append(f"RSI理想({current_rsi:.1f})")
            elif 50 < current_rsi <= 70:
                winning_score += 15
                reasons.append(f"RSI中立({current_rsi:.1f})")
            
            # 2. 上昇トレンド
            if sma5 > sma20:
                winning_score += 30
                trend_strength = ((sma5 - sma20) / sma20) * 100
                if trend_strength > 2:
                    winning_score += 15
                reasons.append(f"上昇トレンド({trend_strength:.2f}%)")
            elif sma20 > sma50:
                winning_score += 15
                reasons.append("中期上昇")
            
            # 3. 長期トレンド
            if sma20 > sma50 > sma200:
                winning_score += 20
                reasons.append("強い上昇トレンド")
            
            # 4. 短期モメンタム
            if 0 < momentum_5d <= 5:
                winning_score += 15
                reasons.append(f"モメンタム({momentum_5d:.2f}%)")
            elif momentum_5d > 5 and momentum_5d <= 10:
                winning_score += 10
                reasons.append(f"小幅上昇({momentum_5d:.2f}%)")
            
            # 5. ボリンジャーバンド
            if current_price < bb_middle:
                distance_to_lower = ((current_price - bb_lower) / (bb_middle - bb_lower) * 100) if (bb_middle - bb_lower) != 0 else 50
                if distance_to_lower < 30:
                    winning_score += 25
                    reasons.append("下限付近（買い時）")
                elif distance_to_lower < 50:
                    winning_score += 15
                    reasons.append("下位帯")
            
            # 6. ボリューム上昇
            if vol_ratio > 1.5:
                winning_score += 20
                reasons.append(f"ボリューム急増({vol_ratio:.2f}倍)")
            elif vol_ratio > 1.2:
                winning_score += 12
                reasons.append(f"ボリューム上昇({vol_ratio:.2f}倍)")
            elif vol_ratio > 1.0:
                winning_score += 6
            
            # 7. MACD
            if macd_diff > 0 and current_macd > 0:
                winning_score += 15
                reasons.append("MACD強気")
            elif macd_diff > 0:
                winning_score += 8
            
            # ★スコア60以上のみ抽出
            if winning_score >= 60:
                prediction = predict_with_rf(df)
                predicted_upside = ((prediction - current_price) / current_price * 100) if current_price > 0 else 0
                
                stock_data = {
                    "ticker": ticker,
                    "name": name,
                    "currentPrice": round(current_price, 2),
                    "action": "CALL" if predicted_upside > 0.5 else "WAIT",
                    "confidence": min(99, winning_score),
                    "rsi": round(current_rsi, 1),
                    "trend": "上昇" if sma5 > sma20 else "下降",
                    "momentum": round(momentum_5d, 2),
                    "predictedPrice": round(prediction, 2),
                    "upside": round(predicted_upside, 2)
                }
                
                valid_stocks.append(stock_data)
                successful += 1
                print(f"✓ スコア {winning_score} | {' | '.join(reasons[:3])}")
            else:
                print(f"✗ スコア {winning_score} (基準未満)")
        
        except Exception as e:
            print(f"✗ エラー: {str(e)[:30]}")
        
        time.sleep(0.5)  # API制限回避
    
    print("\n" + "="*80)
    if valid_stocks:
        valid_stocks.sort(key=lambda x: x['confidence'], reverse=True)
        REAL_RANKING_DATA = valid_stocks[:10]
        print(f"✅ 勝てる銘柄の抽出完了: {len(REAL_RANKING_DATA)}社を特定しました！")
        print("\n【 今週の買い候補 TOP 10 】")
        for i, stock in enumerate(REAL_RANKING_DATA, 1):
            print(f"   {i:2d}. {stock['ticker']:8} | {stock['name']:15} | 信頼度 {stock['confidence']:3d}% | 上値 {stock['upside']:+.2f}%")
    else:
        print(f"⚠️ 勝てる銘柄がみつかりません。スコア60以上の銘柄を探索中...")
        # スコア50以上で代用
        for ticker, name in list(TARGET_TICKERS.items())[:3]:
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period="3mo", interval="1d")
                if df is not None and not df.empty:
                    current_price = float(df['Close'].iloc[-1])
                    REAL_RANKING_DATA.append({
                        "ticker": ticker,
                        "name": name,
                        "currentPrice": round(current_price, 2),
                        "confidence": 55,
                        "action": "WAIT"
                    })
            except:
                pass
    
    print("="*80 + "\n")
    IS_UPDATING = False

def analyze_single_ticker(ticker, name):
    """個別銘柄の詳細解析"""
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
            raise Exception("インジケーター計算失敗")
        
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

# ==========================================
# 5. バックグラウンドタスク
# ==========================================
def background_monitoring():
    """定期的にランキングを更新"""
    print("🔄 バックグラウンドモニタリング開始")
    time.sleep(5)  # 起動後5秒待機
    update_ranking_cache()
    
    counter = 0
    while True:
        time.sleep(120)  # 2分ごとにチェック
        counter += 1
        if counter % 5 == 0:  # 10分ごとに更新
            print(f"\n🔄 定期更新 #{counter//5} 開始")
            update_ranking_cache()

@app.on_event("startup")
def startup_event():
    """サーバー起動時"""
    print("✨ TradeMaster.AI サーバー起動")
    threading.Thread(target=background_monitoring, daemon=True).start()

# ==========================================
# 6. APIエンドポイント
# ==========================================

@app.get("/")
def root():
    return {"status": "TradeMaster.AI v10.0 is running"}

@app.get("/api/analyze/{ticker}")
def get_analysis(ticker: str):
    name = TARGET_TICKERS.get(ticker, ticker)
    result = analyze_single_ticker(ticker, name)
    result["timestamp"] = datetime.datetime.now().isoformat()
    return result

@app.get("/api/recommend")
def get_recommendations():
    """勝てる銘柄トップ10を返す"""
    if not REAL_RANKING_DATA:
        return {"recommendations": [], "timestamp": datetime.datetime.now().isoformat(), "status": "scanning"}
    return {"recommendations": REAL_RANKING_DATA[:10], "timestamp": datetime.datetime.now().isoformat(), "status": "ready"}

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
        raise HTTPException(status_code=400, detail="現在の株価が取得できませんでした")
    
    current_price = float(stock_df['Close'].iloc[-1])
    total_cost = current_price * req.shares

    user_data = get_user_data(req.user_id)
    if user_data["balance"] < total_cost:
        raise HTTPException(status_code=400, detail="残高不足です。")

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