# -*- coding: utf-8 -*-
"""
1단계: 직원 명단 -> 사람마다 고유 토큰/링크 생성

사용법:
  1) employees.txt 파일에 전 직원의 "이메일,이름,팀"을 한 줄에 한 명씩 적는다.
     (팀을 모르면 비워둬도 된다: "이메일,이름,")
     '#'으로 시작하는 줄과 빈 줄은 무시된다.
  2) BASE_URL을 실제 쓸 도메인으로 바꾼다.
  3) python3 generate_links.py 실행.
  4) employees.txt에 "이메일,이름,팀,고유코드" 형태로 그 사람의 고유코드가
     팀 뒤에 자동으로 채워져 저장되고(스크립트가 실행마다 덮어씀. 직접 수정하지 말 것),
     mailmerge_send_list.csv(메일 발송용, 이메일/이름/링크만)와
     tokens.txt(고유코드만 한 줄에 하나씩, 이름/이메일 없음)가 생성된다.

메일 발송 자체는 이 스크립트가 하지 않고, mailmerge_send_list.csv를 Outlook/M365
메일 병합이나 다른 발송 도구에 넣어 사용합니다.

employees.txt와 mailmerge_send_list.csv에는 이름/이메일(개인정보)이 들어있으므로
로컬에만 보관한다. Render 등 외부에 올릴 때는 tokens.txt만 업로드한다
(track_server.py 참고).

토큰은 이메일별로 고정된다: employees.txt에 이미 그 이메일의 고유코드가 있으면
재실행해도 그대로 재사용하고, 새로 추가된 직원에게만 새 토큰을 발급한다. (링크 추측을
막기 위해 순번은 쓰지 않는다 - 순번은 /v/1, /v/2처럼 다른 사람 링크를 추측할 수 있게
해서 훈련 결과를 오염시킬 수 있음)
"""
import csv
import os
import secrets

# ---- 설정 ----------------------------------------------------------
BASE_URL = "https://phish-train-0w8v.onrender.com/v/"   # 운영 도메인
EMPLOYEES_FILE = "employees.txt"   # 직원 명단 텍스트 파일 (이메일,이름,팀,고유코드)
# ---------------------------------------------------------------------


def load_employees(path):
    """
    employees.txt를 읽어 (이메일, 이름, 팀, 기존 고유코드) 리스트로 반환한다.
    형식: 한 줄에 "이메일,이름,팀,고유코드" (팀은 생략 가능 -> "미지정"으로 채움,
    고유코드는 이 스크립트가 자동으로 채워주므로 처음에는 비워둬도 된다)
    '#'으로 시작하는 줄과 빈 줄은 건너뛴다.
    """
    if not os.path.exists(path):
        raise SystemExit(
            f"{path} 파일을 찾을 수 없습니다. "
            f"같은 폴더에 {path}를 만들고 '이메일,이름,팀' 형식으로 한 줄에 한 명씩 적어주세요."
        )

    employees = []
    with open(path, encoding="utf-8-sig") as f:
        for lineno, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2 or not parts[0] or not parts[1]:
                raise SystemExit(
                    f"{path} {lineno}번째 줄 형식 오류: '{raw_line.rstrip()}' "
                    f"(최소 '이메일,이름' 형식이어야 합니다)"
                )
            email, name = parts[0], parts[1]
            team = parts[2] if len(parts) >= 3 and parts[2] else "미지정"
            token = parts[3] if len(parts) >= 4 and parts[3] else None
            employees.append((email, name, team, token))
    return employees


def make_token() -> str:
    """추측 불가능한 무작위 토큰. 순번(1,2,3...)은 쓰지 않는다."""
    return secrets.token_urlsafe(8)  # 예: 'Qk3F9z1xN2A'


def rewrite_employees_file(path, rows):
    """
    employees.txt를 다시 써서 "이메일,이름,팀,고유코드" 형태로 고유코드를 채워 넣는다.
    주석('#') 줄과 빈 줄은 그대로 두고, 직원 데이터 줄만 (원래 순서 그대로) 갱신한다.
    """
    with open(path, encoding="utf-8-sig") as f:
        raw_lines = f.readlines()

    rows_iter = iter(rows)
    out_lines = []
    for raw_line in raw_lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            out_lines.append(stripped)
            continue
        r = next(rows_iter)
        out_lines.append(f"{r['email']},{r['name']},{r['team']},{r['token']}")

    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")


def main():
    employees = load_employees(EMPLOYEES_FILE)

    if not employees:
        raise SystemExit(f"{EMPLOYEES_FILE}에 직원이 한 명도 없습니다. 직원 명단을 채워주세요.")

    # 토큰 우선순위: employees.txt에 이미 적혀 있는 고유코드 -> 없으면 새로 발급.
    # (재실행해도 같은 사람은 같은 토큰을 유지한다)
    used_tokens = {t for *_, t in employees if t}
    reused = 0
    rows = []
    for email, name, team, existing_token in employees:
        token = existing_token
        if token:
            reused += 1
        else:
            while True:
                token = make_token()
                if token not in used_tokens:
                    used_tokens.add(token)
                    break
        link = BASE_URL + token
        rows.append({
            "email": email,
            "name": name,
            "team": team,
            "token": token,
            "link": link,
        })

    rewrite_employees_file(EMPLOYEES_FILE, rows)

    # ---- 발송용 CSV (메일 병합에 사용, 토큰 없이 링크만) ----
    with open("mailmerge_send_list.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["email", "name", "link"])
        for r in rows:
            w.writerow([r["email"], r["name"], r["link"]])

    # ---- Render 업로드용 고유코드 목록 (이름/이메일 없이 고유코드만) ----
    with open("tokens.txt", "w", newline="\n", encoding="utf-8") as f:
        f.write("\n".join(r["token"] for r in rows) + "\n")

    print(f"총 {len(rows)}명 처리 완료. (기존 토큰 재사용 {reused}명, 신규 발급 {len(rows) - reused}명)")
    print(f"생성/갱신 파일: {EMPLOYEES_FILE} (고유코드 채움, 로컬 보관), "
          f"mailmerge_send_list.csv (발송용, 로컬 보관), tokens.txt (Render 업로드용, 개인정보 없음)")


if __name__ == "__main__":
    main()
