"use client";
import { useEffect, useState } from "react";
import Link from "next/link";

type Race = { id: number; date: string; course: string; race_number: number; name: string; distance: number; condition: string; };
type Stats = { total_races: number; total_bets: number; total_spent: number; total_return: number; profit: number; roi: number; hit_rate: number; debug: string[]; };

export default function Home() {
  const [races, setRaces] = useState<Race[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [targetUrl, setTargetUrl] = useState("");

  const API_BASE = "https://horse-racing-app-6yil.onrender.com";

  const loadData = () => {
    fetch(`${API_BASE}/api/races`, { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => setRaces(data))
      .catch((error) => console.error("データ取得エラー:", error));

    fetch(`${API_BASE}/api/stats`, { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => setStats(data))
      .catch((error) => console.error("集計データ取得エラー:", error));
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSync = async () => {
    if (!targetUrl) {
      alert("netkeibaの出馬表URLを入力してください。");
      return;
    }
    setIsUpdating(true);
    try {
      await fetch(`${API_BASE}/api/sync`, { 
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: targetUrl })
      });
      loadData();
      setTargetUrl("");
    } catch (error) {
      console.error("更新エラー:", error);
    }
    setIsUpdating(false);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <main className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">地方競馬予想支援システム</h1>
        
        {/* PCでは横並び、スマホでは縦並びになるシンプルなレイアウト（元通り） */}
        <div className="flex flex-col lg:flex-row gap-8">
          
          <div className="flex-1">
            <div className="bg-white rounded-lg shadow p-6 mb-8 border-t-4 border-blue-600">
              <h2 className="text-lg font-bold mb-4 text-gray-900">新規レースデータの取得</h2>
              <div className="flex gap-4">
                <input 
                  type="text" 
                  value={targetUrl}
                  onChange={(e) => setTargetUrl(e.target.value)}
                  placeholder="https://nar.netkeiba.com/race/shutuba.html?race_id=..." 
                  className="flex-1 border border-gray-300 p-2 rounded text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button 
                  onClick={handleSync} 
                  disabled={isUpdating}
                  className="bg-blue-600 text-white px-6 py-2 rounded font-bold shadow hover:bg-blue-700 disabled:bg-gray-400 whitespace-nowrap"
                >
                  {isUpdating ? "取得中..." : "データ取得"}
                </button>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-bold mb-4 text-gray-900">取得済みレース一覧</h2>
              {races.length === 0 ? (
                <p className="text-gray-600">データがありません。上のフォームからURLを入力して取得してください。</p>
              ) : (
                <ul className="space-y-4">
                  {races.map((race) => (
                    <li key={race.id} className="border border-gray-200 p-4 rounded-md flex justify-between items-center bg-white hover:bg-gray-50 transition">
                      <div>
                        <div className="font-bold text-lg mb-1 text-gray-900">
                          {race.course} {race.race_number}R <span className="ml-2 text-gray-700 text-base font-normal">{race.name}</span>
                        </div>
                        <div className="text-sm text-gray-600">
                          {race.date} | {race.distance}m | 馬場: {race.condition}
                        </div>
                      </div>
                      <Link href={`/races/${race.id}`} className="bg-green-600 text-white px-5 py-2 rounded text-sm hover:bg-green-700 font-bold shadow">
                        詳細・予想を見る
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {stats && (stats.total_races > 0 || stats.debug?.length > 0) && (
            <div className="lg:w-80 flex-shrink-0">
              {stats.total_races === 0 ? (
                <div className="p-4 bg-yellow-50 rounded-lg shadow border-l-4 border-yellow-500">
                  <h2 className="text-lg font-bold text-yellow-800 mb-2">⚠️ ダッシュボード表示待ち</h2>
                  <p className="text-sm text-yellow-700 mb-3">予想と結果が揃ったレースがありません。</p>
                </div>
              ) : (
                <div className="bg-white rounded-lg shadow overflow-hidden sticky top-8">
                  <div className="bg-gray-800 text-white p-4">
                    <h2 className="font-bold text-lg text-center">📊 AIパフォーマンス</h2>
                  </div>
                  <div className="p-5 space-y-4">
                    <div className="border-b border-gray-100 pb-3">
                      <p className="text-xs text-gray-500 font-bold mb-1">回収率 (ROI)</p>
                      <p className={`text-3xl font-bold ${stats.roi >= 100 ? 'text-red-600' : 'text-gray-900'}`}>
                        {stats.roi.toFixed(1)}<span className="text-lg">%</span>
                      </p>
                    </div>
                    <div className="border-b border-gray-100 pb-3">
                      <p className="text-xs text-gray-500 font-bold mb-1">的中率</p>
                      <p className="text-3xl font-bold text-gray-900">
                        {stats.hit_rate.toFixed(1)}<span className="text-lg">%</span>
                      </p>
                    </div>
                    <div className="border-b border-gray-100 pb-3">
                      <p className="text-xs text-gray-500 font-bold mb-1">トータル収支</p>
                      <p className={`text-2xl font-bold ${stats.profit > 0 ? 'text-red-600' : 'text-blue-600'}`}>
                        {stats.profit > 0 ? "+" : ""}{stats.profit.toLocaleString()}<span className="text-base text-gray-900 ml-1">円</span>
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 font-bold mb-1">分析レース / 購入数</p>
                      <p className="text-xl font-bold text-gray-900">
                        {stats.total_races}<span className="text-sm font-normal mx-1">R</span> / {stats.total_bets}<span className="text-sm font-normal mx-1">点</span>
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}