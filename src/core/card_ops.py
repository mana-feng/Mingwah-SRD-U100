from .constants import IC_OK, IC_ERR, IC_ERR_NO_CARD, CARD_READ_CHUNK
from .constants import (
    AT24C01A_SIZE, AT24C02_SIZE, AT24C04_SIZE, AT24C08_SIZE,
    AT24C16_SIZE, AT24C32_SIZE, AT24C64_SIZE,
    SLE4442_MAIN_SIZE, SLE4442_PROTECTION_SIZE, SLE4442_SECURITY_SIZE,
    SLE4428_MAIN_SIZE, SLE4428_PROTECTION_SIZE, SLE4428_SECURITY_SIZE,
    SLE4418_MAIN_SIZE, SLE4418_PROTECTION_SIZE,
    AT88C102_SIZE, AT88C1604_SIZE, AT88C1608_SIZE,
    AT88SC153_SIZE, AT88SC1604B_SIZE,
    CARD4404_SIZE, CARD4406_SIZE, CARD4432_SIZE,
    CARD45D041_SIZE, CARD93C46_SIZE, CARD93C46A_SIZE,
    CARDDVSC_SIZE, CARDSSF1101_SIZE,
)
from .types import CardType, CardFullData, get_card_memory_info


class CardOperationsMixin:

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
                    CardType.AT24C01A: '01a', CardType.AT24C02: '02',
                    CardType.AT24C04: '04', CardType.AT24C08: '08',
                    CardType.AT24C16: '16', CardType.AT24C32: '32',
                    CardType.AT24C64: '64',
                }
                return self.mwic.srd_24c(self.status.device_handle, size_map.get(card_type, '16'), offset, length)

            elif card_type in (CardType.SLE4442,):
                return self.mwic.srd_4442(self.status.device_handle, offset, length)

            elif card_type in (CardType.SLE4428, CardType.SLE4418):
                return self.mwic.srd_4428(self.status.device_handle, offset, length)

            elif card_type in (CardType.CARD4404, CardType.CARD4406, CardType.CARD4432):
                srd_map = {
                    CardType.CARD4404: 'srd_4404',
                    CardType.CARD4406: 'srd_4406',
                    CardType.CARD4432: 'srd_4432',
                }
                srd_fn = getattr(self.mwic, srd_map.get(card_type, ''), None)
                if srd_fn:
                    return srd_fn(self.status.device_handle, offset, length)

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

        try:
            if card_type in (CardType.AT24C01A, CardType.AT24C02, CardType.AT24C04,
                             CardType.AT24C08, CardType.AT24C16, CardType.AT24C32,
                             CardType.AT24C64):
                result.main_data = self._read_24c_full(card_type)

            elif card_type == CardType.SLE4442:
                result.main_data = self._read_sle4442_main()
                result.protection_data = self._read_sle4442_protection()
                result.security_data = self._read_sle4442_security()
                result.remaining_attempts = self.get_remaining_attempts()

            elif card_type == CardType.SLE4428:
                result.main_data = self._read_sle4428_main()
                result.protection_data = self._read_sle4428_protection()
                result.security_data = self._read_sle4428_security()
                result.remaining_attempts = self.get_remaining_attempts()

            elif card_type == CardType.SLE4418:
                result.main_data = self._read_sle4418_main()
                result.protection_data = self._read_sle4418_protection()

            elif card_type == CardType.CPU_CARD:
                result.main_data = self._read_cpu_card()

            elif card_type == CardType.AT88C102:
                result.main_data = self._read_at88c(AT88C102_SIZE, 'srd_at88c102')
            elif card_type == CardType.AT88C1604:
                result.main_data = self._read_at88c(AT88C1604_SIZE, 'srd_at88c1604')
            elif card_type == CardType.AT88C1608:
                result.main_data = self._read_at88c(AT88C1608_SIZE, 'srd_at88c1608')
            elif card_type == CardType.AT88SC153:
                result.main_data = self._read_at88c(AT88SC153_SIZE, 'srd_at88sc153')
            elif card_type == CardType.AT88SC1604B:
                result.main_data = self._read_at88c(AT88SC1604B_SIZE, 'srd_at88sc1604b')

            elif card_type == CardType.CARD4404:
                result.main_data = self._read_44_style(CARD4404_SIZE, 'srd_4404')
            elif card_type == CardType.CARD4406:
                result.main_data = self._read_44_style(CARD4406_SIZE, 'srd_4406')
            elif card_type == CardType.CARD4432:
                result.main_data = self._read_44_style(CARD4432_SIZE, 'srd_4432')
            elif card_type == CardType.CARD45D041:
                result.main_data = self._read_44_style(CARD45D041_SIZE, 'srd_45d041')
            elif card_type == CardType.CARD93C46:
                result.main_data = self._read_93c(CARD93C46_SIZE, 'srd_93c46')
            elif card_type == CardType.CARD93C46A:
                result.main_data = self._read_93c(CARD93C46A_SIZE, 'srd_93c46a')
            elif card_type == CardType.CARDDVSC:
                result.main_data = self._read_44_style(CARDDVSC_SIZE, 'srd_dvsc')
            elif card_type == CardType.CARDSSF1101:
                result.main_data = self._read_44_style(CARDSSF1101_SIZE, 'srd_ssf1101')
            else:
                result.error_message = f"不支持的卡片类型: {card_type.name}"

        except Exception as e:
            result.error_message = f"读取卡片数据异常: {e}"

        if result.main_data:
            result.success = True
        elif not result.error_message:
            result.error_message = "读取卡片数据失败"

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
        st, data = self.mwic.srd_4442(handle, SLE4442_MAIN_SIZE + SLE4442_SECURITY_SIZE, SLE4442_PROTECTION_SIZE)
        if len(data) >= 1:
            return data
        try:
            st, data = self.mwic.srd_4442(handle, 0, SLE4442_MAIN_SIZE + SLE4442_SECURITY_SIZE + SLE4442_PROTECTION_SIZE)
            if len(data) > SLE4442_MAIN_SIZE + SLE4442_SECURITY_SIZE:
                return data[SLE4442_MAIN_SIZE + SLE4442_SECURITY_SIZE:]
        except Exception:
            pass
        return b''

    def _read_sle4442_security(self) -> bytes:
        handle = self.status.device_handle
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
            return (st, b'')

        result = self._read_chunked(SLE4428_PROTECTION_SIZE, read_func)
        if result:
            return result

        def fallback_func(offset, length):
            st, data = self.mwic.srd_4428(handle, SLE4428_MAIN_SIZE + SLE4428_SECURITY_SIZE + offset, length)
            if len(data) >= 1:
                return (st, data)
            return (st, b'')

        return self._read_chunked(SLE4428_PROTECTION_SIZE, fallback_func)

    def _read_sle4428_security(self) -> bytes:
        handle = self.status.device_handle
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

    def _read_sle4418_main(self) -> bytes:
        handle = self.status.device_handle

        def read_func(offset, length):
            return self.mwic.srd_4418(handle, offset, length)

        return self._read_chunked(SLE4418_MAIN_SIZE, read_func)

    def _read_sle4418_protection(self) -> bytes:
        handle = self.status.device_handle

        def read_func(offset, length):
            st, data = self.mwic.rdwpb_4418(handle, offset, length)
            if len(data) >= 1:
                return (st, data)
            return (st, b'')

        result = self._read_chunked(SLE4418_PROTECTION_SIZE, read_func)
        if result:
            return result

        def fallback_func(offset, length):
            st, data = self.mwic.srd_4418(handle, SLE4418_MAIN_SIZE + offset, length)
            if len(data) >= 1:
                return (st, data)
            return (st, b'')

        return self._read_chunked(SLE4418_PROTECTION_SIZE, fallback_func)

    def _read_cpu_card(self) -> bytes:
        handle = self.status.device_handle
        st, atr_data = self.mwic.cpu_reset(handle)
        if st != IC_OK or not atr_data:
            return b''

        self.mwic.cpu_protocol(handle, 0)

        select_mf = bytes.fromhex('00A40000023F00')
        apdu_st, apdu_resp = self.mwic.cpu_comres(handle, select_mf)
        if apdu_st == IC_OK and apdu_resp:
            return atr_data + b'\x1e' + apdu_resp

        return atr_data

    def _read_at88c(self, total_size: int, read_func_name: str, zone: int = 0) -> bytes:
        handle = self.status.device_handle
        read_fn = getattr(self.mwic, read_func_name, None)
        if read_fn is None:
            return b''

        def read_func(offset, length):
            return read_fn(handle, zone, offset, length)

        return self._read_chunked(total_size, read_func)

    def _read_44_style(self, total_size: int, read_func_name: str) -> bytes:
        handle = self.status.device_handle
        read_fn = getattr(self.mwic, read_func_name, None)
        if read_fn is None:
            return b''

        def read_func(offset, length):
            return read_fn(handle, offset, length)

        return self._read_chunked(total_size, read_func)

    def _read_93c(self, total_size: int, read_func_name: str) -> bytes:
        return self._read_44_style(total_size, read_func_name)

    def verify_card_password(self, password: bytes) -> bool:
        if not self.status.connected or self.status.device_handle <= 0:
            return False
        if not self.status.card_type:
            return False

        handle = self.status.device_handle
        card_type = self.status.card_type

        try:
            if card_type == CardType.SLE4442:
                return self.mwic.csc_4442(handle, len(password), password) == IC_OK
            elif card_type == CardType.SLE4428:
                return self.mwic.csc_4428(handle, len(password), password) == IC_OK
            elif card_type == CardType.CPU_CARD:
                return True
            return True
        except Exception as e:
            print(f"密码验证失败：{e}")
            return False

    def change_card_password(self, current_password: bytes, new_password: bytes) -> bool:
        if not self.status.connected or self.status.device_handle <= 0:
            return False
        if not self.status.card_type:
            return False

        handle = self.status.device_handle
        card_type = self.status.card_type

        try:
            if card_type == CardType.SLE4442:
                st = self.mwic.csc_4442(handle, len(current_password), current_password)
                if st != IC_OK:
                    return False
                return self.mwic.wsc_4442(handle, new_password) == IC_OK
            elif card_type == CardType.SLE4428:
                st = self.mwic.csc_4428(handle, len(current_password), current_password)
                if st != IC_OK:
                    return False
                return self.mwic.wsc_4428(handle, new_password) == IC_OK
            return False
        except Exception as e:
            print(f"修改密码异常：{e}")
            return False

    def write_card_data(self, offset: int, data: bytes) -> int:
        if not self.status.connected or self.status.device_handle <= 0:
            return IC_ERR_NO_CARD
        if not self.status.card_type:
            return IC_ERR_NO_CARD

        handle = self.status.device_handle
        card_type = self.status.card_type

        try:
            if card_type in (CardType.AT24C01A, CardType.AT24C02, CardType.AT24C04,
                             CardType.AT24C08, CardType.AT24C16, CardType.AT24C32,
                             CardType.AT24C64):
                size_map = {
                    CardType.AT24C01A: '01a', CardType.AT24C02: '02',
                    CardType.AT24C04: '04', CardType.AT24C08: '08',
                    CardType.AT24C16: '16', CardType.AT24C32: '32',
                    CardType.AT24C64: '64',
                }
                return self.mwic.swr_24c(handle, size_map.get(card_type, '16'), offset, data)

            elif card_type in (CardType.SLE4442, CardType.SLE4428, CardType.SLE4418,
                               CardType.AT88C102, CardType.AT88C1604, CardType.AT88C1608,
                               CardType.AT88SC153, CardType.AT88SC1604B):
                swr_zone_map = {
                    CardType.SLE4442: ('swr_4442', False),
                    CardType.SLE4428: ('swr_4428', False),
                    CardType.SLE4418: ('swr_4418', False),
                    CardType.AT88C102: ('swr_at88c102', True),
                    CardType.AT88C1604: ('swr_at88c1604', True),
                    CardType.AT88C1608: ('swr_at88c1608', True),
                    CardType.AT88SC153: ('swr_at88sc153', True),
                    CardType.AT88SC1604B: ('swr_at88sc1604b', True),
                }
                func_name, has_zone = swr_zone_map.get(card_type, ('', False))
                fn = getattr(self.mwic, func_name, None)
                if fn:
                    return fn(handle, 0, offset, data) if has_zone else fn(handle, offset, data)

            elif card_type in (CardType.CARD4404, CardType.CARD4406, CardType.CARD4432,
                               CardType.CARD45D041, CardType.CARD93C46, CardType.CARD93C46A,
                               CardType.CARDDVSC, CardType.CARDSSF1101):
                swr_name = {
                    CardType.CARD4404: 'swr_4404', CardType.CARD4406: 'swr_4406',
                    CardType.CARD4432: 'swr_4432', CardType.CARD45D041: 'swr_45d041',
                    CardType.CARD93C46: 'swr_93c46', CardType.CARD93C46A: 'swr_93c46a',
                    CardType.CARDDVSC: 'swr_dvsc', CardType.CARDSSF1101: 'swr_ssf1101',
                }.get(card_type, '')
                fn = getattr(self.mwic, swr_name, None)
                if fn:
                    return fn(handle, offset, data)

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
                return self.mwic.wrwpb_4428(handle, offset, data)
            elif card_type == CardType.SLE4418:
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
        try:
            if not self._last_read_data or not self._last_read_data.protection_data:
                return True

            protection_data = self._last_read_data.protection_data
            for i in range(length):
                check_offset = offset + i
                if check_offset < len(protection_data):
                    prot_byte = protection_data[check_offset]
                    if prot_byte == 0x00:
                        return False
            return True
        except Exception:
            return True

    def get_remaining_attempts(self) -> int:
        if not self.status.connected or self.status.device_handle <= 0:
            return -1
        if not self.status.card_type:
            return -1

        handle = self.status.device_handle
        card_type = self.status.card_type

        try:
            if card_type == CardType.SLE4442:
                st, counter = self.mwic.rsct_4442(handle)
                if st == IC_OK and 0 <= counter <= 3:
                    return counter
                st, data = self.mwic.rsc_4442(handle, SLE4442_SECURITY_SIZE)
                if len(data) >= 1 and data[0] != 0:
                    return bin(data[0] & 0x07).count('1')
                st, data = self.mwic.srd_4442(handle, SLE4442_MAIN_SIZE, SLE4442_SECURITY_SIZE)
                if len(data) >= 1 and data[0] != 0:
                    return bin(data[0] & 0x07).count('1')
                return 0 if len(data) >= 1 and data[0] == 0 else -1

            elif card_type == CardType.SLE4428:
                st, counter = self.mwic.rsct_4428(handle)
                if st == IC_OK and 0 <= counter <= 8:
                    return counter
                st, data = self.mwic.rsc_4428(handle, SLE4428_SECURITY_SIZE)
                if len(data) >= 1 and data[0] != 0:
                    return bin(data[0] & 0xFF).count('1')
                st, data = self.mwic.srd_4428(handle, SLE4428_MAIN_SIZE, SLE4428_SECURITY_SIZE)
                if len(data) >= 1 and data[0] != 0:
                    return bin(data[0] & 0xFF).count('1')
                return 0 if len(data) >= 1 and data[0] == 0 else -1

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

            return b''
        except Exception as e:
            print(f"读取安全存储器失败：{e}")
            return b''