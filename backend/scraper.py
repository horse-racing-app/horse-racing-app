import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import json
from database import SessionLocal, Race, RaceEntry

def fetch_and_save_races(target_url: str):
    db = SessionLocal()
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(target_url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding 
        soup = BeautifulSoup(response.text, "html.parser")

        netkeiba_id = None
        id_match = re.search(r'race_id=(\d+)', target_url)
        if id_match:
            netkeiba_id = id_match.group(1)

        title_text = soup.title.text if soup.title else ""
        date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', title_text)
        if date_match: race_date = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
        else: race_date = datetime.now().strftime("%Y-%m-%d")

        course = "不明"
        race_number = 1
        course_match = re.search(r'([一-龥]+)(\d+)R', title_text)
        if course_match:
            course = course_match.group(1)
            race_number = int(course_match.group(2))

        race_name = "不明なレース"
        race_name_elem = soup.find(class_=re.compile(r"RaceName", re.I))
        if race_name_elem: race_name = race_name_elem.text.strip()
        
        distance = 1400
        race_data_elem = soup.find(class_=re.compile(r"RaceData", re.I))
        if race_data_elem:
            distance_match = re.search(r'(\d+)m', race_data_elem.text)
            if distance_match: distance = int(distance_match.group(1))

        existing_race = db.query(Race).filter(
            Race.date == race_date, Race.course == course, Race.race_number == race_number
        ).first()
        if existing_race:
            db.delete(existing_race)
            db.flush()

        new_race = Race(
            netkeiba_id=netkeiba_id,
            date=race_date, course=course, race_number=race_number, 
            name=race_name, distance=distance, condition="良" 
        )
        db.add(new_race)
        db.flush() 

        entries_to_add = []
        seen_horse_numbers = set() 

        for row in soup.find_all("tr"):
            horse_a = row.find("a", href=re.compile(r"horse", re.I))
            if not horse_a: continue 
            horse_name = re.sub(r'\s+', '', horse_a.text.strip())
            
            jockey = "不明"
            jockey_a = row.find("a", href=re.compile(r"jockey", re.I))
            if jockey_a: 
                jockey = re.sub(r'[\s▲△☆◇★]', '', jockey_a.text.strip())
            
            horse_number = 0
            umaban_td = row.find(class_=re.compile(r"Umaban|Num", re.I))
            if umaban_td:
                nums = re.findall(r'\d+', umaban_td.text)
                if nums: horse_number = int(nums[0])
            
            if horse_number == 0 or horse_number in seen_horse_numbers: continue
            seen_horse_numbers.add(horse_number)
                
            # ★ 斤量の取得（より安全に）
            weight = "56.0"
            weight_td = row.find(class_=re.compile(r"Jindai|Weight", re.I))
            if weight_td:
                w = re.search(r'(\d+\.\d+)', weight_td.text)
                if w: weight = w.group(1)
            else:
                for td in row.find_all("td"):
                    w = re.search(r'(\d+\.\d+)', td.text)
                    if w:
                        weight = w.group(1)
                        break

            sex_age = "不明"
            for td in row.find_all("td"):
                match = re.search(r'([牡牝セ][2-9])', td.text)
                if match: sex_age = match.group(1); break
            
            trainer = "不明"
            trainer_a = row.find("a", href=re.compile(r"trainer", re.I))
            if trainer_a: trainer = re.sub(r'\s+', '', trainer_a.text.strip())
                
            # ==========================================
            # ★ 修正：オッズの取得（結果確定後のページにも対応）
            # ==========================================
            odds = 99.9
            odds_td = row.find(class_=re.compile(r"Odds", re.I))
            if odds_td:
                o = re.search(r'(\d+\.\d+)', odds_td.text)
                if o: odds = float(o.group(1))
            
            # クラス名で見つからなかった場合（すでに結果が出ているページなど）
            # テーブルの後ろ（右側）からセルを確認し、斤量とは違う小数をオッズとして強制取得
            if odds == 99.9:
                for td in reversed(row.find_all("td")):
                    txt = re.sub(r'\s+', '', td.text)
                    o = re.search(r'(\d+\.\d+)', txt)
                    if o:
                        val = float(o.group(1))
                        # 斤量と同じ数字を間違えて拾わないようにする
                        if str(val) != weight:
                            odds = val
                            break

            new_entry = RaceEntry(
                race_id=new_race.id, horse_number=horse_number,
                horse_name=horse_name, jockey=jockey,
                weight=weight, odds=odds,
                sex_age=sex_age, trainer=trainer 
            )
            entries_to_add.append(new_entry)

        # 近走成績の取得
        if netkeiba_id:
            past_url = f"https://nar.netkeiba.com/race/shutuba_past.html?race_id={netkeiba_id}"
            try:
                p_res = requests.get(past_url, headers=headers, timeout=10)
                p_res.encoding = p_res.apparent_encoding
                p_soup = BeautifulSoup(p_res.text, "html.parser")
                
                past_data_map = {}
                for row in p_soup.find_all("tr", class_=re.compile(r"HorseList")):
                    num_td = row.find(class_=re.compile(r"Umaban|Num"))
                    if num_td:
                        nums = re.findall(r'\d+', num_td.text)
                        if nums:
                            h_num = int(nums[0])
                            past_texts = []
                            for past_td in row.find_all("td", class_=re.compile(r"Past")):
                                clean_text = re.sub(r'\s+', ' ', past_td.text).strip()
                                if clean_text and len(clean_text) > 5:
                                    past_texts.append(clean_text[:40]) 
                            past_data_map[h_num] = " / ".join(past_texts[:3])
                
                for entry in entries_to_add:
                    if entry.horse_number in past_data_map:
                        entry.past_performance = past_data_map[entry.horse_number]
            except Exception as e:
                print(f"前走データの取得エラー: {e}")

        if not entries_to_add:
            raise ValueError("出馬表のデータが抽出できませんでした。")

        db.add_all(entries_to_add)
        db.commit() 
        return {"status": "success", "message": f"{course}{race_number}R「{race_name}」のデータを取得しました！"}

    except Exception as e:
        db.rollback() 
        return {"status": "error", "message": f"エラー: {str(e)}"}
    finally:
        db.close()

def fetch_and_save_result(race_id: int):
    # (既存のコードそのまま)
    db = SessionLocal()
    try:
        race = db.query(Race).filter(Race.id == race_id).first()
        if not race or not race.netkeiba_id:
            return {"status": "error", "message": "レースIDが不明です。出馬表を再取得してください。"}

        result_url = f"https://nar.netkeiba.com/race/result.html?race_id={race.netkeiba_id}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(result_url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")

        payouts = {}
        for tr in soup.find_all("tr"):
            th = tr.find("th")
            if not th: continue
            type_name = th.text.strip()
            
            if type_name in ["単勝", "馬連", "ワイド", "3連複", "3連単"]:
                tds = tr.find_all("td")
                if len(tds) >= 2:
                    num_str = re.sub(r'\D+', '-', tds[0].text.strip()).strip('-')
                    money_str = re.sub(r'[^\d,円]', '', tds[1].text.strip())
                    
                    if type_name not in payouts:
                        payouts[type_name] = []
                    payouts[type_name].append({"pattern": num_str, "payout": money_str})

        if not payouts:
            return {"status": "error", "message": "レース結果がまだ公開されていないか、取得できませんでした。"}

        race.result_json = json.dumps(payouts, ensure_ascii=False)
        db.commit()
        return {"status": "success", "message": "レース結果と配当を取得しました！", "data": payouts}

    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"エラー: {str(e)}"}
    finally:
        db.close()