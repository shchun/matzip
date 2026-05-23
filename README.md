# 맛집 에이전트

내가 직접 저장한 맛집 근처에 오면 Slack으로 알려주고, Slack에서 지역명으로 맛집을 검색할 수 있는 개인 에이전트.

## 아키텍처

```
data/*.csv
    ↓  scripts/import_csv.py
PostgreSQL + PostGIS
    ↓
mcp/matzip_mcp.py  ← MCP 서버 (6개 도구)
    ↓
Hermes Agent (gpt-4o-mini)
    ↓
Slack 게이트웨이 (DM / 멘션 → 맛집 검색 응답)
         + 프로액티브 알림 (cron → check_and_notify)
```

## 주요 파일

| 경로 | 역할 |
|------|------|
| `mcp/matzip_mcp.py` | MCP 서버 — Hermes가 호출하는 맛집 Tool 모음 |
| `mcp/SOUL.md` | Hermes 에이전트 페르소나 (맛집 검색 행동 원칙) |
| `mcp/hermes_config_template.yaml` | `~/.hermes/config.yaml` MCP 설정 참고용 |
| `scripts/init.sql` | DB 스키마 (PostGIS extension + matzip 테이블) |
| `scripts/import_csv.py` | `data/*.csv` → DB 전체 재임포트 |
| `data/*.csv` | 맛집 데이터 (이름, 주소, 메모, 위도, 경도) |

## MCP 도구 목록

| 도구 | 설명 |
|------|------|
| `find_nearby` | 좌표 반경 내 맛집 검색 (결과 부족 시 1→2→5km 자동 확장) |
| `geocode_area` | 지역명 → 위도·경도 (Google Maps API) |
| `get_current_location` | 현재 위치 반환 (HOME_LAT/LNG 우선, 없으면 IP) |
| `reverse_geocode` | 위도·경도 → 지역명 |
| `get_area_clusters` | 맛집 밀집 지역 상위 5곳 (greedy hotspot 알고리즘) |
| `check_and_notify` | 근처 신규 맛집 확인 후 Slack 알림 |

## 빠른 시작

### 1. DB 실행

```powershell
docker compose up -d db
```

### 2. 데이터 임포트

```powershell
python scripts/import_csv.py
```

### 3. Hermes Agent 설정

```powershell
# Hermes 설치 (이미 설치됐다면 skip)
# https://github.com/nousresearch/hermes-agent

# config.yaml에 MCP 서버 추가 (mcp/hermes_config_template.yaml 참고)
# ~/.hermes/.env에 API 키 및 Slack 토큰 설정
```

### 4. Slack 게이트웨이 실행

```powershell
hermes gateway setup   # 최초 1회
hermes gateway start
```

## 환경변수 (`.env`)

| 변수 | 설명 |
|------|------|
| `SLACK_BOT_TOKEN` | `xoxb-` Bot Token |
| `SLACK_APP_TOKEN` | `xapp-` App-Level Token (Socket Mode) |
| `SLACK_CHANNEL` | 프로액티브 알림 채널 ID |
| `GOOGLE_MAPS_API_KEY` | 지오코딩용 Google Maps API 키 |
| `HOME_LAT` / `HOME_LNG` | 고정 위치 (설정 시 IP 위치 대신 사용) |
| `PROXIMITY_RADIUS_METERS` | 알림 반경 (기본 500m) |

## Slack 앱 설정

- **OAuth Scopes**: `chat:write`, `im:history`
- **Event Subscriptions**: `app_mention`, `message.im`
- **Socket Mode**: 활성화 + App-Level Token 발급

## 로그 확인

```powershell
# MCP 서버 도구 호출 로그 실시간 확인
Get-Content "$env:USERPROFILE\AppData\Local\hermes\logs\mcp-stderr.log" -Wait

# Hermes 에이전트 로그
Get-Content "$env:USERPROFILE\AppData\Local\hermes\logs\agent.log" -Wait
```

## 데이터 재임포트

```powershell
# data/ 폴더의 모든 CSV를 DB에 재임포트 (기존 데이터 전체 교체)
python scripts/import_csv.py
```

## 주의사항

- `.env`는 절대 커밋하지 말 것 (`.gitignore`에 포함)
- MCP 서버는 `mcp/.venv` 가상환경 사용 (`mcp/requirements.txt`)
- Hermes config는 `~/.hermes/config.yaml` (프로젝트 외부)
