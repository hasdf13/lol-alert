import os
import time
import random
import requests
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service

# ===== 환경 변수 로드 (절대경로로 .env 지정) =====
load_dotenv(dotenv_path="/home/ubuntu/lol-alert/.env")
NICKNAME = os.getenv("LOL_NICKNAME", "햅햅비#0000")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # 초 단위

# 디버그 로그
print(f"✔ 설정 완료: NICKNAME={NICKNAME}, Webhook={'OK' if DISCORD_WEBHOOK_URL else 'MISSING'}")
# ===================================================

def format_nickname(name):
    return name.replace("#", "-")

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

# ✅ 관전 버튼 강제 클릭
def click_spectate_button(nickname):
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-gpu")
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.binary_location = "/home/ubuntu/chrome-linux/chrome"

        service = Service("/usr/local/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)

        formatted_name = format_nickname(nickname)
        url = f"https://www.fow.lol/find/kr/{formatted_name}"
        print(f"페이지 로딩 중... {url}")
        driver.get(url)
        time.sleep(3)

        try:
            button = driver.find_element(By.ID, "btnLiveGame")
            driver.execute_script("arguments[0].click();", button)
            print("✅ '게임 관전하기' 버튼 강제 클릭 완료")
        except:
            print("⚠ 버튼 클릭 실패 (DOM에 없음)")
        driver.quit()
    except Exception as e:
        print(f"❌ 버튼 클릭 중 오류: {e}")

# 인게임 정보 가져오기
def get_ingame_info(sid, puuid):
    url = f"https://www.fow.lol/api/livegame?sid={sid}&puuid={puuid}&region=kr&auto=1&_={random.randint(1000000,9999999)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print(f"DEBUG: Request failed with status {res.status_code}")
        return None

    # ✅ 응답 길이와 앞부분 출력
    print("DEBUG: Raw HTML length =", len(res.text))
    print("DEBUG: First 500 chars =", res.text[:500])

    soup = BeautifulSoup(res.text, "html.parser")

    # ✅ livegame_header 존재 여부 확인
    time_tag = soup.select_one(".livegame_header div")
    if time_tag:
        print(f"DEBUG: header_text = {time_tag.get_text(strip=True)}")
    else:
        print("DEBUG: livegame_header not found in parsed HTML")

    if not time_tag:
        return None  # livegame_header가 없으면 게임 중 아님

    header_text = time_tag.get_text(strip=True)

    # ✅ 시간 추출
    time_match = re.search(r"(\d+)분\s*(\d+)초", header_text)
    if not time_match:
        print("DEBUG: 시간 패턴 매칭 실패")
        return None
    current_time = int(time_match.group(1)) * 60 + int(time_match.group(2))

    # ✅ 모드
    mode_info = header_text.split(" ⁝ ")[0] if "⁝" in header_text else header_text

    # ✅ 챔피언 목록
    champs = [img["alt"].strip() for img in soup.find_all("img", alt=True) if len(img["alt"].strip()) > 1]
    champs = champs[:10]

    return {
        "mode": mode_info,
        "champs": champs,
        "time": current_time
    }



# ✅ Discord 알림
def send_discord_alert(message):
    print(f"📢 Discord 알림 시도: {message[:30]}...")  # 디버그용
    if not DISCORD_WEBHOOK_URL:
        print("⚠ Discord Webhook URL이 설정되지 않음")
        return
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        print(f"✅ Discord 응답 코드: {res.status_code}")
    except Exception as e:
        print(f"❌ Discord 알림 오류: {e}")

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
        click_spectate_button(NICKNAME)
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
