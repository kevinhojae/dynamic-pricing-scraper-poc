import os
import json
import re
import time
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from tqdm import tqdm

from src.models.schemas import TreatmentItem, TreatmentType, EquipmentType

# Gemini API를 선택적으로 import
try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


class GeminiTreatmentExtractor:
    def __init__(self, api_key: Optional[str] = None, requests_per_minute: int = 10):
        # API 키 설정 (환경변수에서 가져오거나 직접 입력)
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("⚠️  GEMINI_API_KEY가 설정되지 않았습니다.")
            print("환경변수로 설정하거나 직접 전달해주세요:")
            print("export GEMINI_API_KEY='your-api-key-here'")
            return

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash-lite")

        # Rate limiting 설정
        self.requests_per_minute = requests_per_minute
        self.min_delay_between_requests = 60.0 / requests_per_minute  # 초 단위
        self.last_request_time = 0.0

    def extract_treatments_from_html(
        self, html_content: str, source_url: str
    ) -> List[TreatmentItem]:
        """HTML 컨텐츠에서 시술 정보를 추출합니다."""
        if not self.api_key:
            return []

        # HTML을 텍스트로 변환
        soup = BeautifulSoup(html_content, "html.parser")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text_content = soup.get_text(separator=" ", strip=True)

        # 텍스트가 너무 길면 자르기 (Gemini API 제한)
        if len(text_content) > 30000:
            text_content = text_content[:30000] + "..."

        prompt = self._create_extraction_prompt(text_content, source_url)

        return self._make_api_request_with_retry(prompt, source_url, text_content)

    def _create_extraction_prompt(self, text_content: str, source_url: str) -> str:
        return f"""
다음 피부과/미용 클리닉 웹페이지 텍스트에서 시술 정보를 정확하게 추출해주세요.

웹페이지 내용:
{text_content}

출처 URL: {source_url}

다음 JSON 형식으로 시술 정보를 추출해주세요. 각 key factor를 정확히 추출하는 것이 매우 중요합니다:

{{
  "clinic_name": "병원명 (URL이나 페이지에서 추출)",
  "treatments": [
    {{
      "treatment_name": "시술명 (예: 써마지FLX, 울쎄라)",
      "option_name": "옵션명 (예: 300샷, 600샷, 아이써마지 225샷)",
      "equipment_name": "기기명 (예: 써마지FLX, 울쎄라피 프라임)",
      "medication": "약물명 (있다면)",
      "dosage": "용량 (예: 300샷, 1cc)",
      "unit": "단위 (예: 샷, cc, 회)",
      "price": 현재_판매가격_숫자만,
      "original_price": 정상가_숫자만,
      "discount_rate": 할인율_퍼센트_숫자만,
      "treatment_type": "laser|injection|skincare|surgical|device 중 하나",
      "equipment_used": ["co2_laser", "picosure", "ulthera", "botox", "filler", "thread_lift", "hifu", "rf", "ipl"],
      "description": "시술 설명",
      "duration": 시술시간_분단위_숫자만,
      "target_area": ["타겟 부위"],
      "benefits": ["효과1", "효과2"],
      "recovery_time": "회복기간"
    }}
  ]
}}

핵심 추출 규칙:
1. **가격 정보**: 정상가와 할인가를 정확히 구분하여 추출
   - 정상가: 원래 가격 (취소선이 있거나 "원가" 표시)
   - 현재가: 실제 판매 가격 (강조 표시된 가격)
   - 할인율: (정상가-현재가)/정상가 * 100

2. **상품명/옵션명**:
   - 상품명: 기본 시술명 (예: "써마지FLX")
   - 옵션명: 세부 옵션 (예: "300샷", "아이써마지 225샷")

3. **기기/약물/용량**:
   - 기기명: 사용되는 장비명 정확히 추출
   - 약물: 보톡스, 필러 등 주입되는 약물
   - 용량: 샷 수, cc 수 등 구체적 용량

4. **병원명**: URL 도메인이나 페이지 제목에서 추출

5. 가격이 없으면 null, 정보가 없으면 null로 설정
6. 시술과 무관한 내용은 제외
7. 중복 시술은 하나만 추출

JSON만 응답해주세요:
"""

    def _parse_gemini_response(
        self, response_text: str, source_url: str
    ) -> List[TreatmentItem]:
        """Gemini 응답을 파싱하여 TreatmentItem 리스트로 변환"""
        try:
            # JSON 부분만 추출
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if not json_match:
                tqdm.write("⚠️  JSON 형식을 찾을 수 없습니다")
                return []

            json_str = json_match.group()
            data = json.loads(json_str)

            # 병원명 추출
            clinic_name = data.get("clinic_name") or self._extract_clinic_name(source_url)

            treatments = []
            for item in data.get("treatments", []):
                try:
                    treatment = self._create_treatment_item(item, source_url, clinic_name)
                    if treatment:
                        treatments.append(treatment)
                except Exception as e:
                    tqdm.write(f"⚠️  시술 파싱 오류: {str(e)}")
                    continue

            return treatments

        except json.JSONDecodeError as e:
            tqdm.write(f"❌ JSON 파싱 오류: {str(e)}")
            tqdm.write(f"응답 텍스트: {response_text[:500]}...")
            return []
        except Exception as e:
            tqdm.write(f"❌ 응답 파싱 오류: {str(e)}")
            return []

    def _create_treatment_item(
        self, item: Dict[str, Any], source_url: str, clinic_name: str
    ) -> Optional[TreatmentItem]:
        """딕셔너리에서 TreatmentItem 생성"""
        try:
            treatment_name = item.get("treatment_name", "").strip()
            if not treatment_name:
                return None

            # 가격 처리 (할인율 계산 포함)
            price = self._parse_price(item.get("price"))
            original_price = self._parse_price(item.get("original_price"))

            # 할인율 계산
            discount_rate = None
            if original_price and original_price > 0 and price < original_price:
                discount_rate = round(((original_price - price) / original_price) * 100, 1)
            elif item.get("discount_rate"):
                discount_rate = float(item.get("discount_rate"))

            # 시술 유형 매핑
            type_mapping = {
                "laser": TreatmentType.LASER,
                "injection": TreatmentType.INJECTION,
                "skincare": TreatmentType.SKINCARE,
                "surgical": TreatmentType.SURGICAL,
                "device": TreatmentType.DEVICE,
            }
            treatment_type = type_mapping.get(
                item.get("treatment_type", "device"), TreatmentType.DEVICE
            )

            # 장비 매핑
            equipment_mapping = {
                "co2_laser": EquipmentType.LASER_CO2,
                "picosure": EquipmentType.LASER_PICOSURE,
                "ulthera": EquipmentType.LASER_ULTHERA,
                "botox": EquipmentType.BOTOX,
                "filler": EquipmentType.FILLER,
                "thread_lift": EquipmentType.THREAD_LIFT,
                "hifu": EquipmentType.HIFU,
                "rf": EquipmentType.RF,
                "ipl": EquipmentType.IPL,
            }

            equipment_used = []
            for eq in item.get("equipment_used", []):
                if eq in equipment_mapping:
                    equipment_used.append(equipment_mapping[eq])

            return TreatmentItem(
                # Key Factors
                source_url=source_url,
                source_channel=self._extract_source_channel(source_url),
                clinic_name=clinic_name,
                treatment_name=treatment_name,
                option_name=item.get("option_name"),
                equipment_name=item.get("equipment_name"),
                medication=item.get("medication"),
                dosage=item.get("dosage"),
                unit=item.get("unit"),
                price=price,
                original_price=original_price,
                discount_rate=discount_rate,
                # 기존 필드들
                treatment_type=treatment_type,
                equipment_used=equipment_used,
                description=item.get("description", ""),
                duration=item.get("duration"),
                target_area=item.get("target_area", []),
                benefits=item.get("benefits", []),
                recovery_time=item.get("recovery_time"),
            )

        except Exception as e:
            tqdm.write(f"⚠️  TreatmentItem 생성 오류: {str(e)}")
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

    def _make_api_request_with_retry(
        self, prompt: str, source_url: str, text_content: str, max_retries: int = 3
    ) -> List[TreatmentItem]:
        """Retry 로직과 rate limiting이 적용된 API 요청"""
        for attempt in range(max_retries):
            try:
                tqdm.write(
                    f"🤖 Gemini로 데이터 추출 중... ({len(text_content)} chars) - 시도 {attempt + 1}/{max_retries}"
                )

                # Rate limiting 적용
                self._wait_for_rate_limit()

                response = self.model.generate_content(prompt)
                result = self._parse_gemini_response(response.text, source_url)

                tqdm.write(f"✅ {len(result)}개 시술 정보 추출 완료")
                return result

            except Exception as e:
                error_msg = str(e)
                tqdm.write(
                    f"❌ Gemini API 오류 (시도 {attempt + 1}/{max_retries}): {error_msg}"
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
                    return domain.replace(".com", "").replace(".co.kr", "").title() + " 클리닉"
                else:
                    return domain.replace(".com", "").replace(".co.kr", "").title()
            except:
                return "알 수 없는 클리닉"
