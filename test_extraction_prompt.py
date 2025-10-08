#!/usr/bin/env python3
"""
실제 extraction 프롬프트로 API 호출 테스트
왜 extraction 결과가 0개인지 확인
"""

import os
import json
import re
from dotenv import load_dotenv

try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("❌ OpenAI 라이브러리가 설치되지 않았습니다: pip install openai")
    exit(1)


def test_extraction_prompt():
    """실제 extraction 프롬프트로 테스트"""
    # 환경변수 로드
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    base_url = os.getenv("ANTHROPIC_BASE_URL")

    if not api_key:
        print("❌ ANTHROPIC_AUTH_TOKEN 환경변수가 설정되지 않았습니다.")
        return

    # OpenAI 클라이언트 초기화
    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    model = "bedrock-claude-sonnet-4"

    # 실제 extraction에서 사용하는 프롬프트 (간소화된 버전)
    test_content = """
    세니아 클리닉

    슈링크 유니버스 울트라 MP모드
    - 300샷: 정상가 180,000원 → 이벤트가 99,000원
    - 600샷: 정상가 350,000원 → 이벤트가 198,000원

    보톡스 주사
    - 50유닛: 정상가 150,000원 → 이벤트가 89,000원
    """

    source_url = "https://xenia.clinic/ko/products/test"

    extraction_prompt = f"""
다음 피부과/미용 클리닉 웹페이지 텍스트에서 개별 상품 옵션 정보를 정확하게 추출해주세요.

웹페이지 내용:
{test_content}

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

JSON만 응답해주세요:
"""

    try:
        print("🚀 Extraction 프롬프트 테스트 시작...")

        response = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": extraction_prompt}]
        )

        response_text = response.choices[0].message.content
        print("✅ API 호출 성공!")

        print("\n📝 원본 응답 (처음 1000자):")
        print("-" * 50)
        print(response_text[:1000])
        if len(response_text) > 1000:
            print("...")
        print("-" * 50)

        # JSON 파싱 테스트 (실제 코드와 동일한 방식)
        print("\n🔧 JSON 파싱 테스트:")
        try:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed_data = json.loads(json_str)
                print("✅ JSON 파싱 성공!")

                # products 개수 확인
                products = parsed_data.get("products", [])
                print(f"📦 추출된 products 개수: {len(products)}")

                if products:
                    print("📊 첫 번째 product:")
                    first_product = products[0]
                    print(f"  - product_name: {first_product.get('product_name')}")
                    print(
                        f"  - treatments 개수: {len(first_product.get('treatments', []))}"
                    )
                    print(
                        f"  - original_price: {first_product.get('product_original_price')}"
                    )
                    print(
                        f"  - event_price: {first_product.get('product_event_price')}"
                    )
                else:
                    print("❌ products 배열이 비어있습니다!")

            else:
                print("❌ JSON 형식을 찾을 수 없습니다")
                print("응답이 JSON 형태가 아닐 수 있습니다.")

        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 실패: {str(e)}")
            print("파싱 시도한 JSON:")
            if "json_match" in locals():
                print(json_match.group()[:500])

    except Exception as e:
        print(f"❌ API 호출 실패: {str(e)}")


if __name__ == "__main__":
    test_extraction_prompt()
