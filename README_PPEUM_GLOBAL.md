# 쁨 글로벌 클리닉 스크래퍼

쁨 글로벌 클리닉과 같은 SPA (Single Page Application) 사이트를 위한 동적 콘텐츠 스크래퍼입니다.

## 주요 특징

### 1. 설정 기반 다중 사이트 지원
- **Sitemap 기반**: sitemap.xml을 이용한 자동 URL 수집 (세니아 클리닉 등)
- **Static URLs**: 미리 정의된 URL 목록 사용 (GU 클리닉 등)
- **SPA Dynamic**: JavaScript로 동적 생성되는 콘텐츠 스크래핑 (쁨 글로벌 등)

### 2. SPA 사이트 특화 기능
- **동적 상호작용**: 버튼 클릭, 탭 변경을 통한 콘텐츠 로딩
- **스크롤 기반 로딩**: 지연 로딩 콘텐츠 수집
- **중복 제거**: 같은 콘텐츠 상태 인식 및 필터링
- **Playwright 기반**: 실제 브라우저 환경에서 JavaScript 실행

### 3. 쁨 글로벌 클리닉 전용 최적화
- **예약 페이지 타겟팅**: `https://global.ppeum.com/front/reservation?branchMap=global_kr`
- **한국어 사이트 지원**: 한국어 콘텐츠 인식 및 처리
- **다양한 클릭 요소**: 탭, 카테고리 버튼, 메뉴 항목 등
- **충분한 로딩 시간**: 8초 대기 + 네트워크 안정화

## 설치 및 설정

### 필수 패키지
```bash
pip install playwright aiohttp openai pydantic tqdm beautifulsoup4
playwright install chromium
```

### 환경 변수 설정
```bash
export ANTHROPIC_AUTH_TOKEN="your-anthropic-api-key"
```

또는 `.env` 파일에:
```
ANTHROPIC_AUTH_TOKEN=your-anthropic-api-key
ANTHROPIC_BASE_URL=your-litellm-proxy-url  # LiteLLM Proxy 사용 시
```

## 사용 방법

### 1. 쁨 글로벌 클리닉만 스크래핑

```python
import asyncio
from ppeum_global_scraper import PpeumGlobalScraper

async def main():
    api_key = "your-anthropic-api-key"  # 또는 환경변수에서 자동 로드
    scraper = PpeumGlobalScraper(api_key)

    # 스크래핑 실행
    products = await scraper.scrape_treatments()

    # 결과 저장
    if products:
        scraper.save_results(products)
        print(f"발견된 상품: {len(products)}개")

asyncio.run(main())
```

### 2. 다중 사이트 스크래핑

```python
import asyncio
from multi_site_scraper import MultiSiteScraper

async def main():
    api_key = "your-anthropic-api-key"  # 또는 환경변수에서 자동 로드
    multi_scraper = MultiSiteScraper(api_key)

    # 쁨 글로벌만 스크래핑
    products = await multi_scraper.scrape_ppeum_only()

    # 모든 사이트 스크래핑
    results = await multi_scraper.scrape_all_sites()
    multi_scraper.save_results(results)

asyncio.run(main())
```

### 3. 커스텀 설정으로 스크래핑

```python
import asyncio
from src.config.site_configs import site_config_manager
from src.scrapers.spa_scraper import ConfigurableScraper
from src.utils.llm_extractor import LLMTreatmentExtractor

async def main():
    api_key = "your-anthropic-api-key"  # 또는 환경변수에서 자동 로드

    # 쁨 글로벌 설정 가져오기
    config = site_config_manager.create_ppeum_global_config()

    # 설정 커스터마이징
    config.spa_config.max_interactions = 30  # 더 많은 상호작용
    config.spa_config.wait_time = 10         # 더 긴 대기시간

    # 스크래퍼 실행
    llm_extractor = LLMTreatmentExtractor(api_key)
    scraper = ConfigurableScraper(config, llm_extractor)
    products = await scraper.scrape_by_config()

asyncio.run(main())
```

