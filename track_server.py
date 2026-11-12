# -*- coding: utf-8 -*-
"""
2단계: 링크 클릭 기록 서버.

- /v/<token> 으로 접속하면: 접속 시각과 토큰만 clicks.txt에 추가로 기록하고,
  화면에는 평범한 404(페이지 없음) 화면만 보여준다.
- 로그인 정보나 그 외 입력값은 전혀 받지 않는다. (화면에 입력창 자체가 없음)
- IP나 User-Agent 같은 부가 정보는 기본적으로 기록하지 않는다. 필요하면
  LOG_EXTRA = True 로 바꾸되, 꼭 필요한 최소 정보인지 먼저 검토할 것.
- 서버 시작 시 같은 폴더의 tokens.txt(generate_links.py가 만들어주는, 고유코드만
  한 줄에 하나씩 적힌 파일 - 이름/이메일 없음)를 읽어 "알고 있는 토큰" 목록을
  메모리에 올려둔다. 이 파일이 없으면 목록 없이 시작하며, 클릭 로그 자체는
  그래도 정상 기록된다.
- 클릭이 발생하면 콘솔에 "[클릭] 시각 - 코드: <토큰>" 형태로만 출력된다.
  (이름/이메일은 서버가 아예 알지 못하므로 로그/결과 파일 어디에도 나오지 않는다)
- 훈련 기간이 끝나면 이 서버를 Ctrl+C로 종료한다. 종료되는 순간
   clicks_list.xlsx 결과 파일을 만든다. (clicks.txt는 삭제)
  결과 파일에는 "고유코드,클릭여부,클릭날짜,클릭시각"만 들어있다. 어느 사람인지는
  이 파일을 받은 뒤 로컬의 employees.txt(이메일,이름,팀,고유코드)와 고유코드를
  기준으로 직접 대조해서 확인한다.

실행:
  pip install flask openpyxl   (이미 설치돼 있으면 생략)
  python3 track_server.py
  (훈련 기간 종료 후 Ctrl+C -> clicks_list.xlsx 자동 생성)

배포(Render 등):
  track_server.py와 tokens.txt만 올린다. employees.txt(이름/이메일이 들어있는
  파일)는 절대 올리지 않고 로컬에만 보관한다. 클릭 결과(clicks_list.xlsx)를
  내려받은 뒤 로컬 employees.txt와 고유코드로 매칭해서 누가 클릭했는지 확인한다.
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
TOKENS_FILE = "tokens.txt"  # 고유코드만 한 줄에 하나씩 (이름/이메일 없음)
REPORT_FILE = "clicks_list.xlsx"
LOG_EXTRA = False  # True로 바꾸면 user-agent도 같이 기록 (기본은 최소 수집)
KST = timezone(timedelta(hours=9))
KNOWN_TOKENS = []  # 서버 시작 시 채워짐: tokens.txt의 고유코드 목록 (순서 유지)

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
    if token in KNOWN_TOKENS:
        print(f"[클릭] {now_kst} - 코드: {token}", flush=True)
    else:
        print(f"[클릭] {now_kst} - 알 수 없는 코드: {token}", flush=True)

    return Response(NOT_FOUND_HTML, status=404, mimetype="text/html")


@app.errorhandler(404)
def generic_404(_e):
    # /v/ 뒤에 모르는 경로로 들어오거나 토큰이 없을 때도 같은 404 화면만 보여줌
    return Response(NOT_FOUND_HTML, status=404, mimetype="text/html")


@app.errorhandler(405)
def generic_405(_e):
    return Response(NOT_FOUND_HTML, status=404, mimetype="text/html")


def _load_tokens():
    """
    tokens.txt(고유코드만 한 줄에 하나씩 / '#' 주석, 빈 줄 무시)를 읽어
    고유코드 목록을 순서 그대로 반환한다. 이름/이메일은 이 파일에 없다.
    """
    if not os.path.exists(TOKENS_FILE):
        print(f"[경고] {TOKENS_FILE} 없음 - 코드 목록 없이 시작합니다(클릭 로그는 정상 기록됨).", flush=True)
        return []
    tokens = []
    with open(TOKENS_FILE, encoding="utf-8-sig") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            tokens.append(line)
    return tokens


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
    """
    서버 시작 시 로드해둔 코드 목록(KNOWN_TOKENS) + clicks.txt를 합쳐 clicks_list.xlsx를 만든다.
    이름/이메일은 서버가 모르므로 결과 파일에는 고유코드만 들어간다.
    누가 클릭했는지는 이 파일을 받은 뒤 로컬 employees.txt와 고유코드로 직접 대조한다.
    """
    tokens = KNOWN_TOKENS if KNOWN_TOKENS else _load_tokens()
    first_clicks = _load_first_clicks()

    total = len(tokens)
    clicked_n = 0
    data_rows = []
    for token in tokens:
        clicked_at_utc = first_clicks.get(token)
        clicked_date, clicked_time = _to_kst_parts(clicked_at_utc)
        clicked = "Y" if clicked_at_utc else "N"
        if clicked == "Y":
            clicked_n += 1
        data_rows.append([token, clicked, clicked_date, clicked_time])

    wb = Workbook()
    ws = wb.active
    ws.title = "clicks_list"
    ws.append([f"총 {total}명 중 {clicked_n}명 클릭"])
    ws.append([])
    ws.append(["고유코드", "클릭여부", "클릭날짜(KST)", "클릭시각(KST)"])
    for row in data_rows:
        ws.append(row)
    for col, width in zip("ABCD", (16, 10, 14, 12)):
        ws.column_dimensions[col].width = width

    wb.save(REPORT_FILE)

    if os.path.exists(CLICK_LOG_FILE):
        os.remove(CLICK_LOG_FILE)

    print(f"\n완료: {REPORT_FILE} 생성 (전체 {total}명 중 클릭 {clicked_n}명)")


if __name__ == "__main__":
    _ensure_header()
    KNOWN_TOKENS = _load_tokens()
    print(f"고유코드 {len(KNOWN_TOKENS)}개 로드 완료. 클릭이 발생하면 코드만 출력합니다.")
    try:
        # Render 등 PaaS는 PORT 환경변수로 쓸 포트를 알려준다. 로컬 테스트 시엔 8080 사용.
        port = int(os.environ.get("PORT", 8080))
        app.run(host="0.0.0.0", port=port, debug=False)
    except KeyboardInterrupt:
        pass
    finally:
        generate_report()