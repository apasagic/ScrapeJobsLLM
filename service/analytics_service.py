from collections import Counter
import re
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_LIBRARY_KEYWORDS = [
    "pytorch",
    "tensorflow",
    "keras",
    "scikit-learn",
    "sklearn",
    "huggingface",
    "transformers",
    "xgboost",
    "lightgbm",
    "spark",
    "numpy",
    "pandas",
]

AREA_PATTERNS = {
    "NLP": [r"\bnlp\b", r"natural language", r"language model", r"transformer", r"chatgpt"],
    "Computer Vision": [r"computer vision", r"cv\b", r"image", r"segmentation", r"object detection"],
    "Reinforcement Learning": [r"reinforcement", r"rl\b"],
    "Time Series": [r"time series", r"forecast", r"temporal"],
    "Recommender Systems": [r"recommender", r"recommendation"],
    "MLOps": [r"mlops", r"deployment", r"pipeline", r"production"],
    "Data Science": [r"data science", r"analytics", r"analysis", r"statistical"],
}


def split_comma_separated(value: Optional[str]) -> List[str]:
    if not value:
        return []

    if isinstance(value, list):
        items = [str(item) for item in value]
    else:
        items = re.split(r"[,;\n]", str(value))

    return [item.strip() for item in items if item.strip()]


def count_top_n(values: Iterable[str], n: int = 10) -> List[Dict[str, int]]:
    counts = Counter(values)
    return [{"value": key, "count": count} for key, count in counts.most_common(n)]


def get_area_distribution(jobs: List[Dict[str, Any]]) -> List[Dict[str, int]]:
    counter = Counter()
    for job in jobs:
        text = " ".join([str(job.get("title", "")), str(job.get("description", "")), str(job.get("tags", ""))]).lower()
        matched = False
        for area, patterns in AREA_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    counter[area] += 1
                    matched = True
                    break
            if matched:
                break
        if not matched:
            counter["Other"] += 1

    return [{"category": key, "count": count} for key, count in counter.most_common()]


def get_experience_distribution(jobs: List[Dict[str, Any]]) -> List[Dict[str, int]]:
    buckets = Counter()
    for job in jobs:
        value = str(job.get("experience", "")).lower()
        if "year" in value:
            match = re.search(r"(\d+)(\+)?", value)
            if match:
                years = int(match.group(1))
                if years < 2:
                    buckets["0-2"] += 1
                elif years < 4:
                    buckets["2-4"] += 1
                elif years < 6:
                    buckets["4-6"] += 1
                else:
                    buckets["6+"] += 1
                continue
        buckets["Not specified"] += 1

    return [{"bucket": key, "count": count} for key, count in buckets.most_common()]


def get_top_skills(jobs: List[Dict[str, Any]], n: int = 10) -> List[Dict[str, int]]:
    skills = []
    for job in jobs:
        skills.extend(split_comma_separated(job.get("skills", "")))
        skills.extend(split_comma_separated(job.get("tags", "")))
    return count_top_n(skills, n)


def get_top_libraries(jobs: List[Dict[str, Any]], n: int = 10) -> List[Dict[str, int]]:
    libraries = Counter()
    for job in jobs:
        text = " ".join([str(job.get("description", "")), str(job.get("title", ""))]).lower()
        for name in DEFAULT_LIBRARY_KEYWORDS:
            if name in text:
                libraries[name] += 1
    return [{"value": key, "count": count} for key, count in libraries.most_common(n)]


def get_source_distribution(jobs: List[Dict[str, Any]]) -> List[Dict[str, int]]:
    counter = Counter(str(job.get("source", "Unknown")) for job in jobs)
    return [{"source": key, "count": count} for key, count in counter.most_common()]


class AnalyticsService:
    def __init__(self, storage_adapter):
        self.storage = storage_adapter

    def get_area_distribution(self) -> Dict[str, int]:
        jobs = self.storage.get_jobs(limit=1000)  # Get all jobs for analysis
        result = get_area_distribution(jobs)
        return {item["category"]: item["count"] for item in result}

    def get_top_skills(self, limit: int = 10) -> List[str]:
        jobs = self.storage.get_jobs(limit=1000)
        result = get_top_skills(jobs, limit)
        return [item["value"] for item in result]

    def get_top_libraries(self, limit: int = 10) -> List[str]:
        jobs = self.storage.get_jobs(limit=1000)
        result = get_top_libraries(jobs, limit)
        return [item["value"] for item in result]

    def get_dashboard_stats(self, limit: int = 15) -> Dict[str, Any]:
        jobs = self.storage.get_jobs(limit=1000)
        return {
            "total_jobs": self.storage.count_jobs(),
            "area_distribution": get_area_distribution(jobs),
            "experience_distribution": get_experience_distribution(jobs),
            "source_distribution": get_source_distribution(jobs),
            "top_skills": get_top_skills(jobs, limit),
            "top_libraries": get_top_libraries(jobs, limit),
        }
