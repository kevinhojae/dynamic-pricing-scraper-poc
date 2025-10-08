import asyncio
import time
from typing import List, Set, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dataclasses import dataclass

try:
    import aiohttp
except ImportError:
    print(
        "aiohttp가 설치되지 않았습니다. pip install aiohttp 실행 후 다시 시도해주세요."
    )
    raise

try:
    from tqdm.asyncio import tqdm
except ImportError:
    from tqdm import tqdm

from src.models.schemas import ProductItem, ScrapingConfig
from src.utils.llm_extractor import LLMTreatmentExtractor


@dataclass
class LLMCrawlResult:
    url: str
    content: Optional[str]
    status_code: int
    products: List[ProductItem]
    error: Optional[str] = None
    processing_time: float = 0.0
    llm_processing_time: float = 0.0


class AsyncLLMWebCrawler:
    def __init__(
        self,
        config: ScrapingConfig,
        llm_extractor: LLMTreatmentExtractor,
        max_pages: int = 50,
        max_concurrent: int = 3,
    ):
        self.config = config
        self.llm_extractor = llm_extractor
        self.max_pages = max_pages
        self.max_concurrent = max_concurrent  # LLM 때문에 더 낮게 설정
        self.visited_urls: Set[str] = set()
        self.found_urls: Set[str] = set()
        self.session: Optional[aiohttp.ClientSession] = None
        self.crawl_start_time = time.time()
        self.max_crawl_time = 300  # 5분 최대 크롤링 시간으로 증가

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=self.max_concurrent, limit_per_host=2)
        timeout = aiohttp.ClientTimeout(
            total=30, connect=10
        )  # 타임아웃 줄여서 빠른 실패
        self.session = aiohttp.ClientSession(
            connector=connector, timeout=timeout, headers=self.config.headers
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _should_stop_crawling(self) -> bool:
        """크롤링 중단 조건 체크"""
        elapsed_time = time.time() - self.crawl_start_time

        # 시간 제한 초과
        if elapsed_time > self.max_crawl_time:
            print(f"⏰ 최대 크롤링 시간({self.max_crawl_time}초) 초과로 중단")
            return True

        # 페이지 수 제한 초과
        if len(self.visited_urls) >= self.max_pages:
            print(f"📄 최대 페이지 수({self.max_pages}) 도달로 중단")
            return True

        return False

    def _is_valid_url(self, url: str, base_domain: str) -> bool:
        """URL이 크롤링 대상인지 확인 (시술 관련 페이지 우선)"""
        try:
            parsed = urlparse(url)
            base_parsed = urlparse(base_domain)

            # 같은 도메인만 크롤링
            if parsed.netloc != base_parsed.netloc:
                return False

            # 제외할 파일 확장자들
            excluded_extensions = {
                ".pdf",
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".css",
                ".js",
                ".ico",
                ".zip",
                ".doc",
                ".docx",
                ".xml",
                ".json",
                ".txt",
                ".csv",
            }
            if any(url.lower().endswith(ext) for ext in excluded_extensions):
                return False

            # 제외할 URL 패턴들 (더 관대하게 수정)
            excluded_patterns = {
                "javascript:",
                "mailto:",
                "tel:",
                "/admin",
                "/login",
                "/logout",
                "/api/",
                "/ajax/",
            }
            # query parameter는 허용 (시술 관련일 수 있음)
            url_without_query = url.split("?")[0].lower()
            if any(pattern in url_without_query for pattern in excluded_patterns):
                return False

            # 이미 방문한 URL 제외
            if url in self.visited_urls:
                return False

            # URL 길이 제한 (무한 루프 방지)
            if len(url) > 300:  # 더 길게 허용
                return False

            return True
        except Exception:
            return False

    def _get_url_priority(self, url: str) -> int:
        """URL 우선순위 계산 (시술 관련 키워드 기반)"""
        url_lower = url.lower()

        # 높은 우선순위 키워드 (시술 관련)
        high_priority_keywords = [
            "treatment",
            "procedure",
            "service",
            "menu",
            "price",
            "cost",
            "시술",
            "치료",
            "서비스",
            "메뉴",
            "가격",
            "요금",
            "프로그램",
            "dermatology",
            "skin",
            "beauty",
            "clinic",
            "medical",
            "피부",
            "미용",
            "성형",
            "클리닉",
            "의료",
            "진료",
        ]

        # 중간 우선순위 키워드
        medium_priority_keywords = [
            "about",
            "info",
            "detail",
            "center",
            "department",
            "소개",
            "정보",
            "센터",
            "부서",
            "과",
        ]

        priority = 0

        # 높은 우선순위 키워드 체크
        for keyword in high_priority_keywords:
            if keyword in url_lower:
                priority += 10

        # 중간 우선순위 키워드 체크
        for keyword in medium_priority_keywords:
            if keyword in url_lower:
                priority += 5

        # 메인 페이지는 낮은 우선순위
        if url_lower.endswith("/") or url_lower.endswith("/index.html"):
            priority -= 5

        return priority

    async def _get_sitemap_urls(self, base_url: str) -> List[str]:
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
                async with self.session.get(sitemap_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        parsed_urls = await self._parse_sitemap_content(
                            content, base_url
                        )
                        sitemap_urls.extend(parsed_urls)
                        tqdm.write(
                            f"📄 Sitemap 발견: {sitemap_url} ({len(parsed_urls)}개 URL)"
                        )
                        break  # 첫 번째로 발견된 sitemap만 사용
            except Exception:
                continue  # 다음 sitemap 경로 시도

        return sitemap_urls[:100]  # 최대 100개 URL로 제한

    async def _parse_sitemap_content(self, content: str, base_url: str) -> List[str]:
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
                            async with self.session.get(loc_tag.text) as response:
                                if response.status == 200:
                                    sub_content = await response.text()
                                    sub_urls = await self._parse_sitemap_content(
                                        sub_content, base_url
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

        # 메인 페이지나 소개 페이지도 포함 (시술 정보가 있을 수 있음)
        main_patterns = [
            "/about",
            "/intro",
            "/center",
            "/clinic",
            "소개",
            "센터",
            "클리닉",
            "병원",
        ]

        for pattern in main_patterns:
            if pattern in url_lower:
                return True

        return False  # 기본적으로 제외 (개별 상품 페이지 우선)

    def _get_sitemap_url_priority(self, url: str) -> int:
        """sitemap URL의 우선순위 계산"""
        url_lower = url.lower()
        priority = 0

        # 세니아 클리닉의 개별 상품 페이지는 최고 우선순위
        import re

        if re.match(r".*xenia\.clinic/ko/products/[a-f0-9-]{36}.*", url_lower):
            priority += 100

        # 높은 우선순위 키워드
        high_priority = [
            "treatment",
            "service",
            "procedure",
            "menu",
            "price",
            "products",
            "시술",
            "치료",
            "서비스",
            "메뉴",
            "가격",
            "예약",
        ]

        for keyword in high_priority:
            if keyword in url_lower:
                priority += 20

        # 중간 우선순위 키워드
        medium_priority = [
            "about",
            "center",
            "clinic",
            "medical",
            "소개",
            "센터",
            "클리닉",
            "의료",
        ]

        for keyword in medium_priority:
            if keyword in url_lower:
                priority += 10

        # URL 깊이가 적을수록 높은 우선순위
        depth = url.count("/") - 2  # http://domain.com/ 제외
        priority -= depth * 2

        return priority

    def _extract_urls_from_content(self, html_content: str, base_url: str) -> List[str]:
        """HTML 콘텐츠에서 모든 가능한 URL들을 추출 (다양한 소스 활용)"""
        urls_with_priority = []
        try:
            # XML 경고 방지
            if base_url.endswith(".xml") or "xml" in html_content[:100].lower():
                try:
                    soup = BeautifulSoup(html_content, "xml")
                except Exception:
                    soup = BeautifulSoup(html_content, "html.parser")
            else:
                soup = BeautifulSoup(html_content, "html.parser")

            # 1. 기본 링크 (<a href>) 찾기
            for link in soup.find_all("a", href=True):
                href = link["href"]
                full_url = urljoin(base_url, href)

                # Query parameter 보존 (시술 관련일 수 있음)
                if self._is_valid_url(full_url.split("?")[0], self.config.base_url):
                    priority = self._get_url_priority(full_url)

                    # 링크 텍스트 우선순위
                    link_text = link.get_text(strip=True).lower()
                    text_keywords = [
                        "treatment",
                        "procedure",
                        "service",
                        "price",
                        "menu",
                        "reservation",
                        "시술",
                        "치료",
                        "서비스",
                        "가격",
                        "메뉴",
                        "프로그램",
                        "예약",
                        "상담",
                    ]
                    for keyword in text_keywords:
                        if keyword in link_text:
                            priority += 15

                    # Query parameter 있으면 높은 우선순위
                    if "?" in full_url:
                        priority += 10

                    urls_with_priority.append((full_url, priority))

            # 2. JavaScript 내 URL 패턴 찾기
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string:
                    script_content = script.string
                    import re

                    # JavaScript 내 URL 패턴들
                    url_patterns = [
                        r'["\']([^"\']*treatment[^"\']*)["\']',
                        r'["\']([^"\']*service[^"\']*)["\']',
                        r'["\']([^"\']*reservation[^"\']*)["\']',
                        r'["\']([^"\']*category[^"\']*)["\']',
                        r'location\.href\s*=\s*["\']([^"\']+)["\']',
                        r'window\.open\(["\']([^"\']+)["\']',
                    ]

                    for pattern in url_patterns:
                        matches = re.findall(pattern, script_content, re.IGNORECASE)
                        for match in matches:
                            if match.startswith("/") or match.startswith("http"):
                                full_url = urljoin(base_url, match)
                                if self._is_valid_url(
                                    full_url.split("?")[0], self.config.base_url
                                ):
                                    priority = (
                                        self._get_url_priority(full_url) + 20
                                    )  # JS에서 발견된 것은 높은 우선순위
                                    urls_with_priority.append((full_url, priority))

            # 3. Form action 찾기
            for form in soup.find_all("form", action=True):
                action = form["action"]
                if action:
                    full_url = urljoin(base_url, action)
                    if self._is_valid_url(full_url.split("?")[0], self.config.base_url):
                        priority = self._get_url_priority(full_url) + 5
                        urls_with_priority.append((full_url, priority))

            # 4. 버튼의 onclick, data-* 속성 확인
            for button in soup.find_all(["button", "div", "span"], attrs=True):
                for attr, value in button.attrs.items():
                    if attr in [
                        "onclick",
                        "data-url",
                        "data-href",
                        "data-link",
                    ] and isinstance(value, str):
                        # onclick="location.href='...' 패턴 추출
                        import re

                        url_match = re.search(
                            r'["\']([^"\']*(?:treatment|service|reservation)[^"\']*)["\']',
                            value,
                            re.IGNORECASE,
                        )
                        if url_match:
                            potential_url = url_match.group(1)
                            full_url = urljoin(base_url, potential_url)
                            if self._is_valid_url(
                                full_url.split("?")[0], self.config.base_url
                            ):
                                priority = (
                                    self._get_url_priority(full_url) + 25
                                )  # 버튼에서 발견된 것은 매우 높은 우선순위
                                urls_with_priority.append((full_url, priority))

            # 5. 특별 처리: GU Clinic 같은 SPA 사이트
            if "gu.clinic" in base_url.lower():
                # GU Clinic의 알려진 시술 페이지들 직접 추가
                gu_treatment_urls = [
                    "https://gu.clinic/kr/treatment-reservation",
                    "https://gu.clinic/kr/treatment-reservation?categoryId=64094b472967084b5da2837c",
                    "https://gu.clinic/kr/treatment-reservation?categoryId=64094b652967084b5da2837d",
                    "https://gu.clinic/kr/treatment-reservation?categoryId=64094b7a2967084b5da2837e",
                ]
                for url in gu_treatment_urls:
                    urls_with_priority.append((url, 50))  # 매우 높은 우선순위

            # 6. sitemap.xml 체크 (한 번만) - 동기 메서드에서는 제외
            # sitemap 처리는 별도 비동기 메서드에서 처리

            # 중복 제거 및 정렬
            unique_urls = {}
            for url, priority in urls_with_priority:
                if url in unique_urls:
                    unique_urls[url] = max(
                        unique_urls[url], priority
                    )  # 더 높은 우선순위 유지
                else:
                    unique_urls[url] = priority

            # 우선순위로 정렬
            sorted_urls = sorted(unique_urls.items(), key=lambda x: x[1], reverse=True)
            return [url for url, _ in sorted_urls[:40]]  # 더 많은 URL 허용

        except Exception as e:
            print(f"Error extracting URLs from {base_url}: {str(e)}")

        return []

    async def _fetch_and_process_page(
        self, url: str, semaphore: asyncio.Semaphore
    ) -> LLMCrawlResult:
        """단일 페이지를 가져와서 LLM으로 처리"""
        async with semaphore:
            start_time = time.time()
            try:
                await asyncio.sleep(self.config.rate_limit)  # Rate limiting

                # Playwright로 JavaScript 렌더링 후 LLM 추출 (더 이상 aiohttp 사용 안함)
                llm_start_time = time.time()
                products = await self.llm_extractor.extract_treatments_from_url(url)
                llm_time = time.time() - llm_start_time

                total_time = time.time() - start_time

                return LLMCrawlResult(
                    url=url,
                    content=None,  # Playwright에서는 HTML content를 직접 저장하지 않음
                    status_code=200,  # Playwright로 성공적으로 렌더링됨
                    products=products,
                    processing_time=total_time,
                    llm_processing_time=llm_time,
                )

            except asyncio.TimeoutError:
                processing_time = time.time() - start_time
                return LLMCrawlResult(
                    url=url,
                    content=None,
                    status_code=0,
                    products=[],
                    error="Timeout",
                    processing_time=processing_time,
                )
            except Exception as e:
                processing_time = time.time() - start_time
                return LLMCrawlResult(
                    url=url,
                    content=None,
                    status_code=0,
                    products=[],
                    error=str(e),
                    processing_time=processing_time,
                )

    async def crawl_and_extract(
        self, start_urls: List[str] = None
    ) -> List[LLMCrawlResult]:
        """웹사이트를 크롤링하면서 동시에 LLM으로 시술 정보 추출"""
        if not start_urls:
            start_urls = [self.config.base_url]

        urls_to_visit = set(start_urls)

        # sitemap에서 추가 URL 수집
        try:
            sitemap_urls = await self._get_sitemap_urls(self.config.base_url)
            if sitemap_urls:
                # 시술 관련도가 높은 URL들을 우선 추가
                high_priority_sitemap_urls = [
                    url
                    for url in sitemap_urls
                    if self._get_sitemap_url_priority(url) > 15
                ]
                urls_to_visit.update(
                    high_priority_sitemap_urls[:50]
                )  # 더 많은 개별 상품 페이지 추가
                tqdm.write(
                    f"📄 Sitemap에서 {len(high_priority_sitemap_urls)}개 고우선순위 URL 추가"
                )
        except Exception as e:
            tqdm.write(f"⚠️ Sitemap 처리 오류: {str(e)}")

        results = []
        batch_num = 0

        # 동시 실행 제한을 위한 세마포어 (LLM 때문에 낮게 설정)
        semaphore = asyncio.Semaphore(self.max_concurrent)

        # 진행상황 표시
        pbar = tqdm(desc=f"🤖 LLM Crawling {self.config.site_name}", unit="pages")

        while urls_to_visit and not self._should_stop_crawling():
            batch_num += 1

            # 현재 배치에서 처리할 URL들 (적응적 배치 크기)
            batch_size = min(self.max_concurrent, 5)  # 조금 더 큰 배치로 처리
            current_batch = list(urls_to_visit)[:batch_size]
            urls_to_visit -= set(current_batch)

            # 현재 배치의 URL들을 방문했다고 표시
            self.visited_urls.update(current_batch)

            pbar.set_description(
                f"🤖 LLM Crawling {self.config.site_name} (Batch {batch_num})"
            )

            # 비동기로 페이지들 가져오고 처리
            tasks = [
                self._fetch_and_process_page(url, semaphore) for url in current_batch
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            successful_extractions = 0
            total_treatments_in_batch = 0

            for result in batch_results:
                if isinstance(result, LLMCrawlResult):
                    results.append(result)
                    pbar.update(1)

                    if result.products:
                        successful_extractions += 1
                        total_treatments_in_batch += sum(
                            len(product.treatments) for product in result.products
                        )

                    # 성공적으로 가져온 페이지에서 새로운 URL들 추출
                    if result.content and result.status_code == 200:
                        new_urls = self._extract_urls_from_content(
                            result.content, result.url
                        )
                        unvisited_urls = [
                            url for url in new_urls if url not in self.visited_urls
                        ]

                        # 우선순위가 높은 URL들을 더 많이 추가
                        limited_new_urls = unvisited_urls[:15]  # 더 많은 URL 허용
                        urls_to_visit.update(limited_new_urls)

                        # 디버깅: URL과 콘텐츠 길이 출력
                        if len(result.content) < 1000:
                            tqdm.write(
                                f"⚠️  짧은 콘텐츠: {result.url} ({len(result.content)} chars)"
                            )
                        else:
                            tqdm.write(
                                f"✅ 긴 콘텐츠: {result.url} ({len(result.content)} chars)"
                            )

                    # 상세 진행 정보 표시
                    pbar.set_postfix(
                        {
                            "Found": len(self.visited_urls),
                            "Queue": len(urls_to_visit),
                            "Treatments": len(
                                [
                                    treatment
                                    for r in results
                                    for product in r.products
                                    for treatment in product.treatments
                                ]
                            ),
                            "LLM_Avg": (
                                f"{result.llm_processing_time:.1f}s"
                                if result.llm_processing_time > 0
                                else "0s"
                            ),
                        }
                    )

            # 배치 결과 출력
            if successful_extractions > 0:
                tqdm.write(
                    f"✅ Batch {batch_num}: {successful_extractions}개 페이지에서 {total_treatments_in_batch}개 시술 추출"
                )

            # 크롤링 진행상황 체크
            if len(urls_to_visit) == 0:
                tqdm.write("📝 더 이상 크롤링할 URL이 없습니다.")
                break

        pbar.close()
        return results


class AsyncLLMTreatmentScraper:
    def __init__(
        self,
        site_name: str,
        base_url: str,
        api_key: str,
        max_pages: int = 15,
        max_concurrent: int = 2,
    ):  # 더 보수적인 기본값
        self.site_name = site_name
        self.base_url = base_url
        self.api_key = api_key
        self.max_pages = max_pages
        self.max_concurrent = max_concurrent

    async def scrape_all_treatments(self) -> List[ProductItem]:
        """웹사이트의 모든 페이지에서 LLM으로 시술 정보를 비동기 추출"""

        config = ScrapingConfig(
            site_name=self.site_name,
            base_url=self.base_url,
            selectors={},
            use_selenium=False,  # 비동기에서는 requests 사용
            rate_limit=0.8,  # LLM 속도 개선으로 더 빠르게
        )

        llm_extractor = LLMTreatmentExtractor(self.api_key)

        try:
            async with AsyncLLMWebCrawler(
                config,
                llm_extractor,
                max_pages=self.max_pages,
                max_concurrent=self.max_concurrent,
            ) as crawler:
                print(f"🚀 Starting async LLM crawl of {self.site_name}...")
                crawl_results = await crawler.crawl_and_extract()

                successful_pages = [
                    r for r in crawl_results if r.status_code == 200 and r.products
                ]
                print(
                    f"✅ Successfully processed {len(successful_pages)} pages with products"
                )

                # 모든 상품 정보 수집
                all_products = []
                for result in crawl_results:
                    all_products.extend(result.products)

                print(f"📦 Total extracted: {len(all_products)} products")

                # 중복 제거 (같은 상품명과 클리닉명)
                unique_products = []
                seen = set()
                for product in all_products:
                    key = (
                        product.clinic_name,
                        product.product_name,
                    )
                    if key not in seen:
                        seen.add(key)
                        unique_products.append(product)

                print(f"🎯 Final count: {len(unique_products)} unique products")

                # 총 시술 개수 계산
                total_treatments = sum(
                    len(product.treatments) for product in unique_products
                )
                print(
                    f"💉 Total treatments: {total_treatments} treatments across all products"
                )

                # 통계 출력
                total_llm_time = sum(
                    r.llm_processing_time
                    for r in crawl_results
                    if r.llm_processing_time
                )
                avg_llm_time = (
                    total_llm_time
                    / len([r for r in crawl_results if r.llm_processing_time])
                    if crawl_results
                    else 0
                )
                print(f"📊 Average LLM processing time: {avg_llm_time:.2f}s per page")

                return unique_products

        except Exception as e:
            print(f"❌ Error in async LLM scraping: {str(e)}")
            return []


# 사용 예시 함수
async def run_async_llm_scraping_demo(api_key: str):
    """비동기 LLM 스크래핑 데모 실행"""

    scrapers_config = [
        ("GU Clinic", "https://gu.clinic/", 20, 2),  # 더 많은 페이지와 동시성
        ("Beauty Leader", "https://beautyleader.co.kr/", 15, 2),
        ("Feeline Network", "http://sinchon.feeline.network/skinclinic_", 15, 2),
    ]

    all_treatments = []
    scraping_results = {}

    # 타임아웃 등으로 중단되어도 결과 저장을 위한 함수
    def save_partial_results():
        if all_treatments:
            from datetime import datetime
            import os
            import json

            os.makedirs("data/raw", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 부분 결과 저장
            with open(
                f"data/raw/partial_treatments_{timestamp}.json", "w", encoding="utf-8"
            ) as f:
                json.dump(
                    [t.model_dump() for t in all_treatments],
                    f,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )

            with open(
                f"data/raw/partial_scraping_results_{timestamp}.json",
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    scraping_results, f, ensure_ascii=False, indent=2, default=str
                )

            print("\n💾 부분 결과 저장됨:")
            print(f"   - 시술 정보: {len(all_treatments)}개")
            print(f"   - 파일: data/raw/partial_treatments_{timestamp}.json")

    try:
        for name, base_url, max_pages, concurrent in scrapers_config:
            start_time = time.time()
            print(f"\n🚀 Starting async LLM scraping for {name}...")

            try:
                async_llm_scraper = AsyncLLMTreatmentScraper(
                    name,
                    base_url,
                    api_key,
                    max_pages=max_pages,
                    max_concurrent=concurrent,
                )

                treatments = await async_llm_scraper.scrape_all_treatments()
                all_treatments.extend(treatments)

                duration = time.time() - start_time
                scraping_results[name] = {
                    "success": True,
                    "treatments_found": len(treatments),
                    "error": None,
                    "duration_seconds": round(duration, 2),
                    "pages_crawled": max_pages,
                    "concurrent_workers": concurrent,
                    "scraping_method": "async_llm",
                }

                print(f"✅ {name}: {len(treatments)} treatments in {duration:.1f}s")

            except Exception as e:
                duration = time.time() - start_time
                scraping_results[name] = {
                    "success": False,
                    "treatments_found": 0,
                    "error": str(e),
                    "duration_seconds": round(duration, 2),
                    "scraping_method": "async_llm",
                }
                print(f"❌ {name}: Error - {str(e)}")

    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단됨")
        save_partial_results()
    except Exception as e:
        print(f"\n❌ 전체 스크래핑 오류: {str(e)}")
        save_partial_results()

    print(f"\n🎉 Total treatments collected: {len(all_treatments)}")
    return all_treatments, scraping_results


def run_async_llm_scraping(api_key: str):
    """동기 함수에서 비동기 LLM 스크래핑 실행"""
    return asyncio.run(run_async_llm_scraping_demo(api_key))
