import os
import json
import re
import time
import asyncio
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from tqdm import tqdm
from playwright.async_api import async_playwright

from src.models.schemas import (
    ProductItem,
    IndividualTreatment,
    TreatmentType,
    EquipmentType,
)

# OpenAI API를 선택적으로 import
try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None


class LLMTreatmentExtractor:
    def __init__(self, api_key: Optional[str] = None, requests_per_minute: int = 10):
        # API 키 설정 (환경변수에서 가져오거나 직접 입력)
        self.api_key = api_key or os.getenv("ANTHROPIC_AUTH_TOKEN")
        self.api_base_url = os.getenv("ANTHROPIC_BASE_URL")
        if not self.api_key:
            print("⚠️  ANTHROPIC_AUTH_TOKEN이 설정되지 않았습니다.")
            print("환경변수로 설정하거나 직접 전달해주세요:")
            print("export ANTHROPIC_AUTH_TOKEN='your-api-key-here'")
            return

        # OpenAI 클라이언트 초기화 (LiteLLM Proxy 사용)
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.api_base_url)
        self.model = "bedrock-claude-sonnet-4"

        # Rate limiting 설정
        self.requests_per_minute = requests_per_minute
        self.min_delay_between_requests = 60.0 / requests_per_minute  # 초 단위
        self.last_request_time = 0.0

    async def extract_treatments_from_url(
        self, source_url: str
    ) -> List[ProductItem]:
        """URL에서 JavaScript 렌더링 후 시술 정보를 추출합니다."""
        if not self.api_key:
            return []

        # Playwright로 JavaScript 렌더링 후 HTML 추출
        html_content = await self._fetch_rendered_html(source_url)
        if not html_content:
            return []

        # HTML을 텍스트로 변환
        soup = BeautifulSoup(html_content, "html.parser")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text_content = soup.get_text(separator=" ", strip=True)

        # 텍스트가 너무 길면 자르기
        if len(text_content) > 30000:
            text_content = text_content[:30000] + "..."

        # 텍스트가 너무 짧으면 추출할 의미가 없음
        if len(text_content.strip()) < 100:
            tqdm.write(f"⚠️  텍스트가 너무 짧습니다 ({len(text_content.strip())} chars): {source_url}")
            return []

        prompt = self._create_extraction_prompt(text_content, source_url)

        return await self._make_api_request_with_retry_async(prompt, source_url, text_content)

    def extract_treatments_from_html(
        self, html_content: str, source_url: str
    ) -> List[ProductItem]:
        """기존 HTML 기반 추출 메소드 (하위 호환성 유지)"""
        if not self.api_key:
            return []

        # HTML을 텍스트로 변환
        soup = BeautifulSoup(html_content, "html.parser")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text_content = soup.get_text(separator=" ", strip=True)

        # 텍스트가 너무 길면 자르기
        if len(text_content) > 30000:
            text_content = text_content[:30000] + "..."

        # 텍스트가 너무 짧으면 추출할 의미가 없음
        if len(text_content.strip()) < 100:
            tqdm.write(f"⚠️  텍스트가 너무 짧습니다 ({len(text_content.strip())} chars): {source_url}")
            return []

        prompt = self._create_extraction_prompt(text_content, source_url)

        return self._make_api_request_with_retry(prompt, source_url, text_content)

    async def _fetch_rendered_html(self, url: str) -> Optional[str]:
        """Playwright를 사용하여 JavaScript 렌더링 후 HTML을 가져옵니다."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                page = await context.new_page()

                try:
                    # 페이지 로드
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)

                    # JavaScript 실행 완료 대기
                    await page.wait_for_timeout(3000)

                    # 콘텐츠 요소가 로드될 때까지 대기
                    try:
                        await page.wait_for_selector('main, .content, .product, h1, h2, p', timeout=10000)
                    except:
                        pass  # 특정 요소를 찾지 못해도 계속 진행

                    # 추가 대기 (동적 콘텐츠)
                    await page.wait_for_timeout(2000)

                    # 네트워크 완료 대기 (선택적)
                    try:
                        await page.wait_for_load_state('networkidle', timeout=5000)
                    except:
                        pass  # 네트워크가 계속 활성화되어도 진행

                    # HTML 콘텐츠 가져오기
                    content = await page.content()

                    tqdm.write(f"🌐 Playwright HTML 가져옴: {len(content)} chars from {url}")
                    return content

                except Exception as e:
                    tqdm.write(f"❌ Playwright 페이지 로드 실패: {str(e)}")
                    return None
                finally:
                    await browser.close()

        except Exception as e:
            tqdm.write(f"❌ Playwright 초기화 실패: {str(e)}")
            return None

    def _create_extraction_prompt(self, text_content: str, source_url: str) -> str:
        return f"""
