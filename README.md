# Smart Construction Briefing

스마트건설·건설 AI·AX·DX 데일리 브리핑을 같은 URL에서 제공하는 정적 웹앱입니다.

## 구조

- `index.html`: 브리핑 화면과 날짜·분야 필터
- `data/briefings.json`: 날짜별 브리핑 누적 데이터

## 매일 업데이트

매일 오전 6시 브리핑 생성 후 `data/briefings.json` 배열 맨 앞에 새 날짜 객체를 추가하고 `main` 브랜치에 반영합니다. GitHub Pages가 같은 주소에 최신 내용을 자동 배포합니다.

기존 날짜 데이터는 삭제하지 않고 계속 보관합니다.