## 테스트 실행

```bash
# 전체 테스트
python test_ppeum_scraper.py

# 설정만 테스트
python -c "
from src.config.site_configs import site_config_manager
print('Sites:', site_config_manager.list_sites())
print('SPA sites:', site_config_manager.get_spa_sites())
"
```

## 파일 구조

```
scraper_poc/
├── src/
│   ├── config/
│   │   └── site_configs.py          # 사이트별 설정 관리
│   ├── models/
│   │   └── schemas.py               # 데이터 모델 (SPAConfig, ScrapingConfig 등)
│   ├── scrapers/
│   │   ├── async_llm_scraper.py     # 기존 sitemap 기반 스크래퍼
│   │   └── spa_scraper.py           # SPA 사이트 전용 스크래퍼
│   └── utils/
│       └── llm_extractor.py         # LLM 기반 데이터 추출
├── ppeum_global_scraper.py          # 쁨 글로벌 전용 스크래퍼
├── multi_site_scraper.py            # 다중 사이트 스크래퍼
└── test_ppeum_scraper.py           # 테스트 스크립트
```

## 설정 옵션

### SPA 설정 (SPAConfig)
- `wait_for_element`: 대기할 요소 선택자
- `click_elements`: 클릭할 버튼/요소들 목록
- `scroll_behavior`: 스크롤 수행 여부
- `wait_time`: 페이지 로딩 대기 시간(초)
- `max_interactions`: 최대 상호작용 횟수

### 쁨 글로벌 기본 설정
```python
SPAConfig(
    wait_for_element=".treatment-item, .menu-list, .reservation-item, .price-item",
    click_elements=[
        "button[data-category]",
        ".tab-menu button",
        ".category-button",
        ".menu-tab",
        ".treatment-tab",
        ".btn-category",
        "[role='tab']"
    ],
    scroll_behavior=True,
    wait_time=8,
    max_interactions=20
)
```

## 출력 데이터 구조

```json
{
  "clinic_name": "쁨글로벌의원",
  "product_name": "슈링크 유니버스 300샷 + 울쎄라 200샷",
  "product_original_price": 500000,
  "product_event_price": 350000,
  "source_url": "https://global.ppeum.com/front/reservation?branchMap=global_kr",
  "treatments": [
    {
      "name": "슈링크 유니버스",
      "dosage": 300,
      "unit": "샷",
      "equipments": ["슈링크"],
      "treatment_type": "device"
    },
    {
      "name": "울쎄라",
      "dosage": 200,
      "unit": "샷",
      "equipments": ["울쎄라"],
      "treatment_type": "device"
    }
  ]
}
```

## 성능 최적화

1. **동시성 제한**: SPA 사이트는 max_concurrent=2로 제한
2. **Rate Limiting**: 요청 간 2-3초 간격 유지
3. **중복 제거**: 콘텐츠 해시를 통한 중복 상태 감지
4. **타임아웃 설정**: 네트워크 안정화 대기 포함
5. **점진적 로딩**: 배치 단위로 처리하여 메모리 효율성 확보

## 주의사항

1. **API 키 필수**: OpenAI API 키가 반드시 필요합니다
2. **브라우저 의존성**: Playwright chromium 브라우저 설치 필요
3. **처리 시간**: SPA 사이트는 일반 사이트보다 오래 걸립니다 (1-2분)
4. **사이트 변경**: 사이트 구조 변경 시 click_elements 업데이트 필요
5. **네트워크 상태**: 안정적인 인터넷 연결 필요

## 향후 개선 방안

1. **AI 기반 요소 인식**: 클릭할 요소를 AI가 자동 판단
2. **캐싱 시스템**: 중복 요청 방지를 위한 캐시 도입
3. **에러 복구**: 실패한 상호작용에 대한 재시도 로직
4. **실시간 모니터링**: 스크래핑 진행 상황 대시보드
5. **다국어 지원**: 영어/중국어 등 다국어 사이트 지원