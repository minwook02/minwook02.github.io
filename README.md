# Stock Economy Dashboard

금일 주식경제 상황을 한눈에 보기 위한 GitHub Pages용 정적 사이트입니다.

## 기능

- 국내 지수: `KOSPI`, `KOSDAQ`
- 해외 지수: `S&P 500`, `NASDAQ`, `DOW`
- 거시 자산: `USD/KRW`, `미국 10년물`, `WTI`, `Gold`, `Bitcoin`
- 당일 흐름 라인 차트
- 핵심 시그널 요약
- 경제/증시 헤드라인 RSS
- `data/dashboard.json` 정적 데이터 로드
- GitHub Actions 주기 갱신

## 로컬 미리보기

```powershell
cd C:\Users\403\stock-economy-dashboard
python generate_data.py
python app.py --open
```

브라우저가 자동으로 열리지 않으면 `http://127.0.0.1:8765`로 접속하면 됩니다.

## GitHub Pages 배포 방식

- 사이트 파일은 루트 `index.html`과 `static/`에 있습니다.
- 데이터는 `generate_data.py`가 `data/dashboard.json`으로 생성합니다.
- `.github/workflows/update-dashboard-data.yml`가 30분마다 데이터를 갱신해 커밋합니다.

## 데이터 소스

- Yahoo Finance chart endpoint
- Google News RSS

## 참고

- 외부 네트워크 연결이 필요합니다.
- GitHub Pages는 정적 호스팅만 가능하므로 서버 대신 정적 JSON 갱신 방식으로 구성했습니다.
