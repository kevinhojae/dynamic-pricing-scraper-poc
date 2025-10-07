#!/usr/bin/env python3
"""
세니아 클리닉의 API 엔드포인트나 데이터 소스 찾기
"""

import asyncio
import aiohttp
import json
import re

async def find_xenia_api_endpoints():
    """세니아 클리닉의 API 엔드포인트 찾기"""

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        'Referer': 'https://xenia.clinic/',
    }

    # 시도해볼 API 패턴들
    base_urls = [
        "https://xenia.clinic",
        "https://api.xenia.clinic",
        "https://admin.xenia.clinic",
    ]

    api_paths = [
        "/api/products",
        "/api/treatments",
        "/api/services",
        "/api/v1/products",
        "/api/v1/treatments",
        "/api/v1/services",
        "/products.json",
        "/treatments.json",
        "/services.json",
        "/api/ko/products",
        "/ko/api/products",
    ]

    product_id = "8a2a54b8-0eaa-4d28-945b-2c76cb98eb9b"  # 로그에서 발견된 상품 ID
    specific_endpoints = [
        f"/api/products/{product_id}",
        f"/api/v1/products/{product_id}",
        f"/ko/api/products/{product_id}",
        f"/products/{product_id}.json",
        f"/api/ko/products/{product_id}",
    ]

    async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as session:

        print("🔍 Searching for API endpoints...")

        # 1. 일반 API 엔드포인트 시도
        for base_url in base_urls:
            for path in api_paths:
                url = f"{base_url}{path}"
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            content_type = response.headers.get('Content-Type', '')
                            if 'json' in content_type:
                                data = await response.json()
                                print(f"✅ JSON API Found: {url}")
                                print(f"   Status: {response.status}")
                                print(f"   Content-Type: {content_type}")
                                print(f"   Data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                                if isinstance(data, dict) and len(str(data)) < 1000:
                                    print(f"   Sample data: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}")
                                elif isinstance(data, list) and len(data) > 0:
                                    print(f"   Array length: {len(data)}")
                                    print(f"   First item: {json.dumps(data[0], ensure_ascii=False, indent=2)[:300] if data else 'Empty'}")
                                print()
                        elif response.status in [301, 302, 307, 308]:
                            location = response.headers.get('Location')
                            print(f"🔄 Redirect: {url} -> {location}")
                except Exception as e:
                    continue

        # 2. 특정 상품 API 엔드포인트 시도
        print("\n🎯 Searching for specific product endpoints...")
        for base_url in base_urls:
            for path in specific_endpoints:
                url = f"{base_url}{path}"
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            content_type = response.headers.get('Content-Type', '')
                            if 'json' in content_type:
                                data = await response.json()
                                print(f"✅ Product API Found: {url}")
                                print(f"   Status: {response.status}")
                                print(f"   Content-Type: {content_type}")
                                print(f"   Data: {json.dumps(data, ensure_ascii=False, indent=2)[:800]}")
                                print()
                            else:
                                content = await response.text()
                                print(f"📄 HTML Response: {url}")
                                print(f"   Length: {len(content)} chars")
                                if len(content) < 500:
                                    print(f"   Content: {content}")
                                print()
                except Exception as e:
                    continue

        # 3. robots.txt 확인
        print("\n🤖 Checking robots.txt...")
        try:
            async with session.get("https://xenia.clinic/robots.txt") as response:
                if response.status == 200:
                    robots_content = await response.text()
                    print("📋 robots.txt content:")
                    print(robots_content)

                    # sitemap 링크 찾기
                    sitemap_matches = re.findall(r'Sitemap:\s*(.+)', robots_content, re.IGNORECASE)
                    for sitemap_url in sitemap_matches:
                        print(f"\n🗺️  Checking sitemap: {sitemap_url.strip()}")
                        try:
                            async with session.get(sitemap_url.strip()) as sitemap_response:
                                if sitemap_response.status == 200:
                                    sitemap_content = await sitemap_response.text()
                                    print(f"   Sitemap length: {len(sitemap_content)} chars")
                                    # URL 패턴 찾기
                                    url_matches = re.findall(r'<loc>([^<]+)</loc>', sitemap_content)
                                    product_urls = [url for url in url_matches if '/products/' in url]
                                    print(f"   Product URLs found: {len(product_urls)}")
                                    if product_urls:
                                        print(f"   Sample URLs: {product_urls[:5]}")
                        except Exception as e:
                            print(f"   Sitemap error: {str(e)}")
        except Exception as e:
            print(f"robots.txt error: {str(e)}")

        # 4. 일반적인 Next.js/React API 패턴 확인
        print("\n⚛️  Checking Next.js/React patterns...")
        nextjs_patterns = [
            "/_next/static/chunks/pages/products/[id].js",
            "/_next/data/[buildId]/ko/products/[id].json",
            "/api/trpc/products.get",
            "/_next/data/buildManifest.json",
        ]

        for pattern in nextjs_patterns:
            # buildId가 필요한 경우를 위해 일반적인 값들 시도
            test_patterns = [
                pattern.replace('[id]', product_id).replace('[buildId]', 'static'),
                pattern.replace('[id]', product_id).replace('[buildId]', 'build'),
                pattern.replace('[id]', product_id).replace('[buildId]', 'latest'),
            ]

            for test_pattern in test_patterns:
                url = f"https://xenia.clinic{test_pattern}"
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            content_type = response.headers.get('Content-Type', '')
                            print(f"📦 Next.js resource found: {url}")
                            print(f"   Status: {response.status}, Type: {content_type}")

                            if 'json' in content_type:
                                try:
                                    data = await response.json()
                                    print(f"   JSON data: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}...")
                                except:
                                    content = await response.text()
                                    print(f"   Content (first 300 chars): {content[:300]}")
                            print()
                except Exception as e:
                    continue

if __name__ == "__main__":
    asyncio.run(find_xenia_api_endpoints())