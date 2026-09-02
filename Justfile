backend_dir := "washmycup-backend"
frontend_dir := "washmycup-app"
python := backend_dir / "venv/bin/python"

# 사용 가능한 명령어 목록 보기
default:
    @just --list

# --- 최초 1회 설정 ---

# 백엔드 가상환경 생성 + 패키지 설치 + .env 준비
setup-backend:
    cd {{backend_dir}} && uv venv --python 3.12 venv
    uv pip install --python {{python}} -r {{backend_dir}}/requirements.txt
    test -f {{backend_dir}}/.env || cp {{backend_dir}}/.env.example {{backend_dir}}/.env

# 프론트엔드 패키지 설치
setup-frontend:
    cd {{frontend_dir}} && npm install

# 백엔드+프론트엔드 전체 설치
setup: setup-backend setup-frontend

# --- DB ---

# 마이그레이션 적용
migrate:
    {{python}} {{backend_dir}}/manage.py migrate

# 초기 시드 데이터 + 데모용 리뷰 생성
seed:
    {{python}} {{backend_dir}}/manage.py seed_locations --with-reviews

# Django Admin 계정 생성
superuser:
    {{python}} {{backend_dir}}/manage.py createsuperuser

# --- 실행 ---

# Django 개발 서버 실행 (8000번 포트 사용 중이면 안내 후 중단)
backend:
    #!/usr/bin/env bash
    set -euo pipefail
    if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
        echo "⚠️  8000번 포트가 이미 사용 중입니다:"
        lsof -nP -iTCP:8000 -sTCP:LISTEN
        echo "정리하려면: just kill-8000"
        exit 1
    fi
    {{python}} {{backend_dir}}/manage.py runserver

# Expo 개발 서버 실행 (QR 코드로 Expo Go에서 스캔)
frontend:
    cd {{frontend_dir}} && npx expo start

# AI 신뢰도 리포트 백그라운드 워커 (5분마다 리뷰 바뀐 위치만 재계산)
worker:
    {{python}} {{backend_dir}}/manage.py update_reliability

# 워커를 한 번만 돌리고 종료 (데모 직전 강제 갱신용)
worker-once:
    {{python}} {{backend_dir}}/manage.py update_reliability --once

# 8000번 포트를 점유한 프로세스 종료
kill-8000:
    lsof -ti TCP:8000 -sTCP:LISTEN | xargs -r kill
