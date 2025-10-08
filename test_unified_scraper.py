"""
통합 스크래퍼 테스트 스크립트
"""

import asyncio
import os

from dotenv import load_dotenv

from src.utils.llm_providers import create_llm_provider
from src.utils.prompt_manager import PromptManager

# .env 파일 로드
load_dotenv()


async def test_prompt_manager():
    """프롬프트 매니저 테스트"""
    print("🧪 프롬프트 매니저 테스트...")

    try:
        pm = PromptManager()

        # 버전 정보 확인
        print(f"전체 프롬프트 버전: {pm.get_global_version()}")

        # 프롬프트 정보 확인
        prompt_info = pm.get_prompt_info("product_extraction")
        print(f"상품 추출 프롬프트 버전: {prompt_info['version']}")
        print(f"상품 추출 프롬프트 설명: {prompt_info['description']}")

        # 프롬프트 템플릿 생성 테스트
        formatted_prompt = pm.format_prompt(
            "product_extraction",
            text_content="테스트 콘텐츠",
            source_url="https://test.com",
        )

        print("✅ 프롬프트 매니저 테스트 성공")
        print(f"📝 생성된 프롬프트 길이: {len(formatted_prompt)} 문자")

    except Exception as e:
        print(f"❌ 프롬프트 매니저 테스트 실패: {str(e)}")


async def test_llm_providers():
    """LLM 제공자 테스트"""
    print("\n🧪 LLM 제공자 테스트...")

    # Claude 테스트
    claude_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    if claude_key:
        try:
            print("🤖 Claude 제공자 테스트...")
            claude_provider = create_llm_provider("claude", claude_key)
            model_info = claude_provider.get_model_info()
            print(f"Claude 모델 정보: {model_info}")
            print("✅ Claude 제공자 초기화 성공")
        except Exception as e:
            print(f"❌ Claude 제공자 테스트 실패: {str(e)}")
    else:
        print("⚠️  ANTHROPIC_AUTH_TOKEN이 설정되지 않아 Claude 테스트 건너뜀")

    # Gemini 테스트
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            print("🤖 Gemini 제공자 테스트...")
            gemini_provider = create_llm_provider("gemini", gemini_key)
            model_info = gemini_provider.get_model_info()
            print(f"Gemini 모델 정보: {model_info}")
            print("✅ Gemini 제공자 초기화 성공")
        except Exception as e:
            print(f"❌ Gemini 제공자 테스트 실패: {str(e)}")
    else:
        print("⚠️  GEMINI_API_KEY가 설정되지 않아 Gemini 테스트 건너뜀")


async def test_unified_extractor():
    """통합 추출기 테스트"""
    print("\n🧪 통합 추출기 테스트...")

    # 사용 가능한 모델 확인
    claude_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not claude_key and not gemini_key:
        print("⚠️  API 키가 설정되지 않아 추출기 테스트 건너뜀")
        return

    # Claude 테스트
    if claude_key:
        try:
            from src.utils.unified_llm_extractor import UnifiedLLMTreatmentExtractor

            print("🤖 Claude 통합 추출기 테스트...")
            extractor = UnifiedLLMTreatmentExtractor("claude", claude_key)
            model_info = extractor.get_model_info()
            print(f"Claude 추출기 모델 정보: {model_info}")
            print("✅ Claude 통합 추출기 초기화 성공")

        except Exception as e:
            print(f"❌ Claude 통합 추출기 테스트 실패: {str(e)}")

    # Gemini 테스트
    if gemini_key:
        try:
            from src.utils.unified_llm_extractor import UnifiedLLMTreatmentExtractor

            print("🤖 Gemini 통합 추출기 테스트...")
            extractor = UnifiedLLMTreatmentExtractor("gemini", gemini_key)
            model_info = extractor.get_model_info()
            print(f"Gemini 추출기 모델 정보: {model_info}")
            print("✅ Gemini 통합 추출기 초기화 성공")

        except Exception as e:
            print(f"❌ Gemini 통합 추출기 테스트 실패: {str(e)}")


async def main():
    """메인 테스트 함수"""
    print("🚀 통합 스크래퍼 시스템 테스트 시작\n")

    await test_prompt_manager()
    await test_llm_providers()
    await test_unified_extractor()

    print("\n✅ 모든 테스트 완료!")
    print("\n사용법:")
    print("python unified_ppeum_scraper.py claude   # Claude로 스크래핑")
    print("python unified_ppeum_scraper.py gemini   # Gemini로 스크래핑")


if __name__ == "__main__":
    asyncio.run(main())
