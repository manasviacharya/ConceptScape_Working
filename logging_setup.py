import logging

from config import settings


def configure_logging():
    logging.basicConfig(level=settings.log_level, format=settings.log_format)
