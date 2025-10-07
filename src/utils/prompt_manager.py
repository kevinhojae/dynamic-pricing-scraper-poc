import yaml
import os
from typing import Dict, Any
from pathlib import Path


class PromptManager:
    """YAML 기반 프롬프트 관리자"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            # 프로젝트 루트에서 config/prompts.yaml 찾기
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "prompts.yaml"

        self.config_path = Path(config_path)
        self._prompts = self._load_prompts()

    def _load_prompts(self) -> Dict[str, Any]:
        """YAML 파일에서 프롬프트 설정 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"프롬프트 설정 파일을 찾을 수 없습니다: {self.config_path}")
        except Exception as e:
            raise Exception(f"프롬프트 설정 파일 로드 오류: {str(e)}")

    def get_prompt(self, prompt_name: str) -> Dict[str, Any]:
        """프롬프트 정보 가져오기"""
        prompts = self._prompts.get('prompts', {})
        if prompt_name not in prompts:
            raise KeyError(f"프롬프트 '{prompt_name}'를 찾을 수 없습니다.")

        return prompts[prompt_name]

    def get_prompt_template(self, prompt_name: str) -> str:
        """프롬프트 템플릿 문자열 가져오기"""
        prompt_info = self.get_prompt(prompt_name)
        return prompt_info.get('template', '')

    def get_prompt_version(self, prompt_name: str) -> str:
        """프롬프트 버전 가져오기"""
        prompt_info = self.get_prompt(prompt_name)
        return prompt_info.get('version', '1.0')

    def get_global_version(self) -> str:
        """전체 프롬프트 설정 버전 가져오기"""
        return self._prompts.get('version', '1.0')

    def format_prompt(self, prompt_name: str, **kwargs) -> str:
        """템플릿 변수를 대체하여 최종 프롬프트 생성"""
        template = self.get_prompt_template(prompt_name)
        return template.format(**kwargs)

    def get_prompt_info(self, prompt_name: str) -> Dict[str, Any]:
        """프롬프트의 전체 메타데이터 반환"""
        prompt_info = self.get_prompt(prompt_name)
        return {
            'version': prompt_info.get('version', '1.0'),
            'description': prompt_info.get('description', ''),
            'global_version': self.get_global_version()
        }