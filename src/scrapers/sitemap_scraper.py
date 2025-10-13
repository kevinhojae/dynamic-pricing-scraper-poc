"""
Sitemap 기반 스크래핑을 담당하는 전용 스크래퍼
Claude/Gemini 지원
"""

import asyncio
import aiohttp
from typing import List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from tqdm import tqdm

from src.models.schemas import ProductItem, ScrapingConfig
from src.utils.llm_extractor import LLMTreatmentExtractor


class SitemapScraper:
    """Sitemap 기반 URL 수집 및 스크래핑을 담당하는 클래스 (Claude/Gemini 지원)"""

    def __init__(self, config: ScrapingConfig, llm_extractor: LLMTreatmentExtractor):
        self.config = config
        self.llm_extractor = llm_extractor

    async def scrape_sitemap_content(self) -> List[ProductItem]:
        """Sitemap 기반 스크래핑 수행"""
        print(f"🗺️  Sitemap 스크래핑 시작: {self.config.base_url}")

        # HTTP 세션 생성
        async with aiohttp.ClientSession() as session:
            # Sitemap에서 URL들 수집
            urls = await self._get_sitemap_urls(session, self.config.base_url)

            if not urls:
                print("⚠️  Sitemap에서 유효한 URL을 찾을 수 없습니다")
                return []

            print(f"📄 Sitemap에서 {len(urls)}개 URL 발견")

            # URL들을 병렬로 스크래핑
            all_products = []

            async def scrape_single_url(url: str) -> List[ProductItem]:
                """단일 URL 스크래핑"""
                try:
                    tqdm.write(f"📄 스크래핑 중: {url}")
                    products = await self.llm_extractor.extract_treatments_from_url(url)
                    tqdm.write(f"✅ {url}: {len(products)}개 상품 추출")
                    return products
                except Exception as e:
                    tqdm.write(f"❌ URL 스크래핑 실패 {url}: {str(e)}")
                    return []

            # 최대 50개 URL로 제한하여 병렬 처리
            limited_urls = urls[:50]
            print(f"🚀 {len(limited_urls)}개 URL 병렬 스크래핑 시작...")

            tasks = [scrape_single_url(url) for url in limited_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 결과 수집
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    tqdm.write(f"❌ URL {limited_urls[i]} 처리 중 예외: {str(result)}")
                else:
                    all_products.extend(result)

            print(f"🎉 Sitemap 스크래핑 완료: 총 {len(all_products)}개 상품 수집")
            return all_products

    async def _get_sitemap_urls(
        self, session: aiohttp.ClientSession, base_url: str
    ) -> List[str]:
        """sitemap.xml에서 URL들을 추출"""
        sitemap_urls = []
        potential_sitemaps = [
            "/sitemap.xml",
            "/sitemap_index.xml",
            "/sitemaps.xml",
            "/sitemap/sitemap.xml",
            "/wp-sitemap.xml",
            "/sitemap-index.xml",
        ]

        for sitemap_path in potential_sitemaps:
            sitemap_url = urljoin(base_url, sitemap_path)
            try:
                async with session.get(sitemap_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        parsed_urls = await self._parse_sitemap_content(
                            session, content, base_url
                        )
                        sitemap_urls.extend(parsed_urls)
                        tqdm.write(
                            f"📄 Sitemap 발견: {sitemap_url} ({len(parsed_urls)}개 URL)"
                        )
                        break  # 첫 번째로 발견된 sitemap만 사용
            except Exception as e:
                tqdm.write(f"⚠️  Sitemap 접근 실패 {sitemap_url}: {str(e)}")
                continue  # 다음 sitemap 경로 시도

        return sitemap_urls[:100]  # 최대 100개 URL로 제한

    async def _parse_sitemap_content(
        self, session: aiohttp.ClientSession, content: str, base_url: str
    ) -> List[str]:
        """sitemap XML 콘텐츠를 파싱하여 URL 추출"""
        urls = []
        try:
            soup = BeautifulSoup(content, "xml")

            # sitemap index인 경우 (다른 sitemap들을 참조)
            sitemap_tags = soup.find_all("sitemap")
            if sitemap_tags:
                for sitemap_tag in sitemap_tags:
                    loc_tag = sitemap_tag.find("loc")
                    if loc_tag and loc_tag.text:
                        # 개별 sitemap을 추가로 파싱
                        try:
                            async with session.get(loc_tag.text) as response:
                                if response.status == 200:
                                    sub_content = await response.text()
                                    sub_urls = await self._parse_sitemap_content(
                                        session, sub_content, base_url
                                    )
                                    urls.extend(sub_urls)
                        except Exception:
                            continue

            # 일반 sitemap인 경우 (URL들을 직접 포함)
            url_tags = soup.find_all("url")
            for url_tag in url_tags:
                loc_tag = url_tag.find("loc")
                if loc_tag and loc_tag.text:
                    url = loc_tag.text.strip()

                    # URL 필터링 및 우선순위 판단
                    if self._is_sitemap_url_relevant(url):
                        urls.append(url)

            # 우선순위가 높은 URL들을 앞으로 정렬
            urls.sort(key=lambda url: self._get_sitemap_url_priority(url), reverse=True)

        except Exception as e:
            tqdm.write(f"⚠️ Sitemap 파싱 오류: {str(e)}")

        return urls

    def _is_sitemap_url_relevant(self, url: str) -> bool:
        """sitemap URL이 시술 관련 페이지인지 판단"""
        url_lower = url.lower()

        # 설정에서 exclude_patterns 확인
        if hasattr(self.config, "custom_settings") and self.config.custom_settings:
            exclude_patterns = self.config.custom_settings.get("exclude_patterns", [])
            for pattern in exclude_patterns:
                if pattern in url_lower:
                    return False

        # 세니아 클리닉의 개별 상품 페이지 패턴 우선 체크
        import re

        if re.match(r".*xenia\.clinic/ko/products/[a-f0-9-]{36}.*", url_lower):
            return True

        # 제외할 URL 패턴들
        excluded_patterns = [
            "/blog/",
            "/news/",
            "/notice/",
            "/event/",
            "/category/",
            "/tag/",
            "/author/",
            "/feed/",
            "/rss/",
            "/atom/",
            ".pdf",
            ".jpg",
            ".png",
            ".gif",
            ".css",
            ".js",
            "/admin/",
            "/login/",
            "/api/",
        ]

        for pattern in excluded_patterns:
            if pattern in url_lower:
                return False

        # 설정에서 priority_keywords 확인
        if hasattr(self.config, "custom_settings") and self.config.custom_settings:
            priority_keywords = self.config.custom_settings.get("priority_keywords", [])
            for keyword in priority_keywords:
                if keyword in url_lower:
                    return True

        # 시술 관련 키워드가 있으면 포함
        relevant_keywords = [
            "treatment",
            "service",
            "procedure",
            "menu",
            "price",
            "cost",
            "reservation",
            "booking",
            "consultation",
            "products",
            "시술",
            "치료",
            "서비스",
            "메뉴",
            "가격",
            "요금",
            "예약",
            "상담",
            "프로그램",
            "진료",
        ]

        for keyword in relevant_keywords:
            if keyword in url_lower:
                return True

        return False

    def _get_sitemap_url_priority(self, url: str) -> int:
        """sitemap URL의 우선순위 계산"""
        url_lower = url.lower()
        priority = 0

        # 세니아 클리닉 개별 상품 페이지 (UUID 패턴)
        import re

        if re.match(r".*xenia\.clinic/ko/products/[a-f0-9-]{36}.*", url_lower):
            priority += 50  # 매우 높은 우선순위

        # 설정의 priority_keywords 확인
        if hasattr(self.config, "custom_settings") and self.config.custom_settings:
            priority_keywords = self.config.custom_settings.get("priority_keywords", [])
            for keyword in priority_keywords:
                if keyword in url_lower:
                    priority += 20

        # 시술 관련 키워드
        treatment_keywords = ["treatment", "procedure", "service", "시술", "치료"]
        for keyword in treatment_keywords:
            if keyword in url_lower:
                priority += 15

        # 제품/메뉴 관련 키워드
        product_keywords = ["products", "menu", "price", "제품", "메뉴", "가격"]
        for keyword in product_keywords:
            if keyword in url_lower:
                priority += 10

        # 예약 관련 키워드
        booking_keywords = ["reservation", "booking", "consultation", "예약", "상담"]
        for keyword in booking_keywords:
            if keyword in url_lower:
                priority += 8

        # 메인 페이지는 낮은 우선순위
        if url_lower.endswith("/") or url_lower.endswith("/index.html"):
            priority -= 5

        return priority
