#!/usr/bin/env python3
"""
실제 스크래핑 테스트 (타임아웃 추적용)
"""

import asyncio
import os
import sys
from datetime import datetime


async def test_actual_scraping():
    print("🚀 실제 스크래핑 테스트 시작")
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 환경 설정
    from dotenv import load_dotenv

    load_dotenv()

    sys.path.append(".")
    from ppeum_global_scraper import PpeumGlobalScraper

    api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("❌ API 키가 없습니다")
        return

    try:
        print("\n1️⃣ 스크래퍼 생성")
        scraper = PpeumGlobalScraper(api_key)
        print("✅ 스크래퍼 생성 완료")

        print("\n2️⃣ 실제 스크래핑 시작 (이 부분에서 timeout 가능성 높음)")
        print("   - 이 단계에서 Playwright가 실행되고 LLM API 호출이 발생합니다")
        print("   - 예상 소요 시간: 1-3분")

        start_time = datetime.now()
        products = await scraper.scrape_treatments()
        end_time = datetime.now()

        duration = (end_time - start_time).total_seconds()
        print(f"✅ 스크래핑 완료! 소요시간: {duration:.1f}초")

        if products:
            print("\n3️⃣ 결과 확인")
            print(f"   📦 발견된 상품: {len(products)}개")

            total_treatments = sum(len(product.treatments) for product in products)
            print(f"   💉 총 시술 수: {total_treatments}개")

            print("\n   📋 첫 번째 상품 샘플:")
            if products:
                product = products[0]
                print(f"      상품명: {product.product_name}")
                print(f"      클리닉: {product.clinic_name}")
                if product.product_event_price:
                    print(f"      이벤트가: {product.product_event_price:,}원")
                print(f"      구성 시술: {len(product.treatments)}개")

            # 결과 저장
            scraper.save_results(products, "_test")
            print("   💾 결과 저장 완료")

        else:
            print("❌ 스크래핑 결과가 없습니다")

    except asyncio.TimeoutError:
        print("❌ 타임아웃 발생! 네트워크나 API 응답이 너무 느림")
    except Exception as e:
        print(f"❌ 스크래핑 오류: {e}")
        import traceback

        traceback.print_exc()

    print(f"\n⏰ 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(test_actual_scraping())
