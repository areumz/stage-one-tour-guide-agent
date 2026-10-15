# contracts/

on-stage 에서 이 프로젝트가 실제로 쓰는 계약만 옮겨 둔 폴더다.
**구현은 이 폴더만 보고 진행하고 on-stage 저장소를 열지 않는다.**

## 출처

| 항목 | 값 |
| --- | --- |
| 저장소 | areumz/on-stage (읽기 전용 참고. 이 저장소에서 수정하지 않는다) |
| 브랜치 | main |
| 커밋 | e57361ae88a497bf25857a1ce2414862d84df841 |
| 추출일 | 2026-10-13 |
| 응답 확인 | https://on-stage-nine.vercel.app/api/artists |
| 재확인 | 2026-10-15 on-stage 통지: 위 커밋 이후 `types.ts`·`data.ts`·`api/artists/route.ts` 변경은 export 1줄뿐이라 응답 모양은 같다. 필드별 대조는 하지 않았다 |

## 파일

각 파일은 세 성격 중 하나 이상이다. 섞일 때는 섹션으로 구분한다.

- **[계약]** on-stage 의 실제 동작. 그대로 따른다.
- **[우리 규칙]** 이 프로젝트가 덧붙인 규칙. on-stage 에는 없다.
- **[요구사항]** on-stage 가 구현해야 하는 것. 아직 없을 수 있다.

| 파일 | 성격 |
| --- | --- |
| artists.py, artist_context.md, enums_and_constants.md, fixtures/artists_response.json | [계약] |
| guide_events.py, fixtures/guide_events_sample.json | [요구사항] (이 저장소가 소유하고 on-stage 가 따른다) |
| ui_actions.md | [요구사항] (액션 의미, on-stage 가 정할 값과 해야 할 일) |

## 규칙

1. 계약에 없는 정보가 필요하면 추측하지 않는다. 구현을 멈추고 "계약 갱신" 태스크를 따로 만든다.
2. 계약 갱신 태스크만 on-stage 를 읽을 수 있다. 읽은 뒤 이 README 의 출처 행과 해당 파일을 함께 고친다.
3. fixtures/ 의 골든 벡터는 임의로 고치지 않는다.

## 알려진 공백 (on-stage 의 현재 동작)

| 사실 | 영향 |
| --- | --- |
| `stats.cities` 는 shows 전체 행 수, `cities[]` 는 featured 공연만이다 | 도시 수는 `stats.cities`, 목록은 `cities[]`(대표 도시)로 말한다 |
| 전체 공연을 읽는 GET 엔드포인트가 없다 (`/api/shows` 는 POST 전용) | 에이전트는 `cities[]` 만 검색한다. 엔드포인트가 생기면 계약 갱신 후 `load_shows` 를 바꾼다 |
| `news` 는 고정 문자열이라 D-n 표현이 날짜와 맞지 않을 수 있다 | 날짜 근거로 쓰지 않고 `cities[].date` 로 계산한다 |
| `cities[].name` 은 한국어다 | 영문 도시명 별칭이 필요한지 확인한다 (설계 §12 #10) |
| `stats.tracks` 는 `artists.stat_tracks` 컬럼 값이라 `tracks.length` 와 다를 수 있다 (실제 응답: aurora 8 vs 4) | **해결 (2026-10-15):** 도시와 같은 규칙. 곡 수는 `totalTracks`(= `stats.tracks`), 목록은 `featuredTracks`("대표 곡")로 구분해 반환한다 (artist_context.md) |
