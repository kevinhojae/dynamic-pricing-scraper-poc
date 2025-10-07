#!/usr/bin/env python3
"""
간단한 단계별 테스트
"""
import os
import sys
from datetime import datetime

print("🚀 간단한 단계별 테스트 시작")
print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*50)

# 1단계: 환경변수 체크
print("\n1️⃣ 환경변수 체크")
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("ANTHROPIC_AUTH_TOKEN")
base_url = os.getenv("ANTHROPIC_BASE_URL")

print(f"✅ ANTHROPIC_AUTH_TOKEN: {'설정됨' if api_key else '없음'} (길이: {len(api_key) if api_key else 0})")
print(f"✅ ANTHROPIC_BASE_URL: {base_url if base_url else '없음'}")

if not api_key:
    print("❌ API 키가 없어서 설정 테스트만 실행")
    exit(1)

# 2단계: 모듈 import 테스트
print("\n2️⃣ 모듈 import 테스트")
sys.path.append('.')

try:
    from src.config.site_configs import site_config_manager
    print("✅ site_config_manager import 성공")

    from src.utils.llm_extractor import LLMTreatmentExtractor
    print("✅ LLMTreatmentExtractor import 성공")

    from ppeum_global_scraper import PpeumGlobalScraper
    print("✅ PpeumGlobalScraper import 성공")

except Exception as e:
    print(f"❌ import 오류: {e}")
    exit(1)

# 3단계: 설정 시스템 테스트
print("\n3️⃣ 설정 시스템 테스트")
try:
    sites = site_config_manager.list_sites()
    print(f"✅ 등록된 사이트: {len(sites)}개")

    ppeum_config = site_config_manager.create_ppeum_global_config()
    print(f"✅ 쁨 글로벌 설정: {ppeum_config.site_name}")

except Exception as e:
    print(f"❌ 설정 오류: {e}")
    exit(1)

# 4단계: LLM extractor 초기화 테스트
print("\n4️⃣ LLM extractor 초기화 테스트")
try:
    extractor = LLMTreatmentExtractor(api_key)
    print("✅ LLMTreatmentExtractor 초기화 성공")

    test_url = "https://global.ppeum.com/front/reservation?branchMap=global_kr"
    clinic_name = extractor._extract_clinic_name(test_url)
    print(f"✅ 클리닉명 추출: {clinic_name}")

except Exception as e:
    print(f"❌ LLM extractor 오류: {e}")
    exit(1)

# 5단계: 스크래퍼 객체 생성 테스트 (API 호출 없이)
print("\n5️⃣ 스크래퍼 객체 생성 테스트")
try:
    scraper = PpeumGlobalScraper(api_key)
    print("✅ PpeumGlobalScraper 객체 생성 성공")

    config = scraper.config
    print(f"✅ 스크래퍼 설정 확인: {config.site_name}")

except Exception as e:
    print(f"❌ 스크래퍼 생성 오류: {e}")
    exit(1)

print(f"\n🎉 모든 기본 테스트 성공!")
print(f"⏰ 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("\n💡 실제 스크래핑 테스트를 원하면 scraper.scrape_treatments()를 호출하세요")