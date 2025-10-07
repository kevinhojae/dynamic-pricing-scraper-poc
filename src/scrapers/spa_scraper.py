"""
SPA (Single Page Application) 사이트를 위한 동적 콘텐츠 스크래퍼
"""
import asyncio
import time
from typing import List, Dict, Set, Optional, Any
from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeoutError
from dataclasses import dataclass

from src.models.schemas import ProductItem, ScrapingConfig, ScrapingSourceType, SPAConfig
from src.utils.llm_extractor import LLMTreatmentExtractor


@dataclass
class SPAScrapingResult:
    url: str
    products: List[ProductItem]
    interactions_performed: int
    content_states: List[str]  # 각 상호작용 후 콘텐츠 상태
    error: Optional[str] = None
    processing_time: float = 0.0


class SPAContentScraper:
    """SPA 사이트의 동적 콘텐츠 스크래핑을 담당하는 클래스"""

    def __init__(self, config: ScrapingConfig, llm_extractor: LLMTreatmentExtractor):
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

                # 페이지 로드
                await page.goto(url, wait_until='networkidle')
                await asyncio.sleep(self.spa_config.wait_time)

                # 초기 대기 요소 확인
                if self.spa_config.wait_for_element:
                    try:
                        await page.wait_for_selector(
                            self.spa_config.wait_for_element,
                            timeout=15000
                        )
                    except PlaywrightTimeoutError:
                        print(f"⚠️ 대기 요소를 찾을 수 없음: {self.spa_config.wait_for_element}")

                # 동적 상호작용 수행
                result = await self._perform_spa_interactions(page, url)

                return result

            except Exception as e:
                return SPAScrapingResult(
                    url=url,
                    products=[],
                    interactions_performed=0,
                    content_states=[],
                    error=str(e),
                    processing_time=time.time() - start_time
                )
            finally:
                await browser.close()

    async def _perform_spa_interactions(self, page: Page, url: str) -> SPAScrapingResult:
        """SPA 페이지에서 다양한 상호작용을 수행하여 콘텐츠 수집"""
        start_time = time.time()  # 시작 시간 기록
        all_products = []
        content_states = []
        interactions_count = 0
        seen_content_hashes = set()

        # 초기 콘텐츠 캡처
        initial_content = await page.content()
        initial_hash = hash(initial_content[:5000])  # 처음 5000자만 해시
        seen_content_hashes.add(initial_hash)

        try:
            # 초기 상태에서 데이터 추출
            initial_products = await self._extract_products_from_content(initial_content, url)
            all_products.extend(initial_products)
            content_states.append(f"Initial: {len(initial_products)} products")
            print(f"📄 초기 상태: {len(initial_products)}개 상품 발견")

        except Exception as e:
            print(f"⚠️ 초기 콘텐츠 추출 오류: {str(e)}")

        # 스크롤 수행 (추가 콘텐츠 로딩을 위해)
        if self.spa_config.scroll_behavior:
            await self._perform_scroll_interactions(page)

        # 클릭 가능한 요소들과 상호작용
        for click_selector in self.spa_config.click_elements:
            if interactions_count >= self.spa_config.max_interactions:
                break

            try:
                # 요소들 찾기
                elements = await page.query_selector_all(click_selector)

                if not elements:
                    continue

                print(f"🖱️  '{click_selector}' 요소 {len(elements)}개 발견")

                # 각 요소와 상호작용
                for i, element in enumerate(elements[:5]):  # 최대 5개까지만
                    if interactions_count >= self.spa_config.max_interactions:
                        break

                    try:
                        # 요소가 보이는지 확인하고 클릭
                        if await element.is_visible():
                            await element.scroll_into_view_if_needed()
                            await asyncio.sleep(1)

                            # 클릭 수행
                            await element.click()
                            interactions_count += 1

                            # 클릭 후 대기
                            await asyncio.sleep(self.spa_config.wait_time)

                            # 네트워크 안정화 대기
                            try:
                                await page.wait_for_load_state('networkidle', timeout=5000)
                            except PlaywrightTimeoutError:
                                pass

                            # 새로운 콘텐츠 확인 및 추출
                            new_content = await page.content()
                            new_hash = hash(new_content[:5000])

                            if new_hash not in seen_content_hashes:
                                seen_content_hashes.add(new_hash)

                                try:
                                    new_products = await self._extract_products_from_content(new_content, url)
                                    unique_new_products = self._filter_unique_products(new_products, all_products)

                                    if unique_new_products:
                                        all_products.extend(unique_new_products)
                                        content_states.append(
                                            f"Click {interactions_count} ({click_selector}[{i}]): {len(unique_new_products)} new products"
                                        )
                                        print(f"✅ 클릭 {interactions_count}: {len(unique_new_products)}개 새 상품 발견")
                                    else:
                                        print(f"⚪ 클릭 {interactions_count}: 새 상품 없음")

                                except Exception as e:
                                    print(f"⚠️ 콘텐츠 추출 오류: {str(e)}")
                            else:
                                print(f"⚪ 클릭 {interactions_count}: 중복 콘텐츠")

                    except Exception as e:
                        print(f"⚠️ 요소 클릭 오류: {str(e)}")
                        continue

            except Exception as e:
                print(f"⚠️ 선택자 처리 오류 {click_selector}: {str(e)}")
                continue

        return SPAScrapingResult(
            url=url,
            products=all_products,
            interactions_performed=interactions_count,
            content_states=content_states,
            processing_time=time.time() - start_time
        )

    async def _perform_scroll_interactions(self, page: Page):
        """페이지 스크롤을 통한 추가 콘텐츠 로딩"""
        try:
            # 여러 번 스크롤하여 지연 로딩 콘텐츠 확인
            for i in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                # 중간 위치로 스크롤
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await asyncio.sleep(1)

            # 맨 위로 돌아가기
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1)

        except Exception as e:
            print(f"⚠️ 스크롤 오류: {str(e)}")

    async def _extract_products_from_content(self, content: str, url: str) -> List[ProductItem]:
        """HTML 콘텐츠에서 상품 정보 추출"""
        try:
            # 콘텐츠가 너무 작으면 추출하지 않음
            if len(content) < 1000:
                return []

            # LLM으로 상품 정보 추출 (비동기 메서드 사용)
            products = await self.llm_extractor.extract_treatments_from_html_async(content, url)
            return products

        except Exception as e:
            print(f"⚠️ LLM 추출 오류: {str(e)}")
            return []

    def _filter_unique_products(
        self,
        new_products: List[ProductItem],
        existing_products: List[ProductItem]
    ) -> List[ProductItem]:
        """새로운 상품 중 중복되지 않는 것들만 필터링"""
        existing_keys = set()
        for product in existing_products:
            key = (product.clinic_name, product.product_name)
            existing_keys.add(key)

        unique_products = []
        for product in new_products:
            key = (product.clinic_name, product.product_name)
            if key not in existing_keys:
                unique_products.append(product)
                existing_keys.add(key)

        return unique_products


