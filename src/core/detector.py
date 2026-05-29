import time
import threading
from typing import Optional, Callable

from .mwic import MWIC32
from .constants import IC_OK, IC_ERR, CARD_READ_CHUNK
from .types import CardType, DeviceStatus, CardFullData
from .card_ops import CardOperationsMixin


CHK_ORDER = [
    ('chk_24c01a', CardType.AT24C01A, None),
    ('chk_24c02', CardType.AT24C02, None),
    ('chk_24c04', CardType.AT24C04, None),
    ('chk_24c08', CardType.AT24C08, None),
    ('chk_24c16', CardType.AT24C16, None),
    ('chk_24c32', CardType.AT24C32, None),
    ('chk_24c64', CardType.AT24C64, None),
    ('chk_4442', CardType.SLE4442, None),
    ('chk_4428', CardType.SLE4428, None),
    ('chk_4418', CardType.SLE4418, None),
    ('chk_4404', CardType.CARD4404, None),
    ('chk_4406', CardType.CARD4406, None),
    ('chk_4432', CardType.CARD4432, None),
    ('chk_45d041', CardType.CARD45D041, None),
    ('chk_93c46', CardType.CARD93C46, None),
    ('chk_93c46a', CardType.CARD93C46A, None),
    ('chk_dvsc', CardType.CARDDVSC, None),
    ('chk_ssf1101', CardType.CARDSSF1101, None),
]


