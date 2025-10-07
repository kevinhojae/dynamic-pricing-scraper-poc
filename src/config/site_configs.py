"""
사이트별 스크래핑 설정 관리
"""
from typing import Dict, List, Optional
from src.models.schemas import ScrapingConfig, ScrapingSourceType, SPAConfig


class SiteConfigManager:
    """사이트별 스크래핑 설정을 관리하는 클래스"""

    def __init__(self):
        self._configs: Dict[str, ScrapingConfig] = {}
        self._initialize_default_configs()

    def _initialize_default_configs(self):
        """기본 사이트 설정들을 초기화"""

        # 세니아 클리닉 (sitemap 기반)
        self._configs["xenia"] = ScrapingConfig(
            site_name="Xenia Clinic",
            base_url="https://xenia.clinic/",
            source_type=ScrapingSourceType.SITEMAP,
            rate_limit=1.0,
            use_selenium=False,
            custom_settings={
                "priority_keywords": ["products", "treatment", "ko"],
                "exclude_patterns": ["/en/", "/blog/", "/news/"]
            }
        )

        # 쁨 글로벌 클리닉 (base_url + SPA 기반)
        self._configs["ppeum_global"] = ScrapingConfig(
            site_name="PPEUM Global Clinic",
            base_url="https://global.ppeum.com/",
            source_type=ScrapingSourceType.SPA_DYNAMIC,
            static_urls=["https://global.ppeum.com/front/reservation?branchMap=global_kr"],
            rate_limit=2.0,  # SPA는 더 긴 대기시간 필요
            use_selenium=True,  # JavaScript 필요
            spa_config=SPAConfig(
                wait_for_element=".treatment-list, .menu-container, .product-list",
                click_elements=[
                    ".tab-button",
                    ".category-btn",
                    ".menu-item",
                    "[data-category]",
                    ".treatment-category"
                ],
                scroll_behavior=True,
                wait_time=5,  # 쁨 사이트는 로딩이 느림
                max_interactions=15
            ),
            custom_settings={
                "spa_specific": True,
                "dynamic_content": True,
                "requires_interaction": True
            }
        )

        # GU 클리닉 (기존 설정 유지)
        self._configs["gu_clinic"] = ScrapingConfig(
            site_name="GU Clinic",
            base_url="https://gu.clinic/",
            source_type=ScrapingSourceType.STATIC_URLS,
            static_urls=[
                "https://gu.clinic/kr/treatment-reservation",
                "https://gu.clinic/kr/treatment-reservation?categoryId=64094b472967084b5da2837c",
                "https://gu.clinic/kr/treatment-reservation?categoryId=64094b652967084b5da2837d",
                "https://gu.clinic/kr/treatment-reservation?categoryId=64094b7a2967084b5da2837e",
            ],
            rate_limit=1.5,
            use_selenium=True,
            custom_settings={
                "spa_like": True,
                "category_based": True
            }
        )

        # Beauty Leader (sitemap 기반)
        self._configs["beauty_leader"] = ScrapingConfig(
            site_name="Beauty Leader",
            base_url="https://beautyleader.co.kr/",
            source_type=ScrapingSourceType.SITEMAP,
            rate_limit=1.0,
            use_selenium=False,
            custom_settings={
                "priority_keywords": ["treatment", "service", "procedure"]
            }
        )

    def get_config(self, site_key: str) -> Optional[ScrapingConfig]:
        """사이트 키로 설정을 가져옴"""
        return self._configs.get(site_key)

    def add_config(self, site_key: str, config: ScrapingConfig) -> None:
        """새 사이트 설정을 추가"""
        self._configs[site_key] = config

    def list_sites(self) -> List[str]:
        """등록된 모든 사이트 키를 반환"""
        return list(self._configs.keys())

    def get_spa_sites(self) -> List[str]:
        """SPA 타입 사이트들을 반환"""
        return [
            key for key, config in self._configs.items()
            if config.source_type == ScrapingSourceType.SPA_DYNAMIC
        ]

    def get_sitemap_sites(self) -> List[str]:
        """Sitemap 기반 사이트들을 반환"""
        return [
            key for key, config in self._configs.items()
            if config.source_type == ScrapingSourceType.SITEMAP
        ]

    def create_ppeum_global_config(self) -> ScrapingConfig:
        """쁨 글로벌 클리닉 전용 설정 생성"""
        return ScrapingConfig(
            site_name="PPEUM Global Clinic",
            base_url="https://global.ppeum.com/",
            source_type=ScrapingSourceType.SPA_DYNAMIC,
            static_urls=["https://global.ppeum.com/front/reservation?branchMap=global_kr"],
            rate_limit=3.0,  # 더 보수적인 설정
            use_selenium=True,
            spa_config=SPAConfig(
                wait_for_element=".treatment-item, .menu-list, .reservation-item, .price-item",
                click_elements=[
                    "button[data-category]",
                    ".tab-menu button",
                    ".category-button",
                    ".menu-tab",
                    ".treatment-tab",
                    ".btn-category",
                    "[role='tab']"
                ],
                scroll_behavior=True,
                wait_time=8,  # 충분한 로딩 시간
                max_interactions=20
            ),
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            custom_settings={
                "spa_specific": True,
                "dynamic_content": True,
                "requires_interaction": True,
                "korean_site": True,
                "beauty_clinic": True
            }
        )


# 전역 설정 관리자 인스턴스
site_config_manager = SiteConfigManager()