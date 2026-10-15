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
- `stats.countries` = 국가 중복 제거 수
- `stats.tracks` = `artists.stat_tracks` 컬럼 값. **`tracks[]` 길이와 다를 수 있다** (실제 응답: aurora 8 vs 4, velvet 6 vs 3). **곡 수 규칙 (도시와 같다):** `getArtist` 는 `stats.tracks` 를 `totalTracks` 로, `tracks[]` 의 제목 목록을 `featuredTracks` 로 구분해 돌려준다. "몇 곡이야?" 는 `totalTracks` 로 답하고, 곡 목록은 "대표 곡"이라고 밝혀 말하며 전체 목록처럼 말하지 않는다
- `cities[].date` = DB `show_date` 그대로(YYYY-MM-DD), `cities[].name` = `city_name`(한국어)
- 응답의 모든 필드는 non-null 이다. 비어 있을 수 있는 DB 컬럼은 on-stage 변환 단계에서 `""` 로 바뀐다 (2026-10-15 on-stage 통지)

## 응답

| 요청 | 200 응답 |
| --- | --- |
| `GET /api/artists` | `{ "artists": Artist[] }` |
| `GET /api/artists?slug=<slug>` | `{ "artist": Artist }` (404 `{ "error": "not found" }`) |

`gallery`, `shader`, `color`, `initials`, `orbit`, `angle`, `size` 는 에이전트가 쓰지 않는다. 에이전트의 Pydantic 모델은 모르는 필드를 **무시한다** (`extra` 기본값). 실제 응답 fixture 가 이 필드들을 포함한 채 파싱된다.
