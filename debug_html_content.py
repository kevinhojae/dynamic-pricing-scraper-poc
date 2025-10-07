#!/usr/bin/env python3
"""
실제 스크래핑되는 HTML 콘텐츠를 확인하는 디버깅 스크립트
1. HTML 구조 확인
2. 텍스트 추출 과정 확인
3. 전처리 후 LLM에게 전달되는 내용 확인
"""

import asyncio
import aiohttp
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv

async def debug_html_extraction():
    """실제 HTML 추출 및 전처리 과정 디버깅"""
    # 세니아 클리닉의 개별 상품 페이지 URL (로그에서 발견된 것들)
    test_urls = [
        "https://xenia.clinic/ko/products/8a2a54b8-0eaa-4d28-945b-2c76cb98eb9b",
        "https://xenia.clinic/ko/products/bfcad4ed-f697-43bd-9e1a-ab6e16ae6e34",
        "https://xenia.clinic/ko/products/0880d944-4ff6-44f8-8868-924d61668172",
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as session:
        for i, url in enumerate(test_urls):
            print(f"\n{'='*80}")
            print(f"🔍 URL {i+1}: {url}")
            print('='*80)

            try:
                async with session.get(url) as response:
                    print(f"📊 Status Code: {response.status}")
                    print(f"📊 Content Type: {response.headers.get('Content-Type', 'N/A')}")

                    if response.status == 200:
                        html_content = await response.text()
                        print(f"📊 Raw HTML Length: {len(html_content)} characters")

                        # 원본 HTML 샘플 출력
                        print(f"\n📝 Raw HTML Sample (first 500 chars):")
                        print("-" * 50)
                        print(html_content[:500])
                        print("-" * 50)

                        # HTML 파싱 및 전처리 (실제 LLM extractor와 동일한 과정)
                        soup = BeautifulSoup(html_content, "html.parser")

                        # 불필요한 태그 제거 (실제 코드와 동일)
                        for tag in soup(["script", "style", "nav", "footer", "header"]):
                            tag.decompose()

                        # 텍스트 추출
                        text_content = soup.get_text(separator=" ", strip=True)
                        print(f"📊 Extracted Text Length: {len(text_content)} characters")

                        # 추출된 텍스트 샘플 출력
                        print(f"\n📝 Extracted Text Sample (first 1000 chars):")
                        print("-" * 50)
                        print(text_content[:1000])
                        print("-" * 50)

                        # 시술 관련 키워드 검색
                        treatment_keywords = [
                            '시술', '치료', '서비스', '가격', '원', '샷', 'cc', '보톡스', '필러',
                            '레이저', '슈링크', '울쎄라', '리프팅', '주사', '프로그램'
                        ]

                        found_keywords = []
                        for keyword in treatment_keywords:
                            if keyword in text_content:
                                count = text_content.count(keyword)
                                found_keywords.append(f"{keyword}({count}회)")

                        print(f"\n🔍 Found Treatment Keywords: {', '.join(found_keywords) if found_keywords else '없음'}")

                        # 가격 패턴 검색
                        import re
                        price_patterns = [
                            r'\d+,?\d+원',
                            r'\d+,?\d+\s*원',
                            r'₩\s*\d+,?\d+',
                            r'\d+만원',
                        ]

                        found_prices = []
                        for pattern in price_patterns:
                            matches = re.findall(pattern, text_content)
                            found_prices.extend(matches)

                        print(f"💰 Found Price Patterns: {found_prices[:10] if found_prices else '없음'}")

                        # 텍스트 길이 체크 (30000자 제한)
                        if len(text_content) > 30000:
                            truncated_text = text_content[:30000] + "..."
                            print(f"⚠️  Text truncated from {len(text_content)} to 30000 chars")
                        else:
                            truncated_text = text_content
                            print(f"✅ Text within limit: {len(text_content)} chars")

                        # 마지막으로 전처리된 텍스트가 비어있는지 확인
                        if not truncated_text.strip():
                            print("❌ CRITICAL: Extracted text is empty!")
                        elif len(truncated_text.strip()) < 100:
                            print(f"⚠️  WARNING: Extracted text is very short: {len(truncated_text.strip())} chars")
                        else:
                            print(f"✅ Extracted text looks good: {len(truncated_text.strip())} chars")

                        # 중요한 구조 요소들 확인
                        print(f"\n🏗️  HTML Structure Analysis:")
                        print(f"- <title>: {soup.title.string if soup.title else 'None'}")
                        print(f"- <h1> tags: {len(soup.find_all('h1'))}")
                        print(f"- <h2> tags: {len(soup.find_all('h2'))}")
                        print(f"- <h3> tags: {len(soup.find_all('h3'))}")
                        print(f"- <p> tags: {len(soup.find_all('p'))}")
                        print(f"- <div> tags: {len(soup.find_all('div'))}")
                        print(f"- <span> tags: {len(soup.find_all('span'))}")

                        # React/SPA 관련 체크
                        if 'react' in html_content.lower() or 'vue' in html_content.lower() or 'angular' in html_content.lower():
                            print("⚠️  Detected SPA framework - content might be dynamically loaded")

                        if 'window.__INITIAL_STATE__' in html_content or 'window.__PRELOADED_STATE__' in html_content:
                            print("📊 Detected initial state data in JavaScript")

                        # JSON-LD 구조화된 데이터 체크
                        json_ld_scripts = soup.find_all('script', type='application/ld+json')
                        if json_ld_scripts:
                            print(f"📊 Found {len(json_ld_scripts)} JSON-LD structured data blocks")
                            for j, script in enumerate(json_ld_scripts[:2]):  # 처음 2개만 확인
                                try:
                                    import json
                                    data = json.loads(script.string)
                                    print(f"   JSON-LD {j+1}: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                                except:
                                    print(f"   JSON-LD {j+1}: Failed to parse")

                    else:
                        print(f"❌ Failed to fetch: HTTP {response.status}")

            except Exception as e:
                print(f"❌ Error fetching {url}: {str(e)}")

            # 다음 URL 처리 전 잠시 대기
            if i < len(test_urls) - 1:
                await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(debug_html_extraction())