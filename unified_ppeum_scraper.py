"""
쁨 글로벌 클리닉 통합 스크래퍼 (Claude/Gemini 지원)
"""
import argparse
import asyncio
import os
import json
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

from src.config.site_configs import site_config_manager
from src.scrapers.unified_spa_scraper import UnifiedConfigurableScraper
from src.utils.unified_llm_extractor import UnifiedLLMTreatmentExtractor
from src.models.schemas import ProductItem


class UnifiedPpeumGlobalScraper:
    """쁨 글로벌 클리닉 통합 스크래퍼 (Claude/Gemini 지원)"""

    def __init__(self, provider_type: str, api_key: str = None):
        self.provider_type = provider_type.lower()
        self.api_key = api_key
        self.llm_extractor = UnifiedLLMTreatmentExtractor(provider_type, api_key)
        self.config = site_config_manager.create_ppeum_global_config()

    async def scrape_treatments(self) -> List[ProductItem]:
        """쁨 글로벌 클리닉의 시술 정보 스크래핑"""
        print(f"🚀 쁨 글로벌 클리닉 스크래핑 시작... (모델: {self.provider_type.title()})")
        print(f"📋 설정:")
        print(f"   - 소스 타입: {self.config.source_type}")
        print(f"   - 대상 URL: {self.config.static_urls[0] if self.config.static_urls else self.config.base_url}")
        print(f"   - SPA 모드: {self.config.spa_config.max_interactions}번 최대 상호작용")

        try:
            scraper = UnifiedConfigurableScraper(self.config, self.llm_extractor)
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
        """결과를 JSON 파일로 저장 (모델 정보 포함)"""
        if not products:
            print("저장할 데이터가 없습니다.")
            return ""

        os.makedirs("data/raw", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/raw/ppeum_global_treatments_{timestamp}_{self.provider_type}{suffix}.json"

        # 모델 정보 가져오기
        model_info = self.llm_extractor.get_model_info()

        # 결과 데이터 구조 생성
        result_data = {
            "model_info": {
                **model_info,
                "extraction_timestamp": datetime.now().isoformat(),
                "total_products": len(products),
                "total_treatments": sum(len(product.treatments) for product in products)
            },
            "results": [product.model_dump() for product in products]
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(
                result_data,
                f,
                ensure_ascii=False,
                indent=2,
                default=str
            )

        print(f"💾 결과 저장 완료: {filename}")
        print(f"📊 모델 정보:")
        print(f"   - 제공자: {model_info['source']} ({model_info['provider']})")
        print(f"   - 모델: {model_info['model']}")
        print(f"   - 프롬프트 버전: {model_info['prompt_version']}")

        return filename


def get_api_key(provider_type: str) -> str:
    """환경변수에서 API 키 가져오기"""
    if provider_type.lower() == "claude":
        api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
        if not api_key:
            print("❌ ANTHROPIC_AUTH_TOKEN 환경변수가 설정되지 않았습니다.")
            print("다음 중 하나의 방법으로 설정해주세요:")
            print("1. .env 파일에 ANTHROPIC_AUTH_TOKEN=your-api-key-here")
            print("2. export ANTHROPIC_AUTH_TOKEN='your-api-key-here'")
            exit(1)
    elif provider_type.lower() == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("❌ GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
            print("다음 중 하나의 방법으로 설정해주세요:")
            print("1. .env 파일에 GEMINI_API_KEY=your-api-key-here")
            print("2. export GEMINI_API_KEY='your-api-key-here'")
            exit(1)
    else:
        print(f"❌ 지원하지 않는 모델: {provider_type}")
        print("사용 가능한 모델: claude, gemini")
        exit(1)

    return api_key


async def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(
        description="쁨 글로벌 클리닉 스크래퍼 (Claude/Gemini 지원)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python unified_ppeum_scraper.py claude     # Claude로 스크래핑
  python unified_ppeum_scraper.py gemini     # Gemini로 스크래핑

환경변수 설정:
  Claude 사용시: ANTHROPIC_AUTH_TOKEN=your-claude-api-key
  Gemini 사용시: GEMINI_API_KEY=your-gemini-api-key
        """
    )

    parser.add_argument(
        "model",
        choices=["claude", "gemini"],
        help="사용할 LLM 모델 (claude 또는 gemini)"
    )

    parser.add_argument(
        "--suffix",
        default="",
        help="출력 파일명에 추가할 접미사"
    )

    args = parser.parse_args()

    # API 키 확인
    api_key = get_api_key(args.model)

    print(f"🤖 {args.model.title()} 모델을 사용하여 스크래핑을 시작합니다...")

    # 스크래퍼 실행
    scraper = UnifiedPpeumGlobalScraper(args.model, api_key)
    products = await scraper.scrape_treatments()

    # 결과 저장
    if products:
        scraper.save_results(products, args.suffix)
    else:
        print("📭 스크래핑된 데이터가 없습니다.")


if __name__ == "__main__":
    asyncio.run(main())