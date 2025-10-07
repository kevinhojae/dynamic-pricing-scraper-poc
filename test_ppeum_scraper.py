"""
쁨 글로벌 스크래퍼 테스트 스크립트
"""
import asyncio
import os
import sys
from datetime import datetime

# 상위 디렉토리의 모듈을 import하기 위해 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ppeum_global_scraper import PpeumGlobalScraper
from multi_site_scraper import MultiSiteScraper


async def test_ppeum_global_scraper():
    """쁨 글로벌 스크래퍼 단독 테스트"""
    print("🧪 쁨 글로벌 스크래퍼 테스트 시작")
    print("="*50)

    # API 키 확인
    api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("❌ ANTHROPIC_AUTH_TOKEN 환경변수가 설정되지 않았습니다.")
        print("   export ANTHROPIC_AUTH_TOKEN='your-api-key' 를 실행해주세요.")
        return False

    try:
        # 스크래퍼 생성 및 실행
        scraper = PpeumGlobalScraper(api_key)
        products = await scraper.scrape_treatments()

        if products:
            print(f"\n✅ 테스트 성공!")
            print(f"📦 발견된 데이터:")
            print(f"   - 상품 수: {len(products)}개")

            # 시술 통계
            total_treatments = sum(len(product.treatments) for product in products)
            print(f"   - 총 시술 수: {total_treatments}개")

            # 샘플 데이터 출력
            print(f"\n📋 샘플 데이터:")
            for i, product in enumerate(products[:2], 1):
                print(f"   {i}. {product.product_name}")
                print(f"      - 클리닉: {product.clinic_name}")
                if product.product_event_price:
                    print(f"      - 이벤트가: {product.product_event_price:,}원")
                if product.product_original_price:
                    print(f"      - 정상가: {product.product_original_price:,}원")
                print(f"      - 구성 시술: {len(product.treatments)}개")
                if product.treatments:
                    for j, treatment in enumerate(product.treatments[:2], 1):
                        print(f"        {j}) {treatment.name}")

            # 결과 저장
            filename = scraper.save_results(products, "_test")
            print(f"\n💾 테스트 결과 저장: {filename}")

            return True
        else:
            print("❌ 테스트 실패: 데이터를 찾을 수 없습니다.")
            return False

    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_multi_site_scraper():
    """다중 사이트 스크래퍼 테스트"""
    print("\n🧪 다중 사이트 스크래퍼 테스트 시작")
    print("="*50)

    # API 키 확인
    api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("❌ ANTHROPIC_AUTH_TOKEN 환경변수가 설정되지 않았습니다.")
        return False

    try:
        # 다중 사이트 스크래퍼 생성
        multi_scraper = MultiSiteScraper(api_key)

        # 쁨 글로벌만 테스트
        print("🎯 쁨 글로벌 클리닉만 테스트...")
        products = await multi_scraper.scrape_ppeum_only()

        if products:
            print(f"✅ 다중 사이트 스크래퍼 테스트 성공!")
            print(f"📦 쁨 글로벌에서 {len(products)}개 상품 발견")

            # 결과 저장
            os.makedirs("data/raw", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/raw/multi_scraper_ppeum_test_{timestamp}.json"

            import json
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(
                    [product.model_dump() for product in products],
                    f,
                    ensure_ascii=False,
                    indent=2,
                    default=str
                )

            print(f"💾 다중 스크래퍼 테스트 결과 저장: {filename}")
            return True
        else:
            print("❌ 다중 사이트 스크래퍼 테스트 실패")
            return False

    except Exception as e:
        print(f"❌ 다중 사이트 스크래퍼 테스트 중 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_configuration():
    """설정 시스템 테스트"""
    print("\n🧪 설정 시스템 테스트")
    print("="*30)

    try:
        from src.config.site_configs import site_config_manager

        # 등록된 사이트 목록 확인
        sites = site_config_manager.list_sites()
        print(f"📋 등록된 사이트: {len(sites)}개")
        for site in sites:
            config = site_config_manager.get_config(site)
            print(f"   • {site}: {config.site_name} ({config.source_type.value})")

        # SPA 사이트 목록
        spa_sites = site_config_manager.get_spa_sites()
        print(f"\n🎭 SPA 사이트: {len(spa_sites)}개")
        for site in spa_sites:
            print(f"   • {site}")

        # 쁨 글로벌 설정 확인
        ppeum_config = site_config_manager.create_ppeum_global_config()
        print(f"\n🏥 쁨 글로벌 설정:")
        print(f"   - 사이트명: {ppeum_config.site_name}")
        print(f"   - 소스 타입: {ppeum_config.source_type}")
        print(f"   - 대상 URL: {ppeum_config.static_urls[0] if ppeum_config.static_urls else ppeum_config.base_url}")
        if ppeum_config.spa_config:
            print(f"   - 최대 상호작용: {ppeum_config.spa_config.max_interactions}번")
            print(f"   - 대기 시간: {ppeum_config.spa_config.wait_time}초")
            print(f"   - 클릭 요소: {len(ppeum_config.spa_config.click_elements)}개")

        print("✅ 설정 시스템 테스트 완료")
        return True

    except Exception as e:
        print(f"❌ 설정 시스템 테스트 중 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """메인 테스트 함수"""
    print("🚀 쁨 글로벌 스크래퍼 전체 테스트 시작")
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # .env 파일 로드
    from dotenv import load_dotenv
    load_dotenv()

    # API 키 사전 체크
    api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("❌ ANTHROPIC_AUTH_TOKEN 환경변수가 설정되지 않았습니다.")
        print("다음 중 하나의 방법으로 설정해주세요:")
        print("1. .env 파일에 ANTHROPIC_AUTH_TOKEN=your-api-key-here")
        print("2. export ANTHROPIC_AUTH_TOKEN='your-api-key-here'")
        print("\n⚠️  API 키 없이는 설정 시스템 테스트만 실행됩니다.")

        # API 키 없이는 설정 테스트만 실행
        tests = [("설정 시스템", test_configuration)]
    else:
        print(f"✅ ANTHROPIC_AUTH_TOKEN 설정 확인 (길이: {len(api_key)})")
        # 전체 테스트 실행
        tests = [
            ("설정 시스템", test_configuration),
            ("쁨 글로벌 스크래퍼", test_ppeum_global_scraper),
            ("다중 사이트 스크래퍼", test_multi_site_scraper),
        ]

    results = {}
    for test_name, test_func in tests:
        print(f"\n🧪 {test_name} 테스트 실행...")
        try:
            result = await test_func()
            results[test_name] = result
            if result:
                print(f"✅ {test_name} 테스트 성공")
            else:
                print(f"❌ {test_name} 테스트 실패")
        except Exception as e:
            print(f"💥 {test_name} 테스트 중 예외 발생: {str(e)}")
            results[test_name] = False

    # 전체 테스트 결과 요약
    print(f"\n{'='*60}")
    print("📊 전체 테스트 결과 요약")
    print("="*60)

    success_count = sum(1 for result in results.values() if result)
    total_count = len(results)

    for test_name, result in results.items():
        status = "✅ 성공" if result else "❌ 실패"
        print(f"   {test_name}: {status}")

    print(f"\n🎯 전체 결과: {success_count}/{total_count} 테스트 성공")
    print(f"⏰ 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if success_count == total_count:
        print("🎉 모든 테스트가 성공했습니다!")
    else:
        print("⚠️  일부 테스트가 실패했습니다. 로그를 확인해주세요.")


if __name__ == "__main__":
    asyncio.run(main())