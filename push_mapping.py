# -*- coding: utf-8 -*-
"""
mapping_internal.txt를 Render 등에 올라가 있는 track_server.py로 전송한다.

mapping_internal.txt 파일 자체는 서버에 배포하지 않고(테스트마다 토큰이 바뀌므로),
대신 이 스크립트로 /admin/mapping 엔드포인트에 매핑 내용만 그때그때 전달한다.
서버는 이걸 디스크에 저장하지 않고 메모리에만 들고 있는다(서버 재시작/슬립 시 사라짐
-> 매 테스트 시작 전에 이 스크립트를 다시 실행해야 한다).

사용법:
  1) Render 대시보드 -> 서비스 -> Environment에서 ADMIN_TOKEN 값을 설정해둔다
     (추측 불가능한 긴 랜덤 문자열 권장. 코드/저장소에는 절대 적지 않는다).
  2) 아래 환경변수를 설정하고 실행:
       SERVER_URL=https://phish-train-0w8v.onrender.com ADMIN_TOKEN=... python push_mapping.py
     (Windows PowerShell 예)
       $env:SERVER_URL="https://phish-train-0w8v.onrender.com"
       $env:ADMIN_TOKEN="서버에 설정한 값과 동일하게"
       python push_mapping.py
"""
import os
import sys
import urllib.error
import urllib.request

MAPPING_FILE = "mapping_internal.txt"


def main():
    server_url = os.environ.get("SERVER_URL", "").rstrip("/")
    admin_token = os.environ.get("ADMIN_TOKEN", "")

    if not server_url:
        raise SystemExit("SERVER_URL 환경변수가 없습니다. (예: https://phish-train-0w8v.onrender.com)")
    if not admin_token:
        raise SystemExit("ADMIN_TOKEN 환경변수가 없습니다. Render에 설정한 값과 동일하게 넣어주세요.")
    if not os.path.exists(MAPPING_FILE):
        raise SystemExit(f"{MAPPING_FILE}을 찾을 수 없습니다. 먼저 generate_links.py를 실행하세요.")

    with open(MAPPING_FILE, "rb") as f:
        body = f.read()

    req = urllib.request.Request(
        url=f"{server_url}/admin/mapping",
        data=body,
        method="POST",
        headers={
            "X-Admin-Token": admin_token,
            "Content-Type": "text/csv; charset=utf-8",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(resp.read().decode("utf-8", errors="replace").strip())
    except urllib.error.HTTPError as e:
        print(f"실패: HTTP {e.code}", file=sys.stderr)
        print(e.read().decode("utf-8", errors="replace").strip(), file=sys.stderr)
        raise SystemExit(1)
    except urllib.error.URLError as e:
        raise SystemExit(f"서버에 연결할 수 없습니다: {e}")


if __name__ == "__main__":
    main()
