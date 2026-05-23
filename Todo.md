# Todo

## Cloud Run 배포

- [ ] `app/Dockerfile` Cloud Run 호환 확인 (포트 8080 불필요 — Socket Mode라 HTTP 서버 없음)
- [ ] GCP 프로젝트 설정 및 `gcloud` CLI 인증
- [ ] Artifact Registry에 Docker 이미지 push
- [ ] Cloud Run 서비스 생성 (환경변수로 `.env` 값 주입)
- [ ] PostgreSQL → Cloud SQL (PostgreSQL 15 + PostGIS) 또는 외부 DB 연결
- [ ] DB `DATABASE_URL` Cloud SQL 연결 문자열로 교체
- [ ] 항상 실행 상태 유지 설정 (최소 인스턴스 1 — WebSocket 유지 필요)

## 카카오 로컬 API 지오코딩

- [ ] 카카오 개발자 앱에서 서버 플랫폼 등록 (도메인 제한 없는 REST API 사용)
- [ ] `KAKAO_REST_API_KEY` 환경변수 추가 (`docker-compose.yml`, Cloud Run)
- [ ] `bot.geocode_area()` Nominatim → 카카오 키워드 검색 API로 교체
  - endpoint: `https://dapi.kakao.com/v2/local/search/keyword.json`
  - 응답: `documents[0].x`(경도), `documents[0].y`(위도)
- [ ] 테스트 mock 카카오 응답 형식으로 업데이트
