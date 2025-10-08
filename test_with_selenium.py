#!/usr/bin/env python3
"""
Selenium을 사용해서 JavaScript 렌더링 후 콘텐츠 확인
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup


def test_selenium_content():
    """Selenium으로 JavaScript 렌더링 후 콘텐츠 확인"""

    # Chrome 옵션 설정
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 헤드리스 모드
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    test_url = "https://xenia.clinic/ko/products/8a2a54b8-0eaa-4d28-945b-2c76cb98eb9b"

    try:
        print(f"🚀 Testing Selenium with: {test_url}")

        # WebDriver 초기화
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(test_url)

        print("⏳ Waiting for page to load...")

        # 페이지 로딩 대기 (여러 방법 시도)
        time.sleep(5)  # 기본 대기

        # 특정 요소가 로드될 때까지 대기 시도
        try:
            # 일반적인 콘텐츠 요소들을 기다림
            wait = WebDriverWait(driver, 10)
            wait.until(
                lambda driver: len(driver.find_elements(By.TAG_NAME, "p")) > 0
                or len(driver.find_elements(By.CLASS_NAME, "content")) > 0
                or len(driver.find_elements(By.TAG_NAME, "main")) > 0
            )
        except Exception:
            print(
                "⚠️  No specific content elements found, proceeding with current state"
            )

        # 추가 대기 (동적 콘텐츠 로딩)
        time.sleep(3)

        # 현재 페이지 소스 가져오기
        page_source = driver.page_source
        print(f"📊 Selenium HTML Length: {len(page_source)} characters")

        # 일부 HTML 출력
        print("\n📝 Selenium HTML Sample (first 1000 chars):")
        print("-" * 50)
        print(page_source[:1000])
        print("-" * 50)

        # BeautifulSoup으로 파싱
        soup = BeautifulSoup(page_source, "html.parser")

        # 불필요한 태그 제거 (실제 코드와 동일)
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # 텍스트 추출
        text_content = soup.get_text(separator=" ", strip=True)
        print(f"📊 Selenium Extracted Text Length: {len(text_content)} characters")

        # 추출된 텍스트 샘플
        print("\n📝 Selenium Extracted Text Sample (first 1500 chars):")
        print("-" * 50)
        print(text_content[:1500])
        print("-" * 50)

        # 시술 관련 키워드 검색
        treatment_keywords = [
            "시술",
            "치료",
            "서비스",
            "가격",
            "원",
            "샷",
            "cc",
            "보톡스",
            "필러",
            "레이저",
            "슈링크",
            "울쎄라",
            "리프팅",
            "주사",
            "프로그램",
            "예약",
        ]

        found_keywords = []
        for keyword in treatment_keywords:
            if keyword in text_content:
                count = text_content.count(keyword)
                found_keywords.append(f"{keyword}({count}회)")

        print(
            f"\n🔍 Selenium Found Treatment Keywords: {', '.join(found_keywords) if found_keywords else '없음'}"
        )

        # 가격 패턴 검색
        import re

        price_patterns = [
            r"\d+,?\d+원",
            r"\d+,?\d+\s*원",
            r"₩\s*\d+,?\d+",
            r"\d+만원",
        ]

        found_prices = []
        for pattern in price_patterns:
            matches = re.findall(pattern, text_content)
            found_prices.extend(matches)

        print(
            f"💰 Selenium Found Price Patterns: {found_prices[:10] if found_prices else '없음'}"
        )

        # HTML 구조 분석
        print("\n🏗️  Selenium HTML Structure Analysis:")
        print(f"- <title>: {soup.title.string if soup.title else 'None'}")
        print(f"- <h1> tags: {len(soup.find_all('h1'))}")
        print(f"- <h2> tags: {len(soup.find_all('h2'))}")
        print(f"- <h3> tags: {len(soup.find_all('h3'))}")
        print(f"- <p> tags: {len(soup.find_all('p'))}")
        print(f"- <div> tags: {len(soup.find_all('div'))}")
        print(f"- <button> tags: {len(soup.find_all('button'))}")
        print(f"- <input> tags: {len(soup.find_all('input'))}")

        # 특정 클래스나 ID 찾기
        potential_content_selectors = [
            ".product",
            ".treatment",
            ".service",
            ".content",
            ".main",
            "#product",
            "#treatment",
            "#service",
            "#content",
            "#main",
            "[data-product]",
            "[data-treatment]",
            "[data-service]",
        ]

        print("\n🎯 Content Element Search:")
        for selector in potential_content_selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    print(f"  - {selector}: {len(elements)} elements found")
                    if elements[0].get_text(strip=True):
                        print(
                            f"    Sample text: {elements[0].get_text(strip=True)[:100]}..."
                        )
            except Exception:
                continue

        driver.quit()

        # 결론
        if len(text_content) > 100 and found_keywords:
            print("\n✅ SUCCESS: Selenium successfully extracted meaningful content!")
            return True
        else:
            print("\n❌ FAILURE: Even with Selenium, content is insufficient")
            return False

    except Exception as e:
        print(f"❌ Selenium test failed: {str(e)}")
        try:
            driver.quit()
        except Exception:
            pass
        return False


if __name__ == "__main__":
    test_selenium_content()
