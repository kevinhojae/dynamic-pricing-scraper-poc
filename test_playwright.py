#!/usr/bin/env python3
"""
Playwright를 사용해서 JavaScript 렌더링 후 콘텐츠 확인
"""

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re

async def test_playwright_content():
    """Playwright로 JavaScript 렌더링 후 콘텐츠 확인"""

    test_url = "https://xenia.clinic/ko/products/8a2a54b8-0eaa-4d28-945b-2c76cb98eb9b"

    async with async_playwright() as p:
        print(f"🚀 Testing Playwright with: {test_url}")

        # 브라우저 실행 (headless 모드)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()

        try:
            # 페이지로 이동
            print("⏳ Loading page...")
            await page.goto(test_url, wait_until='domcontentloaded', timeout=30000)

            # JavaScript 실행 완료 대기
            print("⏳ Waiting for content to load...")
            await page.wait_for_timeout(3000)  # 3초 기본 대기

            # 특정 콘텐츠가 로드될 때까지 대기
            try:
                # 일반적인 콘텐츠 요소들을 기다림
                await page.wait_for_selector('main, .content, .product, h1, h2, p', timeout=10000)
                print("✅ Content elements detected")
            except:
                print("⚠️  No specific content elements found, proceeding...")

            # 추가 대기 (동적 콘텐츠를 위해)
            await page.wait_for_timeout(2000)

            # 네트워크 요청이 완료될 때까지 대기
            try:
                await page.wait_for_load_state('networkidle', timeout=5000)
                print("✅ Network requests completed")
            except:
                print("⚠️  Network still active, proceeding...")

            # 페이지 콘텐츠 가져오기
            content = await page.content()
            print(f"📊 Playwright HTML Length: {len(content)} characters")

            # 일부 HTML 출력
            print(f"\n📝 Playwright HTML Sample (first 1000 chars):")
            print("-" * 50)
            print(content[:1000])
            print("-" * 50)

            # BeautifulSoup으로 파싱 (실제 LLM extractor와 동일한 방식)
            soup = BeautifulSoup(content, "html.parser")

            # 불필요한 태그 제거 (실제 코드와 동일)
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            # 텍스트 추출
            text_content = soup.get_text(separator=" ", strip=True)
            print(f"📊 Playwright Extracted Text Length: {len(text_content)} characters")

            # 추출된 텍스트 샘플
            print(f"\n📝 Playwright Extracted Text Sample (first 2000 chars):")
            print("-" * 50)
            print(text_content[:2000])
            print("-" * 50)

            # 시술 관련 키워드 검색
            treatment_keywords = [
                '시술', '치료', '서비스', '가격', '원', '샷', 'cc', '보톡스', '필러',
                '레이저', '슈링크', '울쎄라', '리프팅', '주사', '프로그램', '예약',
                '이벤트', '할인', '정상가', '특가'
            ]

            found_keywords = []
            for keyword in treatment_keywords:
                if keyword in text_content:
                    count = text_content.count(keyword)
                    found_keywords.append(f"{keyword}({count}회)")

            print(f"\n🔍 Playwright Found Treatment Keywords: {', '.join(found_keywords) if found_keywords else '없음'}")

            # 가격 패턴 검색
            price_patterns = [
                r'\d+,?\d+원',
                r'\d+,?\d+\s*원',
                r'₩\s*\d+,?\d+',
                r'\d+만원',
                r'\d{1,3}(?:,\d{3})*원',
            ]

            found_prices = []
            for pattern in price_patterns:
                matches = re.findall(pattern, text_content)
                found_prices.extend(matches)

            print(f"💰 Playwright Found Price Patterns: {found_prices[:15] if found_prices else '없음'}")

            # HTML 구조 분석
            print(f"\n🏗️  Playwright HTML Structure Analysis:")
            print(f"- <title>: {soup.title.string if soup.title else 'None'}")
            print(f"- <h1> tags: {len(soup.find_all('h1'))}")
            print(f"- <h2> tags: {len(soup.find_all('h2'))}")
            print(f"- <h3> tags: {len(soup.find_all('h3'))}")
            print(f"- <p> tags: {len(soup.find_all('p'))}")
            print(f"- <div> tags: {len(soup.find_all('div'))}")
            print(f"- <button> tags: {len(soup.find_all('button'))}")
            print(f"- <span> tags: {len(soup.find_all('span'))}")

            # 특정 클래스나 ID로 콘텐츠 찾기
            potential_selectors = [
                ".product", ".treatment", ".service", ".content", ".main", ".container",
                "#product", "#treatment", "#service", "#content", "#main",
                "[class*='product']", "[class*='treatment']", "[class*='service']",
                "[class*='price']", "[class*='cost']"
            ]

            print(f"\n🎯 Content Element Search:")
            for selector in potential_selectors:
                try:
                    elements = soup.select(selector)
                    if elements:
                        print(f"  - {selector}: {len(elements)} elements found")
                        for i, element in enumerate(elements[:2]):  # 처음 2개만 확인
                            element_text = element.get_text(strip=True)
                            if element_text and len(element_text) > 10:
                                print(f"    [{i+1}] {element_text[:150]}...")
                except Exception as e:
                    continue

            # DOM에서 직접 데이터 찾기 (React state 등)
            print(f"\n🔍 JavaScript Data Search:")
            try:
                # 페이지에서 JavaScript 실행하여 데이터 찾기
                js_data = await page.evaluate("""
                    () => {
                        // React DevTools 데이터 찾기
                        const results = {};

                        // window 객체에서 데이터 찾기
                        if (window.__INITIAL_STATE__) results.initial_state = window.__INITIAL_STATE__;
                        if (window.__PRELOADED_STATE__) results.preloaded_state = window.__PRELOADED_STATE__;
                        if (window.__NEXT_DATA__) results.next_data = window.__NEXT_DATA__;

                        // React Fiber 데이터 찾기
                        const reactFiber = document.querySelector('[data-reactroot]');
                        if (reactFiber && reactFiber._reactInternalFiber) {
                            results.react_fiber = 'found';
                        }

                        // 로컬 스토리지 데이터
                        if (localStorage.length > 0) {
                            results.localStorage_keys = Object.keys(localStorage);
                        }

                        // 세션 스토리지 데이터
                        if (sessionStorage.length > 0) {
                            results.sessionStorage_keys = Object.keys(sessionStorage);
                        }

                        return results;
                    }
                """)

                if js_data:
                    print(f"   JavaScript Data Found: {list(js_data.keys())}")
                    if 'next_data' in js_data:
                        print(f"   Next.js Data Keys: {list(js_data['next_data'].keys()) if isinstance(js_data['next_data'], dict) else 'Not dict'}")
                else:
                    print("   No JavaScript data found")

            except Exception as e:
                print(f"   JavaScript evaluation error: {str(e)}")

            # 결론 판정
            success_criteria = [
                len(text_content) > 500,  # 충분한 텍스트 길이
                len(found_keywords) > 3,  # 시술 관련 키워드 발견
                len(found_prices) > 0,    # 가격 정보 발견
            ]

            success_count = sum(success_criteria)
            print(f"\n📊 Success Criteria Met: {success_count}/3")

            if success_count >= 2:
                print("✅ SUCCESS: Playwright successfully extracted meaningful content!")
                # 텍스트가 30000자 제한 확인
                if len(text_content) > 30000:
                    final_text = text_content[:30000] + "..."
                    print(f"⚠️  Text will be truncated from {len(text_content)} to 30000 chars for LLM")
                else:
                    final_text = text_content
                    print(f"✅ Text within LLM limit: {len(text_content)} chars")

                return True, final_text
            else:
                print("❌ FAILURE: Content extraction still insufficient")
                return False, text_content

        except Exception as e:
            print(f"❌ Playwright test failed: {str(e)}")
            return False, ""

        finally:
            await browser.close()

if __name__ == "__main__":
    success, content = asyncio.run(test_playwright_content())
    if success:
        print(f"\n🎉 Ready to integrate Playwright into LLM extraction pipeline!")
    else:
        print(f"\n⚠️  Need to investigate further or try different approach")