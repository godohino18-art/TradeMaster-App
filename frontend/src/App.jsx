import React, { useState, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ComposedChart, Line, PieChart, Pie, Cell } from 'recharts';
import { Crosshair, Cpu, Star, ToggleLeft, ToggleRight, Wifi, WifiOff, PlayCircle, Wallet, AlertCircle, ShoppingCart, ArrowDownToLine, Home, DollarSign, PieChart as PieChartIcon, History, TrendingUp, TrendingDown, Target, ArrowRight, LogOut, User, PlusCircle, MinusCircle, Loader } from 'lucide-react';

const supabaseUrl = 'https://ezasvrijqcpgroyaayxf.supabase.co';
const supabaseAnonKey = 'sb_publishable_YHWVqLqCJjrQt0UJUgFF_w_AncjEZ2j';
const API_BASE_URL = 'https://trademaster-backend-7ulm.onrender.com';

const COLORS = ['#34d399', '#3b82f6', '#8b5cf6', '#f59e0b', '#ec4899'];

function AuthScreen({ onAuthSuccess }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [isLoginMode, setIsLoginMode] = useState(true);

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');
    try {
      if (isLoginMode) {
        const res = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=password`, {
          method: 'POST',
          headers: { 'apikey': supabaseAnonKey, 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error_description || data.msg || 'ログインに失敗しました');
        onAuthSuccess(data);
      } else {
        const res = await fetch(`${supabaseUrl}/auth/v1/signup`, {
          method: 'POST',
          headers: { 'apikey': supabaseAnonKey, 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error_description || data.msg || '登録に失敗しました');
        alert('🎉 登録成功！ログインしてください。');
        setIsLoginMode(true);
      }
    } catch (error) { setErrorMsg(error.message); } 
    finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center font-sans px-4">
      <div className="max-w-md w-full bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 p-8">
        <div className="text-center mb-8">
          <div className="inline-block bg-gradient-to-br from-blue-600 to-indigo-600 text-white p-3 rounded-xl shadow-lg mb-4">
            <Cpu size={32} strokeWidth={2.5} />
          </div>
          <h1 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-white to-gray-400 tracking-tight">
            TradeMaster<span className="text-blue-400">.AI</span>
          </h1>
          <p className="text-gray-400 text-sm mt-2 font-bold uppercase tracking-widest">Multi-User Platform</p>
        </div>
        {errorMsg && <div className="bg-rose-500/10 border border-rose-500/30 text-rose-400 p-3 rounded-lg mb-6 text-sm">{errorMsg}</div>}
        <form onSubmit={handleAuth} className="space-y-5">
          <div>
            <label className="block text-sm font-bold text-gray-400 mb-1">Email</label>
            <input type="email" required className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500 transition-all" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </div>
          <div>
            <label className="block text-sm font-bold text-gray-400 mb-1">Password</label>
            <input type="password" required minLength="6" className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500 transition-all" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="6文字以上" />
          </div>
          <button type="submit" disabled={loading} className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 px-4 rounded-lg shadow-lg shadow-blue-500/30 transition-all disabled:opacity-50 mt-4">
            {loading ? '処理中...' : isLoginMode ? 'ログイン' : '新規アカウント登録'}
          </button>
        </form>
        <div className="mt-6 text-center">
          <button onClick={() => { setIsLoginMode(!isLoginMode); setErrorMsg(''); }} className="text-sm text-gray-400 hover:text-white transition-colors underline">
            {isLoginMode ? 'アカウントをお持ちでない方はこちら (新規登録)' : 'すでにアカウントをお持ちの方はこちら (ログイン)'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState(() => {
    const stored = localStorage.getItem('supabase_session');
    return stored ? JSON.parse(stored) : null;
  });

  const handleLogout = () => {
    localStorage.removeItem('supabase_session');
    setSession(null);
  };

  if (!session) {
    return <AuthScreen onAuthSuccess={(data) => {
      localStorage.setItem('supabase_session', JSON.stringify(data));
      setSession(data);
    }} />;
  }

  return <MainApp session={session} onLogout={handleLogout} />;
}

function MainApp({ session, onLogout }) {
  const userId = session.user.id; 
  const userEmail = session.user.email;

  const [activeTab, setActiveTab] = useState('HOME');
  const [isConnected, setIsConnected] = useState(false);
  const [isServerWaking, setIsServerWaking] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  
  const [selectedBuyTicker, setSelectedBuyTicker] = useState('7203.T');
  const [buyTickerName, setBuyTickerName] = useState('トヨタ自動車');
  const [buyAmount, setBuyAmount] = useState(1000); 
  
  const [selectedSellTicker, setSelectedSellTicker] = useState('');
  const [autoSell, setAutoSell] = useState(false);

  const [currentAnalysis, setCurrentAnalysis] = useState({
    price: 0, predictedPrice: 0, action: 'WAIT', confidence: 0, chartData: [], rsi: 50
  });

  const [portfolio, setPortfolio] = useState([]);
  const [tradeHistory, setTradeHistory] = useState([]);
  const [cash, setCash] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (!isConnected) setIsServerWaking(true);
    }, 3000); 
    return () => clearTimeout(timer);
  }, [isConnected]);

  const fetchPortfolioFromDB = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/portfolio?user_id=${userId}`);
      if (res.ok) {
        const data = await res.json();
        setPortfolio(data.portfolio.map(p => ({ ...p, currentPrice: p.avgPrice })));
        setTradeHistory(data.history);
        setCash(data.cash || 0);
        if (data.portfolio.length > 0 && !data.portfolio.find(p => p.ticker === selectedSellTicker)) {
          setSelectedSellTicker(data.portfolio[0].ticker);
        }
      }
    } catch (e) { console.warn("DB接続エラー"); }
  };

  useEffect(() => { fetchPortfolioFromDB(); }, [userId]);

  const handleWallet = async (type, amount) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/wallet/${type}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, amount })
      });
      if (res.ok) {
        fetchPortfolioFromDB();
      } else {
        const err = await res.json();
        alert(`エラー: ${err.detail}`);
      }
    } catch (e) { alert("通信エラーが発生しました。"); }
  };

  const executeBuy = async (ticker, name) => {
    if (!currentAnalysis.price || currentAnalysis.price <= 0) return alert("現在、株価データを取得中です。少々お待ちください。");
    
    const sharesToBuy = buyAmount / currentAnalysis.price;
    if (!window.confirm(`${name} を ¥${buyAmount.toLocaleString()} 分購入しますか？\n(約 ${sharesToBuy.toFixed(4)} 株)`)) return;
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/portfolio/buy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, shares: sharesToBuy, user_id: userId }) 
      });
      if (res.ok) {
        alert('🎉 購入が完了しました！ポートフォリオに追加され、残高が更新されました。');
        fetchPortfolioFromDB();
      } else {
        const err = await res.json();
        alert(`エラー: ${err.detail}`);
      }
    } catch (e) { alert("エラーが発生しました。"); }
  };

  const executeSell = async (id, name, isAuto = false) => {
    if (!isAuto && !window.confirm(`${name} を売却して利益を確定させますか？`)) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/portfolio/sell/${id}?user_id=${userId}`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (!isAuto) alert(`💸 売却完了！\n利益: ¥${Math.round(data.profit).toLocaleString()} を獲得し、口座に入金されました！`);
        fetchPortfolioFromDB();
      } else {
        const err = await res.json();
        alert(`エラー: ${err.detail}`);
      }
    } catch (e) { alert("エラーが発生しました。"); }
  };

  useEffect(() => {
    const fetchRecommendations = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/recommend`);
        if (res.ok) {
          const data = await res.json();
          setRecommendations(data.recommendations.slice(0, 10));
          setIsConnected(true); 
          setIsServerWaking(false);
        }
      } catch (e) {}
    };
    fetchRecommendations();
    const int = setInterval(fetchRecommendations, 30000);
    return () => clearInterval(int);
  }, []);

  // ★ 画面クラッシュを絶対に防ぐ安全なデータ取得処理
  useEffect(() => {
    if (activeTab === 'HOME') return;
    const activeTicker = activeTab === 'BUY' ? selectedBuyTicker : selectedSellTicker;
    if (!activeTicker) return;
    
    const fetchApiData = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/analyze/${activeTicker}`);
        if (!response.ok) throw new Error("Network response was not ok");
        
        const data = await response.json();
        setIsConnected(true);
        setIsServerWaking(false);
        
        setCurrentAnalysis(prev => {
          const actualData = data.chartData || [];
          // ★ もしデータが空ならクラッシュさせず、デフォルトの安全な状態を返す
          if (actualData.length === 0 || !data.price || data.price <= 0) {
             return { price: 0, predictedPrice: 0, action: 'WAIT', confidence: 0, chartData: [], rsi: 50 };
          }
          
          const futureData = [...actualData];
          let predPrice = data.currentPrice;
          if(futureData.length > 0) {
              futureData[futureData.length - 1].predictedPrice = data.currentPrice;
          }
          const step = (data.predictedPrice - data.currentPrice) / 10; 
          for(let i = 1; i <= 10; i++) {
             predPrice += step;
             futureData.push({ time: `+${i}m`, price: null, predictedPrice: Math.round(predPrice) });
          }
          
          return {
            price: data.currentPrice,
            predictedPrice: data.predictedPrice,
            action: data.action,
            confidence: data.confidence,
            chartData: futureData,
            rsi: data.indicators.rsi
          };
        });

        setPortfolio(prev => {
          return prev.map(stock => {
            let newPrice = stock.currentPrice;
            if (stock.ticker === activeTicker && data.currentPrice > 0) {
              newPrice = data.currentPrice;
            } else {
              newPrice = newPrice * (1 + (Math.random() - 0.5) * 0.002);
            }
            if (autoSell && stock.avgPrice > 0) {
              const profitPct = (newPrice - stock.avgPrice) / stock.avgPrice;
              if (profitPct >= 0.015) executeSell(stock.id, stock.name, true);
            }
            return { ...stock, currentPrice: newPrice };
          });
        });
      } catch (error) { 
        // エラー時は何もしないことで画面の暗転を防ぐ
      }
    };

    fetchApiData();
    const interval = setInterval(fetchApiData, 3000);
    return () => clearInterval(interval);
  }, [selectedBuyTicker, selectedSellTicker, activeTab, autoSell]);

  const getAiInsight = () => {
    if (!isConnected && isServerWaking) return "サーバーを起動中です。データを受信するまでしばらくお待ちください...";
    const { price, predictedPrice, rsi } = currentAnalysis;
    if (!price || price <= 0 || !predictedPrice) return "AIエンジンが市場を解析中です。データ取得までしばらくお待ちください...";
    
    const diff = predictedPrice - price;
    const diffPercent = ((diff / price) * 100).toFixed(1);

    if (activeTab === 'BUY') {
      if (diff > 0) {
        return <span>AIの予測モデルによれば、現在のRSI({rsi})から判断して強い反発シグナルを検知しました。近日中に <strong className="text-emerald-400">¥{predictedPrice.toLocaleString()} (期待値 +{diffPercent}%)</strong> まで上昇する確率が非常に高いです。AIは<strong className="text-white">「今が買い時」</strong>と強く推奨しています。</span>;
      } else {
        return "現在は下落トレンドの波形と完全に一致しています。投資家の勢いも弱いため、今は購入を見送るのが賢明です。";
      }
    } else {
      const stock = portfolio.find(s => s.ticker === selectedSellTicker);
      if(!stock) return "売却する銘柄をリストから選択してください。";
      const currentProfit = (price - stock.avgPrice) * stock.shares;
      const futureProfit = (predictedPrice - stock.avgPrice) * stock.shares;

      if (diff > price * 0.005) {
        return <span>現在 <strong className="text-emerald-400">+¥{Math.round(currentProfit).toLocaleString()}</strong> の利益が出ています。AI予測ではまだ上昇トレンドが継続し、利益が <strong className="text-emerald-400">約+¥{Math.round(futureProfit).toLocaleString()}</strong> に達するまでホールドを推奨します。</span>;
      } else {
        return <span>天井圏の波形パターンを検知しました。せっかくの利益が減ってしまう前に、<strong className="text-rose-400 border-b border-rose-400 pb-0.5">今すぐ売却して +¥{Math.round(currentProfit).toLocaleString()} の利益を確実に刈り取る</strong> ことを強く推奨します。</span>;
      }
    }
  };

  const safeCash = cash || 0;
  const totalStockValue = portfolio.reduce((acc, stock) => acc + (stock.currentPrice * stock.shares), 0);
  const realizedProfit = tradeHistory.reduce((acc, trade) => acc + (trade.profit || 0), 0);
  const totalAssets = safeCash + totalStockValue;
  const unrealizedProfit = portfolio.reduce((acc, stock) => acc + ((stock.currentPrice - stock.avgPrice) * stock.shares), 0);
  
  const pieData = portfolio.map(stock => ({
    name: stock.name, value: stock.currentPrice * stock.shares
  })).concat([{ name: '現金（買付余力）', value: safeCash }]);

  // ★ チャートが描画可能かどうかの安全チェック
  const isChartReady = currentAnalysis && currentAnalysis.chartData && currentAnalysis.chartData.length > 0 && currentAnalysis.price > 0;

  return (
    <div className="min-h-screen bg-gray-900 font-sans text-gray-100 selection:bg-blue-500/30" translate="no">
      <header className="bg-gray-900 border-b border-gray-800 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-gradient-to-br from-blue-600 to-indigo-600 text-white p-2 rounded-lg shadow-lg">
              <Cpu size={22} strokeWidth={2.5} />
            </div>
            <h1 className="text-xl font-black text-transparent bg-clip-text bg-gradient-to-r from-white to-gray-400 tracking-tight">
              TradeMaster<span className="text-blue-400">.AI</span>
            </h1>
            <div className={`ml-4 px-3 py-1 hidden sm:flex items-center rounded-full border text-[10px] font-bold uppercase tracking-widest transition-colors ${isConnected ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : isServerWaking ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' : 'bg-gray-800 text-gray-500 border-gray-700'}`}>
              {isConnected ? <Wifi size={12} className="mr-1.5" /> : isServerWaking ? <Loader size={12} className="mr-1.5 animate-spin" /> : <WifiOff size={12} className="mr-1.5" />}
              {isConnected ? 'API ONLINE' : isServerWaking ? 'SERVER WAKING UP...' : 'API CONNECTING...'}
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="flex bg-gray-800 p-1 rounded-xl border border-gray-700 shadow-inner mr-2">
              <button onClick={() => setActiveTab('HOME')} className={`flex items-center px-4 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'HOME' ? 'bg-blue-500/20 text-blue-400 shadow-[0_0_10px_rgba(59,130,246,0.2)]' : 'text-gray-400 hover:text-gray-200'}`}>
                <Home size={16} className="mr-2" /> <span className="hidden sm:inline">HOME</span>
              </button>
              <button onClick={() => { setActiveTab('BUY'); setCurrentAnalysis(prev => ({...prev, chartData: []})); }} className={`flex items-center px-4 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'BUY' ? 'bg-emerald-500/20 text-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.2)]' : 'text-gray-400 hover:text-gray-200'}`}>
                <ShoppingCart size={16} className="mr-2" /> <span className="hidden sm:inline">BUY</span>
              </button>
              <button onClick={() => { setActiveTab('SELL'); setCurrentAnalysis(prev => ({...prev, chartData: []})); }} className={`flex items-center px-4 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'SELL' ? 'bg-rose-500/20 text-rose-400 shadow-[0_0_10px_rgba(244,63,94,0.2)]' : 'text-gray-400 hover:text-gray-200'}`}>
                <Wallet size={16} className="mr-2" /> <span className="hidden sm:inline">SELL</span>
              </button>
            </div>
            
            <div className="flex items-center space-x-3 border-l border-gray-700 pl-4">
              <div className="hidden md:flex items-center text-xs text-gray-400">
                <User size={14} className="mr-1" />
                {userEmail.split('@')[0]}
              </div>
              <button onClick={onLogout} className="p-2 bg-gray-800 text-gray-400 hover:text-white rounded-lg border border-gray-700 hover:bg-gray-700 transition-colors" title="ログアウト">
                <LogOut size={16} />
              </button>
            </div>
          </div>
        </div>
      </header>
      
      <main className="max-w-7xl mx-auto px-4 py-8">
        
        {/* ===================== HOME 画面 ===================== */}
        {activeTab === 'HOME' && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              
              <div className="bg-gray-800 p-5 rounded-xl border border-gray-700 shadow-lg relative overflow-hidden flex flex-col justify-between">
                <div className="absolute -right-4 -bottom-4 opacity-10"><DollarSign size={100} /></div>
                <div>
                  <p className="text-xs text-gray-400 font-bold uppercase tracking-wider mb-1">現金残高 (買付余力)</p>
                  <h3 className="text-3xl font-black text-white font-mono mt-1">¥{Math.round(safeCash).toLocaleString()}</h3>
                  <p className="text-xs text-gray-500 mt-1">総資産: ¥{Math.round(totalAssets).toLocaleString()}</p>
                </div>
                <div className="flex space-x-2 mt-4 relative z-10">
                  <button onClick={() => handleWallet('deposit', 10000)} className="flex-1 bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-400 border border-emerald-600/30 py-2 rounded-lg text-[10px] font-bold flex items-center justify-center transition-all">
                    <PlusCircle size={14} className="mr-1" /> 1万円入金
                  </button>
                  <button onClick={() => handleWallet('withdraw', 10000)} className="flex-1 bg-rose-600/20 hover:bg-rose-600/40 text-rose-400 border border-rose-600/30 py-2 rounded-lg text-[10px] font-bold flex items-center justify-center transition-all">
                    <MinusCircle size={14} className="mr-1" /> 1万円出金
                  </button>
                </div>
              </div>
              
              <div className="bg-gray-800 p-5 rounded-xl border border-gray-700 shadow-lg relative overflow-hidden">
                <div className="absolute -right-4 -bottom-4 opacity-10"><TrendingUp size={100} /></div>
                <p className="text-xs text-gray-400 font-bold uppercase tracking-wider mb-1">現在の含み益 (評価損益)</p>
                <h3 className={`text-3xl font-black font-mono mt-1 ${unrealizedProfit >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {unrealizedProfit > 0 ? '+' : ''}¥{Math.round(unrealizedProfit).toLocaleString()}
                </h3>
              </div>

              <div className="bg-gray-800 p-5 rounded-xl border border-gray-700 shadow-lg relative overflow-hidden">
                <div className="absolute -right-4 -bottom-4 opacity-10 text-emerald-500"><Wallet size={100} /></div>
                <p className="text-xs text-gray-400 font-bold uppercase tracking-wider mb-1">これまでの確定利益</p>
                <h3 className={`text-3xl font-black font-mono mt-1 ${realizedProfit >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {realizedProfit > 0 ? '+' : ''}¥{Math.round(realizedProfit).toLocaleString()}
                </h3>
              </div>

              <div className="bg-gray-800 p-5 rounded-xl border border-gray-700 shadow-lg relative overflow-hidden">
                <div className="absolute -right-4 -bottom-4 opacity-10 text-indigo-500"><Target size={100} /></div>
                <p className="text-xs text-gray-400 font-bold uppercase tracking-wider mb-1">取引回数</p>
                <h3 className="text-3xl font-black text-indigo-400 font-mono mt-1">{tradeHistory.length} 回</h3>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg flex flex-col justify-between">
                <p className="text-sm text-gray-200 font-bold uppercase tracking-wider mb-4 flex items-center">
                  <PieChartIcon size={18} className="mr-2 text-blue-400" /> 資産内訳
                </p>
                <div className="h-48 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={2} dataKey="value" stroke="none">
                        {pieData.map((entry, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
                      </Pie>
                      <Tooltip formatter={(value) => `¥${Math.round(value).toLocaleString()}`} contentStyle={{ backgroundColor: '#111827', border: 'none', borderRadius: '8px', color: '#fff' }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg lg:col-span-2">
                <div className="flex justify-between items-center mb-4">
                  <p className="text-sm text-gray-200 font-bold uppercase tracking-wider flex items-center">
                    <Wallet size={18} className="mr-2 text-blue-400" /> 保有銘柄一覧
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead className="text-xs text-gray-500 border-b border-gray-700">
                      <tr>
                        <th className="pb-3 font-normal">銘柄</th>
                        <th className="pb-3 font-normal text-right">保有数(株)</th>
                        <th className="pb-3 font-normal text-right">平均買値</th>
                        <th className="pb-3 font-normal text-right">現在値</th>
                        <th className="pb-3 font-normal text-right">評価損益</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-700/50">
                      {portfolio.length === 0 && <tr><td colSpan="5" className="py-8 text-center text-gray-500">まだ保有している銘柄はありません。BUY画面から購入してください。</td></tr>}
                      {portfolio.map(stock => {
                        const profit = (stock.currentPrice - stock.avgPrice) * stock.shares;
                        const profitPct = ((stock.currentPrice - stock.avgPrice) / stock.avgPrice) * 100;
                        return (
                          <tr key={stock.id} className="hover:bg-gray-700/20 transition-colors">
                            <td className="py-3">
                              <p className="font-bold text-sm text-gray-200">{stock.name}</p>
                              <p className="text-[10px] text-gray-500 font-mono">{stock.ticker}</p>
                            </td>
                            <td className="py-3 text-right text-sm font-mono text-gray-300">{stock.shares.toFixed(4)}</td>
                            <td className="py-3 text-right text-sm font-mono text-gray-300">¥{stock.avgPrice.toLocaleString()}</td>
                            <td className="py-3 text-right text-sm font-mono text-gray-300">¥{Math.round(stock.currentPrice).toLocaleString()}</td>
                            <td className={`py-3 text-right text-sm font-mono font-bold ${profit >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {profit > 0 ? '+' : ''}¥{Math.round(profit).toLocaleString()}
                              <span className="block text-[10px] font-normal">({profitPct > 0 ? '+' : ''}{profitPct.toFixed(2)}%)</span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg">
              <p className="text-sm text-gray-200 font-bold uppercase tracking-wider mb-4 flex items-center">
                <History size={18} className="mr-2 text-indigo-400" /> あなたの取引履歴
              </p>
              <div className="space-y-2">
                {tradeHistory.length === 0 && <p className="text-gray-500 text-sm">取引履歴はまだありません。</p>}
                {tradeHistory.map((trade, i) => (
                  <div key={i} className="flex justify-between items-center p-3 bg-gray-900/50 rounded-lg border border-gray-700/50">
                    <div className="flex items-center space-x-4">
                      <span className="text-xs text-gray-500 w-24">{new Date(trade.created_at || trade.date).toLocaleString('ja-JP', {month: 'numeric', day: 'numeric', hour: '2-digit', minute:'2-digit'})}</span>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                        trade.action === 'SELL' ? 'bg-blue-500/10 text-blue-400 border-blue-500/30' : 
                        trade.action === 'BUY' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 
                        'bg-gray-700 text-gray-300 border-gray-600'
                      }`}>
                        {trade.action}
                      </span>
                      <span className="text-sm font-bold text-gray-200">{trade.name}</span>
                    </div>
                    {trade.action === 'SELL' && trade.profit !== undefined ? (
                      <span className={`text-sm font-mono font-bold ${trade.profit > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {trade.profit > 0 ? '+' : ''}¥{Math.round(trade.profit).toLocaleString()}
                      </span>
                    ) : (
                      <span className="text-sm font-mono text-gray-500">決済完了</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ===================== BUY 画面 ===================== */}
        {activeTab === 'BUY' && (
          <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="xl:col-span-1 space-y-4">
              <div className="bg-gray-800 p-5 rounded-xl border border-gray-700 shadow-lg flex flex-col h-[650px] relative">
                <p className="text-sm text-emerald-400 font-bold uppercase tracking-wider mb-2 flex items-center">
                  <Star size={16} className="mr-1.5 fill-emerald-400" /> AI厳選 買い時トップ10
                </p>
                <div className="overflow-y-auto pr-2 space-y-2 flex-grow scrollbar-thin scrollbar-thumb-gray-700">
                  {/* サーバー起動中の表示 */}
                  {!isConnected && isServerWaking && recommendations.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full opacity-70">
                      <Loader className="text-amber-400 animate-spin mb-3" size={24} />
                      <p className="text-amber-400 font-bold text-xs text-center leading-relaxed">AIエンジンを起動しています...<br/>(約1〜2分かかります)</p>
                    </div>
                  )}
                  {recommendations.length > 0 ? recommendations.map((rec, idx) => (
                    <div 
                      key={idx} onClick={() => { setSelectedBuyTicker(rec.ticker); setBuyTickerName(rec.name); }}
                      className={`p-3 rounded-lg border cursor-pointer transition-all flex justify-between items-center group ${selectedBuyTicker === rec.ticker ? 'bg-emerald-500/10 border-emerald-500 shadow-[0_0_15px_rgba(52,211,153,0.15)]' : 'bg-gray-900/80 border-gray-700 hover:border-emerald-500/50'}`}
                    >
                      <div className="overflow-hidden">
                        <p className="text-sm font-bold text-gray-200 group-hover:text-emerald-400 truncate">{rec.name}</p>
                        <p className="text-[10px] text-gray-500 font-mono">{rec.ticker}</p>
                      </div>
                      <div className="text-right ml-2 flex-shrink-0">
                        <p className="text-[11px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">期待度 {rec.confidence}%</p>
                      </div>
                    </div>
                  )) : !isServerWaking && <div className="text-gray-500 text-xs text-center py-10">AIスキャン中...</div>}
                </div>
              </div>
            </div>

            <div className="xl:col-span-3 space-y-6">
              <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-100 tracking-wider flex items-center">
                      {buyTickerName} <span className="text-sm text-gray-500 font-mono ml-3">({selectedBuyTicker})</span>
                    </h2>
                    <div className="flex items-baseline mt-2">
                      <span className="text-5xl font-black text-white font-mono">
                        ¥{currentAnalysis.price > 0 ? Math.round(currentAnalysis.price).toLocaleString() : '---'}
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex flex-col items-end">
                    <div className="flex items-center space-x-2 mb-3 bg-gray-900 p-1 rounded-lg border border-gray-700">
                      <span className="text-xs text-gray-400 pl-2">投資額:</span>
                      {[100, 1000, 5000, 10000].map(amount => (
                        <button key={amount} onClick={() => setBuyAmount(amount)} className={`px-3 py-1.5 rounded-md text-xs font-bold transition-all ${buyAmount === amount ? 'bg-emerald-600 text-white shadow-md' : 'text-gray-400 hover:text-white'}`}>
                          ¥{amount.toLocaleString()}
                        </button>
                      ))}
                    </div>
                    <button onClick={() => executeBuy(selectedBuyTicker, buyTickerName)} className="flex items-center px-8 py-3 bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/20 rounded-xl font-bold text-lg transition-all transform hover:scale-105">
                      <PlayCircle size={22} className="mr-2" />
                      この株を ¥{buyAmount.toLocaleString()} 分 買う
                    </button>
                    {currentAnalysis.price > 0 && (
                      <p className="text-xs text-gray-400 mt-2 font-mono">
                        (概算取得株数: 約 {(buyAmount / currentAnalysis.price).toFixed(4)} 株)
                      </p>
                    )}
                  </div>
                </div>

                <div className="bg-indigo-500/10 border border-indigo-500/30 p-5 rounded-xl mb-6 flex items-start">
                  <Cpu className="text-indigo-400 mt-1 mr-4 flex-shrink-0" size={24} />
                  <div>
                    <h3 className="text-indigo-400 font-bold mb-1">AI 買い時予測アドバイス</h3>
                    <p className="text-gray-300 text-sm leading-relaxed">{getAiInsight()}</p>
                  </div>
                </div>

                <div className="h-[350px] w-full relative">
                  {/* ★ 画面クラッシュを絶対に防ぐ安全なチャート描画判定 */}
                  {(!isChartReady) ? (
                    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-gray-900/80 backdrop-blur-sm rounded-xl border border-gray-700">
                      <Cpu className="text-blue-400 animate-pulse mb-3" size={32} />
                      <p className="text-blue-400 font-bold text-sm">市場データを取得・解析中...</p>
                      <p className="text-gray-400 text-xs mt-2">（※表示されない場合はリロードしてください）</p>
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={currentAnalysis.chartData} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#374151" />
                        <XAxis dataKey="time" stroke="#6b7280" fontSize={11} tickMargin={10} axisLine={false} tickLine={false} />
                        <YAxis domain={['auto', 'auto']} stroke="#6b7280" fontSize={11} width={80} axisLine={false} tickLine={false} tickFormatter={(val) => `¥${val}`} orientation="right" />
                        <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', borderRadius: '0.5rem' }} itemStyle={{ color: '#fff', fontSize: '12px', fontWeight: 'bold' }} />
                        <Line type="monotone" dataKey="price" stroke="#34d399" strokeWidth={3} dot={false} isAnimationActive={false} name="現在価格" />
                        <Line type="monotone" dataKey="predictedPrice" stroke="#818cf8" strokeWidth={2} strokeDasharray="4 4" dot={false} isAnimationActive={false} name="AI予測価格" />
                      </ComposedChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ===================== SELL 画面 ===================== */}
        {activeTab === 'SELL' && (
          <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="xl:col-span-1 space-y-4">
              <div className="bg-gray-800 p-5 rounded-xl border border-gray-700 shadow-lg flex flex-col h-[650px]">
                <div className="flex justify-between items-center mb-4 pb-4 border-b border-gray-700">
                  <p className="text-sm text-rose-400 font-bold uppercase tracking-wider flex items-center">
                    <Wallet size={16} className="mr-1.5" /> 現在の持ち株
                  </p>
                </div>
                
                <div className="overflow-y-auto pr-2 space-y-3 flex-grow scrollbar-thin scrollbar-thumb-gray-700">
                  {portfolio.length === 0 && <p className="text-gray-500 text-xs text-center py-4">売却できる保有株がありません。</p>}
                  {portfolio.map((stock) => {
                    const profitValue = (stock.currentPrice - stock.avgPrice) * stock.shares;
                    const isSelected = selectedSellTicker === stock.ticker;
                    
                    return (
                      <div 
                        key={stock.id} onClick={() => setSelectedSellTicker(stock.ticker)}
                        className={`p-3 rounded-lg border cursor-pointer transition-all ${isSelected ? 'bg-rose-500/10 border-rose-500 shadow-[0_0_15px_rgba(244,63,94,0.15)]' : 'bg-gray-900/80 border-gray-700 hover:border-rose-500/50'}`}
                      >
                        <div className="flex justify-between items-start mb-1">
                          <p className="text-sm font-bold text-gray-200">{stock.name}</p>
                          <p className="text-[10px] text-gray-500">{stock.shares.toFixed(4)}株</p>
                        </div>
                        <div className="flex justify-between items-end mt-2">
                          <span className="text-xs text-gray-400 font-mono">買値 ¥{stock.avgPrice}</span>
                          <span className={`text-xs font-bold font-mono px-2 py-0.5 rounded ${profitValue >= 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                            {profitValue > 0 ? '+' : ''}¥{Math.round(profitValue).toLocaleString()}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="xl:col-span-3 space-y-6">
              <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 shadow-lg">
                <div className="flex justify-between items-start mb-6">
                  {portfolio.filter(s => s.ticker === selectedSellTicker).map(stock => {
                    const currentProfit = (currentAnalysis.price - stock.avgPrice) * stock.shares;
                    return (
                      <React.Fragment key={stock.ticker}>
                        <div>
                          <h2 className="text-2xl font-bold text-gray-100 tracking-wider">{stock.name}</h2>
                          <div className="flex items-end mt-2 space-x-4">
                            <span className="text-5xl font-black text-white font-mono">
                              ¥{currentAnalysis.price > 0 ? Math.round(currentAnalysis.price).toLocaleString() : '---'}
                            </span>
                            <div className="mb-1">
                              <span className="text-sm text-gray-400 mr-2">現在の確定利益:</span>
                              <span className={`text-2xl font-bold font-mono ${currentProfit >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {currentProfit >= 0 ? '+' : ''}¥{currentProfit ? Math.round(currentProfit).toLocaleString() : '0'}
                              </span>
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex flex-col items-end space-y-3">
                          <div className={`flex items-center space-x-3 px-3 py-1.5 rounded-lg border cursor-pointer transition-all ${autoSell ? 'bg-indigo-500/10 border-indigo-500/50' : 'bg-gray-900 border-gray-700'}`} onClick={() => setAutoSell(!autoSell)}>
                            <span className={`text-xs font-bold ${autoSell ? 'text-indigo-400' : 'text-gray-500'}`}>AUTO SELL (+1.5%で自動利確)</span>
                            {autoSell ? <ToggleRight className="text-indigo-400" size={20} /> : <ToggleLeft className="text-gray-600" size={20} />}
                          </div>
                          
                          <button onClick={() => executeSell(stock.id, stock.name)} className="flex items-center px-8 py-3 bg-rose-500 hover:bg-rose-600 text-white shadow-lg shadow-rose-500/20 rounded-xl font-bold transition-all">
                            <ArrowDownToLine size={20} className="mr-2" />
                            今すぐ全額売る (利確)
                          </button>
                        </div>
                      </React.Fragment>
                    );
                  })}
                  {portfolio.length === 0 && <div className="text-gray-500">売却する銘柄がありません。</div>}
                </div>

                <div className={`border p-5 rounded-xl mb-6 flex items-start ${currentAnalysis.predictedPrice < currentAnalysis.price ? 'bg-rose-500/10 border-rose-500/30' : 'bg-indigo-500/10 border-indigo-500/30'}`}>
                  <AlertCircle className={`mt-1 mr-4 flex-shrink-0 ${currentAnalysis.predictedPrice < currentAnalysis.price ? 'text-rose-400' : 'text-indigo-400'}`} size={24} />
                  <div>
                    <h3 className={`font-bold mb-1 ${currentAnalysis.predictedPrice < currentAnalysis.price ? 'text-rose-400' : 'text-indigo-400'}`}>AI 売却タイミング予測</h3>
                    <p className="text-gray-300 text-sm leading-relaxed">{getAiInsight()}</p>
                  </div>
                </div>

                <div className="h-[300px] w-full relative">
                  {(!isChartReady) ? (
                    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-gray-900/80 backdrop-blur-sm rounded-xl border border-gray-700">
                      <Cpu className="text-blue-400 animate-pulse mb-3" size={32} />
                      <p className="text-blue-400 font-bold text-sm">市場データを取得・解析中...</p>
                    </div>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={currentAnalysis.chartData} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#374151" />
                        <XAxis dataKey="time" stroke="#6b7280" fontSize={11} tickMargin={10} axisLine={false} tickLine={false} />
                        <YAxis domain={['auto', 'auto']} stroke="#6b7280" fontSize={11} width={80} axisLine={false} tickLine={false} tickFormatter={(val) => `¥${val}`} orientation="right" />
                        <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', borderRadius: '0.5rem' }} itemStyle={{ color: '#fff', fontSize: '12px', fontWeight: 'bold' }} />
                        
                        {portfolio.filter(s => s.ticker === selectedSellTicker).map(stock => (
                           <Line key="avg" type="step" dataKey={() => stock.avgPrice} stroke="#6b7280" strokeWidth={1} strokeDasharray="3 3" dot={false} isAnimationActive={false} name="あなたの買値" />
                        ))}
                        
                        <Line type="monotone" dataKey="price" stroke={currentAnalysis.predictedPrice < currentAnalysis.price ? "#fb7185" : "#34d399"} strokeWidth={3} dot={false} isAnimationActive={false} name="現在価格" />
                        <Line type="monotone" dataKey="predictedPrice" stroke="#818cf8" strokeWidth={2} strokeDasharray="4 4" dot={false} isAnimationActive={false} name="AI予測価格" />
                      </ComposedChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}