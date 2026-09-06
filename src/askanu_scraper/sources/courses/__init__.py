"""Courses collector module."""
from askanu_scraper.sources.courses.collector import CoursesCollector, SOURCE_ID
from askanu_scraper.sources.courses.parser import CoursesParser

__all__ = ["CoursesCollector", "CoursesParser", "SOURCE_ID"]
