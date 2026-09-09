"""Courses collector module."""
from askanu_scraper.sources.courses.collector import CoursesCollector, SOURCE_ID
from askanu_scraper.sources.courses.discovery import (
    CatalogueDiscoveryResult,
    CatalogueEntityType,
    CatalogueItem,
    CoursesCatalogueDiscovery,
)
from askanu_scraper.sources.courses.parser import CoursesParser

__all__ = [
    "CatalogueDiscoveryResult",
    "CatalogueEntityType",
    "CatalogueItem",
    "CoursesCatalogueDiscovery",
    "CoursesCollector",
    "CoursesParser",
    "SOURCE_ID",
]