다음 피부과/미용 클리닉 웹페이지 텍스트에서 개별 상품 옵션 정보를 정확하게 추출해주세요.

웹페이지 내용:
{text_content}

출처 URL: {source_url}

각 개별 상품 옵션을 별도의 product로 추출하여 다음 JSON 형식으로 응답해주세요:

{{
  "clinic_name": "병원명 (URL이나 페이지에서 추출)",
  "category": "시술 카테고리 (예: 탄력/리프팅)",
  "description": "카테고리 전체 설명",
  "products": [
    {{
      "product_name": "개별 상품 옵션명 (예: 더마 슈링크 100샷 (이마, 목주름), 슈링크 유니버스 울트라 MP모드 300샷 + 얼굴지방분해주사 3cc)",
      "product_original_price": 정상가_숫자만,
      "product_event_price": 이벤트가_숫자만,
      "product_description": "상품 설명",
      "treatments": [
        {{
          "name": "시술 구성 요소명 (예: 슈링크 유니버스 울트라 MP모드, 얼굴지방분해주사)",
          "dosage": 용량_숫자만,
          "unit": "단위 (예: 샷, cc, 회)",
          "equipments": ["장비명1", "장비명2"],
          "medications": ["약물명1", "약물명2"],
          "treatment_type": "laser|injection|skincare|surgical|device 중 하나",
          "description": "시술 설명",
          "duration": 시술시간_분단위_숫자만,
          "target_area": ["타겟 부위"],
          "benefits": ["효과1", "효과2"],
          "recovery_time": "회복기간"
        }}
      ]
    }}
  ]
}}

핵심 추출 규칙:

1. **개별 상품 옵션 처리**: 각 가격이 표시된 개별 옵션을 별도의 product로 추출
   - 예: "더마 슈링크 100샷" → 하나의 product
   - 예: "슈링크 300샷 + 지방분해주사 3cc" → 하나의 product (하지만 treatments에 2개 요소)

2. **복합 상품 처리**: "A + B" 형태의 상품은 treatments 배열에 각 구성 요소를 분리
   - 상품명: "슈링크 유니버스 울트라 MP모드 300샷 + 얼굴지방분해주사 (비스테로이드) 3cc"
   - treatments: [
       {{"name": "슈링크 유니버스 울트라 MP모드", "dosage": 300, "unit": "샷"}},
       {{"name": "얼굴지방분해주사 (비스테로이드)", "dosage": 3, "unit": "cc"}}
     ]

3. **가격 정보**: product 레벨에서 추출
   - product_original_price: 취소선이 있는 높은 가격
   - product_event_price: 강조 표시된 낮은 가격

4. **용량/단위**: 숫자는 dosage, 문자는 unit으로 분리
   - "300샷" → dosage: 300, unit: "샷"
   - "3cc" → dosage: 3, unit: "cc"

5. **장비/약물**: 각각 배열로 추출
   - equipments: ["슈링크", "울쎄라"]
   - medications: ["GT38", "보톡스"]

6. 정보가 없으면 null 또는 빈 배열로 설정
7. 시술과 무관한 내용은 제외

