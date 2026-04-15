"""
类型定义模块
包含卡片类型枚举、数据结构等
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class CardType(Enum):
    """卡片类型定义"""
    UNKNOWN = 0
    CPU_CARD = 3
    AT24C01A = 4
    AT24C02 = 5
    AT24C04 = 6
    AT24C08 = 7
    AT24C16 = 8
    AT24C32 = 9
    AT24C64 = 10
    SLE4428 = 11
    SLE4442 = 12
    SLE4418 = 18
    AT88C102 = 13
    AT88C1604 = 14
    AT88C1608 = 15
    AT88SC153 = 16
    AT88SC1604B = 17


@dataclass
class DeviceStatus:
    """设备状态信息"""
    connected: bool = False
    device_handle: int = -1
    port_type: int = 0
    baud_rate: int = 9600
    card_present: bool = False
    card_type: Optional[CardType] = None
    card_snr: str = ""
    card_ver: str = ""
    hardware_ver: str = ""
    firmware_ver: str = ""
    
    def reset(self):
        """重置设备状态"""
        self.connected = False
        self.device_handle = -1
        self.port_type = 0
        self.baud_rate = 9600
        self.card_present = False
        self.card_type = None
        self.card_snr = ""
        self.card_ver = ""
        self.hardware_ver = ""
        self.firmware_ver = ""
    
    def is_valid(self) -> bool:
        """检查设备状态是否有效"""
        return self.connected and self.device_handle > 0
    
    def has_card(self) -> bool:
        """检查是否有卡"""
        return self.card_present and self.card_type is not None


class EventType(Enum):
    """事件类型"""
    CARD_DETECTED = "card_detected"
    CARD_REMOVED = "card_removed"
    CARD_STATUS = "card_status"
    CARD_INFO = "card_info"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class CardMemoryInfo:
    """卡片存储信息"""
    card_type: CardType = CardType.UNKNOWN
    total_bytes: int = 0
    page_size: int = 1
    sector_size: int = 0
    num_sectors: int = 0
    has_protection: bool = False
    protection_bytes: int = 0
    has_security_memory: bool = False
    security_memory_size: int = 0
    description: str = ""

    def get_read_chunk_size(self) -> int:
        if self.card_type in (CardType.SLE4442, CardType.SLE4428, CardType.SLE4418):
            return 32
        if self.card_type in (CardType.AT24C01A, CardType.AT24C02, CardType.AT24C04,
                              CardType.AT24C08, CardType.AT24C16, CardType.AT24C32,
                              CardType.AT24C64):
            return 32
        if self.card_type in (CardType.AT88C102, CardType.AT88C1604, CardType.AT88C1608,
                              CardType.AT88SC153, CardType.AT88SC1604B):
            return 32
        return 32


CARD_MEMORY_MAP = {
    CardType.AT24C01A: CardMemoryInfo(
        card_type=CardType.AT24C01A, total_bytes=128, page_size=8,
        description="AT24C01A - 128字节 EEPROM"
    ),
    CardType.AT24C02: CardMemoryInfo(
        card_type=CardType.AT24C02, total_bytes=256, page_size=8,
        description="AT24C02 - 256字节 EEPROM"
    ),
    CardType.AT24C04: CardMemoryInfo(
        card_type=CardType.AT24C04, total_bytes=512, page_size=16,
        description="AT24C04 - 512字节 EEPROM"
    ),
    CardType.AT24C08: CardMemoryInfo(
        card_type=CardType.AT24C08, total_bytes=1024, page_size=16,
        description="AT24C08 - 1KB EEPROM"
    ),
    CardType.AT24C16: CardMemoryInfo(
        card_type=CardType.AT24C16, total_bytes=2048, page_size=16,
        description="AT24C16 - 2KB EEPROM"
    ),
    CardType.AT24C32: CardMemoryInfo(
        card_type=CardType.AT24C32, total_bytes=4096, page_size=32,
        description="AT24C32 - 4KB EEPROM"
    ),
    CardType.AT24C64: CardMemoryInfo(
        card_type=CardType.AT24C64, total_bytes=8192, page_size=32,
        description="AT24C64 - 8KB EEPROM"
    ),
    CardType.SLE4442: CardMemoryInfo(
        card_type=CardType.SLE4442, total_bytes=256, page_size=1,
        has_protection=True, protection_bytes=32,
        has_security_memory=True, security_memory_size=4,
        description="SLE4442 - 256字节 + 32字节保护位 + 4字节安全存储器"
    ),
    CardType.SLE4428: CardMemoryInfo(
        card_type=CardType.SLE4428, total_bytes=1024, page_size=1,
        has_protection=True, protection_bytes=1024,
        has_security_memory=True, security_memory_size=2,
        description="SLE4428 - 1KB + 1024字节保护位 + 2字节安全存储器"
    ),
    CardType.SLE4418: CardMemoryInfo(
        card_type=CardType.SLE4418, total_bytes=1024, page_size=1,
        has_protection=True, protection_bytes=1024,
        description="SLE4418 - 1KB + 1024字节保护位"
    ),
    CardType.AT88C102: CardMemoryInfo(
        card_type=CardType.AT88C102, total_bytes=128, page_size=1,
        description="AT88C102 - 128字节"
    ),
    CardType.AT88C1604: CardMemoryInfo(
        card_type=CardType.AT88C1604, total_bytes=2048, page_size=1,
        description="AT88C1604 - 2KB"
    ),
    CardType.AT88C1608: CardMemoryInfo(
        card_type=CardType.AT88C1608, total_bytes=2048, page_size=1,
        description="AT88C1608 - 2KB"
    ),
    CardType.AT88SC153: CardMemoryInfo(
        card_type=CardType.AT88SC153, total_bytes=128, page_size=1,
        description="AT88SC153 - 128字节"
    ),
    CardType.AT88SC1604B: CardMemoryInfo(
        card_type=CardType.AT88SC1604B, total_bytes=2048, page_size=1,
        description="AT88SC1604B - 2KB"
    ),
}


def get_card_memory_info(card_type: CardType) -> CardMemoryInfo:
    return CARD_MEMORY_MAP.get(card_type, CardMemoryInfo(card_type=card_type))


@dataclass
class CardFullData:
    """卡片完整读取结果"""
    card_type: CardType = CardType.UNKNOWN
    memory_info: CardMemoryInfo = None
    main_data: bytes = b''
    protection_data: bytes = b''
    security_data: bytes = b''
    remaining_attempts: int = -1
    error_message: str = ""
    success: bool = False

    def get_hex_display(self, bytes_per_line: int = 16) -> str:
        lines = []
        lines.append(f"=== {self.card_type.name} 卡片数据 ===")
        if self.memory_info:
            lines.append(f"说明: {self.memory_info.description}")
        lines.append("")

        if self.main_data:
            lines.append(f"--- 主存储器 ({len(self.main_data)} 字节) ---")
            lines.extend(self._format_hex(self.main_data, bytes_per_line))

        if self.protection_data:
            lines.append(f"--- 保护位 ({len(self.protection_data)} 字节) ---")
            lines.extend(self._format_hex(self.protection_data, bytes_per_line))

        if self.security_data:
            lines.append(f"--- 安全存储器 ({len(self.security_data)} 字节) ---")
            lines.extend(self._format_hex(self.security_data, bytes_per_line))

        return '\n'.join(lines)

    @staticmethod
    def _format_hex(data: bytes, bytes_per_line: int = 16) -> list:
        lines = []
        for offset in range(0, len(data), bytes_per_line):
            chunk = data[offset:offset + bytes_per_line]
            hex_part = ' '.join(f'{b:02X}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            lines.append(f'{offset:04X}: {hex_part:<{bytes_per_line * 3 - 1}}  {ascii_part}')
        return lines


@dataclass
class CardEvent:
    """卡片事件"""
    type: EventType
    data: dict
    timestamp: float
    
    def __str__(self) -> str:
        return f"{self.type.value}: {self.data}"
