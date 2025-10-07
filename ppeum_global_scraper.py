"""
쁨 글로벌 클리닉 전용 스크래퍼
"""
import asyncio
import os
from datetime import datetime
from typing import List

from src.config.site_configs import site_config_manager
from src.scrapers.spa_scraper import ConfigurableScraper
from src.utils.llm_extractor import LLMTreatmentExtractor
from src.models.schemas import ProductItem


class PpeumGlobalScraper:
    """쁨 글로벌 클리닉 전용 스크래퍼"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.llm_extractor = LLMTreatmentExtractor(api_key)
        self.config = site_config_manager.create_ppeum_global_config()

    async def scrape_treatments(self) -> List[ProductItem]:
        """쁨 글로벌 클리닉의 시술 정보 스크래핑"""
        print(f"🚀 쁨 글로벌 클리닉 스크래핑 시작...")
        print(f"📋 설정:")
        print(f"   - 소스 타입: {self.config.source_type}")
        print(f"   - 대상 URL: {self.config.static_urls[0] if self.config.static_urls else self.config.base_url}")
        print(f"   - SPA 모드: {self.config.spa_config.max_interactions}번 최대 상호작용")

        try:
            scraper = ConfigurableScraper(self.config, self.llm_extractor)
            products = await scraper.scrape_by_config()

            print(f"✅ 스크래핑 완료!")
            print(f"📦 발견된 상품: {len(products)}개")

            if products:
                # 시술 통계
                total_treatments = sum(len(product.treatments) for product in products)
                print(f"💉 총 시술 수: {total_treatments}개")

                # 샘플 상품 정보 출력
                print(f"\n📄 샘플 상품들:")
                for i, product in enumerate(products[:3], 1):
                    print(f"   {i}. {product.product_name}")
                    print(f"      클리닉: {product.clinic_name}")
                    if product.product_event_price:
                        print(f"      가격: {product.product_event_price:,}원")
                    print(f"      시술 수: {len(product.treatments)}개")

            return products

        except Exception as e:
            print(f"❌ 스크래핑 오류: {str(e)}")
            return []

    def save_results(self, products: List[ProductItem], suffix: str = "") -> str:
        """결과를 JSON 파일로 저장"""
        if not products:
            print("저장할 데이터가 없습니다.")
            return ""

        os.makedirs("data/raw", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/raw/ppeum_global_treatments_{timestamp}{suffix}.json"

        import json
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(
                [product.model_dump() for product in products],
                f,
                ensure_ascii=False,
                indent=2,
                default=str
            )

        print(f"💾 결과 저장 완료: {filename}")
        return filename


async def main():
    """메인 실행 함수"""
    # Anthropic API 키 확인
    api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("❌ ANTHROPIC_AUTH_TOKEN 환경변수가 설정되지 않았습니다.")
        print("다음 중 하나의 방법으로 설정해주세요:")
        print("1. .env 파일에 ANTHROPIC_AUTH_TOKEN=your-api-key-here")
        print("2. export ANTHROPIC_AUTH_TOKEN='your-api-key-here'")
        return

    # 스크래퍼 실행
    scraper = PpeumGlobalScraper(api_key)
    products = await scraper.scrape_treatments()

    # 결과 저장
    if products:
        scraper.save_results(products)
    else:
        print("📭 스크래핑된 데이터가 없습니다.")


if __name__ == "__main__":
    asyncio.run(main())