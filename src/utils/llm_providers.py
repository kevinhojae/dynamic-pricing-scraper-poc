import os
import time
import asyncio
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
from tqdm import tqdm

from src.utils.prompt_manager import PromptManager


class LLMProvider(ABC):
    """LLM 제공자를 위한 추상 기본 클래스"""

    def __init__(self, api_key: str, requests_per_minute: int = 10):
        self.api_key = api_key
        self.requests_per_minute = requests_per_minute
        self.min_delay_between_requests = 60.0 / requests_per_minute
        self.last_request_time = 0.0
        self.prompt_manager = PromptManager()

    @abstractmethod
    async def generate_async(self, prompt: str) -> str:
        """비동기 텍스트 생성"""
        pass

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """동기 텍스트 생성"""
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """모델 정보 반환"""
        pass

    def _wait_for_rate_limit(self):
        """Rate limiting을 위한 대기"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.min_delay_between_requests:
            wait_time = self.min_delay_between_requests - time_since_last_request
            tqdm.write(f"⏱️ Rate limiting: {wait_time:.1f}초 대기 중...")
            time.sleep(wait_time)

        self.last_request_time = time.time()


class ClaudeProvider(LLMProvider):
    """Claude API 제공자"""

    def __init__(self, api_key: str, requests_per_minute: int = 10):
        super().__init__(api_key, requests_per_minute)

        # OpenAI 클라이언트 import (LiteLLM Proxy 사용)
        try:
            import openai
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url=os.getenv("ANTHROPIC_BASE_URL")
            )
            self.model = "bedrock-claude-sonnet-4"
        except ImportError:
            raise ImportError("openai 패키지가 필요합니다: pip install openai")

    async def generate_async(self, prompt: str) -> str:
        """비동기 Claude API 호출"""
        self._wait_for_rate_limit()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                # max_tokens 제한 제거 - 완전한 JSON 응답을 위해
            )
            return response.choices[0].message.content

        except Exception as e:
            raise Exception(f"Claude API 오류: {str(e)}")

    def generate(self, prompt: str) -> str:
        """동기 Claude API 호출"""
        self._wait_for_rate_limit()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                # max_tokens 제한 제거 - 완전한 JSON 응답을 위해
            )
            return response.choices[0].message.content

        except Exception as e:
            raise Exception(f"Claude API 오류: {str(e)}")

    def get_model_info(self) -> Dict[str, Any]:
        """Claude 모델 정보 반환"""
        return {
            "source": "claude",
            "model": self.model,
            "provider": "Anthropic",
            "version": "4.0"
        }


class GeminiProvider(LLMProvider):
    """Google Gemini API 제공자"""

    def __init__(self, api_key: str, requests_per_minute: int = 10):
        super().__init__(api_key, requests_per_minute)

        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
            self.genai = genai
        except ImportError:
            raise ImportError("google-generativeai 패키지가 필요합니다: pip install google-generativeai")

    async def generate_async(self, prompt: str) -> str:
        """비동기 Gemini API 호출"""
        self._wait_for_rate_limit()

        try:
            # Gemini는 기본적으로 동기 API이므로 asyncio.to_thread 사용
            return await asyncio.to_thread(self._generate_sync, prompt)

        except Exception as e:
            raise Exception(f"Gemini API 오류: {str(e)}")

    def generate(self, prompt: str) -> str:
        """동기 Gemini API 호출"""
        self._wait_for_rate_limit()
        return self._generate_sync(prompt)

    def _generate_sync(self, prompt: str) -> str:
        """실제 Gemini API 호출"""
        try:
            # Gemini 생성 설정 (출력 길이 최대화)
            generation_config = {
                "max_output_tokens": 32768,  # 최대 출력 토큰 증가
                "temperature": 0.1,  # 일관성 있는 JSON 생성을 위해 낮은 temperature
            }

            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            return response.text

        except Exception as e:
            raise Exception(f"Gemini API 호출 오류: {str(e)}")

    def get_model_info(self) -> Dict[str, Any]:
        """Gemini 모델 정보 반환"""
        return {
            "source": "gemini",
            "model": "gemini-2.5-flash-lite",
            "provider": "Google",
            "version": "1.5"
        }


def create_llm_provider(provider_type: str, api_key: str, requests_per_minute: int = 10) -> LLMProvider:
    """LLM 제공자 팩토리 함수"""
    if provider_type.lower() == "claude":
        return ClaudeProvider(api_key, requests_per_minute)
    elif provider_type.lower() == "gemini":
        return GeminiProvider(api_key, requests_per_minute)
    else:
        raise ValueError(f"지원하지 않는 LLM 제공자: {provider_type}. 'claude' 또는 'gemini'를 사용하세요.")