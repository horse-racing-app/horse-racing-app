import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import json
import time
from database import SessionLocal, Race, RaceEntry

def fetch_and_save_races(target_url: str):
    db = SessionLocal()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    target_url = target_url.replace("/result.html", "/shutuba.html")

    try:
        response = requests.get(target_url, headers=headers, timeout=10)
        # ★修正：文字コード指定を一切やめ、生データ(content)を直接渡してBS4に完璧な自動判別をさせる
        soup = BeautifulSoup(response.content, "html.parser")

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

        race_table = soup.find("table", class_=re.compile(r"Shutuba_Table|RaceTable", re.I))
        rows = race_table.find_all("tr") if race_table else soup.find_all("tr")

        for row in rows:
            tds = row.find_all("td")
            if not tds: continue

            horse_a = row.find("a", href=re.compile(r"horse", re.I))
            if not horse_a: continue 
            horse_name = re.sub(r'\s+', '', horse_a.text.strip())
            
            horse_url = horse_a.get("href", "")
            if horse_url and not horse_url.startswith("http"):
                if "db.netkeiba.com" not in horse_url:
                    horse_url = "https://db.netkeiba.com" + horse_url
            
            jockey = "不明"
            trainer = "不明"
            for a in row.find_all("a"):
                href = a.get("href", "")
                if "jockey" in href: jockey = re.sub(r'[\s▲△☆◇★]', '', a.text.strip())
                if "trainer" in href: trainer = re.sub(r'\s+', '', a.text.strip())
            
            texts = [td.text.replace("\n", "").strip() for td in tds]
            
            horse_number = 0
            nums_found = []
            for t in texts:
                if re.match(r'^[0-9]+$', t):
                    nums_found.append(int(t))
            
            if len(nums_found) >= 2:
                horse_number = nums_found[1] 
            elif len(nums_found) == 1:
                horse_number = nums_found[0]
            
            if horse_number == 0 or horse_number in seen_horse_numbers: continue
            seen_horse_numbers.add(horse_number)
                
            sex_age = "不明"
            weight = "56.0"
            odds = 99.9
            is_cancel = False

            for t in texts:
                if "取消" in t or "除外" in t:
                    is_cancel = True
                
                if sex_age == "不明":
                    sa_match = re.search(r'([牡牝セせん]+[1-9][0-9]?)', t)
                    if sa_match: sex_age = sa_match.group(1)
                
                if weight == "56.0":
                    w_match = re.search(r'([4-7]\d\.\d)', t)
                    if w_match: weight = w_match.group(1)
            
            if not is_cancel:
                for t in reversed(texts):
                    o_match = re.search(r'^(\d{1,4}\.\d)$', t)
                    if o_match:
                        val = float(o_match.group(1))
                        if str(val) != weight:
                            odds = val
                            break

            new_entry = RaceEntry(
                race_id=new_race.id, horse_number=horse_number,
                horse_name=horse_name, jockey=jockey,
                weight=weight, odds=odds,
                sex_age=sex_age, trainer=trainer 
            )
            new_entry._horse_url = horse_url
            entries_to_add.append(new_entry)

        # ----------------近走成績の取得----------------
        past_data_map = {}
        if netkeiba_id:
            past_url = target_url.replace("/shutuba.html", "/shutuba_past.html")
            try:
                p_res = requests.get(past_url, headers=headers, timeout=10)
                # ★修正：content渡しに変更
                p_soup = BeautifulSoup(p_res.content, "html.parser")
                
                for row in p_soup.find_all("tr"):
                    tds = row.find_all(["td", "th"])
                    if not tds: continue
                    
                    h_num = 0
                    for td in tds[:3]:
                        txt = td.text.strip()
                        if txt.isdigit() and 1 <= int(txt) <= 18:
                            h_num = int(txt)
                            break
                            
                    if h_num > 0:
                        past_texts = []
                        for td in tds:
                            clean_text = re.sub(r'\s+', ' ', td.text).strip()
                            if re.search(r'\d{2,4}[\./]\d{1,2}[\./]\d{1,2}', clean_text):
                                past_texts.append(clean_text[:40]) 
                                
                        if past_texts: 
                            past_data_map[h_num] = " / ".join(past_texts[:3])
            except Exception as e:
                print("過去ページ一括取得エラー:", e)

        for entry in entries_to_add:
            if entry.horse_number in past_data_map:
                entry.past_performance = past_data_map[entry.horse_number]
            elif hasattr(entry, '_horse_url') and entry._horse_url:
                try:
                    h_res = requests.get(entry._horse_url, headers=headers, timeout=10)
                    # ★修正：content渡しに変更
                    h_soup = BeautifulSoup(h_res.content, "html.parser")
                    
                    past_texts = []
                    for tr in h_soup.find_all("tr"):
                        tds = tr.find_all("td")
                        if len(tds) >= 10:
                            date_txt = tds[0].text.strip()
                            if re.match(r'^\d{4}/\d{1,2}/\d{1,2}$', date_txt):
                                p_date = re.sub(r'^\d{4}/', '', date_txt) 
                                p_name = tds[4].text.strip()
                                p_pop = tds[10].text.strip()
                                p_rank = tds[11].text.strip()
                                
                                if not p_rank: p_rank = "-"
                                past_texts.append(f"{p_date} {p_name} {p_pop}人気 {p_rank}着")
                        
                        if len(past_texts) >= 3:
                            break

                    if past_texts:
                        entry.past_performance = " / ".join(past_texts)
                    time.sleep(0.5) 
                except Exception as e:
                    print("個別ページ取得エラー:", e)

        if not entries_to_add:
            return {"status": "error", "message": "出馬表データが見つかりませんでした。"}

        db.add_all(entries_to_add)
        db.commit() 
        return {"status": "success", "message": f"{course}{race_number}R「{race_name}」を取得しました！"}

    except Exception as e:
        db.rollback() 
        return {"status": "error", "message": f"エラー: {str(e)}"}
    finally:
        db.close()

def fetch_and_save_result(race_id: int):
    db = SessionLocal()
    try:
        race = db.query(Race).filter(Race.id == race_id).first()
        if not race or not race.netkeiba_id:
            return {"status": "error", "message": "レースIDが不明です。出馬表を再取得してください。"}

        result_url = f"https://nar.netkeiba.com/race/result.html?race_id={race.netkeiba_id}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(result_url, headers=headers, timeout=10)
        # ★修正：content渡しに変更
        soup = BeautifulSoup(response.content, "html.parser")

        payouts = {}
        pay_table = soup.find("table", class_=re.compile(r"Pay_Table_C|Payout", re.I))
        rows = pay_table.find_all("tr") if pay_table else soup.find_all("tr")

        for tr in rows:
            th = tr.find("th")
            if not th: continue
            type_name = th.text.strip()
            
            if type_name in ["単勝", "馬連", "ワイド", "3連複", "3連単"]:
                tds = tr.find_all("td")
                if len(tds) >= 2:
                    nums = [re.sub(r'\D+', '-', s).strip('-') for s in tds[0].stripped_strings]
                    moneys = [re.sub(r'[^\d,円]', '', s) for s in tds[1].stripped_strings]
                    
                    nums = [n for n in nums if n]
                    moneys = [m for m in moneys if m]
                    
                    if type_name not in payouts:
                        payouts[type_name] = []
                    
                    for n, m in zip(nums, moneys):
                        payouts[type_name].append({"pattern": n, "payout": m})

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