# 피부과/미용 클리닉 스크래핑 도구

이 패키지는 피부과 및 미용 클리닉 웹사이트에서 시술 정보를 자동으로 스크래핑하는 도구입니다.

## 설치

1. 필요한 의존성 설치:

```bash
pip install -r requirements.txt
```

2. Gemini API 키 설정:

```bash
export GEMINI_API_KEY='your-gemini-api-key-here'
```

## 사용법

```bash
python test_scraper.py
```

## 주요 기능

- 비동기 웹 크롤링으로 빠른 데이터 수집
- Google Gemini AI를 활용한 자동 데이터 추출
- 시술명, 가격, 설명 등 구조화된 데이터 수집
- JSON 형태로 결과 저장

## 파일 구조

- `test_scraper.py`: 메인 스크래퍼 테스트 스크립트
- `src/scrapers/async_llm_scraper.py`: 비동기 크롤링 로직
- `src/utils/llm_extractor.py`: LLM 기반 데이터 추출
- `src/models/schemas.py`: 데이터 모델 정의
- `requirements.txt`: 의존성 목록

## 참고사항

- GEMINI_API_KEY 환경변수가 필요합니다
- 결과는 `data/` 폴더에 JSON 파일로 저장됩니다
- 각 사이트별로 크롤링 속도와 페이지 수가 제한되어 있습니다
