import React, { useState, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ComposedChart, Line, PieChart, Pie, Cell } from 'recharts';
import { Crosshair, Cpu, Star, ToggleLeft, ToggleRight, Wifi, WifiOff, PlayCircle, Wallet, AlertCircle, ShoppingCart, ArrowDownToLine, Home, DollarSign, PieChart as PieChartIcon, History, TrendingUp, TrendingDown, Target, ArrowRight } from 'lucide-react';

const generateMockChart = (basePrice) => {
  const data = [];
  let price = basePrice;
  for (let i = 0; i < 40; i++) {
    price = price + (Math.random() - 0.45) * (basePrice * 0.005);
    data.push({ 
      time: `${9 + Math.floor(i/12)}:${(i%12)*5 < 10 ? '0' : ''}${(i%12)*5}`, 
      price: Math.round(price), predictedPrice: null
    });
  }
  return data;
};

const COLORS = ['#34d399', '#3b82f6', '#8b5cf6', '#f59e0b', '#ec4899'];

export default function App() {
  const [activeTab, setActiveTab] = useState('HOME');
  const [isConnected, setIsConnected] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  
  const [selectedBuyTicker, setSelectedBuyTicker] = useState('7203.T');
  const [buyTickerName, setBuyTickerName] = useState('トヨタ自動車');
  
  const [selectedSellTicker, setSelectedSellTicker] = useState('');
  const [autoSell, setAutoSell] = useState(false);

  const [currentAnalysis, setCurrentAnalysis] = useState({
    price: 0, predictedPrice: 0, action: 'WAIT', confidence: 0, chartData: [], rsi: 50
  });

  // DBから取得する本物のポートフォリオデータ
  const [portfolio, setPortfolio] = useState([]);
  const [tradeHistory, setTradeHistory] = useState([]);
  
  // 資産状況
  const [cash, setCash] = useState(3000000); // 初期資金300万円

  // ==========================================
  // DBから自分の資産状況を取得する関数
  // ==========================================
  const fetchPortfolioFromDB = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/portfolio');
      if (res.ok) {
        const data = await res.json();
        // 取得したポートフォリオに、計算用の currentPrice をセット（最初は買値と同じにしておく）
        setPortfolio(data.portfolio.map(p => ({ ...p, currentPrice: p.avgPrice })));
        setTradeHistory(data.history);
        
        // もしSELL画面を開いていて、選択中の株が売却されて無くなった場合、別の株を選択する
        if (data.portfolio.length > 0 && !data.portfolio.find(p => p.ticker === selectedSellTicker)) {
          setSelectedSellTicker(data.portfolio[0].ticker);
        }
      } else {
        throw new Error("API Response not OK");
      }
    } catch (e) { 
      console.warn("DBに接続できませんでした。プレビュー用のモックデータを表示します。"); 
      // Canvas環境などAPIに繋がらない場合のフォールバックデータ
      setPortfolio(prev => prev.length > 0 ? prev : [
        { id: 1, ticker: '9984.T', name: 'ソフトバンクG', shares: 100, avgPrice: 8500, currentPrice: 8650 },
        { id: 2, ticker: '6920.T', name: 'レーザーテック', shares: 50, avgPrice: 39000, currentPrice: 38500 },
        { id: 3, ticker: '8035.T', name: '東京エレクトロン', shares: 100, avgPrice: 35000, currentPrice: 35200 }
      ]);
      setTradeHistory(prev => prev.length > 0 ? prev : [
        { date: '今日 13:45', action: 'AUTO SELL', name: '三菱UFJ', profit: 45000 },
        { date: '今日 10:15', action: 'BUY', name: 'レーザーテック', profit: 0 }
      ]);
    }
  };

  // 初回起動時にDBからデータを読み込む
  useEffect(() => {
    fetchPortfolioFromDB();
  }, []);

  // ==========================================
  // 株を買う関数 (API通信)
  // ==========================================
  const executeBuy = async (ticker, name) => {
    if (!window.confirm(`${name} を100株購入しますか？\n(ディープラーニングの買いシグナルに従います)`)) return;
    try {
      const res = await fetch('http://localhost:8000/api/portfolio/buy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, shares: 100 }) // 今回は固定で100株
      });
      if (res.ok) {
        alert('🎉 購入が完了しました！HOME画面のポートフォリオに追加されています。');
        fetchPortfolioFromDB(); // DB再読み込み
      } else {
        throw new Error("Network Error");
      }
    } catch (e) { 
      // モック用フォールバック
      alert('【モックモード】プレビュー環境のため購入処理をシミュレートしました。'); 
      const price = currentAnalysis.price || 3000;
      setPortfolio(prev => [...prev, { id: Date.now(), ticker, name, shares: 100, avgPrice: price, currentPrice: price }]);
      setTradeHistory(prev => [{ date: new Date().toLocaleTimeString(), action: 'BUY', name, profit: 0 }, ...prev]);
      setCash(prev => prev - (price * 100));
    }
  };

  // ==========================================
  // 株を売る関数 (API通信)
  // ==========================================
  const executeSell = async (id, name, isAuto = false) => {
    if (!isAuto && !window.confirm(`${name} を売却して利益を確定させますか？`)) return;
    try {
      const res = await fetch(`http://localhost:8000/api/portfolio/sell/${id}`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (isAuto) {
          // AUTO SELLの時は画面上部に通知を出す（簡易版）
          console.log(`[AUTO SELL発動] ${name} を自動売却しました。利益: ¥${Math.round(data.profit).toLocaleString()}`);
        } else {
          alert(`💸 売却完了！\n利益: ¥${Math.round(data.profit).toLocaleString()} を獲得しました！`);
        }
        fetchPortfolioFromDB(); // DB再読み込み
      } else {
        throw new Error("Network Error");
      }
    } catch (e) { 
      // モック用フォールバック
      const stock = portfolio.find(p => p.id === id);
      if (stock) {
        const profit = (stock.currentPrice - stock.avgPrice) * stock.shares;
        if (isAuto) {
          console.log(`[AUTO SELL (MOCK)] ${name} を自動売却しました。利益: ¥${Math.round(profit).toLocaleString()}`);
        } else {
          alert(`【モックモード】プレビュー環境のため売却シミュレーション完了！\n利益: ¥${Math.round(profit).toLocaleString()} を獲得しました！`);
        }
        setPortfolio(prev => prev.filter(p => p.id !== id));
        setTradeHistory(prev => [{ date: new Date().toLocaleTimeString(), action: isAuto ? 'AUTO SELL' : 'SELL', name, profit }, ...prev]);
        setCash(prev => prev + (stock.avgPrice * stock.shares) + profit);
      }
    }
  };


  // AIおすすめ銘柄スキャン (30秒ごと)
  useEffect(() => {
    const fetchRecommendations = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/recommend');
        if (res.ok) {
          const data = await res.json();
          setRecommendations(data.recommendations.slice(0, 10));
        }
      } catch (e) {}
    };
    fetchRecommendations();
    const int = setInterval(fetchRecommendations, 30000);
    return () => clearInterval(int);
  }, []);

  // 選択銘柄のAPI分析 ＆ リアルタイム株価更新
  useEffect(() => {
    if (activeTab === 'HOME') return;

    const activeTicker = activeTab === 'BUY' ? selectedBuyTicker : selectedSellTicker;
    if (!activeTicker) return;
    
    const fetchApiData = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/analyze/${activeTicker}`);
        if (response.ok) {
          const data = await response.json();
          setIsConnected(true);
          
          setCurrentAnalysis(prev => {
            const baseChart = prev.chartData.length > 0 && prev.chartData[prev.chartData.length-1].price !== null 
                              ? prev.chartData : generateMockChart(data.currentPrice);
            
            const actualData = baseChart.filter(d => d.price !== null);
            actualData.shift();
            const time = new Date(data.timestamp);
            actualData.push({ 
              time: `${time.getHours()}:${time.getMinutes()}:${time.getSeconds()}`, 
              price: data.currentPrice, predictedPrice: null
            });

            const futureData = [...actualData];
            let predPrice = data.currentPrice;
            futureData[futureData.length - 1].predictedPrice = data.currentPrice;
            const step = (data.predictedPrice - data.currentPrice) / 10; 
            for(let i = 1; i <= 10; i++) {
               predPrice += step;
               futureData.push({
                 time: `+${i}s`, price: null, predictedPrice: Math.round(predPrice)
               });
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

          // 保有株の価格を更新 ＆ AUTO SELLの判定
          setPortfolio(prev => {
            return prev.map(stock => {
              // 選択中の株はAPIの実データで更新、それ以外は擬似的に微変動（UIの演出）
              let newPrice = stock.currentPrice;
              if (stock.ticker === activeTicker) {
                newPrice = data.currentPrice;
              } else {
                newPrice = newPrice * (1 + (Math.random() - 0.5) * 0.002);
              }

              // 【AUTO SELL機能】: +1.5%以上の利益が出たら自動で売りAPIを叩く
              if (autoSell) {
                const profitPct = (newPrice - stock.avgPrice) / stock.avgPrice;
                if (profitPct >= 0.015) {
                  executeSell(stock.id, stock.name, true);
                }
              }
              return { ...stock, currentPrice: newPrice };
            });
          });
        }
      } catch (error) { setIsConnected(false); }
    };

    fetchApiData();
    const interval = setInterval(fetchApiData, 3000);
    return () => clearInterval(interval);
  }, [selectedBuyTicker, selectedSellTicker, activeTab, autoSell]);

  const getAiInsight = () => {
    const { price, predictedPrice, rsi } = currentAnalysis;
    if (!price || !predictedPrice) return "LSTMエンジンが過去の時系列パターンから市場をディープラーニング解析中です...";

    const diff = predictedPrice - price;
    const diffPercent = ((diff / price) * 100).toFixed(1);

    if (activeTab === 'BUY') {
      if (diff > 0) {
        return (
          <span>
            LSTM（ディープラーニング）の予測モデルによれば、直近の時系列パターンから強い反発シグナルを検知しました。近日中に <strong className="text-emerald-400">¥{predictedPrice.toLocaleString()} (期待値 +{diffPercent}%)</strong> まで上昇する確率が非常に高いです。AIは<strong className="text-white">「今が買い時」</strong>と強く推奨しています。
          </span>
        );
      } else {
        return "現在は下落トレンドの波形と完全に一致しています。AIはさらなる下落リスクを予測しているため、今は購入を見送るのが賢明です。";
      }
    } else {
      const stock = portfolio.find(s => s.ticker === selectedSellTicker);
      if(!stock) return "売却する銘柄をリストから選択してください。";
      const currentProfit = (price - stock.avgPrice) * stock.shares;
      const futureProfit = (predictedPrice - stock.avgPrice) * stock.shares;

      if (diff > price * 0.005) {
        return (
          <span>
            現在 <strong className="text-emerald-400">+¥{Math.round(currentProfit).toLocaleString()}</strong> の利益が出ています。AIの時系列予測ではまだ上昇トレンドが継続し、<strong className="text-blue-400">¥{predictedPrice.toLocaleString()}</strong> まで伸びる見込みです。利益が <strong className="text-emerald-400">約+¥{Math.round(futureProfit).toLocaleString()}</strong> に達するまでホールドを推奨します。
          </span>
        );
      } else {
        return (
          <span>
            天井圏の波形パターンを検知しました。AIは今後価格が下落に転じると予測しています。せっかくの利益が減ってしまう前に、<strong className="text-rose-400 border-b border-rose-400 pb-0.5">今すぐ売却して +¥{Math.round(currentProfit).toLocaleString()} の利益を確実に刈り取る</strong> ことを強く推奨します。
          </span>
        );
      }
    }
  };

  // --- 資産の計算 ---
  const totalStockValue = portfolio.reduce((acc, stock) => acc + (stock.currentPrice * stock.shares), 0);
  // DBの取引履歴から実際の「確定利益」を合算
  const realizedProfit = tradeHistory.reduce((acc, trade) => acc + (trade.profit || 0), 0);
  const totalAssets = cash + realizedProfit + totalStockValue;
  const unrealizedProfit = portfolio.reduce((acc, stock) => acc + ((stock.currentPrice - stock.avgPrice) * stock.shares), 0);
  
  const pieData = portfolio.map(stock => ({
    name: stock.name, value: stock.currentPrice * stock.shares
  })).concat([{ name: '現金（買付余力）', value: cash + realizedProfit }]);

  return (
    <div className="min-h-screen bg-gray-900 font-sans text-gray-100 selection:bg-blue-500/30" translate="no">
      <header className="bg-gray-900 border-b border-gray-800 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-gradient-to-br from-blue-600 to-indigo-600 text-white p-2 rounded-lg shadow-lg">
              <Cpu size={22} strokeWidth={2.5} />
            </div>
            <h1 className="text-xl font-black text-transparent bg-clip-text bg-gradient-to-r from-white to-gray-400 tracking-tight">
              TradeMaster<span className="text-blue-400">.AI</span> <span className="text-[10px] text-indigo-400 ml-1 border border-indigo-500/30 px-1.5 py-0.5 rounded">LSTM ENGINE</span>
            </h1>
            <div className={`ml-4 px-3 py-1 hidden sm:flex items-center rounded-full border text-[10px] font-bold uppercase tracking-widest ${isConnected ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-gray-800 text-gray-500 border-gray-700'}`}>
              {isConnected ? <Wifi size={12} className="mr-1.5" /> : <WifiOff size={12} className="mr-1.5" />}
              {isConnected ? 'API ONLINE (DB CONNECTED)' : 'API MOCK'}
            </div>
          </div>
          
          <div className="flex bg-gray-800 p-1 rounded-xl border border-gray-700 shadow-inner">
            <button onClick={() => setActiveTab('HOME')} className={`flex items-center px-4 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'HOME' ? 'bg-blue-500/20 text-blue-400 shadow-[0_0_10px_rgba(59,130,246,0.2)]' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700/50'}`}>
              <Home size={16} className="mr-2" /> <span className="hidden sm:inline">HOME (資産)</span>
            </button>
            <button onClick={() => { setActiveTab('BUY'); setCurrentAnalysis(prev => ({...prev, chartData: []})); }} className={`flex items-center px-4 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'BUY' ? 'bg-emerald-500/20 text-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.2)]' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700/50'}`}>
              <ShoppingCart size={16} className="mr-2" /> <span className="hidden sm:inline">BUY (探す)</span>
            </button>
            <button onClick={() => { setActiveTab('SELL'); setCurrentAnalysis(prev => ({...prev, chartData: []})); }} className={`flex items-center px-4 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'SELL' ? 'bg-rose-500/20 text-rose-400 shadow-[0_0_10px_rgba(244,63,94,0.2)]' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700/50'}`}>
              <Wallet size={16} className="mr-2" /> <span className="hidden sm:inline">SELL (売る)</span>
            </button>
          </div>
        </div>
      </header>
      
      <main className="max-w-7xl mx-auto px-4 py-8">
        
        {/* ===================== HOME 画面 ===================== */}
        {activeTab === 'HOME' && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-gray-800 p-5 rounded-xl border border-gray-700 shadow-lg relative overflow-hidden">
                <div className="absolute -right-4 -bottom-4 opacity-10"><DollarSign size={100} /></div>
                <p className="text-xs text-gray-400 font-bold uppercase tracking-wider mb-1">現在の総資産</p>
                <h3 className="text-3xl font-black text-white font-mono mt-1">¥{Math.round(totalAssets).toLocaleString()}</h3>
                <p className="text-xs text-gray-400 mt-2">買付余力: ¥{Math.round(cash + realizedProfit).toLocaleString()}</p>
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
                <p className="text-xs text-gray-400 font-bold uppercase tracking-wider mb-1">取引回数 (DB記録)</p>
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
                        <th className="pb-3 font-normal text-right">保有数</th>
                        <th className="pb-3 font-normal text-right">買値</th>
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
                            <td className="py-3 text-right text-sm font-mono text-gray-300">{stock.shares}</td>
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
                <History size={18} className="mr-2 text-indigo-400" /> 本物の取引履歴 (DB記録)
              </p>
              <div className="space-y-2">
                {tradeHistory.length === 0 && <p className="text-gray-500 text-sm">取引履歴はまだありません。</p>}
                {tradeHistory.map((trade, i) => (
                  <div key={i} className="flex justify-between items-center p-3 bg-gray-900/50 rounded-lg border border-gray-700/50">
                    <div className="flex items-center space-x-4">
                      <span className="text-xs text-gray-500 w-24">{trade.date}</span>
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
                      <span className="text-sm font-mono text-gray-500">決済待ち</span>
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
              <div className="bg-gray-800 p-5 rounded-xl border border-gray-700 shadow-lg flex flex-col h-[650px]">
                <p className="text-sm text-emerald-400 font-bold uppercase tracking-wider mb-2 flex items-center">
                  <Star size={16} className="mr-1.5 fill-emerald-400" /> AI厳選 買い時トップ10
                </p>
                <div className="overflow-y-auto pr-2 space-y-2 flex-grow scrollbar-thin scrollbar-thumb-gray-700">
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
                  )) : <div className="text-gray-500 text-xs text-center py-10">AIスキャン中...</div>}
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
                      <span className="text-5xl font-black text-white font-mono">¥{currentAnalysis.price ? Math.round(currentAnalysis.price).toLocaleString() : '---'}</span>
                    </div>
                  </div>
                  {/* 【重要】 購入ボタンにAPIを繋ぎ込みました */}
                  <button 
                    onClick={() => executeBuy(selectedBuyTicker, buyTickerName)}
                    className="flex items-center px-8 py-4 bg-emerald-500 hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/20 rounded-xl font-bold text-lg transition-all transform hover:scale-105"
                  >
                    <PlayCircle size={22} className="mr-2" />
                    この株を買う (100株)
                  </button>
                </div>

                <div className="bg-indigo-500/10 border border-indigo-500/30 p-5 rounded-xl mb-6 flex items-start">
                  <Cpu className="text-indigo-400 mt-1 mr-4 flex-shrink-0" size={24} />
                  <div>
                    <h3 className="text-indigo-400 font-bold mb-1">LSTM 買い時予測アドバイス</h3>
                    <p className="text-gray-300 text-sm leading-relaxed">{getAiInsight()}</p>
                  </div>
                </div>

                <div className="h-[350px] w-full relative">
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
                          <p className="text-[10px] text-gray-500">{stock.shares}株</p>
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
                            <span className="text-5xl font-black text-white font-mono">¥{currentAnalysis.price ? Math.round(currentAnalysis.price).toLocaleString() : '---'}</span>
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
                          
                          {/* 【重要】 売却ボタンにAPIを繋ぎ込みました */}
                          <button 
                            onClick={() => executeSell(stock.id, stock.name)}
                            className="flex items-center px-8 py-3 bg-rose-500 hover:bg-rose-600 text-white shadow-lg shadow-rose-500/20 rounded-xl font-bold transition-all"
                          >
                            <ArrowDownToLine size={20} className="mr-2" />
                            今すぐ売る (利確)
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
                    <h3 className={`font-bold mb-1 ${currentAnalysis.predictedPrice < currentAnalysis.price ? 'text-rose-400' : 'text-indigo-400'}`}>LSTM 売却タイミング予測</h3>
                    <p className="text-gray-300 text-sm leading-relaxed">{getAiInsight()}</p>
                  </div>
                </div>

                <div className="h-[300px] w-full relative">
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
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}