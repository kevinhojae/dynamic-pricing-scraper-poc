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


class TreatmentItem(BaseModel):
    id: Optional[str] = None
    # Key Factor: 정보 수집 채널
    source_url: str
    source_channel: Optional[str] = Field(None, description="정보 수집 채널 (웹사이트명)")

    # Key Factor: 병원명
    clinic_name: str

    # Key Factor: 상품명・옵션명
    treatment_name: str
    option_name: Optional[str] = Field(None, description="시술 옵션명 (예: 300샷, 600샷)")

    # Key Factor: 기기
    equipment_used: List[EquipmentType] = []
    equipment_name: Optional[str] = Field(None, description="기기명 (예: 써마지FLX, 울쎄라)")

    # Key Factor: 약물
    medication: Optional[str] = Field(None, description="사용되는 약물명")

    # Key Factor: 용량・단위
    dosage: Optional[str] = Field(None, description="용량 (예: 300샷, 1cc)")
    unit: Optional[str] = Field(None, description="단위 (예: 샷, cc, 회)")

    # Key Factor: 가격 (정상가・이벤트가・할인율)
    price: float = Field(description="현재 판매가격 (이벤트가 또는 할인가)")
    original_price: Optional[float] = Field(None, description="정상가")
    discount_rate: Optional[float] = Field(None, description="할인율 (%)")
    event_price: Optional[float] = Field(None, description="이벤트 가격")

    # 기존 필드들
    treatment_type: TreatmentType
    duration: Optional[int] = Field(None, description="Duration in minutes")
    target_area: List[str] = []
    description: Optional[str] = None
    benefits: List[str] = []
    contraindications: List[str] = []
    recovery_time: Optional[str] = None
    sessions_required: Optional[int] = None
    location: Optional[str] = None
    clinic_rating: Optional[float] = None
    review_count: Optional[int] = None
    scraped_at: datetime = Field(default_factory=datetime.now)
    additional_info: Dict[str, Any] = {}


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


class ScrapingConfig(BaseModel):
    site_name: str
    base_url: str
    selectors: Dict[str, str]
    rate_limit: float = 1.0
    use_selenium: bool = False
    headers: Dict[str, str] = {}