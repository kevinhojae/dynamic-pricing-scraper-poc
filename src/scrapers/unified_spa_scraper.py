"""
SPA (Single Page Application) 사이트를 위한 통합 동적 콘텐츠 스크래퍼
Claude/Gemini 지원
"""
import asyncio
import time
from typing import List, Dict, Set, Optional, Any
from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeoutError
from dataclasses import dataclass

from src.models.schemas import ProductItem, ScrapingConfig, ScrapingSourceType, SPAConfig
from src.utils.unified_llm_extractor import UnifiedLLMTreatmentExtractor


@dataclass
class SPAScrapingResult:
    url: str
    products: List[ProductItem]
    interactions_performed: int
    content_states: List[str]  # 각 상호작용 후 콘텐츠 상태
    error: Optional[str] = None
    processing_time: float = 0.0


class UnifiedSPAContentScraper:
    """SPA 사이트의 동적 콘텐츠 스크래핑을 담당하는 클래스 (Claude/Gemini 지원)"""

    def __init__(self, config: ScrapingConfig, llm_extractor: UnifiedLLMTreatmentExtractor):
        self.config = config
        self.llm_extractor = llm_extractor
        self.spa_config = config.spa_config
        if not self.spa_config:
            raise ValueError("SPA config is required for SPA scraping")

    async def scrape_spa_content(self, url: str) -> SPAScrapingResult:
        """SPA 사이트에서 동적 콘텐츠를 스크래핑"""
        start_time = time.time()

        async with async_playwright() as p:
            # 브라우저 실행
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )

            try:
                page = await browser.new_page()

                # User-Agent 설정
                if self.config.headers.get("User-Agent"):
                    await page.set_extra_http_headers({
                        "User-Agent": self.config.headers["User-Agent"]
                    })

                # 초기 페이지 로드
                print(f"🌐 페이지 로딩: {url}")
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(3000)  # 초기 로딩 대기

                content_states = []
                all_products = []
                interactions_performed = 0

                # 페이지 상호작용 수행
                for interaction_num in range(self.spa_config.max_interactions):
                    print(f"🔄 상호작용 {interaction_num + 1}/{self.spa_config.max_interactions}")

                    # 현재 콘텐츠 상태 캡처
                    current_content = await page.content()
                    content_hash = str(hash(current_content))

                    # 중복 콘텐츠 체크
                    if content_hash in content_states:
                        print(f"⚠️  중복 콘텐츠 감지, 상호작용 중단")
                        break

                    content_states.append(content_hash)

                    # 각 interaction의 HTML을 독립적으로 처리 - 디버깅 추가
                    try:
                        print(f"🤖 상호작용 {interaction_num + 1}의 HTML 독립 처리 중...")
                        print(f"📏 HTML 크기: {len(current_content)} 문자")

                        # HTML 샘플을 로그로 저장해서 실제 내용 확인
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                        debug_filename = f"data/errors/html_debug_interaction_{interaction_num + 1}_{timestamp}.txt"

                        import os
                        os.makedirs("data/errors", exist_ok=True)
                        with open(debug_filename, "w", encoding="utf-8") as f:
                            f.write(f"=== Interaction {interaction_num + 1} Debug ===\n")
                            f.write(f"HTML 크기: {len(current_content)} 문자\n")
                            f.write(f"시간: {datetime.now().isoformat()}\n")
                            f.write("=" * 50 + "\n\n")
                            # 처음 5000자만 저장
                            f.write("HTML 샘플 (처음 5000자):\n")
                            f.write(current_content[:5000])

                        products = await self.llm_extractor.extract_treatments_from_html_async(
                            current_content, url
                        )
                        if products:
                            # 중복 제거하면서 추가
                            new_products = self._deduplicate_products(all_products, products)
                            all_products.extend(new_products)
                            print(f"✅ 상호작용 {interaction_num + 1}: {len(products)}개 추출 → {len(new_products)}개 신규 (총 {len(all_products)}개)")
                        else:
                            print(f"📭 상호작용 {interaction_num + 1}: 새로운 제품 없음")
                    except Exception as e:
                        print(f"⚠️  상호작용 {interaction_num + 1} 제품 추출 오류: {str(e)}")

                    # 다음 상호작용 수행
                    if interaction_num < self.spa_config.max_interactions - 1:
                        success = await self._perform_interaction(page)
                        if success:
                            interactions_performed += 1
                            # 상호작용 후 콘텐츠 로딩 대기
                            await page.wait_for_timeout(2000)
                        else:
                            print("🔚 더 이상 상호작용할 요소가 없음")
                            break

                processing_time = time.time() - start_time

                return SPAScrapingResult(
                    url=url,
                    products=all_products,
                    interactions_performed=interactions_performed,
                    content_states=content_states,
                    processing_time=processing_time
                )

            except Exception as e:
                processing_time = time.time() - start_time
                return SPAScrapingResult(
                    url=url,
                    products=[],
                    interactions_performed=0,
                    content_states=[],
                    error=str(e),
                    processing_time=processing_time
                )

            finally:
                await browser.close()

    async def _perform_interaction(self, page: Page) -> bool:
        """페이지에서 상호작용 수행"""
        # 클릭 가능한 요소들을 우선순위 순으로 정의
        interaction_selectors = [
            'button:contains("더보기")',
            'button:contains("더 보기")',
            'a:contains("더보기")',
            'a:contains("더 보기")',
            '.load-more',
            '.btn-more',
            '.more-button',
            '[data-action="load-more"]',
            # 페이지네이션
            '.pagination .next',
            '.pagination a:last-child',
            '.page-next',
            'a:contains("다음")',
            # 일반적인 버튼들
            'button[type="button"]:visible',
            'a[href="#"]:visible',
        ]

        for selector in interaction_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    # 요소가 보이고 클릭 가능한지 확인
                    if await element.is_visible() and await element.is_enabled():
                        print(f"🖱️  클릭: {selector}")
                        await element.click()
                        return True
            except Exception as e:
                continue

        # 스크롤 시도
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
            return True
        except:
            pass

        return False

    def _deduplicate_products(self, existing_products: List[ProductItem], new_products: List[ProductItem]) -> List[ProductItem]:
        """중복 제품 제거"""
        existing_names = {p.product_name for p in existing_products}
        return [p for p in new_products if p.product_name not in existing_names]


