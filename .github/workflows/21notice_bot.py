# 21notice_bot.py  — 5분 스케줄용 원샷 실행 (번호만 바뀌면 알림)
import os, re, json, sys, requests
from bs4 import BeautifulSoup

TARGET_URL = "https://es.kgct.or.kr/es/sim_spot_info?status=2"
STATE_FILE = "state.json"

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
DEBUG     = os.getenv("DEBUG") == "1"
BOOTSTRAP = os.getenv("BOOTSTRAP_ON_START") == "1"
TIMEOUT   = 30

def send(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("[ERROR] TELEGRAM_BOT_TOKEN/CHAT_ID env가 없습니다.", file=sys.stderr)
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}
    if DEBUG: print("[DEBUG] sending:", data)
    r = requests.post(url, data=data, timeout=20)
    ok = False
    try:
        jr = r.json()
        ok = jr.get("ok") is True
    except Exception:
        jr = {"raw": r.text}
    print(f"[SEND] status={r.status_code} resp={jr}")
    return ok

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(s: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

def parse_first_number(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table")
    if not table:
        if DEBUG: print("[DEBUG] table not found")
        return None

    body_rows = table.select("tbody tr")
    if not body_rows:
        rows = table.select("tr")
        if rows and rows[0].find_all("th"):
            body_rows = rows[1:]
        else:
            body_rows = rows

    first_data_row = None
    for r in body_rows:
        tds = r.find_all("td")
        if tds:
            first_data_row = r
            break
    if not first_data_row:
        if DEBUG: print("[DEBUG] no data row")
        return None

    idx = 0
    thead = table.select_one("thead tr")
    if thead:
        headers = [re.sub(r"\s+", "", h.get_text(strip=True)) for h in thead.find_all(["th","td"])]
        for i, h in enumerate(headers):
            if h in ("번호",):
                idx = i
                break
    cells = first_data_row.find_all("td")
    if idx >= len(cells):
        idx = 0

    raw = cells[idx].get_text(" ", strip=True)
    m = re.search(r"\d+", raw)
    return m.group(0) if m else raw or None

def fetch_first_number() -> str | None:
    r = requests.get(
        TARGET_URL,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return parse_first_number(r.text)

def main():
    state = load_state()
    last_serial = state.get("last_serial")
    if DEBUG: print("[DEBUG] last_serial =", last_serial)

    try:
        current_serial = fetch_first_number()
    except Exception as e:
        print("[ERROR] fetch/parse failed:", repr(e))
        return 1

    if not current_serial:
        print("[WARN] 번호를 찾지 못했습니다.")
        return 0

    if last_serial is None:
        save_state({"last_serial": current_serial})
        if BOOTSTRAP:
            send(f"시작: 현재 최신 공지 번호 {current_serial}\n{TARGET_URL}")
        print("[INFO] bootstrap ->", current_serial)
        return 0

    if current_serial != str(last_serial):
        text = f"♻️ 공지 번호가 변경되었습니다\n현재 번호: {current_serial} (이전: {last_serial})\n{TARGET_URL}"
        print("[INFO] serial changed:", last_serial, "→", current_serial)
        send(text)
        save_state({"last_serial": current_serial})
    else:
        print("[DEBUG] no change")

    return 0

if __name__ == "__main__":
    sys.exit(main())
