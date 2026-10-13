"use client";
import { useEffect, useState, useRef, Suspense } from "react";
import { useParams, useRouter } from "next/navigation";

type Race = { id: number; date: string; course: string; race_number: number; name: string; distance: number; condition: string; };
type RaceEntry = { id: number; horse_number: number; horse_name: string; jockey: string; weight: string; odds: number; sex_age: string; trainer: string; past_performance: string; };
type PredictionData = { marks: { [key: number]: string }; bets: { type: string; pattern: string; level: string }[]; source?: string; };
type PayoutItem = { pattern: string; payout: string };
type RaceResults = { [key: string]: PayoutItem[] };

// 実際の処理を行う中身のコンポーネント
function RaceDetailContent() {
  const params = useParams();
  const router = useRouter();
  const raceId = Array.isArray(params?.id) ? params.id[0] : params?.id;

  const [race, setRace] = useState<Race | null>(null);
  const [entries, setEntries] = useState<RaceEntry[]>([]);
  const [predictions, setPredictions] = useState<PredictionData | null>(null);
  const [raceResults, setRaceResults] = useState<RaceResults | null>(null);
  
  const [isLoading, setIsLoading] = useState(true);
  const [isPredicting, setIsPredicting] = useState(false);
  const [isFetchingResult, setIsFetchingResult] = useState(false);

  const hasFetchedPredictions = useRef(false);

  const fetchPredictions = async (targetId: string, isForce = false) => {
    setIsPredicting(true);
    try {
      const forceParam = isForce ? "?force=true" : "";
      const res = await fetch(`http://127.0.0.1:8080/api/races/${targetId}/predictions${forceParam}`);
      const data = await res.json();
      setPredictions(data);
    } catch (error) {
      console.error("予想取得エラー:", error);
    }
    setIsPredicting(false);
  };

  const handleSyncResults = async () => {
    if (!raceId) return;
    setIsFetchingResult(true);
    try {
      const res = await fetch(`http://127.0.0.1:8080/api/races/${raceId}/results`, { method: "POST" });
      const data = await res.json();
      if (data.status === "success") {
        setRaceResults(data.data);
        alert("レース結果と配当を取得しました！");
      } else {
        alert(data.message || "結果の取得に失敗しました。まだレースが終わっていない可能性があります。");
      }
    } catch (error) {
      console.error("結果取得エラー:", error);
    }
    setIsFetchingResult(false);
  };

  useEffect(() => {
    if (!raceId) return;

    Promise.all([
      fetch(`http://127.0.0.1:8080/api/races/${raceId}`).then((res) => res.json()),
      fetch(`http://127.0.0.1:8080/api/races/${raceId}/entries`).then((res) => res.json()),
      fetch(`http://127.0.0.1:8080/api/races/${raceId}/results`).then((res) => res.json())
    ]).then(([raceData, entriesData, resultsData]) => {
        setRace(raceData);
        setEntries(entriesData);
        if (resultsData.status === "success") setRaceResults(resultsData.data);
        setIsLoading(false);
        
        if (!hasFetchedPredictions.current) {
          hasFetchedPredictions.current = true;
          fetchPredictions(raceId, false);
        }
    }).catch((error) => console.error("データ取得エラー:", error));
  }, [raceId]);

  const checkHit = (bet: { type: string; pattern: string }) => {
    if (!raceResults || !raceResults[bet.type]) return null;
    const isCombo = ["馬連", "ワイド", "3連複"].includes(bet.type);
    const normalize = (p: string) => isCombo 
      ? p.split(/[-ー]/).map(n => parseInt(n)).sort((a,b)=>a-b).join('-')
      : p.replace(/\s+/g, '').replace(/ー/g, '-');
    const betPattern = normalize(bet.pattern);
    for (const item of raceResults[bet.type]) {
      if (normalize(item.pattern) === betPattern) return item.payout;
    }
    return null;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <main className="max-w-5xl mx-auto">
        <div className="mb-6 flex justify-between items-end flex-wrap gap-4">
          <button onClick={() => router.back()} className="text-blue-600 font-bold hover:underline">
            ← 一覧に戻る
          </button>
          
          <div className="flex gap-2">
            <button 
              onClick={handleSyncResults} 
              disabled={isFetchingResult || isLoading}
              className="bg-green-600 text-white px-5 py-2 rounded font-bold shadow hover:bg-green-700 disabled:bg-gray-400"
            >
              {isFetchingResult ? "結果を取得中..." : "🏁 レース結果を取得"}
            </button>
            <button 
              onClick={() => raceId && fetchPredictions(raceId, true)} 
              disabled={isPredicting || isLoading}
              className="bg-blue-600 text-white px-5 py-2 rounded font-bold shadow hover:bg-blue-700 disabled:bg-gray-400"
            >
              {isPredicting ? "予想を生成中..." : "🔄 AIで予想を再生成"}
            </button>
          </div>
        </div>

        <div className="flex items-center gap-4 mb-4">
          <h1 className="text-3xl font-bold text-gray-900">出馬表・AI予想</h1>
          {predictions?.source === "AI" && <span className="bg-blue-100 text-blue-800 border border-blue-300 text-sm font-bold px-3 py-1 rounded-full">✨ AI予想 (Gemini)</span>}
          {predictions?.source === "Rule-based" && <span className="bg-orange-100 text-orange-800 border border-orange-300 text-sm font-bold px-3 py-1 rounded-full">⚙️ 独自ロジック (API制限中)</span>}
        </div>

        {race && (
          <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200 shadow-sm">
            <h2 className="text-2xl font-bold text-gray-900 mb-1">
              {race.course} {race.race_number}R <span className="ml-3 text-xl font-normal text-gray-800">{race.name}</span>
            </h2>
            <p className="text-gray-700 font-medium">{race.date} | {race.distance}m | 馬場: {race.condition}</p>
          </div>
        )}

        {isLoading ? (
          <p className="text-gray-600 font-bold">データを読み込み中...</p>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <div className="xl:col-span-2 bg-white rounded-lg shadow overflow-hidden">
              <div className="bg-gray-800 text-white p-4"><h2 className="font-bold text-lg">出馬表</h2></div>
              <table className="w-full text-left border-collapse bg-white">
                <thead>
                  <tr className="bg-gray-100 text-gray-900 text-sm border-b-2 border-gray-300">
                    <th className="p-3 text-center font-bold">予想</th>
                    <th className="p-3 font-bold">馬番</th>
                    <th className="p-3 font-bold">馬名</th>
                    <th className="p-3 font-bold">性齢</th>
                    <th className="p-3 font-bold">斤量</th>
                    <th className="p-3 font-bold">騎手</th>
                    <th className="p-3 font-bold">厩舎</th>
                    <th className="p-3 font-bold">オッズ</th>
                    <th className="p-3 font-bold">近走成績 (過去3走)</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr key={entry.id} className="hover:bg-blue-50 border-b border-gray-200">
                      <td className="p-3 text-center text-red-600 font-bold text-xl">{predictions?.marks[entry.horse_number] || ""}</td>
                      <td className="p-3 font-bold text-gray-900 text-lg">{entry.horse_number}</td>
                      <td className="p-3 font-bold text-gray-900 text-base">{entry.horse_name}</td>
                      <td className="p-3 text-sm text-gray-600 font-medium">{entry.sex_age}</td>
                      <td className="p-3 text-sm text-gray-600 font-medium">{entry.weight}</td>
                      <td className="p-3 text-sm text-gray-900 font-medium">{entry.jockey}</td>
                      <td className="p-3 text-sm text-gray-600 font-medium">{entry.trainer}</td>
                      <td className="p-3 text-right text-sm text-gray-900 font-bold">{entry.odds.toFixed(1)}</td>
                      <td className="p-2 text-xs text-gray-500 max-w-[200px] truncate" title={entry.past_performance}>{entry.past_performance || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-col gap-6">
              <div className="bg-white rounded-lg shadow overflow-hidden h-fit">
                <div className="bg-green-700 text-white p-4"><h2 className="font-bold text-lg">推奨買い目</h2></div>
                <div className="p-4 bg-white">
                  {!predictions ? (
                    <p className="text-gray-600 text-sm font-medium">{isPredicting ? "予想生成中..." : "予想データがありません"}</p>
                  ) : predictions.bets && predictions.bets.length > 0 ? (
                    <ul className="space-y-3">
                      {predictions.bets.map((bet, index) => {
                        const hitPayout = checkHit(bet); 
                        return (
                          <li key={index} className="flex justify-between items-center border-b border-gray-200 pb-2">
                            <div className="flex items-center">
                              <span className="inline-block bg-gray-200 text-gray-900 font-bold text-xs px-2 py-1 rounded mr-2">{bet.type}</span>
                              <span className="font-bold text-lg text-gray-900 tracking-widest">{bet.pattern}</span>
                            </div>
                            <div className="flex items-center gap-3">
                              {hitPayout ? (
                                <span className="text-red-600 font-bold bg-red-100 px-2 py-1 rounded text-sm shadow-sm border border-red-200">
                                  🎯 的中! {hitPayout}
                                </span>
                              ) : raceResults ? (
                                <span className="text-gray-400 text-sm font-bold">✖ ハズレ</span>
                              ) : null}
                              <span className={`font-bold text-lg ${bet.level === 'A' ? 'text-red-600' : 'text-blue-600'}`}>{bet.level}</span>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p className="text-gray-600 text-sm font-medium">買い目データがありません</p>
                  )}
                </div>
              </div>

              {raceResults && (
                <div className="bg-white rounded-lg shadow overflow-hidden h-fit border border-gray-200">
                  <div className="bg-gray-200 text-gray-900 p-3 border-b border-gray-300">
                    <h2 className="font-bold text-md">🏁 実際のレース配当</h2>
                  </div>
                  <div className="p-3 text-sm">
                    {["単勝", "馬連", "ワイド", "3連複", "3連単"].map(type => (
                      raceResults[type] && (
                        <div key={type} className="flex border-b border-gray-100 py-2 last:border-0">
                          <span className="w-16 font-bold text-gray-700">{type}</span>
                          <div className="flex-1">
                            {raceResults[type].map((item, i) => (
                              <div key={i} className="flex justify-between mb-1 last:mb-0">
                                <span className="text-gray-900 font-bold tracking-widest">{item.pattern}</span>
                                <span className="text-gray-900">{item.payout}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

// ★ 追加：全体のコンポーネントを Suspense で包んで Next.js の事前レンダリングエラーを回避
export default function RaceDetail() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-50 p-8 flex items-center justify-center">
        <p className="text-xl font-bold text-gray-600">画面を準備中...</p>
      </div>
    }>
      <RaceDetailContent />
    </Suspense>
  );
}