class UnifiedConfigurableScraper:
    """통합 설정 기반 스크래퍼 (Claude/Gemini 지원)"""

    def __init__(self, config: ScrapingConfig, llm_extractor: UnifiedLLMTreatmentExtractor):
        self.config = config
        self.llm_extractor = llm_extractor

    async def scrape_by_config(self) -> List[ProductItem]:
        """설정에 따라 스크래핑 수행"""
        all_products = []

        if self.config.source_type == ScrapingSourceType.STATIC_URLS:
            # 정적 URL 병렬 스크래핑 (Promise.all 방식)
            print(f"🚀 {len(self.config.static_urls)}개 URL 병렬 스크래핑 시작...")

            async def scrape_single_url(url: str) -> List[ProductItem]:
                """단일 URL 스크래핑"""
                try:
                    print(f"📄 스크래핑 중: {url}")
                    products = await self.llm_extractor.extract_treatments_from_url(url)
                    print(f"✅ {url}: {len(products)}개 상품 추출")
                    return products
                except Exception as e:
                    print(f"❌ URL 스크래핑 실패 {url}: {str(e)}")
                    return []

            # 모든 URL을 병렬로 처리 (Promise.all과 동일)
            tasks = [scrape_single_url(url) for url in self.config.static_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 결과 수집
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"❌ URL {self.config.static_urls[i]} 처리 중 예외: {str(result)}")
                else:
                    all_products.extend(result)

            print(f"🎉 병렬 스크래핑 완료: 총 {len(all_products)}개 상품 수집")

        elif self.config.source_type == ScrapingSourceType.SPA_DYNAMIC:
            # SPA 동적 스크래핑
            if not self.config.spa_config:
                raise ValueError("SPA 스크래핑에는 spa_config가 필요합니다")

            spa_scraper = UnifiedSPAContentScraper(self.config, self.llm_extractor)

            # 시작 URL 결정
            start_url = self.config.static_urls[0] if self.config.static_urls else self.config.base_url

            result = await spa_scraper.scrape_spa_content(start_url)

            if result.error:
                print(f"❌ SPA 스크래핑 오류: {result.error}")
            else:
                all_products.extend(result.products)
                print(f"✅ SPA 스크래핑 완료: {len(result.products)}개 제품, {result.interactions_performed}번 상호작용")

        return all_products