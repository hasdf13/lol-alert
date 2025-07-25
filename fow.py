import requests
import time
from bs4 import BeautifulSoup
import re
import os

# ===== 설정 =====
NICKNAME = os.getenv("LOL_NICKNAME", "햅햅비#0000")  # Render 환경변수에서 가져옴
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "10"))  # 초
# =================

def format_nickname(name):
    return name.replace("#", "-")

def get_sid_puuid(nickname):
    formatted_name = format_nickname(nickname)
    url = f"https://www.fow.lol/find/kr/{formatted_name}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print("닉네임 검색 실패")
        return None, None

    match = re.search(r"sid=(\d+)&puuid=([\w\-]+)&", res.text)
    if match:
        return match.group(1), match.group(2)
    return None, None

def get_ingame_info(sid, puuid):
    url = f"https://www.fow.lol/api/livegame?sid={sid}&puuid={puuid}&region=kr&auto=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        return None

    soup = BeautifulSoup(res.text, "html.parser")
    full_text = soup.get_text().strip()

    # 시간 패턴으로 인게임 여부 확인
    if not re.search(r"\d+분 \d+초", full_text):
        return None  # 인게임 아님

    lines = [line.strip() for line in full_text.split("\n") if line.strip()]
    mode_info = lines[0] if lines else "알 수 없음"

    # 시간 추출 (초 단위)
    time_match = re.search(r"(\d+)분 (\d+)초", mode_info)
    current_time = int(time_match.group(1)) * 60 + int(time_match.group(2)) if time_match else 0

    champs = [img["alt"].strip() for img in soup.find_all("img", alt=True) if len(img["alt"].strip()) > 1]
    champs = champs[:10]

    return {"mode": mode_info, "champs": champs, "time": current_time}

def send_discord_alert(message):
    if not DISCORD_WEBHOOK_URL:
        print("⚠ Discord Webhook URL이 설정되지 않음")
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print(f"Discord 알림 오류: {e}")

def main():
    print(f"✔ {NICKNAME} 인게임 감지 시작...")
    sid, puuid = get_sid_puuid(NICKNAME)
    if not sid or not puuid:
        print("sid/puuid 가져오기 실패")
        return

    print(f"✔ sid: {sid}, puuid: {puuid}")
    last_signature = None
    last_time = None
    
    print("✔ Script started. Monitoring...")
    
    while True:
        info = get_ingame_info(sid, puuid)
        if info:
            signature = info['mode'] + "-" + ",".join(info['champs'])
            current_time = info['time']

            # 새 게임 시작 조건
            if signature != last_signature or (last_time and current_time < last_time):
                msg = f"🔥 새 게임 시작!\n모드: {info['mode']}\n챔피언: {', '.join(info['champs']) if info['champs'] else '정보 없음'}"
                print(msg)
                send_discord_alert(msg)
                last_signature = signature

            last_time = current_time
        else:
            print("아직 게임 중이 아님...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