JSON만 응답해주세요:
"""

    def _parse_llm_response(
        self, response_text: str, source_url: str
    ) -> List[ProductItem]:
        """LLM 응답을 파싱하여 ProductItem 리스트로 변환"""
        try:
            # JSON 부분만 추출
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if not json_match:
                tqdm.write("⚠️  JSON 형식을 찾을 수 없습니다")
                return []

            json_str = json_match.group()
            data = json.loads(json_str)

            # 공통 정보 추출
            clinic_name = data.get("clinic_name") or self._extract_clinic_name(
                source_url
            )
            category = data.get("category")
            description = data.get("description")

            products = []
            for product_data in data.get("products", []):
                try:
                    product = self._create_product_item(
                        product_data, source_url, clinic_name, category, description
                    )
                    if product:
                        products.append(product)
                except Exception as e:
                    tqdm.write(f"⚠️  상품 파싱 오류: {str(e)}")
                    continue

            return products

        except json.JSONDecodeError as e:
            tqdm.write(f"❌ JSON 파싱 오류: {str(e)}")
            tqdm.write(f"응답 텍스트: {response_text[:500]}...")
            return []
        except Exception as e:
            tqdm.write(f"❌ 응답 파싱 오류: {str(e)}")
            return []

    def _create_product_item(
        self,
        product_data: Dict[str, Any],
        source_url: str,
        clinic_name: str,
        category: str,
        description: str,
    ) -> Optional[ProductItem]:
        """딕셔너리에서 ProductItem 생성"""
        try:
            product_name = product_data.get("product_name", "").strip()
            if not product_name:
                return None

            # 개별 시술들 파싱
            treatments = []
            for treatment_data in product_data.get("treatments", []):
                treatment = self._create_individual_treatment(treatment_data)
                if treatment:
                    treatments.append(treatment)

            if not treatments:
                return None

            return ProductItem(
                # Key Factors
                source_url=source_url,
                source_channel=self._extract_source_channel(source_url),
                clinic_name=clinic_name,
                product_name=product_name,
                product_original_price=self._parse_price_value(
                    product_data.get("product_original_price")
                ),
                product_event_price=self._parse_price_value(
                    product_data.get("product_event_price")
                ),
                product_description=product_data.get("product_description"),
                treatments=treatments,
                category=category,
                description=description,
            )

        except Exception as e:
            tqdm.write(f"⚠️  ProductItem 생성 오류: {str(e)}")
            return None

    def _create_individual_treatment(
        self, treatment_data: Dict[str, Any]
    ) -> Optional[IndividualTreatment]:
        """딕셔너리에서 IndividualTreatment 생성"""
        try:
            name = treatment_data.get("name", "").strip()
            if not name:
                return None

            # 시술 유형 매핑
            type_mapping = {
                "laser": TreatmentType.LASER,
                "injection": TreatmentType.INJECTION,
                "skincare": TreatmentType.SKINCARE,
                "surgical": TreatmentType.SURGICAL,
                "device": TreatmentType.DEVICE,
            }
            treatment_type = type_mapping.get(treatment_data.get("treatment_type"))

            return IndividualTreatment(
                name=name,
                dosage=treatment_data.get("dosage"),
                unit=treatment_data.get("unit"),
                equipments=treatment_data.get("equipments", []),
                medications=treatment_data.get("medications", []),
                treatment_type=treatment_type,
                description=treatment_data.get("description"),
                duration=treatment_data.get("duration"),
                target_area=treatment_data.get("target_area", []),
                benefits=treatment_data.get("benefits", []),
                recovery_time=treatment_data.get("recovery_time"),
            )

        except Exception as e:
            tqdm.write(f"⚠️  IndividualTreatment 생성 오류: {str(e)}")
            return None

    def _parse_price(self, price_value: Any) -> float:
        """가격 값을 파싱하여 float로 변환"""
        if price_value is None:
            return 0.0
        if isinstance(price_value, str):
            # 숫자가 아닌 문자 제거
            price_str = re.sub(r"[^\d]", "", price_value)
            return float(price_str) if price_str else 0.0
        return float(price_value) if price_value else 0.0

    def _parse_price_value(self, price_value: Any) -> Optional[float]:
        """가격 값을 파싱하되 None일 경우 None 반환"""
        if price_value is None:
            return None
        if isinstance(price_value, str):
            # 숫자가 아닌 문자 제거
            price_str = re.sub(r"[^\d]", "", price_value)
            return float(price_str) if price_str else None
        return float(price_value) if price_value else None

    def _extract_source_channel(self, source_url: str) -> str:
        """URL에서 정보 수집 채널명 추출"""
        if "xenia.clinic" in source_url:
            return "세니아 클리닉"
        elif "feeline.network" in source_url:
            return "피라인 네트워크"
        elif "gu.clinic" in source_url:
            return "GU 클리닉"
        elif "beautyleader.co.kr" in source_url:
            return "뷰티리더"
        else:
            # 도메인에서 채널명 추출
            try:
                from urllib.parse import urlparse

                domain = urlparse(source_url).netloc
                return domain.replace("www.", "")
            except:
                return "알 수 없음"

    async def _make_api_request_with_retry_async(
        self, prompt: str, source_url: str, text_content: str, max_retries: int = 3
    ) -> List[ProductItem]:
        """Async Retry 로직과 rate limiting이 적용된 API 요청"""
        for attempt in range(max_retries):
            try:
                tqdm.write(
                    f"🤖 Claude로 데이터 추출 중... ({len(text_content)} chars) - 시도 {attempt + 1}/{max_retries}"
                )

                # Rate limiting 적용
                self._wait_for_rate_limit()

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4000  # thinking 기능을 위한 충분한 토큰 설정
                )

                response_text = response.choices[0].message.content
                result = self._parse_llm_response(response_text, source_url)

                tqdm.write(f"✅ {len(result)}개 시술 정보 추출 완료")
                return result

            except Exception as e:
                error_msg = str(e)
                tqdm.write(
                    f"❌ Claude API 오류 (시도 {attempt + 1}/{max_retries}): {error_msg}"
                )

                # 429 에러 (rate limit) 감지
                if (
                    "429" in error_msg
                    or "quota" in error_msg.lower()
                    or "exceeded" in error_msg.lower()
                ):
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2^attempt * 30초
                        wait_time = (2**attempt) * 30
                        tqdm.write(
                            f"⏳ Rate limit 초과. {wait_time}초 대기 후 재시도..."
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        tqdm.write("❌ 최대 재시도 횟수 도달. 요청을 건너뜁니다.")
                        return []
                else:
                    # 다른 에러의 경우 즉시 중단
                    tqdm.write(f"❌ API 요청 실패: {error_msg}")
                    return []

        return []

    def _make_api_request_with_retry(
        self, prompt: str, source_url: str, text_content: str, max_retries: int = 3
    ) -> List[ProductItem]:
        """기존 동기 버전 유지 (하위 호환성)"""
        for attempt in range(max_retries):
            try:
                tqdm.write(
                    f"🤖 Claude로 데이터 추출 중... ({len(text_content)} chars) - 시도 {attempt + 1}/{max_retries}"
                )

                # Rate limiting 적용
                self._wait_for_rate_limit()

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4000  # thinking 기능을 위한 충분한 토큰 설정
                )

                response_text = response.choices[0].message.content
                result = self._parse_llm_response(response_text, source_url)

                tqdm.write(f"✅ {len(result)}개 시술 정보 추출 완료")
                return result

            except Exception as e:
                error_msg = str(e)
                tqdm.write(
                    f"❌ Claude API 오류 (시도 {attempt + 1}/{max_retries}): {error_msg}"
                )

                # 429 에러 (rate limit) 감지
                if (
                    "429" in error_msg
                    or "quota" in error_msg.lower()
                    or "exceeded" in error_msg.lower()
                ):
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2^attempt * 30초
                        wait_time = (2**attempt) * 30
                        tqdm.write(
                            f"⏳ Rate limit 초과. {wait_time}초 대기 후 재시도..."
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        tqdm.write("❌ 최대 재시도 횟수 도달. 요청을 건너뜁니다.")
                        return []
                else:
                    # 다른 에러의 경우 즉시 중단
                    tqdm.write(f"❌ API 요청 실패: {error_msg}")
                    return []

        return []

    def _wait_for_rate_limit(self):
        """Rate limiting을 위한 대기"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.min_delay_between_requests:
            wait_time = self.min_delay_between_requests - time_since_last_request
            tqdm.write(f"⏱️ Rate limiting: {wait_time:.1f}초 대기 중...")
            time.sleep(wait_time)

        self.last_request_time = time.time()

    def _extract_clinic_name(self, source_url: str) -> str:
        """URL에서 클리닉 이름 추출"""
        if "xenia.clinic" in source_url:
            return "세니아 클리닉"
        elif "feeline.network" in source_url:
            return "피라인 네트워크"
        elif "gu.clinic" in source_url:
            return "GU 클리닉"
        elif "beautyleader.co.kr" in source_url:
            return "뷰티리더"
        else:
            # 도메인에서 클리닉명 추출 시도
            try:
                from urllib.parse import urlparse

                domain = urlparse(source_url).netloc.replace("www.", "")
                # 도메인을 기반으로 클리닉명 생성
                if "clinic" in domain:
                    return (
                        domain.replace(".com", "").replace(".co.kr", "").title()
                        + " 클리닉"
                    )
                else:
                    return domain.replace(".com", "").replace(".co.kr", "").title()
            except:
                return "알 수 없는 클리닉"
