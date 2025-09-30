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
    clinic_name: str
    treatment_name: str
    treatment_type: TreatmentType
    equipment_used: List[EquipmentType] = []
    price: float
    original_price: Optional[float] = None
    discount_rate: Optional[float] = None
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
    source_url: str
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