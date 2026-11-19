# -*- coding: utf-8 -*-
"""
2단계: 링크 클릭 기록 서버 (Render 무료 플랜용)

- /v/<token> 으로 접속하면: 접속 시각과 고유코드만 기록하고,
  화면에는 평범한 404(페이지 없음) 화면만 보여준다.
- 로그인 정보나 그 외 입력값은 전혀 받지 않는다. (화면에 입력창 자체가 없음)
- IP나 User-Agent 같은 부가 정보는 기본적으로 기록하지 않는다. 필요하면
  LOG_EXTRA = True 로 바꾸되, 꼭 필요한 최소 정보인지 먼저 검토할 것.
- 서버 시작 시 같은 폴더의 tokens.txt(generate_links.py가 만들어주는, 고유코드만
  한 줄에 하나씩 적힌 파일 - 이름/이메일 없음)를 읽어 "알고 있는 코드" 목록을
  메모리에 올려둔다. 이 파일이 없어도 클릭 기록 자체는 정상 동작한다.


"""
import os
from datetime import datetime, timedelta, timezone
from flask import Flask, Response, request, abort

app = Flask(__name__)

TOKENS_FILE = "tokens.txt"      # 고유코드만 한 줄에 하나씩 (이름/이메일 없음)
RESULTS_FILE = "results.txt"    # 클릭마다 "시각, 고유코드"를 한 줄씩 누적 기록
LOG_EXTRA = False               # True로 바꾸면 user-agent도 같이 기록 (기본은 최소 수집)
# /results/<KEY> 로 결과를 브라우저에서 보기 위한 비밀 키. 환경변수 RESULTS_KEY로 바꿀 수 있다.
RESULTS_KEY = os.environ.get("RESULTS_KEY", "changeme")
KST = timezone(timedelta(hours=9))
KNOWN_TOKENS = []               # 모듈 로드 시 tokens.txt에서 채워짐 (아래 _load_tokens 호출)

NOT_FOUND_HTML = """\
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>404 Not Found</title></head>
<body style="font-family:sans-serif;text-align:center;margin-top:15%;color:#555;">
<h1>404</h1><p>요청하신 페이지를 찾을 수 없습니다.</p>
</body></html>
"""


@app.route("/v/<token>")
def visit(token):
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    known = "" if token in KNOWN_TOKENS else " (알 수 없는 코드)"

    # (1) Render Logs 에 출력
    console_line = f"[클릭] {now_kst} - 코드: {token}{known}"
    if LOG_EXTRA:
        console_line += f" - UA: {request.headers.get('User-Agent', '')}"
    print(console_line, flush=True)

    # (2) results.txt 에 누적 (시각, 고유코드)
    file_line = f"{now_kst}, {token}{known}"
    if LOG_EXTRA:
        file_line += f", {request.headers.get('User-Agent', '')}"
    try:
        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
            f.write(file_line + "\n")
    except OSError as e:
        print(f"[경고] results.txt 기록 실패: {e}", flush=True)

    return Response(NOT_FOUND_HTML, status=404, mimetype="text/html")


@app.route("/results/<key>")
def show_results(key):
    """브라우저에서 결과를 확인하는 보호된 주소. 키가 틀리면 똑같은 404를 보여준다."""
    if key != RESULTS_KEY:
        abort(404)
    if not os.path.exists(RESULTS_FILE):
        body = "아직 클릭 기록이 없습니다."
    else:
        with open(RESULTS_FILE, encoding="utf-8") as f:
            body = f.read() or "아직 클릭 기록이 없습니다."
    return Response(body, status=200, mimetype="text/plain; charset=utf-8")


@app.errorhandler(404)
def generic_404(_e):
    return Response(NOT_FOUND_HTML, status=404, mimetype="text/html")


@app.errorhandler(405)
def generic_405(_e):
    return Response(NOT_FOUND_HTML, status=404, mimetype="text/html")


def _load_tokens():
    """tokens.txt(고유코드만 한 줄에 하나씩 / '#' 주석, 빈 줄 무시)를 읽어 목록으로 반환."""
    if not os.path.exists(TOKENS_FILE):
        print(f"[경고] {TOKENS_FILE} 없음 - 코드 목록 없이 시작합니다(클릭 기록은 정상 동작).", flush=True)
        return []
    tokens = []
    with open(TOKENS_FILE, encoding="utf-8-sig") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            tokens.append(line)
    return tokens


# 모듈이 import 되는 시점(= gunicorn으로 띄울 때 포함)에 고유코드 목록을 불러온다.
KNOWN_TOKENS = _load_tokens()
print(f"고유코드 {len(KNOWN_TOKENS)}개 로드 완료. 클릭이 발생하면 코드만 기록합니다.", flush=True)


if __name__ == "__main__":
    # `python3 track_server.py` 로 직접 실행할 때만 쓰는 개발용 서버.
    # Render 등 PaaS는 PORT 환경변수로 쓸 포트를 알려준다. 로컬 테스트 시엔 8080 사용.
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
