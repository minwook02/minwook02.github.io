# minwook02.github.io

포트폴리오 메인 사이트와 주식경제 대시보드를 함께 운영하는 GitHub Pages 저장소입니다.

## 구조

- `/`
  포트폴리오 메인 소개 페이지
- `/market/`
  금일 주식경제 브리핑 대시보드
- `/data/dashboard.json`
  시장 데이터 정적 스냅샷
- `.github/workflows/update-dashboard-data.yml`
  30분마다 데이터 갱신

## 로컬 미리보기

```powershell
cd C:\Users\403\stock-economy-dashboard
python generate_data.py
python app.py --open
```

메인 페이지는 `http://127.0.0.1:8765/`, 대시보드는 `http://127.0.0.1:8765/market/`입니다.

## 데이터 소스

- Yahoo Finance chart endpoint
- Google News RSS

## 비고

- GitHub Pages는 정적 호스팅만 가능하므로 `data/dashboard.json`을 주기적으로 생성해 사용합니다.
- 대시보드는 포트폴리오 메인에서 대표 프로젝트로 연결됩니다.
