"""
核心模块
包含 MWIC32 实现、自动探测器、类型定义和常量
"""

from .mwic import MWIC32
from .detector import AutoCardDetector
from .types import CardType, DeviceStatus, CardMemoryInfo, CardFullData, get_card_memory_info
from .constants import *

__all__ = [
    "MWIC32",
    "AutoCardDetector",
    "CardType",
    "DeviceStatus",
    "CardMemoryInfo",
    "CardFullData",
    "get_card_memory_info",
]
