from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import engine, SessionLocal, Base, Race, RaceEntry
from scraper import fetch_and_save_races
from analyzer import calculate_predictions
from pydantic import BaseModel
import json

class SyncRequest(BaseModel):
    url: str

Base.metadata.create_all(bind=engine)

app = FastAPI(title="地方競馬予想支援システム API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "APIサーバーが正常に起動しました"}

@app.get("/api/races")
def get_races(db: Session = Depends(get_db)):
    # ★修正：idの降順（新しいデータが一番上に来るように）で取得
    races = db.query(Race).order_by(Race.id.desc()).all()
    return races
    
# 単一レース取得API
@app.get("/api/races/{race_id}")
def get_race(race_id: int, db: Session = Depends(get_db)):
    return db.query(Race).filter(Race.id == race_id).first()

# 出馬表取得API
@app.get("/api/races/{race_id}/entries")
def get_race_entries(race_id: int, db: Session = Depends(get_db)):
    return db.query(RaceEntry).filter(RaceEntry.race_id == race_id).order_by(RaceEntry.horse_number).all()

@app.post("/api/sync")
def sync_races(req: SyncRequest):
    # 受け取ったURLをスクレイピング関数に渡す
    return fetch_and_save_races(req.url)

@app.get("/api/races/{race_id}/predictions")
def get_predictions(race_id: int, db: Session = Depends(get_db)):
    # 該当レースの出走馬を取得
    entries = db.query(RaceEntry).filter(RaceEntry.race_id == race_id).all()
    
    # 独立させた analyzer.py の関数にデータを渡して結果を受け取る
    return calculate_predictions(entries)

@app.get("/api/races/{race_id}/predictions")
def get_predictions(race_id: int, model: str = "gemini-3.8-flash", force: bool = False, db: Session = Depends(get_db)):
    race = db.query(Race).filter(Race.id == race_id).first()
    if not race:
        return {"marks": {}, "bets": []}

    # ① キャッシュが存在し、かつ強制再生成(force)でない場合はキャッシュを返す
    if not force and race.predictions_json:
        try:
            import json
            cached_data = json.loads(race.predictions_json)
            if cached_data.get("marks") or cached_data.get("bets"):
                print(f"✅ [Race {race_id}] DBのキャッシュから予想結果を即座に返却しました！")
                return cached_data
        except Exception as e:
            print(f"⚠️ キャッシュの読み込みエラー: {e}")
            pass

    # ② キャッシュがない、または「AIで再生成」ボタンを押した場合のみ新規生成
    print(f"🔄 [Race {race_id}] Gemini API（または独自ロジック）で予想を新規生成しています...")
    entries = db.query(RaceEntry).filter(RaceEntry.race_id == race_id).all()
    from analyzer import calculate_predictions
    predictions_result = calculate_predictions(entries, model_name=model)

    # ③ 推論結果をデータベースに【確実に】保存（updateメソッドを使用）
    if predictions_result.get("marks") or predictions_result.get("bets"):
        import json
        json_str = json.dumps(predictions_result, ensure_ascii=False)
        
        # ★ 修正：変数への代入ではなく、明示的なupdate文でデータベースを直接書き換える
        db.query(Race).filter(Race.id == race_id).update({"predictions_json": json_str})
        db.commit()
        print(f"💾 [Race {race_id}] 予想結果をデータベースに保存しました。次回以降はキャッシュを使用します。")

    return predictions_result

@app.post("/api/races/{race_id}/results")
def sync_race_results(race_id: int):
    from scraper import fetch_and_save_result
    return fetch_and_save_result(race_id)

@app.get("/api/races/{race_id}/results")
def get_race_results(race_id: int, db: Session = Depends(get_db)):
    race = db.query(Race).filter(Race.id == race_id).first()
    if not race or not race.result_json:
        return {"status": "none"}
    
    import json
    return {"status": "success", "data": json.loads(race.result_json)}

@app.get("/api/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    import json
    import re

    races = db.query(Race).all()
    debug_logs = [] # ★追加：何が原因で弾かれたかを記録するリスト
    
    total_races_evaluated = 0
    total_bets_count = 0
    total_spent = 0
    total_return = 0
    hit_count = 0

    for race in races:
        status = "OK"
        if not race.predictions_json:
            status = "❌ 予想データなし（詳細画面でAI再生成ボタンを押してください）"
        elif not race.result_json:
            status = "❌ 結果データなし（詳細画面で結果取得ボタンを押してください）"
        else:
            try:
                preds = json.loads(race.predictions_json)
                results = json.loads(race.result_json)
                bets = preds.get("bets", [])
                if not bets:
                    status = "❌ 買い目データなし（予想が空です）"
                elif not results:
                    status = "❌ 配当データなし"
                else:
                    status = "✅ 集計対象（準備完了）"
                    total_races_evaluated += 1
                    for bet in bets:
                        bet_type = bet.get("type")
                        bet_pattern = bet.get("pattern", "")
                        if not bet_type or not bet_pattern: continue
                        total_bets_count += 1
                        total_spent += 100
                        if bet_type not in results: continue
                        is_combo = bet_type in ["馬連", "ワイド", "3連複"]
                        def normalize(p):
                            nums = [int(n) for n in re.findall(r'\d+', p)]
                            if is_combo: nums.sort()
                            return "-".join(map(str, nums))
                        normalized_bet = normalize(bet_pattern)
                        for item in results[bet_type]:
                            if normalize(item["pattern"]) == normalized_bet:
                                hit_count += 1
                                payout_val = int(re.sub(r'\D', '', item["payout"]))
                                total_return += payout_val
                                break 
            except Exception as e:
                status = f"❌ 解析エラー: {str(e)}"
                
        # 各レースの調査結果を記録
        debug_logs.append(f"{race.course}{race.race_number}R ({race.date}): {status}")

    roi = (total_return / total_spent * 100) if total_spent > 0 else 0
    hit_rate = (hit_count / total_bets_count * 100) if total_bets_count > 0 else 0

    return {
        "total_races": total_races_evaluated,
        "total_bets": total_bets_count,
        "total_spent": total_spent,
        "total_return": total_return,
        "profit": total_return - total_spent,
        "roi": round(roi, 1),
        "hit_rate": round(hit_rate, 1),
        "debug": debug_logs # ★追加
    }