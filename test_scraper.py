#!/usr/bin/env python3
"""
간단한 스크래핑 전용 스크립트
"""

import asyncio
import json
import os
from datetime import datetime
from typing import List

# Environment variables
from dotenv import load_dotenv

# 프로젝트 의존성
from src.scrapers.async_llm_scraper import AsyncLLMTreatmentScraper
from src.models.schemas import TreatmentItem

def load_gemini_api_key() -> str:
    """Gemini API 키를 환경변수에서 로드"""
    # .env 파일 로드
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        print("다음 중 하나의 방법으로 설정해주세요:")
        print("1. .env 파일에 GEMINI_API_KEY=your-api-key-here")
        print("2. export GEMINI_API_KEY='your-api-key-here'")
        exit(1)
    return api_key

async def scrape_single_site(site_name: str, base_url: str, gemini_api_key: str, max_pages: int = 15) -> List[TreatmentItem]:
    """단일 사이트 스크래핑"""
    print(f"🚀 {site_name} 스크래핑 시작...")

    scraper = AsyncLLMTreatmentScraper(
        site_name=site_name,
        base_url=base_url,
        gemini_api_key=gemini_api_key,
        max_pages=max_pages,
        max_concurrent=2
    )

    treatments = await scraper.scrape_all_treatments()
    print(f"✅ {site_name}: {len(treatments)}개 시술 정보 수집 완료")

    return treatments

def save_results(treatments: List[TreatmentItem], filename: str = None):
    """결과를 JSON 파일로 저장"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scraped_treatments_{timestamp}.json"

    os.makedirs("data", exist_ok=True)
    filepath = f"data/{filename}"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(
            [treatment.model_dump() for treatment in treatments],
            f,
            ensure_ascii=False,
            indent=2,
            default=str
        )

    print(f"💾 결과 저장됨: {filepath}")
    print(f"📊 총 {len(treatments)}개 시술 정보")

async def main():
    """메인 실행 함수"""
    gemini_api_key = load_gemini_api_key()

    # 스크래핑할 사이트 설정 - 세니아 클리닉 테스트
    sites = [
        ("Xenia Clinic", "https://xenia.clinic/ko/products/", 5),
    ]

    all_treatments = []

    for site_name, base_url, max_pages in sites:
        try:
            treatments = await scrape_single_site(site_name, base_url, gemini_api_key, max_pages)
            all_treatments.extend(treatments)
        except Exception as e:
            print(f"❌ {site_name} 스크래핑 실패: {str(e)}")

    if all_treatments:
        save_results(all_treatments)
    else:
        print("❌ 수집된 데이터가 없습니다.")

if __name__ == "__main__":
    asyncio.run(main())