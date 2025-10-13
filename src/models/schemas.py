from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TreatmentType(str, Enum):
    LASER = "laser"
    INJECTION = "injection"
    SKINCARE = "skincare"
    SURGICAL = "surgical"
    DEVICE = "device"


class EquipmentType(str, Enum):
    LASER_CO2 = "co2_laser"
    LASER_PICOSURE = "picosure"
    LASER_ULTHERA = "ulthera"
    BOTOX = "botox"
    FILLER = "filler"
    THREAD_LIFT = "thread_lift"
    HIFU = "hifu"
    RF = "radiofrequency"
    IPL = "ipl"


class IndividualTreatment(BaseModel):
    """개별 시술 정보"""

    name: str = Field(
        description="시술명 (예: 슈링크 유니버스 울트라 MP모드, 얼굴지방분해주사)"
    )
    dosage: Optional[float] = Field(None, description="용량 (예: 300, 100, 3, 0.5)")
    unit: Optional[str] = Field(None, description="단위 (예: 샷, cc, 회)")
    equipments: List[str] = Field(
        default=[], description="사용 장비명 리스트 (예: ['슈링크', '울쎄라'])"
    )
    medications: List[str] = Field(
        default=[], description="사용 약물명 리스트 (예: ['GT38', '보톡스'])"
    )
    treatment_type: Optional[TreatmentType] = Field(None, description="시술 유형")
    description: Optional[str] = Field(None, description="시술 설명")
    duration: Optional[int] = Field(None, description="시술 시간 (분)")
    target_area: List[str] = Field(default=[], description="시술 대상 부위")
    benefits: List[str] = Field(default=[], description="효과")
    recovery_time: Optional[str] = Field(None, description="회복 기간")


class ProductItem(BaseModel):
    """개별 상품 옵션 정보"""

    id: Optional[str] = None

    # Key Factor: 정보 수집 채널
    source_url: str = Field(description="상품 페이지 전체 URL")
    source_channel: Optional[str] = Field(
        None, description="정보 수집 채널 (웹사이트명)"
    )

    # Key Factor: 병원명
    clinic_name: str = Field(description="병원명")

    # Key Factor: 상품명 (개별 옵션)
    product_name: str = Field(
        description="개별 상품 옵션명 (예: 더마 슈링크 100샷, 슈링크 300샷 + 지방분해주사 3cc)"
    )

    # Key Factor: 가격 정보
    product_original_price: Optional[float] = Field(None, description="상품 정상가")
    product_event_price: Optional[float] = Field(
        None, description="상품 이벤트가/할인가"
    )
    product_description: Optional[str] = Field(None, description="상품 설명")

    # Key Factor: 시술 구성 요소 리스트
    treatments: List[IndividualTreatment] = Field(
        description="상품을 구성하는 개별 시술들"
    )

    # 상품 전체 정보
    category: Optional[str] = Field(None, description="시술 카테고리 (예: 탄력/리프팅)")
    description: Optional[str] = Field(None, description="카테고리 전체 설명")

    # 메타 정보
    scraped_at: datetime = Field(default_factory=datetime.now)
    additional_info: Dict[str, Any] = Field(default={})


# 하위 호환성을 위해 기존 TreatmentItem을 ProductItem의 alias로 유지
TreatmentItem = ProductItem


class TreatmentCluster(BaseModel):
    cluster_id: int
    cluster_name: str
    treatment_type: TreatmentType
    common_equipment: List[EquipmentType]
    treatment_items: List[str] = Field(description="List of treatment item IDs")
    price_range: Dict[str, float] = Field(description="min, max, avg, median prices")
    common_features: Dict[str, Any] = {}
    cluster_size: int


class PriceRecommendation(BaseModel):
    treatment_name: str
    treatment_type: TreatmentType
    recommended_price: float
    price_range: Dict[str, float]
    confidence_score: float
    market_position: str = Field(description="premium, mid-range, budget")
    reasoning: List[str] = []
    similar_treatments: List[str] = []
    cluster_id: Optional[int] = None


class ScrapingSourceType(str, Enum):
    SITEMAP = "sitemap"
    BASE_URL = "base_url"
    STATIC_URLS = "static_urls"
    SPA_DYNAMIC = "spa_dynamic"


class SPAConfig(BaseModel):
    """SPA 사이트 동적 콘텐츠 스크래핑 설정"""

    wait_for_element: Optional[str] = None  # 기다릴 요소 선택자
    click_elements: List[str] = []  # 클릭할 버튼/요소들
    scroll_behavior: bool = False  # 스크롤하여 더 많은 콘텐츠 로드
    wait_time: int = 3  # 페이지 로딩 대기 시간(초)
    max_interactions: int = 10  # 최대 상호작용 횟수


class ScrapingConfig(BaseModel):
    site_name: str
    base_url: str

    # 소스 유형과 관련 설정
    source_type: ScrapingSourceType = ScrapingSourceType.SITEMAP
    static_urls: List[str] = []  # source_type이 STATIC_URLS일 때 사용

    # SPA 설정 (source_type이 SPA_DYNAMIC일 때 사용)
    spa_config: Optional[SPAConfig] = None

    # 기존 설정들
    selectors: Dict[str, str] = {}
    rate_limit: float = 1.0
    use_selenium: bool = False
    headers: Dict[str, str] = {}

    # 사이트별 커스텀 설정
    custom_settings: Dict[str, Any] = {}


@dataclass
class ScrapingResult:
    """스크래핑 결과 데이터 클래스"""

    url: str
    products: List[ProductItem]
    interactions_performed: int
    content_states: List[str]  # 각 상호작용 후 콘텐츠 상태
    error: Optional[str] = None
    processing_time: float = 0.0
