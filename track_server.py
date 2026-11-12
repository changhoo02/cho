# -*- coding: utf-8 -*-
"""
2단계: 링크 클릭 기록 서버.

- /v/<token> 으로 접속하면: 접속 시각과 토큰만 clicks.txt에 추가로 기록하고,
  화면에는 평범한 404(페이지 없음) 화면만 보여준다.
- 로그인 정보나 그 외 입력값은 전혀 받지 않는다. (화면에 입력창 자체가 없음)
- IP나 User-Agent 같은 부가 정보는 기본적으로 기록하지 않는다. 필요하면
  LOG_EXTRA = True 로 바꾸되, 꼭 필요한 최소 정보인지 먼저 검토할 것.
- 훈련 기간이 끝나면 이 서버를 Ctrl+C로 종료한다. 종료되는 순간
   clicks_list.xlsx 결과 파일을 만든다. (clicks.txt는 삭제)

실행:
  pip install flask openpyxl   (이미 설치돼 있으면 생략)
  python3 track_server.py
  (훈련 기간 종료 후 Ctrl+C -> clicks_list.xlsx 자동 생성)
"""
import csv
import logging
import os
from datetime import datetime, timedelta, timezone
from flask import Flask, Response, request
from openpyxl import Workbook

app = Flask(__name__)
logging.getLogger("werkzeug").setLevel(logging.ERROR)  # 기본 "GET /v/<토큰> 404" 로그 끄기

CLICK_LOG_FILE = "clicks.txt"  # 쉼표로 구분된 순수 텍스트(csv 포맷), 확장자만 .txt
EMPLOYEES_FILE = "employees.txt"  # 직원 명단 + 고유코드 (이메일,이름,팀,고유코드)
REPORT_FILE = "clicks_list.xlsx"
LOG_EXTRA = False  # True로 바꾸면 user-agent도 같이 기록 (기본은 최소 수집)
KST = timezone(timedelta(hours=9))
MAPPING_BY_TOKEN = {}  # 서버 시작 시 채워짐: token -> {email, name, team}

NOT_FOUND_HTML = """\
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>404 Not Found</title></head>
<body style="font-family:sans-serif;text-align:center;margin-top:15%;color:#555;">
<h1>404</h1><p>요청하신 페이지를 찾을 수 없습니다.</p>
</body></html>
"""


def _ensure_header():
    if not os.path.exists(CLICK_LOG_FILE):
        with open(CLICK_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            header = ["token", "clicked_at_utc"]
            if LOG_EXTRA:
                header.append("user_agent")
            w.writerow(header)


def _log_click(token: str, user_agent: str = ""):
    _ensure_header()
    with open(CLICK_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        row = [token, datetime.now(timezone.utc).isoformat()]
        if LOG_EXTRA:
            row.append(user_agent)
        w.writerow(row)


@app.route("/v/<token>")
def visit(token):
    ua = request.headers.get("User-Agent", "") if LOG_EXTRA else ""
    _log_click(token, ua)

    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    who = MAPPING_BY_TOKEN.get(token)
    if who:
        print(f"[클릭] {now_kst} - {who['name']} ({who['email']})", flush=True)
    else:
        print(f"[클릭] {now_kst} - 알 수 없는 토큰: {token}", flush=True)

    return Response(NOT_FOUND_HTML, status=404, mimetype="text/html")


@app.errorhandler(404)
def generic_404(_e):
    # /v/ 뒤에 모르는 경로로 들어오거나 토큰이 없을 때도 같은 404 화면만 보여줌
    return Response(NOT_FOUND_HTML, status=404, mimetype="text/html")


@app.errorhandler(405)
def generic_405(_e):
    return Response(NOT_FOUND_HTML, status=404, mimetype="text/html")


def _load_mapping():
    """
    employees.txt(이메일,이름,팀,고유코드 / '#' 주석, 빈 줄 포함)를 읽어
    매핑 리스트로 반환한다. 고유코드가 비어 있는 줄(아직 generate_links.py를
    안 돌려서 코드가 없는 사람)은 매핑에서 건너뛴다.
    """
    if not os.path.exists(EMPLOYEES_FILE):
        print(f"[경고] {EMPLOYEES_FILE} 없음 - 매핑 없이 시작합니다(클릭 로그는 정상 기록됨).", flush=True)
        return []
    mapping = []
    with open(EMPLOYEES_FILE, encoding="utf-8-sig") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4 or not parts[3]:
                continue
            email, name, team, token = parts[0], parts[1], parts[2], parts[3]
            mapping.append({"email": email, "name": name, "team": team, "token": token})
    return mapping


def _load_first_clicks():
    """토큰별 '가장 먼저 클릭한 시각(UTC, 원본 문자열)'을 반환한다."""
    first_click = {}
    if not os.path.exists(CLICK_LOG_FILE):
        return first_click
    with open(CLICK_LOG_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            token = row["token"]
            ts = row["clicked_at_utc"]
            if token not in first_click or ts < first_click[token]:
                first_click[token] = ts
    return first_click


def _to_kst_parts(utc_iso: str):
    """clicks.txt에 저장된 UTC ISO 시각을 한국 시간 (날짜, 시각) 문자열 쌍으로 바꾼다."""
    if not utc_iso:
        return "", ""
    dt = datetime.fromisoformat(utc_iso).astimezone(KST)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")


def generate_report():
    """서버 시작 시 로드해둔 매핑(MAPPING_BY_TOKEN) + clicks.txt를 합쳐 clicks_list.xlsx를 만든다."""
    mapping = list(MAPPING_BY_TOKEN.values()) if MAPPING_BY_TOKEN else _load_mapping()
    first_clicks = _load_first_clicks()

    total = len(mapping)
    clicked_n = 0
    data_rows = []
    for m in mapping:
        clicked_at_utc = first_clicks.get(m["token"])
        clicked_date, clicked_time = _to_kst_parts(clicked_at_utc)
        clicked = "Y" if clicked_at_utc else "N"
        if clicked == "Y":
            clicked_n += 1
        data_rows.append([m["email"], m["name"], m["team"], clicked, clicked_date, clicked_time])

    wb = Workbook()
    ws = wb.active
    ws.title = "clicks_list"
    ws.append([f"총 {total}명 중 {clicked_n}명 클릭"])
    ws.append([])
    ws.append(["email", "name", "team", "클릭여부", "클릭날짜(KST)", "클릭시각(KST)"])
    for row in data_rows:
        ws.append(row)
    for col, width in zip("ABCDEF", (28, 12, 12, 10, 14, 12)):
        ws.column_dimensions[col].width = width

    wb.save(REPORT_FILE)

    if os.path.exists(CLICK_LOG_FILE):
        os.remove(CLICK_LOG_FILE)

    print(f"\n완료: {REPORT_FILE} 생성 (전체 {total}명 중 클릭 {clicked_n}명)")


if __name__ == "__main__":
    _ensure_header()
    MAPPING_BY_TOKEN = {m["token"]: m for m in _load_mapping()}
    print(f"매핑 {len(MAPPING_BY_TOKEN)}명 로드 완료. 클릭이 발생하면 이름/이메일을 바로 출력합니다.")
    try:
        # Render 등 PaaS는 PORT 환경변수로 쓸 포트를 알려준다. 로컬 테스트 시엔 8080 사용.
        port = int(os.environ.get("PORT", 8080))
        app.run(host="0.0.0.0", port=port, debug=False)
    except KeyboardInterrupt:
        pass
    finally:
        generate_report()