class ConfigurableScraper:
    """설정 기반으로 다양한 스크래핑 방식을 지원하는 스크래퍼"""

    def __init__(self, config: ScrapingConfig, llm_extractor: LLMTreatmentExtractor):
        self.config = config
        self.llm_extractor = llm_extractor

    async def scrape_by_config(self) -> List[ProductItem]:
        """설정에 따라 적절한 스크래핑 방식 선택"""

        if self.config.source_type == ScrapingSourceType.SPA_DYNAMIC:
            return await self._scrape_spa_sites()

        elif self.config.source_type == ScrapingSourceType.STATIC_URLS:
            return await self._scrape_static_urls()

        elif self.config.source_type == ScrapingSourceType.SITEMAP:
            # 기존 sitemap 방식 호출 (async_llm_scraper 사용)
            from src.scrapers.async_llm_scraper import AsyncLLMTreatmentScraper
            scraper = AsyncLLMTreatmentScraper(
                self.config.site_name,
                self.config.base_url,
                self.llm_extractor.api_key,
                max_pages=20,
                max_concurrent=2
            )
            return await scraper.scrape_all_treatments()

        else:
            # BASE_URL - 일반적인 크롤링
            return await self._scrape_base_url()

    async def _scrape_spa_sites(self) -> List[ProductItem]:
        """SPA 사이트 스크래핑"""
        spa_scraper = SPAContentScraper(self.config, self.llm_extractor)
        all_products = []

        # static_urls이 있으면 그것들을 사용, 없으면 base_url 사용
        urls_to_scrape = self.config.static_urls if self.config.static_urls else [self.config.base_url]

        for url in urls_to_scrape:
            print(f"🚀 SPA 스크래핑 시작: {url}")
            result = await spa_scraper.scrape_spa_content(url)

            if result.error:
                print(f"❌ SPA 스크래핑 오류 ({url}): {result.error}")
            else:
                print(f"✅ SPA 스크래핑 완료 ({url}): {len(result.products)}개 상품, {result.interactions_performed}번 상호작용")
                all_products.extend(result.products)

            # 요청 간 간격
            await asyncio.sleep(self.config.rate_limit)

        return all_products

    async def _scrape_static_urls(self) -> List[ProductItem]:
        """정적 URL 목록 스크래핑"""
        all_products = []

        for url in self.config.static_urls:
            try:
                products = await self.llm_extractor.extract_treatments_from_url(url)
                all_products.extend(products)
                print(f"✅ URL 처리 완료: {url} ({len(products)}개 상품)")

                await asyncio.sleep(self.config.rate_limit)

            except Exception as e:
                print(f"❌ URL 처리 오류 ({url}): {str(e)}")

        return all_products

    async def _scrape_base_url(self) -> List[ProductItem]:
        """Base URL에서 기본 크롤링"""
        try:
            products = await self.llm_extractor.extract_treatments_from_url(self.config.base_url)
            print(f"✅ Base URL 처리 완료: {len(products)}개 상품")
            return products
        except Exception as e:
            print(f"❌ Base URL 처리 오류: {str(e)}")
            return []