#!/usr/bin/env python3
"""
API 호출 테스트 스크립트
client.chat.completions.create 방식이 제대로 작동하는지 확인
"""

import os
import json
from dotenv import load_dotenv

try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("❌ OpenAI 라이브러리가 설치되지 않았습니다: pip install openai")
    exit(1)


def test_api_call():
    """간단한 API 호출 테스트"""
    # 환경변수 로드
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
    base_url = os.getenv("ANTHROPIC_BASE_URL")

    print("🔍 API 설정 확인:")
    print(f"API Key: {'✅ 설정됨' if api_key else '❌ 없음'}")
    print(f"Base URL: {base_url if base_url else '❌ 없음'}")

    if not api_key:
        print("❌ ANTHROPIC_AUTH_TOKEN 환경변수가 설정되지 않았습니다.")
        return

    # OpenAI 클라이언트 초기화
    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    # 현재 사용 중인 모델
    model = "bedrock-claude-sonnet-4"
    print(f"🤖 사용 모델: {model}")

    # 간단한 테스트 프롬프트
    test_prompt = """
다음 간단한 JSON 형태로 응답해주세요:

{
  "test": "success",
  "message": "API 호출이 정상적으로 작동합니다",
  "model_used": "현재 사용 중인 모델명"
}

JSON만 응답해주세요:
"""

    try:
        print("\n🚀 API 호출 테스트 시작...")

        response = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": test_prompt}]
        )

        print("✅ API 호출 성공!")

        # 응답 내용 확인
        response_text = response.choices[0].message.content
        print("\n📝 원본 응답:")
        print("-" * 50)
        print(response_text)
        print("-" * 50)

        # JSON 파싱 테스트
        print("\n🔧 JSON 파싱 테스트:")
        try:
            import re

            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed_data = json.loads(json_str)
                print("✅ JSON 파싱 성공!")
                print("📊 파싱된 데이터:")
                print(json.dumps(parsed_data, ensure_ascii=False, indent=2))
            else:
                print("❌ JSON 형식을 찾을 수 없습니다")

        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 실패: {str(e)}")

        # 응답 메타데이터 확인
        print("\n📊 응답 메타데이터:")
        print(f"- 모델: {response.model}")
        print(
            f"- 사용 토큰: {response.usage.total_tokens if hasattr(response, 'usage') and response.usage else '정보 없음'}"
        )

    except Exception as e:
        print(f"❌ API 호출 실패: {str(e)}")
        print(f"오류 타입: {type(e).__name__}")

        # 자세한 오류 정보
        if hasattr(e, "response"):
            print(
                f"HTTP 상태 코드: {e.response.status_code if hasattr(e.response, 'status_code') else '알 수 없음'}"
            )
            print(
                f"응답 내용: {e.response.text if hasattr(e.response, 'text') else '없음'}"
            )


if __name__ == "__main__":
    test_api_call()
