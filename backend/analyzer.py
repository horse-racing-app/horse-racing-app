import google.generativeai as genai
import json
import re

GEMINI_API_KEY = "Ab8RN6KmiYc0FUUk53TqL6EdNBkycAF89ObK56kQfdyCL1XkdQ"
genai.configure(api_key=GEMINI_API_KEY)

def calculate_rule_based_predictions(entries):
    if not entries: return {"marks": {}, "bets": [], "source": "Rule-based"}

    import re
    scored_entries = []
    for entry in entries:
        score = 100.0
        
        # ★大改修：オッズの逆数を使った強力なスコアリング
        # 例: オッズ1.5倍なら+133点, 5倍なら+40点, 50倍なら+4点 となり、人気馬が圧倒的に有利になります
        if entry.odds != 99.9 and entry.odds > 0:
            score += (100.0 / entry.odds) * 2.0
        else:
            score -= 50.0 # オッズ未確定や極端な穴馬はマイナス

        # 枠順（地方競馬は内枠が有利な傾向があるため、1〜3番に少し加点）
        if 1 <= entry.horse_number <= 3:
            score += 4.0

        # トップ騎手による加点
        top_jockeys = [
            "吉村智", "下原理", "田中学", "赤岡修", "宮川実", 
            "岡部誠", "森泰斗", "御神本", "笹川翼", "矢野貴", 
            "吉原寛", "落合玄", "石川倭", "桑村真", "渡邊竜", "山口勲"
        ]
        if any(j in entry.jockey for j in top_jockeys): score += 10.0
            
        # 近走成績（着順）
        if entry.past_performance:
            if re.search(r'(?<!\d)1着', entry.past_performance): score += 10.0
            if re.search(r'(?<!\d)2着', entry.past_performance): score += 5.0
            if re.search(r'(?<!\d)1番人気', entry.past_performance): score += 5.0

        scored_entries.append({"horse_number": entry.horse_number, "score": score, "odds": entry.odds})

    # スコア順に並び替え
    scored_entries.sort(key=lambda x: x["score"], reverse=True)
    marks = ["◎", "○", "▲", "△", "×", "注"]
    prediction_marks = {item["horse_number"]: marks[i] if i < len(marks) else "" for i, item in enumerate(scored_entries)}

    bets = []
    if len(scored_entries) >= 4:
        h1 = scored_entries[0]["horse_number"] # 本命(1位)
        h2 = scored_entries[1]["horse_number"] # 対抗(2位)
        h3 = scored_entries[2]["horse_number"] # 単穴(3位)
        h4 = scored_entries[3]["horse_number"] # 連下(4位)

        # 買い目は本命(◎)と対抗(○)をベースにした堅実なものに絞る
        bets.append({"type": "単勝", "pattern": f"{h1}", "level": "A"})
        bets.append({"type": "馬連", "pattern": f"{h1} - {h2}", "level": "A"})
        bets.append({"type": "馬連", "pattern": f"{h1} - {h3}", "level": "B"})
        bets.append({"type": "ワイド", "pattern": f"{h1} - {h4}", "level": "B"})
        bets.append({"type": "3連複", "pattern": f"{h1} - {h2} - {h3}", "level": "A"})
        bets.append({"type": "3連複", "pattern": f"{h1} - {h2} - {h4}", "level": "B"})

    return {"marks": prediction_marks, "bets": bets, "source": "Rule-based"}


def calculate_predictions(entries, model_name="gemini-3.8-flash"):
    if not entries: return {"marks": {}, "bets": []}
    horse_data_str = ""
    for e in entries:
        horse_data_str += f"馬番{e.horse_number}: {e.horse_name} ({e.sex_age}) 斤量{e.weight} 騎手:{e.jockey} 厩舎:{e.trainer} オッズ:{e.odds} 近走:{e.past_performance}\n"

    prompt = f"""
    あなたはプロの競馬予想家です。以下の地方競馬の出馬表データ（近走成績含む）を分析し、勝率の高い馬を予想して印と推奨買い目を出力してください。
    出力は必ず以下のJSONフォーマットのみで行い、マークダウンや解説文は一切含めないでください。
    【出馬表データ】\n{horse_data_str}
    【出力JSONフォーマットの例】
    {{"marks": {{"1": "◎", "2": "○"}}, "bets": [{{"type": "単勝", "pattern": "1", "level": "A"}}]}}
    """
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        if result_text.startswith("```json"): result_text = result_text.replace("```json", "").replace("```", "").strip()
        elif result_text.startswith("```"): result_text = result_text.replace("```", "").strip()
        prediction_data = json.loads(result_text)
        formatted_marks = {int(k): v for k, v in prediction_data.get("marks", {}).items() if str(k).isdigit()}
        return {"marks": formatted_marks, "bets": prediction_data.get("bets", []), "source": "AI"}
    except Exception as e:
        print(f"Gemini APIエラー（独自ロジックに切り替えます）: {e}")
        return calculate_rule_based_predictions(entries)