import asyncio
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from tqdm import tqdm

from src.models.schemas import (
    IndividualTreatment,
    ProductItem,
    TreatmentType,
)
from src.utils.llm_providers import create_llm_provider
from src.utils.prompt_manager import PromptManager

# .env 파일 로드
load_dotenv()


class UnifiedLLMTreatmentExtractor:
    """통합 LLM 시술 정보 추출기 (Claude/Gemini 지원)"""

    def __init__(
        self,
        provider_type: str,
        api_key: Optional[str] = None,
        requests_per_minute: int = 10,
    ):
        self.provider_type = provider_type.lower()

        # API 키 설정
        if api_key is None:
            if self.provider_type == "claude":
                api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
                if not api_key:
                    raise ValueError(
                        "ANTHROPIC_AUTH_TOKEN 환경변수가 설정되지 않았습니다."
                    )
            elif self.provider_type == "gemini":
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    raise ValueError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

        # LLM 제공자 생성
        self.llm_provider = create_llm_provider(
            provider_type, api_key, requests_per_minute
        )

        # 프롬프트 매니저 초기화
        self.prompt_manager = PromptManager()

    async def extract_treatments_from_url(self, source_url: str) -> List[ProductItem]:
        """URL에서 JavaScript 렌더링 후 시술 정보를 추출합니다."""
        # Playwright로 JavaScript 렌더링 후 HTML 추출
        html_content = await self._fetch_rendered_html(source_url)
        if not html_content:
            return []

        return await self.extract_treatments_from_html_async(html_content, source_url)

    async def extract_treatments_from_html_async(
        self, html_content: str, source_url: str
    ) -> List[ProductItem]:
        """HTML 기반 비동기 추출 메소드"""
        # HTML을 텍스트로 변환
        soup = BeautifulSoup(html_content, "html.parser")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text_content = soup.get_text(separator=" ", strip=True)

        # 텍스트 크기를 줄여서 JSON 응답 길이 제한 (Gemini 출력 제한 방지)
        if len(text_content) > 10000:
            text_content = text_content[:10000] + "..."

        # 텍스트가 너무 짧으면 추출할 의미가 없음
        if len(text_content.strip()) < 100:
            tqdm.write(
                f"⚠️  텍스트가 너무 짧습니다 ({len(text_content.strip())} chars): {source_url}"
            )
            return []

        # 프롬프트 생성
        prompt = self._create_extraction_prompt(text_content, source_url)

        return await self._make_api_request_with_retry_async(
            prompt, source_url, text_content
        )

    def extract_treatments_from_html(
        self, html_content: str, source_url: str
    ) -> List[ProductItem]:
        """동기 HTML 기반 추출 메소드 (하위 호환성)"""
        # HTML을 텍스트로 변환
        soup = BeautifulSoup(html_content, "html.parser")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text_content = soup.get_text(separator=" ", strip=True)

        # 텍스트 크기를 줄여서 JSON 응답 길이 제한 (Gemini 출력 제한 방지)
        if len(text_content) > 10000:
            text_content = text_content[:10000] + "..."

        # 텍스트가 너무 짧으면 추출할 의미가 없음
        if len(text_content.strip()) < 100:
            tqdm.write(
                f"⚠️  텍스트가 너무 짧습니다 ({len(text_content.strip())} chars): {source_url}"
            )
            return []

        # 프롬프트 생성
        prompt = self._create_extraction_prompt(text_content, source_url)

        return self._make_api_request_with_retry(prompt, source_url, text_content)

    async def _fetch_rendered_html(self, url: str) -> Optional[str]:
        """Playwright를 사용하여 JavaScript 렌더링 후 HTML을 가져옵니다."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()

                try:
                    # 페이지 로드
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                    # JavaScript 실행 완료 대기
                    await page.wait_for_timeout(3000)

                    # 콘텐츠 요소가 로드될 때까지 대기
                    try:
                        await page.wait_for_selector(
                            "main, .content, .product, h1, h2, p", timeout=10000
                        )
                    except Exception:
                        pass  # 특정 요소를 찾지 못해도 계속 진행

                    # 추가 대기 (동적 콘텐츠)
                    await page.wait_for_timeout(2000)

                    # 네트워크 완료 대기 (선택적)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass  # 네트워크가 계속 활성화되어도 진행

                    # HTML 콘텐츠 가져오기
                    content = await page.content()

                    tqdm.write(
                        f"🌐 Playwright HTML 가져옴: {len(content)} chars from {url}"
                    )
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
        """프롬프트 매니저를 사용하여 추출 프롬프트 생성"""
        return self.prompt_manager.format_prompt(
            "product_extraction", text_content=text_content, source_url=source_url
        )

    def get_model_info(self) -> Dict[str, Any]:
        """현재 사용 중인 모델 정보와 프롬프트 버전 반환"""
        model_info = self.llm_provider.get_model_info()
        prompt_info = self.prompt_manager.get_prompt_info("product_extraction")

        return {
            **model_info,
            "prompt_version": prompt_info["version"],
            "prompt_global_version": prompt_info["global_version"],
        }

    async def _make_api_request_with_retry_async(
        self, prompt: str, source_url: str, text_content: str, max_retries: int = 3
    ) -> List[ProductItem]:
        """비동기 API 요청 (재시도 로직 포함)"""
        for attempt in range(max_retries):
            try:
                tqdm.write(
                    f"🤖 {self.provider_type.title()}로 데이터 추출 중... ({len(text_content)} chars) - 시도 {attempt + 1}/{max_retries}"
                )

                response_text = await self.llm_provider.generate_async(prompt)
                result = self._parse_llm_response(response_text, source_url)

                tqdm.write(f"✅ {len(result)}개 시술 정보 추출 완료")
                return result

            except Exception as e:
                error_msg = str(e)
                tqdm.write(
                    f"❌ {self.provider_type.title()} API 오류 (시도 {attempt + 1}/{max_retries}): {error_msg}"
                )

                # Rate limit 처리
                if (
                    "429" in error_msg
                    or "quota" in error_msg.lower()
                    or "exceeded" in error_msg.lower()
                ):
                    if attempt < max_retries - 1:
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
                    tqdm.write(f"❌ API 요청 실패: {error_msg}")
                    return []

        return []

    def _make_api_request_with_retry(
        self, prompt: str, source_url: str, text_content: str, max_retries: int = 3
    ) -> List[ProductItem]:
        """동기 API 요청 (재시도 로직 포함)"""
        for attempt in range(max_retries):
            try:
                tqdm.write(
                    f"🤖 {self.provider_type.title()}로 데이터 추출 중... ({len(text_content)} chars) - 시도 {attempt + 1}/{max_retries}"
                )

                response_text = self.llm_provider.generate(prompt)
                result = self._parse_llm_response(response_text, source_url)

                tqdm.write(f"✅ {len(result)}개 시술 정보 추출 완료")
                return result

            except Exception as e:
                error_msg = str(e)
                tqdm.write(
                    f"❌ {self.provider_type.title()} API 오류 (시도 {attempt + 1}/{max_retries}): {error_msg}"
                )

                # Rate limit 처리
                if (
                    "429" in error_msg
                    or "quota" in error_msg.lower()
                    or "exceeded" in error_msg.lower()
                ):
                    if attempt < max_retries - 1:
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
                    tqdm.write(f"❌ API 요청 실패: {error_msg}")
                    return []

        return []

    def _parse_llm_response(
        self, response_text: str, source_url: str
    ) -> List[ProductItem]:
        """LLM 응답을 파싱하여 ProductItem 리스트로 변환"""
        try:
            # 마크다운 코드 블록 제거 (```json ... ``` 형식)
            if "```json" in response_text:
                # 코드 블록에서 JSON 부분만 추출
                json_pattern = r"```json\s*(.*?)\s*```"
                json_match = re.search(json_pattern, response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                else:
                    # 코드 블록이 닫히지 않은 경우
                    json_start = response_text.find("```json") + 7
                    json_str = response_text[json_start:].strip()
            else:
                # 일반 JSON 추출
                json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                if not json_match:
                    tqdm.write("⚠️  JSON 형식을 찾을 수 없습니다")
                    tqdm.write(f"응답 텍스트 샘플: {response_text[:200]}...")
                    return []
                json_str = json_match.group()

            # JSON 파싱 전 디버깅 정보
            tqdm.write(f"🔍 JSON 길이: {len(json_str)} 문자")

            # JSON 유효성 검사 및 파싱
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

            # 오류 위치 주변 텍스트 표시
            error_pos = getattr(e, "pos", 0)
            start_pos = max(0, error_pos - 100)
            end_pos = min(len(json_str), error_pos + 100)

            tqdm.write("🔍 오류 위치 주변 텍스트:")
            tqdm.write(f"   {json_str[start_pos:end_pos]}")
            tqdm.write(f"📝 전체 JSON 길이: {len(json_str)}")

            # 에러 데이터를 파일로 저장
            self._save_error_data(response_text, json_str, str(e), source_url)

            # JSON 수정 시도
            try:
                # 일반적인 JSON 오류 수정 시도
                fixed_json = self._try_fix_json(json_str)
                if fixed_json:
                    data = json.loads(fixed_json)
                    tqdm.write("✅ JSON 수정 성공!")

                    # 공통 정보 추출 (수정된 JSON으로)
                    clinic_name = data.get("clinic_name") or self._extract_clinic_name(
                        source_url
                    )
                    category = data.get("category")
                    description = data.get("description")

                    products = []
                    for product_data in data.get("products", []):
                        try:
                            product = self._create_product_item(
                                product_data,
                                source_url,
                                clinic_name,
                                category,
                                description,
                            )
                            if product:
                                products.append(product)
                        except Exception as e:
                            tqdm.write(f"⚠️  상품 파싱 오류: {str(e)}")
                            continue

                    return products
            except Exception:
                pass

            return []
        except Exception as e:
            tqdm.write(f"❌ 응답 파싱 오류: {str(e)}")
            return []

    def _try_fix_json(self, json_str: str) -> Optional[str]:
        """JSON 문자열 수정 시도"""
        try:
            # 1. 끝부분이 잘린 경우 처리
            if not json_str.rstrip().endswith("}"):
                # 마지막 완전한 객체나 배열까지만 추출
                brace_count = 0
                last_complete_pos = -1

                for i, char in enumerate(json_str):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            last_complete_pos = i
                            break

                if last_complete_pos > 0:
                    json_str = json_str[: last_complete_pos + 1]
                    tqdm.write(f"🔧 JSON 끝부분 잘림 수정: {len(json_str)} 문자로 축소")

            # 2. 일반적인 JSON 구문 오류 수정
            # 마지막 쉼표 제거
            json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)

            # 3. 유효성 검사
            json.loads(json_str)
            return json_str

        except Exception as e:
            tqdm.write(f"⚠️  JSON 수정 실패: {str(e)}")
            return None

    def _save_error_data(
        self, response_text: str, json_str: str, error_msg: str, source_url: str
    ):
        """JSON 파싱 에러 데이터를 파일로 저장"""
        try:
            import os
            from datetime import datetime

            # log/errors 디렉토리 생성
            os.makedirs("log/errors", exist_ok=True)

            # 타임스탬프와 모델 타입으로 파일명 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 밀리초까지
            filename = f"log/errors/json_error_{self.provider_type}_{timestamp}.txt"

            with open(filename, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("JSON 파싱 에러 로그\n")
                f.write(f"시간: {datetime.now().isoformat()}\n")
                f.write(f"모델: {self.provider_type}\n")
                f.write(f"URL: {source_url}\n")
                f.write(f"에러: {error_msg}\n")
                f.write("=" * 80 + "\n\n")

                f.write("전체 응답 텍스트:\n")
                f.write("-" * 40 + "\n")
                f.write(response_text)
                f.write("\n" + "-" * 40 + "\n\n")

                f.write("추출된 JSON 문자열:\n")
                f.write("-" * 40 + "\n")
                f.write(json_str)
                f.write("\n" + "-" * 40 + "\n")

            tqdm.write(f"💾 에러 데이터 저장: {filename}")

        except Exception as save_error:
            tqdm.write(f"⚠️  에러 데이터 저장 실패: {str(save_error)}")

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

    def _parse_price_value(self, price_value: Any) -> Optional[float]:
        """가격 값을 파싱하되 None일 경우 None 반환"""
        if price_value is None:
            return None
        if isinstance(price_value, str):
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
        elif "global.ppeum.com" in source_url:
            return "쁨글로벌의원"
        else:
            try:
                from urllib.parse import urlparse

                domain = urlparse(source_url).netloc
                return domain.replace("www.", "")
            except Exception:
                return "알 수 없음"

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
        elif "global.ppeum.com" in source_url:
            return "쁨글로벌의원"
        else:
            try:
                from urllib.parse import urlparse

                domain = urlparse(source_url).netloc.replace("www.", "")
                if "clinic" in domain:
                    return (
                        domain.replace(".com", "").replace(".co.kr", "").title()
                        + " 클리닉"
                    )
                else:
                    return domain.replace(".com", "").replace(".co.kr", "").title()
            except Exception:
                return "알 수 없는 클리닉"
