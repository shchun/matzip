# Hermes 맛집 에이전트

저장된 맛집 DB를 기반으로 현재 위치 근처에 있으면 Slack 알림을 보내고, Slack DM·멘션으로 지역명 검색에 응답하는 개인용 에이전트.

## 아키텍처

```
main.py
 ├── agent.run()      # 스레드: 60초마다 위치 체크 → 근처 맛집 → Slack 알림
 └── bot.start()      # 메인: Slack Socket Mode WebSocket (blocking)
```

- **DB**: PostgreSQL 15 + PostGIS 3.4 (공간 쿼리: `ST_DWithin`, `ST_MakePoint`)
- **위치**: `HOME_LAT`/`HOME_LNG` 환경변수 우선, 없으면 ip-api.com (도시 수준)
- **지오코딩**: Nominatim (`"{area} 대한민국"`) — 구·동·역 전국 검색
- **Slack**: Socket Mode (공개 URL 불필요), `SLACK_APP_TOKEN`(xapp-) 필요

## 주요 파일

| 파일 | 역할 |
|------|------|
| `app/agent.py` | 위치 루프, `find_nearby`, `send_slack`, `haversine` |
| `app/bot.py` | Slack 이벤트 핸들러, `parse_area`, `geocode_area`, `build_blocks` |
| `app/main.py` | 진입점 — agent 스레드 + bot 시작 |
| `scripts/init.sql` | DB 스키마 (PostGIS extension + matzip 테이블) |
| `scripts/import_csv.py` | `data/*.csv` → DB 전체 재임포트 |
| `data/*.csv` | 맛집 데이터 (순번, 이름, 주소, 메모, 위도, 경도, 등록일) |

## 개발 환경 시작

```bash
# DB + 에이전트 실행
docker compose up -d

# DB만 (로컬 개발용)
docker compose up -d db

# 에이전트 로그 확인
docker compose logs -f agent

# CSV 데이터 재임포트
python scripts/import_csv.py
```

## 테스트

```bash
pip install -r requirements-test.txt
pytest                    # DB 없으면 통합 테스트 자동 skip
pytest -k "not needs_db"  # 단위 테스트만
```

- DB 통합 테스트: `docker compose up -d db` 후 실행
- `tests/conftest.py`에서 환경변수 기본값 설정 (실제 토큰 불필요)
- `DB_URL`: `postgresql://hermes:hermes1234@localhost:5432/hermes`

## 환경 변수 (`.env`)

`.env.example` 참고. 필수값:

| 변수 | 설명 |
|------|------|
| `SLACK_BOT_TOKEN` | `xoxb-` 로 시작하는 Bot Token |
| `SLACK_APP_TOKEN` | `xapp-` 로 시작하는 App-Level Token (Socket Mode용, `connections:write` 스코프) |
| `SLACK_CHANNEL` | 프로액티브 알림을 보낼 채널 ID 또는 이름 |
| `HOME_LAT` / `HOME_LNG` | 고정 위치 좌표 (설정 시 IP 위치 대신 사용) |

## Slack 앱 설정 요구사항

- **OAuth Scopes**: `chat:write`, `im:history`
- **Event Subscriptions**: `app_mention`, `message.im`
- **App Home**: Messages Tab 활성화
- **Socket Mode**: 활성화 + App-Level Token 발급

## 주의사항

- `.env`는 절대 커밋하지 말 것 (`.gitignore`에 포함)
- `bot.py`에서 `App(token=...)`은 `start()` 안에서 생성 — 모듈 임포트 시 auth.test 호출 방지 (테스트 가능하게)
- `find_with_expanding_radius()`: 결과 < 3개면 1km → 2km → 5km 자동 확장
- CSV 파일명 필터: 한글·영문·숫자만 허용 (`_valid_filename()`), 인코딩 깨진 파일 제외
