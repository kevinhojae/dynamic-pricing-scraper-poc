"""
SPA (Single Page Application) 사이트를 위한 통합 동적 콘텐츠 스크래퍼
Claude/Gemini 지원
"""
import asyncio
import time
import aiohttp
from typing import List, Dict, Set, Optional, Any
from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeoutError
from dataclasses import dataclass
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from tqdm import tqdm

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
        self.interacted_elements: Set[str] = set()  # 이미 상호작용한 요소들의 fingerprint 저장
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

                # HTML 수집과 LLM 처리를 분리하여 병렬 처리
                collected_htmls = []  # (interaction_num, html_content) 저장

                # 1단계: 브라우저 상호작용으로 HTML들 수집
                print("📥 1단계: 브라우저 상호작용으로 HTML 수집...")

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

                    # HTML을 수집 목록에 저장 (LLM 처리는 나중에)
                    collected_htmls.append((interaction_num + 1, current_content))
                    print(f"📏 상호작용 {interaction_num + 1} HTML 수집: {len(current_content)} 문자")

                    # 다음 상호작용 수행
                    if interaction_num < self.spa_config.max_interactions - 1:
                        success = await self._perform_interaction(page, interaction_num + 2)
                        if success:
                            interactions_performed += 1
                            # 상호작용 후 콘텐츠 로딩 대기
                            await page.wait_for_timeout(2000)
                        else:
                            print("🔚 더 이상 상호작용할 요소가 없음")
                            break

                # 2단계: 수집된 모든 HTML을 병렬로 LLM 처리
                if collected_htmls:
                    print(f"🚀 2단계: {len(collected_htmls)}개 HTML을 병렬 LLM 처리...")

                    async def process_single_html(interaction_num: int, html_content: str) -> List[ProductItem]:
                        """단일 HTML을 LLM으로 처리"""
                        try:
                            # HTML 디버그 로그 저장
                            from datetime import datetime
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                            debug_filename = f"log/errors/html_debug_interaction_{interaction_num}_{timestamp}.txt"

                            import os
                            os.makedirs("log/errors", exist_ok=True)
                            with open(debug_filename, "w", encoding="utf-8") as f:
                                f.write(f"=== Interaction {interaction_num} Debug ===\n")
                                f.write(f"HTML 크기: {len(html_content)} 문자\n")
                                f.write(f"시간: {datetime.now().isoformat()}\n")
                                f.write("=" * 50 + "\n\n")
                                f.write("HTML 샘플 (처음 5000자):\n")
                                f.write(html_content[:5000])

                            print(f"🤖 상호작용 {interaction_num} LLM 처리 중...")
                            products = await self.llm_extractor.extract_treatments_from_html_async(
                                html_content, url
                            )
                            print(f"✅ 상호작용 {interaction_num}: {len(products)}개 상품 추출 완료")
                            return products

                        except Exception as e:
                            print(f"⚠️ 상호작용 {interaction_num} LLM 처리 오류: {str(e)}")
                            return []

                    # 모든 HTML을 병렬로 LLM 처리 (Promise.all 방식)
                    tasks = [process_single_html(num, html) for num, html in collected_htmls]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # 결과 수집 및 중복 제거
                    for i, result in enumerate(results):
                        interaction_num = collected_htmls[i][0]
                        if isinstance(result, Exception):
                            print(f"❌ 상호작용 {interaction_num} 처리 중 예외: {str(result)}")
                        elif result:
                            new_products = self._deduplicate_products(all_products, result)
                            all_products.extend(new_products)
                            print(f"🔗 상호작용 {interaction_num}: {len(result)}개 추출 → {len(new_products)}개 신규 (총 {len(all_products)}개)")
                        else:
                            print(f"📭 상호작용 {interaction_num}: 추출된 상품 없음")

                    print(f"🎉 병렬 LLM 처리 완료: 총 {len(all_products)}개 상품 수집")

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

    async def _perform_interaction(self, page: Page, interaction_num: int = 0) -> bool:
        """페이지에서 상호작용 수행 (메뉴/네비게이션 요소 우선)"""

        # 메뉴/네비게이션 요소 우선 탐지 (일반적인 패턴들)
        menu_selectors = [
            # 최고 우선순위: 데이터 속성 기반 메뉴
            '[data-target]',  # 데이터 타겟 속성 (일반적인 메뉴 패턴)
            '[data-toggle]',  # 데이터 토글 속성
            '[data-category]',  # 데이터 카테고리 속성

            # 높은 우선순위: 메뉴/카테고리 클래스 (사용자 요청 반영)
            '.mainCateBox a',  # 메인 카테고리 (사용자 예시 기반)
            '.subCateBox a',   # 서브 카테고리 (사용자 예시 기반)
            '.category a',     # 일반 카테고리
            '.menu-item a',    # 메뉴 아이템
            '.nav-item a',     # 네비게이션 아이템

            # 중간 우선순위: 슬라이더/탭 네비게이션
            '.swiper-slide a',  # 스와이퍼 슬라이드 내 링크
            '.tabs li a',       # 탭 메뉴
            '.tab-list a',      # 탭 리스트
            '[role="tab"]',     # ARIA 탭
            '[role="menuitem"]', # ARIA 메뉴 아이템

            # 낮은 우선순위: 카테고리/메뉴 버튼
            '.btn-category',    # 카테고리 버튼
            '.btn-menu',        # 메뉴 버튼
            'button[class*="category"]', # 카테고리가 포함된 버튼
            'button[class*="menu"]',     # 메뉴가 포함된 버튼

            # 기존 더보기/페이지네이션 (낮은 우선순위)
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

            # 최저 우선순위: 일반 링크/버튼
            'a[href]:not([href="#"]):not([href="javascript:void(0)"])', # 유효한 링크
            'button:not([disabled])', # 활성화된 버튼
        ]

        clicked_element = None

        # 메뉴 셀렉터들을 우선순위대로 시도
        for selector in menu_selectors:
            try:
                elements = await page.query_selector_all(selector)
                # 보이는 요소만 필터링
                visible_elements = []
                for element in elements:
                    try:
                        is_visible = await element.is_visible()
                        is_enabled = await element.is_enabled()
                        if is_visible and is_enabled:
                            visible_elements.append(element)
                    except:
                        continue

                if visible_elements:
                    # 이미 상호작용한 요소들 제외
                    available_elements = []
                    for element in visible_elements:
                        signature = await self._get_element_signature(element)
                        if signature not in self.interacted_elements:
                            available_elements.append(element)

                    if not available_elements:
                        print(f"   🔄 모든 '{selector}' 요소와 이미 상호작용 완료, 다음 셀렉터 시도...")
                        continue

                    # 사용 가능한 요소 중에서 랜덤 선택
                    import random
                    clicked_element = random.choice(available_elements)

                    try:
                        # 클릭하기 전에 요소 서명 생성 (추가는 나중에)
                        element_signature = await self._get_element_signature(clicked_element)

                        # 요소 정보 수집
                        element_text = await clicked_element.text_content()
                        element_tag = await clicked_element.evaluate('el => el.tagName.toLowerCase()')
                        element_class = await clicked_element.get_attribute('class') or ''
                        element_id = await clicked_element.get_attribute('id') or ''
                        element_href = await clicked_element.get_attribute('href') or ''
                        element_data_attrs = await clicked_element.evaluate('''el => {
                            const attrs = {};
                            for (let attr of el.attributes) {
                                if (attr.name.startsWith('data-')) {
                                    attrs[attr.name] = attr.value;
                                }
                            }
                            return attrs;
                        }''')

                        # 요소 위치 정보
                        bounding_box = await clicked_element.bounding_box()

                        # 상세 로깅
                        print(f"🎯 상호작용 {interaction_num}: 메뉴 요소 클릭")
                        print(f"   🔍 셀렉터: {selector}")
                        print(f"   🔑 서명: {element_signature}")
                        print(f"   📝 텍스트: '{element_text[:50]}...'")
                        print(f"   🏷️  태그: {element_tag}")
                        print(f"   🎨 클래스: '{element_class[:50]}...'")
                        if element_id:
                            print(f"   🆔 ID: '{element_id}'")
                        if element_href:
                            print(f"   🔗 링크: '{element_href[:50]}...'")
                        if element_data_attrs:
                            print(f"   📊 데이터 속성: {element_data_attrs}")
                        if bounding_box:
                            print(f"   📍 위치: ({bounding_box['x']:.1f}, {bounding_box['y']:.1f}) 크기: {bounding_box['width']:.1f}x{bounding_box['height']:.1f}")

                        # 상호작용 로그를 파일에도 저장
                        await self._log_interaction_details(interaction_num, {
                            'selector': selector,
                            'element_text': element_text,
                            'element_tag': element_tag,
                            'element_class': element_class,
                            'element_id': element_id,
                            'element_href': element_href,
                            'element_data_attrs': element_data_attrs,
                            'bounding_box': bounding_box,
                            'timestamp': time.time()
                        })

                        # 부드러운 스크롤 후 클릭
                        await clicked_element.scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)  # 스크롤 완료 대기

                        # 클릭 전 페이지 URL 기록
                        before_url = page.url

                        # 여러 클릭 방법 시도
                        click_success = False
                        try:
                            # 방법 1: 기본 클릭 (타임아웃 짧게)
                            await clicked_element.click(timeout=5000)
                            click_success = True
                        except Exception as e1:
                            print(f"   ⚠️ 기본 클릭 실패: {str(e1)[:80]}...")
                            try:
                                # 방법 2: force 클릭 (가로막는 요소 무시)
                                await clicked_element.click(force=True, timeout=3000)
                                click_success = True
                                print(f"   ✅ Force 클릭으로 성공")
                            except Exception:
                                try:
                                    # 방법 3: JavaScript 클릭
                                    await clicked_element.evaluate("element => element.click()")
                                    click_success = True
                                    print(f"   ✅ JavaScript 클릭으로 성공")
                                except Exception:
                                    print(f"   ❌ 모든 클릭 방법 실패")
                                    raise e1  # 원래 에러를 다시 발생시킴

                        if not click_success:
                            raise Exception("All click methods failed")

                        # 클릭 후 페이지 변화 대기 및 확인
                        await page.wait_for_timeout(1500)
                        after_url = page.url

                        # URL 변화 체크
                        if before_url != after_url:
                            print(f"   🔀 URL 변화: {before_url} → {after_url}")

                        # 클릭 성공 시에만 interacted_elements에 추가
                        self.interacted_elements.add(element_signature)
                        print(f"   ✅ 클릭 성공 (총 {len(self.interacted_elements)}개 요소와 상호작용 완료)")
                        return True

                    except Exception as e:
                        print(f"⚠️ 클릭 실행 오류: {str(e)}")
                        print(f"   🔄 요소 '{element_signature[:50]}...'는 다음 상호작용에서 재시도 가능")
                        # 실패한 상호작용도 로깅 (단, interacted_elements에는 추가하지 않음)
                        await self._log_interaction_details(interaction_num, {
                            'selector': selector,
                            'element_signature': element_signature,
                            'error': str(e),
                            'timestamp': time.time(),
                            'status': 'failed'
                        })
                        continue

            except Exception as e:
                continue

        # 메뉴 요소를 찾지 못한 경우 스크롤 시도
        if not clicked_element:
            try:
                print(f"📜 상호작용 {interaction_num}: 메뉴 요소 없음, 스크롤 시도...")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)
                return True
            except:
                pass

        print(f"⚠️ 상호작용 {interaction_num}: 상호작용 가능한 요소를 찾을 수 없습니다.")
        print(f"   📋 총 {len(self.interacted_elements)}개 요소와 이미 상호작용 완료")
        return False

    async def _log_interaction_details(self, interaction_num: int, interaction_data: Dict[str, Any]) -> None:
        """상호작용 상세 정보를 파일에 로깅"""
        try:
            from datetime import datetime
            import json
            import os

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            log_filename = f"log/interactions/interaction_{interaction_num}_{timestamp}.json"

            os.makedirs("log/interactions", exist_ok=True)

            # 타임스탬프를 ISO 형식으로 변환
            if 'timestamp' in interaction_data:
                interaction_data['timestamp'] = datetime.fromtimestamp(interaction_data['timestamp']).isoformat()

            log_data = {
                'interaction_number': interaction_num,
                'status': interaction_data.get('status', 'success'),
                'details': interaction_data,
                'logged_at': datetime.now().isoformat()
            }

            with open(log_filename, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)

            print(f"   📄 상호작용 로그 저장: {log_filename}")

        except Exception as e:
            print(f"   ⚠️ 상호작용 로그 저장 실패: {str(e)}")

    async def _get_element_signature(self, element) -> str:
        """요소의 간단한 식별자 생성"""
        try:
            text = (await element.text_content() or '').strip()
            tag = await element.evaluate('el => el.tagName.toLowerCase()')
            class_name = await element.get_attribute('class') or ''
            element_id = await element.get_attribute('id') or ''
            href = await element.get_attribute('href') or ''

            # data attributes 수집
            data_attrs = await element.evaluate('''el => {
                const attrs = [];
                for (let attr of el.attributes) {
                    if (attr.name.startsWith('data-')) {
                        attrs.push(`${attr.name}=${attr.value}`);
                    }
                }
                return attrs.sort().join('|');
            }''')

            # 간단한 서명 생성: 태그명 + 텍스트 + 클래스 + ID + href + data attributes
            signature = f"{tag}:{text[:50]}:{class_name}:{element_id}:{href}:{data_attrs}"
            return signature
        except:
            return f"unknown:{time.time()}"

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