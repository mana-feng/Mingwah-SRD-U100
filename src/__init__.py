"""
MWIC Python Package
明华读写器
"""

__version__ = "1.0.0"
__author__ = "manafeng"

from .core.mwic import MWIC32
from .core.detector import AutoCardDetector, DeviceStatus
from .core.types import CardType
from .core.constants import *

__all__ = [
    "MWIC32",
    "AutoCardDetector",
    "DeviceStatus",
    "CardType",
]
