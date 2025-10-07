"""
다중 사이트 스크래퍼 - 설정 기반으로 여러 사이트 동시 스크래핑
"""
import asyncio
import os
import time
from datetime import datetime
from typing import List, Dict, Any

from src.config.site_configs import site_config_manager
from src.scrapers.spa_scraper import ConfigurableScraper
from src.utils.llm_extractor import LLMTreatmentExtractor
from src.models.schemas import ProductItem


class MultiSiteScraper:
    """여러 사이트를 설정 기반으로 스크래핑하는 클래스"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.llm_extractor = LLMTreatmentExtractor(api_key)

    async def scrape_all_sites(self, site_keys: List[str] = None) -> Dict[str, Any]:
        """지정된 사이트들을 모두 스크래핑"""

        if site_keys is None:
            site_keys = site_config_manager.list_sites()

        print(f"🚀 다중 사이트 스크래핑 시작")
        print(f"📋 대상 사이트: {', '.join(site_keys)}")

        results = {}
        all_products = []

        for site_key in site_keys:
            print(f"\n{'='*50}")
            print(f"🏥 사이트: {site_key}")

            start_time = time.time()
            config = site_config_manager.get_config(site_key)

            if not config:
                print(f"❌ {site_key} 설정을 찾을 수 없습니다.")
                results[site_key] = {
                    "success": False,
                    "error": "Configuration not found",
                    "products": [],
                    "product_count": 0,
                    "duration": 0
                }
                continue

            try:
                scraper = ConfigurableScraper(config, self.llm_extractor)
                products = await scraper.scrape_by_config()

                duration = time.time() - start_time
                treatment_count = sum(len(product.treatments) for product in products)

                results[site_key] = {
                    "success": True,
                    "error": None,
                    "products": products,
                    "product_count": len(products),
                    "treatment_count": treatment_count,
                    "duration": duration,
                    "source_type": config.source_type.value,
                    "site_name": config.site_name
                }

                all_products.extend(products)

                print(f"✅ {config.site_name} 완료")
                print(f"   📦 상품: {len(products)}개")
                print(f"   💉 시술: {treatment_count}개")
                print(f"   ⏱️  소요시간: {duration:.1f}초")

            except Exception as e:
                duration = time.time() - start_time
                print(f"❌ {site_key} 스크래핑 오류: {str(e)}")

                results[site_key] = {
                    "success": False,
                    "error": str(e),
                    "products": [],
                    "product_count": 0,
                    "treatment_count": 0,
                    "duration": duration,
                    "source_type": config.source_type.value if config else "unknown",
                    "site_name": config.site_name if config else site_key
                }

        # 전체 결과 요약
        self._print_summary(results, all_products)

        return {
            "results": results,
            "all_products": all_products,
            "summary": self._generate_summary(results, all_products)
        }

    async def scrape_ppeum_only(self) -> List[ProductItem]:
        """쁨 글로벌 클리닉만 스크래핑"""
        config = site_config_manager.create_ppeum_global_config()
        scraper = ConfigurableScraper(config, self.llm_extractor)
        return await scraper.scrape_by_config()

    async def scrape_spa_sites_only(self) -> Dict[str, Any]:
        """SPA 타입 사이트들만 스크래핑"""
        spa_sites = site_config_manager.get_spa_sites()
        return await self.scrape_all_sites(spa_sites)

    def _print_summary(self, results: Dict[str, Any], all_products: List[ProductItem]):
        """스크래핑 결과 요약 출력"""
        print(f"\n{'='*60}")
        print(f"📊 스크래핑 결과 요약")
        print(f"{'='*60}")

        successful_sites = [k for k, v in results.items() if v["success"]]
        failed_sites = [k for k, v in results.items() if not v["success"]]

        print(f"✅ 성공한 사이트: {len(successful_sites)}개")
        print(f"❌ 실패한 사이트: {len(failed_sites)}개")

        if successful_sites:
            print(f"\n🏆 성공한 사이트들:")
            for site in successful_sites:
                result = results[site]
                print(f"   • {result['site_name']}: {result['product_count']}개 상품, {result['treatment_count']}개 시술")

        if failed_sites:
            print(f"\n💥 실패한 사이트들:")
            for site in failed_sites:
                result = results[site]
                print(f"   • {result['site_name']}: {result['error']}")

        total_products = len(all_products)
        total_treatments = sum(len(product.treatments) for product in all_products)
        total_duration = sum(result["duration"] for result in results.values())

        print(f"\n📈 전체 통계:")
        print(f"   📦 총 상품 수: {total_products}개")
        print(f"   💉 총 시술 수: {total_treatments}개")
        print(f"   ⏱️  총 소요시간: {total_duration:.1f}초")

        if total_products > 0:
            print(f"   📊 평균 상품당 시술 수: {total_treatments/total_products:.1f}개")

    def _generate_summary(self, results: Dict[str, Any], all_products: List[ProductItem]) -> Dict[str, Any]:
        """요약 정보 생성"""
        return {
            "total_sites": len(results),
            "successful_sites": len([r for r in results.values() if r["success"]]),
            "failed_sites": len([r for r in results.values() if not r["success"]]),
            "total_products": len(all_products),
            "total_treatments": sum(len(product.treatments) for product in all_products),
            "total_duration": sum(result["duration"] for result in results.values()),
            "scraping_timestamp": datetime.now().isoformat()
        }

    def save_results(self, scraping_results: Dict[str, Any], suffix: str = "") -> str:
        """전체 결과를 JSON 파일로 저장"""
        os.makedirs("data/raw", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/raw/multi_site_scraping_{timestamp}{suffix}.json"

        import json

        # ProductItem 객체들을 직렬화 가능한 형태로 변환
        serializable_results = {}
        for site_key, result in scraping_results["results"].items():
            serializable_results[site_key] = {
                **result,
                "products": [product.model_dump() for product in result["products"]]
            }

        save_data = {
            "results": serializable_results,
            "summary": scraping_results["summary"],
            "all_products": [product.model_dump() for product in scraping_results["all_products"]]
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2, default=str)

        print(f"💾 전체 결과 저장 완료: {filename}")
        return filename


async def main():
    """메인 실행 함수 - 사용 예시"""
    # Anthropic API 키 확인
    api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("❌ ANTHROPIC_AUTH_TOKEN 환경변수가 설정되지 않았습니다.")
        print("다음 중 하나의 방법으로 설정해주세요:")
        print("1. .env 파일에 ANTHROPIC_AUTH_TOKEN=your-api-key-here")
        print("2. export ANTHROPIC_AUTH_TOKEN='your-api-key-here'")
        return

    # 다중 사이트 스크래퍼 생성
    multi_scraper = MultiSiteScraper(api_key)

    # 사용 가능한 옵션들
    print("사용 가능한 스크래핑 옵션:")
    print("1. 모든 사이트 스크래핑")
    print("2. 쁨 글로벌만 스크래핑")
    print("3. SPA 사이트들만 스크래핑")
    print("4. 특정 사이트들만 스크래핑")

    # 예시: 쁨 글로벌만 스크래핑
    print(f"\n🎯 쁨 글로벌 클리닉 스크래핑 실행...")
    products = await multi_scraper.scrape_ppeum_only()

    if products:
        # 결과 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import json
        os.makedirs("data/raw", exist_ok=True)
        filename = f"data/raw/ppeum_global_only_{timestamp}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(
                [product.model_dump() for product in products],
                f,
                ensure_ascii=False,
                indent=2,
                default=str
            )

        print(f"💾 쁨 글로벌 결과 저장: {filename}")

    # 전체 사이트 스크래핑 예시 (주석 처리)
    # print(f"\n🌐 전체 사이트 스크래핑...")
    # results = await multi_scraper.scrape_all_sites()
    # multi_scraper.save_results(results)


if __name__ == "__main__":
    asyncio.run(main())