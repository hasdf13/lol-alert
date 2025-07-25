import os
import time
import random
import re
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# ===== 환경 변수 로드 =====
load_dotenv()
NICKNAME = os.getenv("LOL_NICKNAME", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))
# ==========================

def format_nickname(name):
    return name.replace("#", "-")

# ✅ 관전 버튼 클릭 (Selenium)
def click_spectate_button(driver, nickname):
    try:
        formatted_name = format_nickname(nickname)
        url = f"https://www.fow.lol/find/kr/{formatted_name}"
        print(f"페이지 로딩 중... {url}")
        driver.get(url)
        time.sleep(3)

        button = driver.find_element(By.ID, "btnLiveGame")
        button.click()
        print("✅ '게임 관전하기' 버튼 강제 클릭 완료")
    except Exception as e:
        print(f"⚠ 관전 버튼 클릭 실패: {e}")

# ✅ 게임 정보 가져오기
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

    # ✅ 한글/영어 시간 패턴 지원
    time_match = re.search(r"(\d+)\s*(?:분|minutes?)\s*(\d+)\s*(?:초|seconds?)", header_text)
    if not time_match:
        print("DEBUG: 시간 패턴 매칭 실패")
        return None
    current_time = int(time_match.group(1)) * 60 + int(time_match.group(2))

    mode_info = header_text.split(" ⁝ ")[0] if "⁝" in header_text else header_text
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
        print("⚠ Discord Webhook URL이 설정되지 않음")
        return
    print(f"📢 Webhook URL: [{DISCORD_WEBHOOK_URL}]")  # 디버그용
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        print(f"📢 Discord 응답 코드: {response.status_code}")
        print(f"📢 Discord 응답 본문: {response.text}")
    except Exception as e:
        print(f"Discord 알림 오류: {e}")

# ✅ 메인 실행
def main():
    print(f"✔ 설정 완료: NICKNAME={NICKNAME}, Webhook={'OK' if DISCORD_WEBHOOK_URL else 'Missing'}")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--user-data-dir=/tmp/chrome-profile-" + str(time.time()))
    options.binary_location = "/home/ubuntu/chrome-linux/chrome"  # 서버용 Chrome 경로
    driver = webdriver.Chrome(options=options)

    sid = None
    last_signature = None
    last_time = None
    game_active = False

    while True:
        click_spectate_button(driver, NICKNAME)
        time.sleep(3)
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
