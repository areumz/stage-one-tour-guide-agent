# 아티스트 컨텍스트 [계약]

출처: on-stage `GET /api/artists` (README.md 의 출처 커밋 기준).

에이전트는 Supabase 를 읽지 않는다. `GET {ONSTAGE_URL}/api/artists` 한 응답만 쓴다.

## 에이전트가 쓰는 부분집합

| 필드 | 타입 | 용도 |
| --- | --- | --- |
| `slug` | string | 아티스트 식별. 도구 입력·액션의 enum 원천 |
| `name` | string | 영문 대문자 표기 |
| `nameKo` | string | 한글 표기 |
| `news` | string | 참고 문구. 날짜 표현은 근거로 쓰지 않는다 |
| `tour.badge`, `tour.titleKo`, `tour.year` | string, string, int | 투어명 |
| `stats.cities` | int | **shows 전체 행 수.** 답변의 도시 수 기준 |
| `stats.countries`, `stats.tracks` | int | |
| `cities[].code` | string | 도시 코드. 도구 입력·`highlightCity` 의 enum 원천 |
| `cities[].name` | string | 한국어 도시명 |
| `cities[].date` | string(YYYY-MM-DD) | 공연일 |
| `tracks[].no`, `title`, `duration` | int, string, string | 트랙 |

## 의미 (on-stage `src/lib/data.ts` 기준)

- `stats.cities` = `shows` 테이블의 해당 아티스트 전체 행 수
- `cities[]` = 그중 `featured = true` 인 공연 (A탭 투어 오빗 노출 대상)

## 응답

| 요청 | 200 응답 |
| --- | --- |
| `GET /api/artists` | `{ "artists": Artist[] }` |
| `GET /api/artists?slug=<slug>` | `{ "artist": Artist }` (404 `{ "error": "not found" }`) |

`gallery`, `shader`, `color`, `initials`, `orbit`, `angle`, `size` 는 에이전트가 쓰지 않는다.
