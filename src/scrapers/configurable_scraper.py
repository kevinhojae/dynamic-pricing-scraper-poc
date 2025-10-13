import asyncio
from typing import List

from src.models.schemas import ProductItem, ScrapingConfig, ScrapingSourceType
from src.scrapers.sitemap_scraper import SitemapScraper
from src.scrapers.spa_scraper import SPAContentScraper
from src.utils.llm_extractor import LLMTreatmentExtractor


class ConfigurableScraper:
    """통합 설정 기반 스크래퍼 (Claude/Gemini 지원)"""

    def __init__(self, config: ScrapingConfig, llm_extractor: LLMTreatmentExtractor):
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
                    print(
                        f"❌ URL {self.config.static_urls[i]} 처리 중 예외: {str(result)}"
                    )
                else:
                    all_products.extend(result)

            print(f"🎉 병렬 스크래핑 완료: 총 {len(all_products)}개 상품 수집")

        elif self.config.source_type == ScrapingSourceType.SPA_DYNAMIC:
            # SPA 동적 스크래핑
            if not self.config.spa_config:
                raise ValueError("SPA 스크래핑에는 spa_config가 필요합니다")

            spa_scraper = SPAContentScraper(self.config, self.llm_extractor)

            # 시작 URL 결정
            start_url = (
                self.config.static_urls[0]
                if self.config.static_urls
                else self.config.base_url
            )

            result = await spa_scraper.scrape_spa_content(start_url)

            if result.error:
                print(f"❌ SPA 스크래핑 오류: {result.error}")
            else:
                all_products.extend(result.products)
                print(
                    f"✅ SPA 스크래핑 완료: {len(result.products)}개 제품, {result.interactions_performed}번 상호작용"
                )

        elif self.config.source_type == ScrapingSourceType.SITEMAP:
            # Sitemap 기반 스크래핑
            sitemap_scraper = SitemapScraper(self.config, self.llm_extractor)

            result_products = await sitemap_scraper.scrape_sitemap_content()
            all_products.extend(result_products)

            print(f"✅ Sitemap 스크래핑 완료: {len(result_products)}개 제품")

        return all_products
