"""
의료 시술 데이터 통계 분석 및 집계 스크립트
PPEUM Global Clinic 스크래핑 데이터를 분석하여 다양한 통계를 생성합니다.
"""

import argparse
import json
import pandas as pd
from collections import Counter, defaultdict
from datetime import datetime
import os
from typing import Dict, Any


class TreatmentDataAnalyzer:
    """의료 시술 데이터 분석 클래스"""

    def __init__(self, json_file_path: str):
        """
        Args:
            json_file_path: 분석할 JSON 파일 경로
        """
        self.json_file_path = json_file_path
        self.data = self._load_data()
        self.results = self.data.get("results", [])
        self.model_info = self.data.get("model_info", {})

    def _load_data(self) -> Dict[str, Any]:
        """JSON 데이터 로드"""
        try:
            with open(self.json_file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"데이터 로드 오류: {e}")
            return {}

    def get_basic_stats(self) -> Dict[str, Any]:
        """기본 통계 정보 수집"""
        stats = {
            "total_products": len(self.results),
            "total_treatments": sum(
                len(item.get("treatments", [])) for item in self.results
            ),
            "model_info": self.model_info,
            "extraction_date": self.model_info.get("extraction_timestamp", "Unknown"),
            "clinic_name": (
                self.results[0].get("clinic_name", "Unknown")
                if self.results
                else "Unknown"
            ),
        }
        return stats

    def analyze_price_distribution(self) -> Dict[str, Any]:
        """가격 분포 분석"""
        original_prices = []
        event_prices = []
        discount_rates = []

        for item in self.results:
            orig_price = item.get("product_original_price")
            event_price = item.get("product_event_price")

            if orig_price is not None:
                original_prices.append(orig_price)
            if event_price is not None:
                event_prices.append(event_price)

            if orig_price and event_price and orig_price > 0:
                discount_rate = ((orig_price - event_price) / orig_price) * 100
                discount_rates.append(discount_rate)

        return {
            "original_price_stats": {
                "count": len(original_prices),
                "mean": (
                    sum(original_prices) / len(original_prices)
                    if original_prices
                    else 0
                ),
                "min": min(original_prices) if original_prices else 0,
                "max": max(original_prices) if original_prices else 0,
                "median": (
                    sorted(original_prices)[len(original_prices) // 2]
                    if original_prices
                    else 0
                ),
            },
            "event_price_stats": {
                "count": len(event_prices),
                "mean": sum(event_prices) / len(event_prices) if event_prices else 0,
                "min": min(event_prices) if event_prices else 0,
                "max": max(event_prices) if event_prices else 0,
                "median": (
                    sorted(event_prices)[len(event_prices) // 2] if event_prices else 0
                ),
            },
            "discount_stats": {
                "count": len(discount_rates),
                "mean_discount_rate": (
                    sum(discount_rates) / len(discount_rates) if discount_rates else 0
                ),
                "min_discount": min(discount_rates) if discount_rates else 0,
                "max_discount": max(discount_rates) if discount_rates else 0,
            },
        }

    def analyze_treatments(self) -> Dict[str, Any]:
        """시술 종류 분석"""
        treatment_types = Counter()
        treatment_names = Counter()
        equipments = Counter()
        medications = Counter()
        target_areas = Counter()
        benefits = Counter()

        for item in self.results:
            treatments = item.get("treatments", [])
            for treatment in treatments:
                # 시술 타입
                treatment_type = treatment.get("treatment_type", "unknown")
                treatment_types[treatment_type] += 1

                # 시술명
                treatment_name = treatment.get("name", "unknown")
                treatment_names[treatment_name] += 1

                # 장비
                for equipment in treatment.get("equipments", []):
                    equipments[equipment] += 1

                # 약물/재료
                for medication in treatment.get("medications", []):
                    medications[medication] += 1

                # 타겟 부위
                for area in treatment.get("target_area", []):
                    target_areas[area] += 1

                # 효과/혜택
                for benefit in treatment.get("benefits", []):
                    benefits[benefit] += 1

        return {
            "treatment_types": dict(treatment_types.most_common()),
            "popular_treatments": dict(treatment_names.most_common(20)),
            "popular_equipments": dict(equipments.most_common(15)),
            "popular_medications": dict(medications.most_common(15)),
            "popular_target_areas": dict(target_areas.most_common(15)),
            "popular_benefits": dict(benefits.most_common(15)),
        }

    def analyze_categories(self) -> Dict[str, Any]:
        """카테고리별 분석"""
        category_counts = Counter()
        category_prices = defaultdict(list)

        for item in self.results:
            category = item.get("category", "Unknown")
            category_counts[category] += 1

            event_price = item.get("product_event_price")
            if event_price is not None:
                category_prices[category].append(event_price)

        # 카테고리별 가격 통계
        category_price_stats = {}
        for category, prices in category_prices.items():
            if prices:
                category_price_stats[category] = {
                    "count": len(prices),
                    "mean": sum(prices) / len(prices),
                    "min": min(prices),
                    "max": max(prices),
                    "median": sorted(prices)[len(prices) // 2],
                }

        return {
            "category_counts": dict(category_counts.most_common()),
            "category_price_stats": category_price_stats,
        }

    def analyze_dosage_patterns(self) -> Dict[str, Any]:
        """용량/수량 패턴 분석"""
        dosage_patterns = defaultdict(list)
        unit_counts = Counter()

        for item in self.results:
            treatments = item.get("treatments", [])
            for treatment in treatments:
                dosage = treatment.get("dosage")
                unit = treatment.get("unit")

                if dosage is not None and unit:
                    dosage_patterns[unit].append(dosage)
                    unit_counts[unit] += 1

        # 단위별 용량 통계
        dosage_stats = {}
        for unit, dosages in dosage_patterns.items():
            if dosages:
                dosage_stats[unit] = {
                    "count": len(dosages),
                    "mean": sum(dosages) / len(dosages),
                    "min": min(dosages),
                    "max": max(dosages),
                    "median": sorted(dosages)[len(dosages) // 2],
                }

        return {
            "unit_counts": dict(unit_counts.most_common()),
            "dosage_stats": dosage_stats,
        }

    def create_comprehensive_report(
        self, output_files: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """종합 리포트 생성"""
        # 상대 경로로 변환
        import os

        current_dir = os.getcwd()
        relative_input_path = os.path.relpath(self.json_file_path, current_dir)

        report = {
            "metadata": {
                "input_file_path": relative_input_path,
                "generated_files": output_files or {},
                "generated_at": datetime.now().isoformat(),
            },
            "basic_stats": self.get_basic_stats(),
            "price_analysis": self.analyze_price_distribution(),
            "treatment_analysis": self.analyze_treatments(),
            "category_analysis": self.analyze_categories(),
            "dosage_analysis": self.analyze_dosage_patterns(),
        }
        return report

    def save_report_to_files(self, output_dir: str = "data/statistics"):
        """리포트를 다양한 형식으로 저장"""
        # 출력 디렉토리 생성
        os.makedirs(output_dir, exist_ok=True)

        # 타임스탬프 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # CSV 형태로 주요 데이터 저장 (먼저 실행해서 파일 경로들 수집)
        csv_files = self._save_csv_reports(output_dir, timestamp)

        # 생성된 파일들의 상대 경로 정보
        current_dir = os.getcwd()
        json_filename = f"{output_dir}/treatment_analysis_{timestamp}.json"
        relative_json_path = os.path.relpath(json_filename, current_dir)

        # 모든 생성된 파일들의 상대 경로
        generated_files = {
            "json_report": relative_json_path,
            **{k: os.path.relpath(v, current_dir) for k, v in csv_files.items()},
        }

        # 종합 리포트 생성 (파일 경로 정보 포함)
        report = self.create_comprehensive_report(generated_files)

        # JSON 형태로 저장
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON 리포트 저장: {json_filename}")

        return json_filename

    def _save_csv_reports(self, output_dir: str, timestamp: str):
        """주요 데이터를 CSV로 저장하고 파일 경로들을 반환"""
        # 제품 목록 CSV
        products_data = []
        for item in self.results:
            products_data.append(
                {
                    "product_name": item.get("product_name"),
                    "category": item.get("category"),
                    "original_price": item.get("product_original_price"),
                    "event_price": item.get("product_event_price"),
                    "clinic_name": item.get("clinic_name"),
                    "treatment_count": len(item.get("treatments", [])),
                }
            )

        products_df = pd.DataFrame(products_data)
        products_csv = f"{output_dir}/products_{timestamp}.csv"
        products_df.to_csv(products_csv, index=False, encoding="utf-8-sig")
        print(f"✅ 제품 CSV 저장: {products_csv}")

        # 시술 목록 CSV
        treatments_data = []
        for item in self.results:
            product_name = item.get("product_name")
            for treatment in item.get("treatments", []):
                treatments_data.append(
                    {
                        "product_name": product_name,
                        "treatment_name": treatment.get("name"),
                        "treatment_type": treatment.get("treatment_type"),
                        "dosage": treatment.get("dosage"),
                        "unit": treatment.get("unit"),
                        "equipments": ", ".join(treatment.get("equipments", [])),
                        "medications": ", ".join(treatment.get("medications", [])),
                        "target_area": ", ".join(treatment.get("target_area", [])),
                        "benefits": ", ".join(treatment.get("benefits", [])),
                    }
                )

        treatments_df = pd.DataFrame(treatments_data)
        treatments_csv = f"{output_dir}/treatments_{timestamp}.csv"
        treatments_df.to_csv(treatments_csv, index=False, encoding="utf-8-sig")
        print(f"✅ 시술 CSV 저장: {treatments_csv}")

        # 생성된 CSV 파일 경로들을 딕셔너리로 반환
        return {"products_csv": products_csv, "treatments_csv": treatments_csv}


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(
        description="의료 시술 데이터 분석 및 집계 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python aggregate_treatments.py --data-path data/raw/ppeum_global_treatments_20251007_222100_gemini.json
        """,
    )

    parser.add_argument(
        "--data-path", type=str, required=True, help="분석할 JSON 파일 경로"
    )

    # JSON 파일 경로
    json_file_path = parser.parse_args().data_path

    print("🔍 의료 시술 데이터 분석 시작...")

    # 분석기 초기화
    analyzer = TreatmentDataAnalyzer(json_file_path)

    if not analyzer.results:
        print("❌ 데이터를 로드할 수 없습니다.")
        return

    # 기본 통계 출력
    basic_stats = analyzer.get_basic_stats()
    print("\n📊 기본 통계:")
    print(f"  - 총 제품 수: {basic_stats['total_products']:,}개")
    print(f"  - 총 시술 수: {basic_stats['total_treatments']:,}개")
    print(f"  - 병원명: {basic_stats['clinic_name']}")
    print(f"  - 추출 일시: {basic_stats['extraction_date']}")

    # 리포트 생성 및 저장
    output_file = analyzer.save_report_to_files()

    print("\n✅ 분석 완료! 결과는 다음 위치에 저장되었습니다:")
    print(f"   - 종합 리포트: {output_file}")
    print("   - CSV 파일들: data/statistics/ 디렉토리")


if __name__ == "__main__":
    main()
