#!/usr/bin/env python3
"""
Playwright가 통합된 LLM Extractor 테스트
"""

import asyncio
import os
from dotenv import load_dotenv
from src.utils.llm_extractor import LLMTreatmentExtractor

async def test_playwright_extraction():
    """Playwright 통합 LLM Extractor 테스트"""

    # 환경변수 로드
    load_dotenv()

    # API 키 확인
    api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("❌ ANTHROPIC_AUTH_TOKEN 환경변수가 설정되지 않았습니다.")
        return

    # 테스트 URL
    test_url = "https://xenia.clinic/ko/products/8a2a54b8-0eaa-4d28-945b-2c76cb98eb9b"

    print(f"🚀 Playwright 통합 LLM Extractor 테스트")
    print(f"URL: {test_url}")
    print("=" * 80)

    try:
        # LLM Extractor 초기화
        extractor = LLMTreatmentExtractor(api_key=api_key, requests_per_minute=5)

        # Playwright로 추출 실행 (새로운 async 메소드)
        products = await extractor.extract_treatments_from_url(test_url)

        print(f"\n📊 추출 결과: {len(products)}개 상품")

        if products:
            for i, product in enumerate(products, 1):
                print(f"\n🎯 상품 {i}:")
                print(f"  - 클리닉: {product.clinic_name}")
                print(f"  - 상품명: {product.product_name}")
                print(f"  - 정상가: {product.product_original_price:,}원" if product.product_original_price else "  - 정상가: 없음")
                print(f"  - 이벤트가: {product.product_event_price:,}원" if product.product_event_price else "  - 이벤트가: 없음")
                print(f"  - 카테고리: {product.category}")
                print(f"  - 시술 수: {len(product.treatments)}개")

                for j, treatment in enumerate(product.treatments, 1):
                    print(f"    시술 {j}: {treatment.name}")
                    if treatment.dosage and treatment.unit:
                        print(f"      용량: {treatment.dosage}{treatment.unit}")
                    if treatment.equipments:
                        print(f"      장비: {', '.join(treatment.equipments)}")
                    if treatment.medications:
                        print(f"      약물: {', '.join(treatment.medications)}")
                    if treatment.treatment_type:
                        print(f"      유형: {treatment.treatment_type.value}")

        else:
            print("❌ 추출된 상품이 없습니다.")

    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_playwright_extraction())