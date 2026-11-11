# -*- coding: utf-8 -*-
"""
1단계: 직원 명단 -> 사람마다 고유 토큰/링크 생성 -> 매핑표(텍스트) 저장

사용법:
  1) employees.txt 파일에 전 직원의 "이메일,이름,팀"을 한 줄에 한 명씩 적는다.
     (팀을 모르면 비워둬도 된다: "이메일,이름,")
     '#'으로 시작하는 줄과 빈 줄은 무시된다.
  2) BASE_URL을 실제 쓸 도메인으로 바꾼다.
  3) python3 generate_links.py 실행.
  4) mapping_internal.txt(보안팀 전용, 토큰<->이름 연결 포함)와
     mailmerge_send_list.csv(메일 발송용, 이메일/이름/링크만)가 생성된다.

이 매핑표는 보안팀만 보관합니다. 메일 발송 자체는 이 스크립트가 하지 않고,
mailmerge_send_list.csv를 Outlook/M365 메일 병합이나 다른 발송 도구에 넣어 사용합니다.
"""
import csv
import os
import secrets

# ---- 설정 ----------------------------------------------------------
BASE_URL = "https://phish-train-0w8v.onrender.com/v/"   # 운영 도메인
EMPLOYEES_FILE = "employees.txt"   # 직원 명단 텍스트 파일 (이메일,이름,팀)
# ---------------------------------------------------------------------


def load_employees(path):
    """
    employees.txt를 읽어 (이메일, 이름, 팀) 리스트로 반환한다.
    형식: 한 줄에 "이메일,이름,팀" (팀은 생략 가능 -> "미지정"으로 채움)
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
            employees.append((email, name, team))
    return employees


def make_token() -> str:
    """추측 불가능한 무작위 토큰. 순번(1,2,3...)은 쓰지 않는다."""
    return secrets.token_urlsafe(8)  # 예: 'Qk3F9z1xN2A'


def main():
    employees = load_employees(EMPLOYEES_FILE)

    if not employees:
        raise SystemExit(f"{EMPLOYEES_FILE}에 직원이 한 명도 없습니다. 직원 명단을 채워주세요.")

    used_tokens = set()
    rows = []
    for email, name, team in employees:
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

    # ---- 보안팀 전용 매핑표 (텍스트 파일) ----
    # link를 맨 마지막 컬럼에 둔다: 메모장 등에서 줄 끝까지 긁어 복사해도
    # link 뒤에 다른 값이 붙어서 토큰이 오염되는 실수를 막기 위함.
    with open("mapping_internal.txt", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["email", "name", "team", "token", "link"])
        for r in rows:
            w.writerow([r["email"], r["name"], r["team"], r["token"], r["link"]])

    # ---- 발송용 CSV (메일 병합에 사용, 토큰 없이 링크만) ----
    with open("mailmerge_send_list.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["email", "name", "link"])
        for r in rows:
            w.writerow([r["email"], r["name"], r["link"]])

    print(f"총 {len(rows)}명 처리 완료.")
    print("생성 파일: mapping_internal.txt (보안팀 전용), mailmerge_send_list.csv (발송용)")


if __name__ == "__main__":
    main()
