import time
import threading
from typing import Optional, Callable

from .mwic import MWIC32
from .constants import IC_OK, IC_ERR, IC_ERR_NO_CARD, CARD_READ_CHUNK
from .constants import (
    AT24C01A_SIZE, AT24C02_SIZE, AT24C04_SIZE, AT24C08_SIZE,
    AT24C16_SIZE, AT24C32_SIZE, AT24C64_SIZE,
    SLE4442_MAIN_SIZE, SLE4442_PROTECTION_SIZE, SLE4442_SECURITY_SIZE,
    SLE4428_MAIN_SIZE, SLE4428_PROTECTION_SIZE, SLE4428_SECURITY_SIZE,
    SLE4418_MAIN_SIZE, SLE4418_PROTECTION_SIZE,
    AT88C102_SIZE, AT88C1604_SIZE, AT88C1608_SIZE,
    AT88SC153_SIZE, AT88SC1604B_SIZE,
)
from .types import CardType, DeviceStatus, CardFullData, CardMemoryInfo, get_card_memory_info


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
]


class AutoCardDetector:

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
        self._last_read_data: Optional[CardFullData] = None  # 存储最后一次读取的卡片数据

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
                # 不在连接时识别卡片，留给检测循环处理

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

        # 如果已经识别过，不再重复识别
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

    def read_card_data(self, offset: int = 0, length: int = 32) -> tuple:
        if not self.status.connected or self.status.device_handle <= 0:
            return (IC_ERR_NO_CARD, b'')

        if not self.status.card_type:
            return (IC_ERR_NO_CARD, b'')

        try:
            card_type = self.status.card_type

            if card_type in (CardType.AT24C01A, CardType.AT24C02, CardType.AT24C04,
                             CardType.AT24C08, CardType.AT24C16, CardType.AT24C32,
                             CardType.AT24C64):
                size_map = {
                    CardType.AT24C01A: '01a',
                    CardType.AT24C02: '02',
                    CardType.AT24C04: '04',
                    CardType.AT24C08: '08',
                    CardType.AT24C16: '16',
                    CardType.AT24C32: '32',
                    CardType.AT24C64: '64',
                }
                size = size_map.get(card_type, '16')
                return self.mwic.srd_24c(self.status.device_handle, size, offset, length)

            elif card_type in (CardType.SLE4442,):
                return self.mwic.srd_4442(self.status.device_handle, offset, length)

            elif card_type in (CardType.SLE4428, CardType.SLE4418):
                return self.mwic.srd_4428(self.status.device_handle, offset, length)

            return (IC_ERR_NO_CARD, b'')

        except Exception as e:
            print(f"读取卡片数据失败：{e}")
            return (IC_ERR_NO_CARD, b'')

    def read_card_full_data(self) -> CardFullData:
        result = CardFullData(card_type=self.status.card_type or CardType.UNKNOWN)

        if not self.status.connected or self.status.device_handle <= 0:
            result.error_message = "设备未连接"
            return result

        if not self.status.card_type or self.status.card_type == CardType.UNKNOWN:
            result.error_message = "未知卡片类型"
            return result

        card_type = self.status.card_type
        result.memory_info = get_card_memory_info(card_type)
        handle = self.status.device_handle

        try:
            if card_type in (CardType.AT24C01A, CardType.AT24C02, CardType.AT24C04,
                             CardType.AT24C08, CardType.AT24C16, CardType.AT24C32,
                             CardType.AT24C64):
                result.main_data = self._read_24c_full(card_type)
                if result.main_data:
                    result.success = True
                else:
                    result.error_message = "读取 AT24C 卡片数据失败"

            elif card_type == CardType.SLE4442:
                result.main_data = self._read_sle4442_main()
                result.protection_data = self._read_sle4442_protection()
                result.security_data = self._read_sle4442_security()
                result.remaining_attempts = self.get_remaining_attempts()
                if result.main_data:
                    result.success = True
                else:
                    result.error_message = "读取 SLE4442 卡片数据失败"

            elif card_type == CardType.SLE4428:
                result.main_data = self._read_sle4428_main()
                result.protection_data = self._read_sle4428_protection()
                result.security_data = self._read_sle4428_security()
                result.remaining_attempts = self.get_remaining_attempts()
                if result.main_data:
                    result.success = True
                else:
                    result.error_message = "读取 SLE4428 卡片数据失败"

            elif card_type == CardType.SLE4418:
                result.main_data = self._read_sle4418_main()
                result.protection_data = self._read_sle4418_protection()
                if result.main_data:
                    result.success = True
                else:
                    result.error_message = "读取 SLE4418 卡片数据失败"

            elif card_type == CardType.CPU_CARD:
                result.main_data = self._read_cpu_card()
                if result.main_data:
                    result.success = True
                else:
                    result.error_message = "读取 CPU 卡片数据失败"

            elif card_type == CardType.AT88C102:
                result.main_data = self._read_at88c(AT88C102_SIZE, 'srd_at88c102')
                if result.main_data:
                    result.success = True
                else:
                    result.error_message = "读取 AT88C102 卡片数据失败"

            elif card_type == CardType.AT88C1604:
                result.main_data = self._read_at88c(AT88C1604_SIZE, 'srd_at88c1604')
                if result.main_data:
                    result.success = True
                else:
                    result.error_message = "读取 AT88C1604 卡片数据失败"

            elif card_type == CardType.AT88C1608:
                result.main_data = self._read_at88c(AT88C1608_SIZE, 'srd_at88c1608')
                if result.main_data:
                    result.success = True
                else:
                    result.error_message = "读取 AT88C1608 卡片数据失败"

            elif card_type == CardType.AT88SC153:
                result.main_data = self._read_at88c(AT88SC153_SIZE, 'srd_at88sc153')
                if result.main_data:
                    result.success = True
                else:
                    result.error_message = "读取 AT88SC153 卡片数据失败"

            elif card_type == CardType.AT88SC1604B:
                result.main_data = self._read_at88c(AT88SC1604B_SIZE, 'srd_at88sc1604b')
                if result.main_data:
                    result.success = True
                else:
                    result.error_message = "读取 AT88SC1604B 卡片数据失败"

            else:
                result.error_message = f"不支持的卡片类型: {card_type.name}"

        except Exception as e:
            result.error_message = f"读取卡片数据异常: {e}"

        # 保存最后一次读取的数据，用于保护位检查
        if result.success:
            self._last_read_data = result

        return result

    def _read_chunked(self, total_size: int, read_func, chunk_size: int = CARD_READ_CHUNK) -> bytes:
        data = bytearray()
        offset = 0
        while offset < total_size:
            remaining = total_size - offset
            read_len = min(chunk_size, remaining)
            st, chunk = read_func(offset, read_len)
            if st == IC_OK and len(chunk) >= 1:
                data.extend(chunk)
                offset += read_len
            elif len(chunk) >= 1:
                data.extend(chunk)
                offset += read_len
            else:
                if offset > 0:
                    break
                return b''
        return bytes(data[:total_size])

    def _read_24c_full(self, card_type: CardType) -> bytes:
        size_map = {
            CardType.AT24C01A: ('01a', AT24C01A_SIZE),
            CardType.AT24C02: ('02', AT24C02_SIZE),
            CardType.AT24C04: ('04', AT24C04_SIZE),
            CardType.AT24C08: ('08', AT24C08_SIZE),
            CardType.AT24C16: ('16', AT24C16_SIZE),
            CardType.AT24C32: ('32', AT24C32_SIZE),
            CardType.AT24C64: ('64', AT24C64_SIZE),
        }
        size_str, total = size_map.get(card_type, ('16', AT24C16_SIZE))
        handle = self.status.device_handle

        def read_func(offset, length):
            return self.mwic.srd_24c(handle, size_str, offset, length)

        return self._read_chunked(total, read_func)

    def _read_sle4442_main(self) -> bytes:
        handle = self.status.device_handle

        def read_func(offset, length):
            return self.mwic.srd_4442(handle, offset, length)

        return self._read_chunked(SLE4442_MAIN_SIZE, read_func)

    def _read_sle4442_protection(self) -> bytes:
        handle = self.status.device_handle
        st, data = self.mwic.prd_4442(handle, SLE4442_PROTECTION_SIZE)
        if len(data) >= 1:
            return data
        print(f"[DEBUG] prd_4442 失败：st={st}, data_len={len(data)}")
        st, data = self.mwic.srd_4442(handle, SLE4442_MAIN_SIZE + SLE4442_SECURITY_SIZE, SLE4442_PROTECTION_SIZE)
        if len(data) >= 1:
            print(f"[DEBUG] srd_4442(offset=260) 保护位使用非OK状态数据: st={st}, data={data.hex()}")
            return data
        try:
            st, data = self.mwic.srd_4442(handle, 0, SLE4442_MAIN_SIZE + SLE4442_SECURITY_SIZE + SLE4442_PROTECTION_SIZE)
            if len(data) > SLE4442_MAIN_SIZE + SLE4442_SECURITY_SIZE:
                pro_data = data[SLE4442_MAIN_SIZE + SLE4442_SECURITY_SIZE:]
                print(f"[DEBUG] srd_4442(offset=0,len=292) 保护位使用非OK状态数据: st={st}, pro_data={pro_data.hex()}")
                return pro_data
            print(f"[DEBUG] srd_4442(offset=0,len=292) 保护位数据不足: st={st}, data_len={len(data)}")
        except Exception as e:
            print(f"[DEBUG] srd_4442(offset=0,len=292) 保护位异常: {e}")
        return b''

    def _read_sle4442_security(self) -> bytes:
        handle = self.status.device_handle
        st, data = self.mwic.rsc_4442(handle, SLE4442_SECURITY_SIZE)
        if len(data) >= 1:
            return data
        print(f"[DEBUG] rsc_4442 失败：st={st}, data_len={len(data)}")
        st, data = self.mwic.srd_4442(handle, SLE4442_MAIN_SIZE, SLE4442_SECURITY_SIZE)
        if len(data) >= 1:
            print(f"[DEBUG] srd_4442(offset=256) 使用非OK状态数据: st={st}, data={data.hex()}")
            return data
        print(f"[DEBUG] srd_4442(offset=256) 无数据: st={st}, data_len={len(data)}")
        try:
            st, data = self.mwic.srd_4442(handle, 0, SLE4442_MAIN_SIZE + SLE4442_SECURITY_SIZE)
            if len(data) > SLE4442_MAIN_SIZE:
                sec_data = data[SLE4442_MAIN_SIZE:]
                print(f"[DEBUG] srd_4442(offset=0,len=260) 使用非OK状态数据: st={st}, sec_data={sec_data.hex()}")
                return sec_data
            print(f"[DEBUG] srd_4442(offset=0,len=260) 数据不足: st={st}, data_len={len(data)}")
        except Exception as e:
            print(f"[DEBUG] srd_4442(offset=0,len=260) 异常: {e}")
        return b''

    def _read_sle4428_main(self) -> bytes:
        handle = self.status.device_handle

        def read_func(offset, length):
            return self.mwic.srd_4428(handle, offset, length)

        return self._read_chunked(SLE4428_MAIN_SIZE, read_func)

    def _read_sle4428_protection(self) -> bytes:
        handle = self.status.device_handle

        def read_func(offset, length):
            st, data = self.mwic.rdwpb_4428(handle, offset, length)
            if len(data) >= 1:
                return (st, data)
            print(f"[DEBUG] rdwpb_4428 失败：st={st}, offset={offset}, data_len={len(data)}")
            return (st, b'')

        result = self._read_chunked(SLE4428_PROTECTION_SIZE, read_func)
        if result:
            return result

        def fallback_func(offset, length):
            st, data = self.mwic.srd_4428(handle, SLE4428_MAIN_SIZE + SLE4428_SECURITY_SIZE + offset, length)
            if len(data) >= 1:
                print(f"[DEBUG] srd_4428 保护位回退: offset={SLE4428_MAIN_SIZE + SLE4428_SECURITY_SIZE + offset}, st={st}, data_len={len(data)}")
                return (st, data)
            return (st, b'')

        return self._read_chunked(SLE4428_PROTECTION_SIZE, fallback_func)

    def _read_sle4428_security(self) -> bytes:
        handle = self.status.device_handle
        st, data = self.mwic.rsc_4428(handle, SLE4428_SECURITY_SIZE)
        if len(data) >= 1:
            return data
        print(f"[DEBUG] rsc_4428 失败：st={st}, data_len={len(data)}")
        st, data = self.mwic.srd_4428(handle, SLE4428_MAIN_SIZE, SLE4428_SECURITY_SIZE)
        if len(data) >= 1:
            print(f"[DEBUG] srd_4428(offset=1024) 使用非OK状态数据: st={st}, data={data.hex()}")
            return data
        print(f"[DEBUG] srd_4428(offset=1024) 无数据: st={st}, data_len={len(data)}")
        try:
            st, data = self.mwic.srd_4428(handle, 0, SLE4428_MAIN_SIZE + SLE4428_SECURITY_SIZE)
            if len(data) > SLE4428_MAIN_SIZE:
                sec_data = data[SLE4428_MAIN_SIZE:]
                print(f"[DEBUG] srd_4428(offset=0,len=1026) 使用非OK状态数据: st={st}, sec_data={sec_data.hex()}")
                return sec_data
            print(f"[DEBUG] srd_4428(offset=0,len=1026) 数据不足: st={st}, data_len={len(data)}")
        except Exception as e:
            print(f"[DEBUG] srd_4428(offset=0,len=1026) 异常: {e}")
        return b''

    def _read_sle4418_main(self) -> bytes:
        handle = self.status.device_handle

        def read_func(offset, length):
            return self.mwic.srd_4418(handle, offset, length)

        return self._read_chunked(SLE4418_MAIN_SIZE, read_func)

    def _read_sle4418_protection(self) -> bytes:
        handle = self.status.device_handle

        def read_func(offset, length):
            # SLE4418 的保护位使用 rdwpb_4418 函数
            st, data = self.mwic.rdwpb_4418(handle, offset, length)
            if len(data) >= 1:
                return (st, data)
            print(f"[DEBUG] rdwpb_4418 失败：st={st}, offset={offset}, data_len={len(data)}")
            return (st, b'')

        result = self._read_chunked(SLE4418_PROTECTION_SIZE, read_func)
        if result:
            return result

        # 回退方案：使用 srd_4418 读取
        def fallback_func(offset, length):
            st, data = self.mwic.srd_4418(handle, SLE4418_MAIN_SIZE + offset, length)
            if len(data) >= 1:
                print(f"[DEBUG] srd_4418 保护位回退: offset={SLE4418_MAIN_SIZE + offset}, st={st}, data_len={len(data)}")
                return (st, data)
            return (st, b'')

        return self._read_chunked(SLE4418_PROTECTION_SIZE, fallback_func)

    def _read_cpu_card(self) -> bytes:
        handle = self.status.device_handle
        st, atr_data = self.mwic.cpu_reset(handle)
        if st == IC_OK and atr_data:
            return atr_data
        return b''

    def _read_at88c(self, total_size: int, read_func_name: str, zone: int = 0) -> bytes:
        handle = self.status.device_handle
        read_fn = getattr(self.mwic, read_func_name, None)
        if read_fn is None:
            return b''

        def read_func(offset, length):
            return read_fn(handle, zone, offset, length)

        return self._read_chunked(total_size, read_func)

    def verify_card_password(self, password: bytes) -> bool:
        if not self.status.connected or self.status.device_handle <= 0:
            return False
        if not self.status.card_type:
            return False

        handle = self.status.device_handle
        card_type = self.status.card_type

        try:
            if card_type == CardType.SLE4442:
                st = self.mwic.csc_4442(handle, len(password), password)
                return st == IC_OK
            elif card_type == CardType.SLE4428:
                st = self.mwic.csc_4428(handle, len(password), password)
                return st == IC_OK
            elif card_type == CardType.CPU_CARD:
                return True
            else:
                return True
        except Exception as e:
            print(f"密码验证失败：{e}")
            return False

    def change_card_password(self, current_password: bytes, new_password: bytes) -> bool:
        if not self.status.connected or self.status.device_handle <= 0:
            print(f"[ERROR] change_card_password: 设备未连接")
            return False
        if not self.status.card_type:
            print(f"[ERROR] change_card_password: 卡片类型未知")
            return False

        handle = self.status.device_handle
        card_type = self.status.card_type

        print(f"[DEBUG] change_card_password: card_type={card_type.name}, current_pwd={current_password.hex().upper()}, new_pwd={new_password.hex().upper()}")

        try:
            if card_type == CardType.SLE4442:
                print(f"[DEBUG] 步骤1: 验证当前密码 (csc_4442)")
                st = self.mwic.csc_4442(handle, len(current_password), current_password)
                print(f"[DEBUG] csc_4442 返回: st={st}")
                if st != IC_OK:
                    print(f"[ERROR] 验证当前密码失败：st={st}")
                    return False
                
                print(f"[DEBUG] 步骤2: 写入新密码 (wsc_4442)")
                print(f"[DEBUG] wsc_4442 参数: handle={handle}, len={len(new_password)}, data={new_password.hex().upper()}")
                st = self.mwic.wsc_4442(handle, new_password)
                print(f"[DEBUG] wsc_4442 返回: st={st}")
                return st == IC_OK
                
            elif card_type == CardType.SLE4428:
                print(f"[DEBUG] 步骤1: 验证当前密码 (csc_4428)")
                st = self.mwic.csc_4428(handle, len(current_password), current_password)
                print(f"[DEBUG] csc_4428 返回: st={st}")
                if st != IC_OK:
                    print(f"[ERROR] 验证当前密码失败：st={st}")
                    return False
                
                print(f"[DEBUG] 步骤2: 写入新密码 (wsc_4428)")
                print(f"[DEBUG] wsc_4428 参数: handle={handle}, len={len(new_password)}, data={new_password.hex().upper()}")
                st = self.mwic.wsc_4428(handle, new_password)
                print(f"[DEBUG] wsc_4428 返回: st={st}")
                return st == IC_OK
            else:
                print(f"[ERROR] change_card_password: 不支持的卡片类型 {card_type.name}")
                return False
        except Exception as e:
            print(f"[ERROR] 修改密码异常：{e}")
            import traceback
            traceback.print_exc()
            return False

    def write_card_data(self, offset: int, data: bytes) -> int:
        if not self.status.connected or self.status.device_handle <= 0:
            return IC_ERR_NO_CARD
        if not self.status.card_type:
            return IC_ERR_NO_CARD

        handle = self.status.device_handle
        card_type = self.status.card_type

        print(f"[DEBUG] write_card_data: card_type={card_type.name}, offset={offset}, data_len={len(data)}")

        try:
            if card_type in (CardType.AT24C01A, CardType.AT24C02, CardType.AT24C04,
                             CardType.AT24C08, CardType.AT24C16, CardType.AT24C32,
                             CardType.AT24C64):
                size_map = {
                    CardType.AT24C01A: '01a',
                    CardType.AT24C02: '02',
                    CardType.AT24C04: '04',
                    CardType.AT24C08: '08',
                    CardType.AT24C16: '16',
                    CardType.AT24C32: '32',
                    CardType.AT24C64: '64',
                }
                size = size_map.get(card_type, '16')
                return self.mwic.swr_24c(handle, size, offset, data)

            elif card_type == CardType.SLE4442:
                return self.mwic.swr_4442(handle, offset, data)

            elif card_type == CardType.SLE4428:
                print(f"[DEBUG] 写入 SLE4428 主存储器: offset={offset}, len={len(data)}")
                return self.mwic.swr_4428(handle, offset, data)

            elif card_type == CardType.SLE4418:
                print(f"[DEBUG] 写入 SLE4418 主存储器: offset={offset}, len={len(data)}")
                return self.mwic.swr_4418(handle, offset, data)

            elif card_type == CardType.AT88C102:
                return self.mwic.swr_at88c102(handle, 0, offset, data)

            elif card_type == CardType.AT88C1604:
                return self.mwic.swr_at88c1604(handle, 0, offset, data)

            elif card_type == CardType.AT88SC1604B:
                return self.mwic.swr_at88sc1604b(handle, 0, offset, data)

            elif card_type == CardType.AT88C1608:
                return self.mwic.swr_at88c1608(handle, 0, offset, data)

            elif card_type == CardType.AT88SC153:
                return self.mwic.swr_at88sc153(handle, 0, offset, data)

            return IC_ERR

        except Exception as e:
            print(f"写入卡片数据失败：{e}")
            return IC_ERR

    def write_card_protection(self, offset: int, data: bytes) -> int:
        if not self.status.connected or self.status.device_handle <= 0:
            return IC_ERR_NO_CARD
        if not self.status.card_type:
            return IC_ERR_NO_CARD

        handle = self.status.device_handle
        card_type = self.status.card_type

        try:
            if card_type == CardType.SLE4442:
                return self.mwic.pwr_4442(handle, offset, data)
            elif card_type == CardType.SLE4428:
                print(f"[DEBUG] 写入 SLE4428 保护位: offset={offset}, len={len(data)}")
                return self.mwic.wrwpb_4428(handle, offset, data)
            elif card_type == CardType.SLE4418:
                print(f"[DEBUG] 写入 SLE4418 保护位: offset={offset}, len={len(data)}")
                return self.mwic.wrwpb_4418(handle, offset, data)
            return IC_ERR
        except Exception as e:
            print(f"写入保护位失败：{e}")
            return IC_ERR

    def card_needs_password(self) -> bool:
        if not self.status.card_type:
            return False
        return self.status.card_type in (CardType.SLE4442, CardType.SLE4428)

    def _check_protection_before_write(self, card_type: CardType, offset: int, length: int) -> bool:
        """在写入前检查保护位，返回 True 表示可以写入，False 表示被保护"""
        try:
            # 检查保护位数据是否已加载
            if not self._last_read_data or not self._last_read_data.protection_data:
                print(f"[WARNING] 保护位数据未加载，跳过检查")
                return True  # 无法检查时允许写入

            protection_data = self._last_read_data.protection_data
            
            # 检查偏移范围内的每个字节对应的保护位
            for i in range(length):
                check_offset = offset + i
                if check_offset < len(protection_data):
                    # 保护位为 0x00 表示已锁定，0xFF 表示可写
                    prot_byte = protection_data[check_offset]
                    if prot_byte == 0x00:
                        print(f"[DEBUG] 保护位检查：偏移 {check_offset:04X} 对应的保护位=0x{prot_byte:02X} (已锁定)")
                        return False
                    elif prot_byte != 0xFF:
                        # 部分位被保护（按位保护）
                        print(f"[DEBUG] 保护位检查：偏移 {check_offset:04X} 对应的保护位=0x{prot_byte:02X} (部分锁定)")
                        # 这里简化处理，实际应该按位检查
                        # 暂时允许写入，让DLL返回具体错误
            
            return True
        except Exception as e:
            print(f"[WARNING] 保护位检查异常：{e}")
            return True  # 检查失败时允许写入

    def get_remaining_attempts(self) -> int:
        if not self.status.connected or self.status.device_handle <= 0:
            print(f"[DEBUG] get_remaining_attempts: 设备未连接 connected={self.status.connected}, handle={self.status.device_handle}")
            return -1
        if not self.status.card_type:
            print("[DEBUG] get_remaining_attempts: 卡片类型未知")
            return -1

        handle = self.status.device_handle
        card_type = self.status.card_type

        try:
            if card_type == CardType.SLE4442:
                st, counter = self.mwic.rsct_4442(handle)
                print(f"[DEBUG] get_remaining_attempts SLE4442: rsct_4442 st={st}, counter={counter}")
                if st == IC_OK and counter >= 0 and counter <= 3:
                    return counter
                st, data = self.mwic.rsc_4442(handle, SLE4442_SECURITY_SIZE)
                print(f"[DEBUG] get_remaining_attempts SLE4442: rsc_4442 st={st}, data={data.hex() if data else 'None'}")
                if len(data) >= 1:
                    err_counter = data[0]
                    if err_counter == 0:
                        return 0
                    remaining = bin(err_counter & 0x07).count('1')
                    print(f"[DEBUG] rsc_4442 解析剩余次数：{remaining}")
                    return remaining
                st, data = self.mwic.srd_4442(handle, SLE4442_MAIN_SIZE, SLE4442_SECURITY_SIZE)
                print(f"[DEBUG] get_remaining_attempts SLE4442: srd_4442(offset=256) st={st}, data={data.hex() if data else 'None'}")
                if len(data) >= 1:
                    err_counter = data[0]
                    if err_counter == 0:
                        return 0
                    remaining = bin(err_counter & 0x07).count('1')
                    print(f"[DEBUG] srd_4442 解析剩余次数：{remaining}")
                    return remaining
                print("[DEBUG] get_remaining_attempts SLE4442: 所有方法均失败")
                return -1

            elif card_type == CardType.SLE4428:
                st, counter = self.mwic.rsct_4428(handle)
                print(f"[DEBUG] get_remaining_attempts SLE4428: rsct_4428 st={st}, counter={counter}")
                if st == IC_OK and counter >= 0 and counter <= 8:
                    return counter
                st, data = self.mwic.rsc_4428(handle, SLE4428_SECURITY_SIZE)
                print(f"[DEBUG] get_remaining_attempts SLE4428: rsc_4428 st={st}, data={data.hex() if data else 'None'}")
                if len(data) >= 1:
                    err_counter = data[0]
                    if err_counter == 0:
                        return 0
                    remaining = bin(err_counter & 0xFF).count('1')
                    print(f"[DEBUG] rsc_4428 解析剩余次数：{remaining}")
                    return remaining
                st, data = self.mwic.srd_4428(handle, SLE4428_MAIN_SIZE, SLE4428_SECURITY_SIZE)
                print(f"[DEBUG] get_remaining_attempts SLE4428: srd_4428(offset=1024) st={st}, data={data.hex() if data else 'None'}")
                if len(data) >= 1:
                    err_counter = data[0]
                    if err_counter == 0:
                        return 0
                    remaining = bin(err_counter & 0xFF).count('1')
                    print(f"[DEBUG] srd_4428 解析剩余次数：{remaining}")
                    return remaining
                print("[DEBUG] get_remaining_attempts SLE4428: 所有方法均失败")
                return -1

            else:
                print(f"[DEBUG] get_remaining_attempts: 不支持的卡片类型 {card_type}")
                return -1
        except Exception as e:
            print(f"获取剩余校验次数失败：{e}")
            return -1

    def get_security_memory_data(self) -> bytes:
        if not self.status.connected or self.status.device_handle <= 0:
            return b''
        if not self.status.card_type:
            return b''

        handle = self.status.device_handle
        card_type = self.status.card_type

        try:
            if card_type == CardType.SLE4442:
                st, data = self.mwic.rsc_4442(handle, SLE4442_SECURITY_SIZE)
                if len(data) >= 1:
                    return data
                st, data = self.mwic.srd_4442(handle, SLE4442_MAIN_SIZE, SLE4442_SECURITY_SIZE)
                if len(data) >= 1:
                    return data
                try:
                    st, data = self.mwic.srd_4442(handle, 0, SLE4442_MAIN_SIZE + SLE4442_SECURITY_SIZE)
                    if len(data) > SLE4442_MAIN_SIZE:
                        return data[SLE4442_MAIN_SIZE:]
                except Exception:
                    pass
                return b''

            elif card_type == CardType.SLE4428:
                st, data = self.mwic.rsc_4428(handle, SLE4428_SECURITY_SIZE)
                if len(data) >= 1:
                    return data
                st, data = self.mwic.srd_4428(handle, SLE4428_MAIN_SIZE, SLE4428_SECURITY_SIZE)
                if len(data) >= 1:
                    return data
                try:
                    st, data = self.mwic.srd_4428(handle, 0, SLE4428_MAIN_SIZE + SLE4428_SECURITY_SIZE)
                    if len(data) > SLE4428_MAIN_SIZE:
                        return data[SLE4428_MAIN_SIZE:]
                except Exception:
                    pass
                return b''

            else:
                return b''
        except Exception as e:
            print(f"读取安全存储器失败：{e}")
            return b''

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

        # 优先尝试 USB 和 HID 接口（最常见）
        for port in [self.PORT_USB, self.PORT_HID, 0]:
            for baud in self.BAUD_RATES:
                print(f"尝试端口 {port} @ {baud}...")
                if self.connect(port, baud):
                    print(f"✓ 连接成功 (port={port}, baud={baud})")
                    return True

        # 如果 USB/HID 都失败，再尝试 COM 口
        for port in range(1, 5):
            for baud in self.BAUD_RATES:
                print(f"尝试 COM{port + 1} @ {baud}...")
                if self.connect(port, baud):
                    print(f"✓ COM{port + 1} @ {baud} 连接成功")
                    return True

        print("✗ 未找到任何读写器")
        return False
