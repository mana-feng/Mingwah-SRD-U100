"""
MWIC Python Package
明华读写器纯 Python 实现
不依赖 MWIC_32.dll，直接使用串口通信实现读写器控制
"""

__version__ = "1.0.0"
__author__ = "Based on MWIC_32.h and demo.exe reverse engineering"
__description__ = "纯 Python 实现的明华读写器控制库"

from .core.mwic import MWIC32
from .core.detector import AutoCardDetector, DeviceStatus
from .core.types import CardType
from .protocols import CommandProtocol
from .core.constants import *

__all__ = [
    "MWIC32",
    "AutoCardDetector",
    "DeviceStatus",
    "CardType",
    "CommandProtocol",
]
