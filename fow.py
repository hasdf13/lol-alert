import os
import time
import random
import requests
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===== 환경 변수 로드 =====
load_dotenv()
NICKNAME = os.getenv("LOL_NICKNAME", "햅햅비#0000")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # 초 단위
# ==========================

# 닉네임 포맷 변환 (햅햅비#0000 -> 햅햅비-0000)
def format_nickname(name):
    return name.replace("#", "-")

# sid, puuid 가져오기
def get_sid_puuid(nickname):
    formatted_name = format_nickname(nickname)
    url = f"https://www.fow.lol/find/kr/{formatted_name}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print("❌ 닉네임 검색 실패")
        return None, None

    match = re.search(r"sid=(\d+)&puuid=([\w\-]+)&", res.text)
    if match:
        return match.group(1), match.group(2)
    return None, None

# ✅ 관전 버튼 클릭 (Selenium)
def click_spectate_button(nickname):
    try:
        options = Options()
        options.add_argument("--headless")  # GUI 없이 실행
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--user-data-dir=/tmp/chrome-profile-" + str(time.time()))

        service = Service('/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=options)

        formatted_name = format_nickname(nickname)
        url = f"https://www.fow.lol/find/kr/{formatted_name}"
        print("페이지 로딩 중...")
        driver.get(url)

        # 버튼 로딩 대기
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "btnLiveGame")))
        button = driver.find_element(By.ID, "btnLiveGame")
        button.click()
        print("✅ '게임 관전하기 - 인게임 정보' 버튼 클릭 완료")

    except Exception as e:
        print(f"⚠ 버튼 클릭 실패: {e}")
    finally:
        driver.quit()

# 게임 정보 가져오기 (BeautifulSoup)
def get_ingame_info(sid, puuid):
    url = f"https://www.fow.lol/api/livegame?sid={sid}&puuid={puuid}&region=kr&auto=1&_={random.randint(1000000,9999999)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        return None

    soup = BeautifulSoup(res.text, "html.parser")
    full_text = soup.get_text().strip()

    # 인게임 여부 확인
    if not re.search(r"\d+분 \d+초", full_text):
        return None

    lines = [line.strip() for line in full_text.split("\n") if line.strip()]
    mode_info = lines[0] if lines else "알 수 없음"

    # 시간 추출
    time_match = re.search(r"(\d+)분 (\d+)초", full_text)
    current_time = int(time_match.group(1)) * 60 + int(time_match.group(2)) if time_match else 0

    champs = [img["alt"].strip() for img in soup.find_all("img", alt=True) if len(img["alt"].strip()) > 1]
    champs = champs[:10]

    return {"mode": mode_info, "champs": champs, "time": current_time}

# Discord 알림
def send_discord_alert(message):
    if not DISCORD_WEBHOOK_URL:
        print("⚠ Discord Webhook URL이 설정되지 않음")
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print(f"Discord 알림 오류: {e}")

# 메인 로직
def main():
    print(f"✔ {NICKNAME} 인게임 감지 시작...")
    sid, puuid = get_sid_puuid(NICKNAME)
    if not sid or not puuid:
        print("❌ sid/puuid 가져오기 실패")
        return

    print(f"✔ sid: {sid}, puuid: {puuid}")
    last_signature = None
    last_time = None
    game_active = False
    print("✔ Script started. Monitoring...")

    while True:
        # ✅ 관전 버튼 클릭 시도
        click_spectate_button(NICKNAME)

        # 2초 대기 후 인게임 정보 확인
        time.sleep(2)
        info = get_ingame_info(sid, puuid)

        if info:
            signature = info['mode'] + "-" + ",".join(sorted(info['champs']))
            current_time = info['time']

            if not game_active or signature != last_signature or (last_time and current_time < last_time):
                msg = f"🔥 새 게임 시작!\n모드: {info['mode']}\n챔피언: {', '.join(info['champs']) if info['champs'] else '정보 없음'}"
                print(msg)
                send_discord_alert(msg)
                last_signature = signature
                game_active = True

            last_time = current_time
        else:
            if game_active:
                print("✔ 게임 종료 감지")
                send_discord_alert("✔ 게임이 종료되었습니다.")
                game_active = False
            else:
                print("아직 게임 중이 아님...")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
