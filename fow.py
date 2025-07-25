import os
import time
import random
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# ===== 환경 변수 로드 =====
load_dotenv()
NICKNAME = os.getenv("LOL_NICKNAME", "햅햅비#0000")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # 초 단위
# ==========================

# ✅ 닉네임 포맷 (햅햅비#0000 -> 햅햅비-0000)
def format_nickname(name):
    return name.replace("#", "-")

# ✅ Selenium 크롬 설정
def create_driver():
    options = Options()
    options.add_argument("--headless=new")  # 최신 방식 headless
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--user-agent=Mozilla/5.0")
    options.add_argument("--user-data-dir=/tmp/chrome-profile-" + str(time.time()))
    driver = webdriver.Chrome(options=options)
    return driver

# ✅ sid, puuid 가져오기
def get_sid_puuid(nickname):
    formatted_name = format_nickname(nickname)
    url = f"https://www.fow.lol/find/kr/{formatted_name}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    match = re.search(r"sid=(\d+)&puuid=([\w\-]+)&", res.text)
    if match:
        return match.group(1), match.group(2)
    return None, None

# ✅ 관전 버튼 클릭
def click_spectate_button(driver, nickname):
    try:
        formatted_name = format_nickname(nickname)
        url = f"https://www.fow.lol/find/kr/{formatted_name}"
        print(f"페이지 로딩 중... {url}")
        driver.get(url)
        time.sleep(3)

        button = driver.find_element(By.CSS_SELECTOR, "#btnLiveGame")
        button.click()
        print("✅ '게임 관전하기' 버튼 강제 클릭 완료")
        time.sleep(3)
    except Exception as e:
        print(f"⚠ 관전 버튼 클릭 실패: {e}")

# ✅ 인게임 정보 가져오기 (Selenium page_source 활용)
def get_ingame_info(driver):
    html = driver.page_source
    if not html or len(html) < 100:
        print("DEBUG: page_source 비어있음")
        return None

    soup = BeautifulSoup(html, "html.parser")
    time_tag = soup.select_one(".livegame_header div")
    if not time_tag:
        print("DEBUG: livegame_header not found")
        return None

    header_text = time_tag.get_text(strip=True)
    print(f"DEBUG: header_text = {header_text}")

    # 시간 추출
    time_match = re.search(r"(\d+)분\s*(\d+)초", header_text)
    if not time_match:
        print("DEBUG: 시간 패턴 매칭 실패")
        return None
    current_time = int(time_match.group(1)) * 60 + int(time_match.group(2))

    # 모드
    mode_info = header_text.split(" ⁝ ")[0] if "⁝" in header_text else header_text

    # 챔피언 목록
    champs = [img["alt"].strip() for img in soup.find_all("img", alt=True) if len(img["alt"].strip()) > 1]
    champs = champs[:10]

    return {
        "mode": mode_info,
        "champs": champs,
        "time": current_time
    }

# ✅ Discord 알림
def send_discord_alert(message):
    if not DISCORD_WEBHOOK_URL:
        print("⚠ Webhook URL이 설정되지 않음")
        return
    try:
        print(f"📢 Discord 알림 시도: {message[:50]}...")
        res = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        if res.status_code == 204:
            print("✅ Discord 알림 성공")
        else:
            print(f"❌ Discord 알림 실패 (status: {res.status_code})")
    except Exception as e:
        print(f"❌ Discord 알림 오류: {e}")

# ✅ 메인 로직
def main():
    print(f"✔ 설정 완료: NICKNAME={NICKNAME}, Webhook={'OK' if DISCORD_WEBHOOK_URL else 'None'}")
    sid, puuid = get_sid_puuid(NICKNAME)
    if not sid or not puuid:
        print("❌ sid/puuid 가져오기 실패")
        return

    print(f"✔ 햅햅비#0000 인게임 감지 시작...")
    print(f"✔ sid: {sid}, puuid: {puuid}")
    print("✔ Script started. Monitoring...")

    driver = create_driver()
    last_signature = None
    last_time = None
    game_active = False

    while True:
        # 관전 버튼 클릭
        click_spectate_button(driver, NICKNAME)
        info = get_ingame_info(driver)

        if info:
            signature = info['mode'] + "-" + ",".join(sorted(info['champs']))
            current_time = info['time']

            if not game_active or signature != last_signature or (last_time and current_time < last_time):
                msg = f"🔥 새 게임 시작!\n모드: {info['mode']}\n챔피언: {', '.join(info['champs'])}"
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
