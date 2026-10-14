# enum 값과 상수 [계약]

## 아티스트 slug

`aurora`, `velvet`, `nova`, `halo`, `lumen`, `echo`

런타임의 진실은 `/api/artists` 응답이며 에이전트는 응답에서 enum 을 만든다. 이 표는 확인용이다.

## 도시 code

- `cities[].code` 는 공연 도시 코드다 (예: `LA`, `LDN`, `SEO`, `TYO`, `BUS`).
- `cities[].name` 은 한국어다 (예: `로스앤젤레스`, `서울`, `도쿄`). 영문명 필드는 없다.
- 같은 도시라도 아티스트마다 date 가 다르다. 유니크 키는 (artist, city_code, show_date) 이다.

## 날짜

- `cities[].date` 는 `YYYY-MM-DD` 문자열이고 시간대 정보가 없다. 서버는 KST(`Asia/Seoul`) 날짜 기준으로 남은 일수를 계산한다.