class AutoCardDetector(CardOperationsMixin):

    PORT_COM1 = 0
    PORT_COM2 = 1
    PORT_COM3 = 2
    PORT_COM4 = 3
    PORT_USB = 632
    PORT_HID = 888

    BAUD_RATES = [9600, 115200]

    def __init__(self, mwic: MWIC32):
        self.mwic = mwic
        self.status = DeviceStatus()
        self._running = False
        self._detect_thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable] = None
        self._mutex = threading.Lock()
        self._last_read_data: Optional[CardFullData] = None

    def connect(self, port_type: int = 0, baud_rate: int = 9600) -> bool:
        try:
            if self.status.device_handle > 0:
                self.disconnect()

            handle = self.mwic.ic_init(port_type, baud_rate)

            if handle < 0:
                self.status.connected = False
                self.status.device_handle = -1
                return False

            self.status.connected = True
            self.status.device_handle = handle
            self.status.port_type = port_type
            self.status.baud_rate = baud_rate

            result, status_val = self.mwic.get_status(handle)
            if result == 0:
                self.status.card_present = (status_val & 1) == 1

            return True

        except Exception as e:
            print(f"连接失败：{e}")
            self.status.connected = False
            return False

    def disconnect(self) -> bool:
        try:
            if self.status.device_handle > 0:
                self.mwic.ic_exit(self.status.device_handle)
                self.status.device_handle = -1
                self.status.connected = False
                self.status.card_present = False
                self.status.card_type = None
            return True
        except Exception as e:
            print(f"断开连接失败：{e}")
            return False

    def _check_card(self) -> bool:
        if not self.status.connected or self.status.device_handle <= 0:
            return False

        try:
            result, status_val = self.mwic.get_status(self.status.device_handle)
            if result != 0:
                return self.status.card_present

            has_card = (status_val & 1) == 1

            if has_card != self.status.card_present:
                self.status.card_present = has_card
                if self._callback:
                    self._callback("card_status", has_card)

            return has_card
        except Exception as e:
            print(f"检查卡片失败：{e}")
            return False

    def _identify_card(self) -> Optional[CardType]:
        if not self.status.connected or self.status.device_handle <= 0:
            return None

        if self.status.card_type and self.status.card_type != CardType.UNKNOWN:
            print(f"[DEBUG] 卡片已识别，返回缓存类型: {self.status.card_type.name}")
            return self.status.card_type

        try:
            handle = self.status.device_handle
            print(f"[DEBUG] 开始识别卡片类型...")

            for func_name, card_type, size_suffix in CHK_ORDER:
                try:
                    st = getattr(self.mwic, func_name)(handle)
                    print(f"[DEBUG] {func_name}: st={st}")

                    if st == 0:
                        self.status.card_type = card_type
                        print(f"[DEBUG] ✓ 识别成功: {card_type.name}")
                        return card_type
                except Exception as e:
                    print(f"[DEBUG] {func_name} 异常: {e}")
                    continue

            self.status.card_type = CardType.UNKNOWN
            print(f"[DEBUG] ✗ 无法识别卡片类型")
            return CardType.UNKNOWN

        except Exception as e:
            print(f"[ERROR] 识别卡片失败：{e}")
            import traceback
            traceback.print_exc()
            return None

    def _read_card_info(self) -> bool:
        if not self.status.connected or self.status.device_handle <= 0:
            return False

        try:
            st, ver = self.mwic.srd_ver(self.status.device_handle, 18)
            if st == 0 and ver:
                self.status.card_ver = ver

            st, snr = self.mwic.srd_snr(self.status.device_handle, 16)
            if st == 0 and snr:
                self.status.card_snr = snr.upper()

            if self._callback:
                self._callback("card_info", {
                    "snr": self.status.card_snr,
                    "ver": self.status.card_ver,
                    "type": self.status.card_type.name if self.status.card_type else "UNKNOWN"
                })

            return True

        except Exception as e:
            print(f"读取卡片信息失败：{e}")
            return False

    def _detect_loop(self):
        last_card_status = False
        last_card_type = None

        while self._running:
            try:
                if not self.status.connected:
                    time.sleep(0.5)
                    continue

                has_card = self._check_card()

                if has_card:
                    if not last_card_status:
                        card_type = self._identify_card()
                        if card_type and card_type != CardType.UNKNOWN:
                            self._read_card_info()
                            if self._callback:
                                self._callback("card_detected", {
                                    "type": card_type.name,
                                    "snr": self.status.card_snr,
                                    "ver": self.status.card_ver
                                })
                        elif card_type == CardType.UNKNOWN:
                            if self._callback:
                                self._callback("card_detected", {
                                    "type": "UNKNOWN",
                                    "snr": "",
                                    "ver": ""
                                })

                    elif last_card_type != self.status.card_type:
                        self._read_card_info()
                else:
                    if last_card_status:
                        self.status.card_type = None
                        self.status.card_snr = ""
                        self.status.card_ver = ""
                        if self._callback:
                            self._callback("card_removed", None)

                last_card_status = has_card
                last_card_type = self.status.card_type

                time.sleep(0.3)

            except Exception as e:
                print(f"检测循环错误：{e}")
                time.sleep(1)

    def start_auto_detect(self, callback: Optional[Callable] = None):
        if self._running:
            return

        self._callback = callback
        self._running = True
        self._detect_thread = threading.Thread(target=self._detect_loop, daemon=True)
        self._detect_thread.start()

    def stop_auto_detect(self):
        self._running = False
        if self._detect_thread:
            self._detect_thread.join(timeout=2.0)
            self._detect_thread = None

    def get_status(self) -> DeviceStatus:
        return self.status

    def auto_search_port(self) -> bool:
        print("开始自动搜索读写器...")

        for port in [self.PORT_USB, self.PORT_HID, 0]:
            for baud in self.BAUD_RATES:
                print(f"尝试端口 {port} @ {baud}...")
                if self.connect(port, baud):
                    print(f"✓ 连接成功 (port={port}, baud={baud})")
                    return True

        for port in range(1, 5):
            for baud in self.BAUD_RATES:
                print(f"尝试 COM{port + 1} @ {baud}...")
                if self.connect(port, baud):
                    print(f"✓ COM{port + 1} @ {baud} 连接成功")
                    return True

        print("✗ 未找到任何读写器")
        return False