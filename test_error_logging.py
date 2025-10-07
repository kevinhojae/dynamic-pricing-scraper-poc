"""
에러 로깅 테스트 스크립트
"""
import asyncio
from src.utils.unified_llm_extractor import UnifiedLLMTreatmentExtractor


async def test_error_logging():
    """에러 로깅 테스트"""
    # 가짜 JSON 응답으로 에러 유발
    extractor = UnifiedLLMTreatmentExtractor("gemini")

    # 구문 오류가 있는 JSON 응답 시뮬레이션 (JSON 끝부분 잘림)
    broken_json_response = """{
  "clinic_name": "테스트 클리닉",
  "category": "테스트 카테고리",
  "products": [
    {
      "product_name": "테스트 상품",
      "product_original_price": 100000,
      "product_event_price": 50000,
      "treatments": [
        {
          "name": "테스트 시술",
          "dosage": 1,
          "unit": "회",
          "equipments": [],
          "medications": [],
          "treatment_type": "device",
          "description": "테스트용 시술입니다"
        }
      ]
    }
  ]"""  # 마지막 중괄호 누락

    # 파싱 시도 (에러 발생 예상)
    result = extractor._parse_llm_response(broken_json_response, "https://test.com")
    print(f"결과: {len(result)}개 상품")


if __name__ == "__main__":
    asyncio.run(test_error_logging())