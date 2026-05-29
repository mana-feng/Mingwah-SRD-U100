import ctypes
import time
import threading
import os
import sys
from typing import Optional, Tuple

from .constants import (
    IC_OK, IC_ERR, IC_ERR_NO_CARD, IC_ERR_PORT,
    PORT_USB, PORT_HID,
)
from .types import CardType, DeviceStatus


class MWIC32:

    def __init__(self):
        self.device_handle = None
        self.port_type = 0
        self.baud_rate = 9600
        self._mutex = threading.Lock()
        self._last_error = ""
        self._dll_path = self._find_dll()
        self._dll = None
        self._func_cache = {}
        if os.path.exists(self._dll_path):
            try:
                self._dll = ctypes.WinDLL(self._dll_path)
            except OSError as e:
                self._last_error = f"DLL 加载失败: {self._dll_path} ({e})"
        elif not self._last_error:
            self._last_error = f"DLL 未找到: {self._dll_path}"

    def _find_dll(self) -> str:
        if getattr(sys, 'frozen', False):
            candidates = []
            try:
                meipass_dir = sys._MEIPASS
                candidates.append(os.path.join(meipass_dir, 'Mwic_32.dll'))
            except Exception:
                pass
            base_dir = os.path.dirname(sys.executable)
            candidates.append(os.path.join(base_dir, 'Mwic_32.dll'))
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            candidates = [
                os.path.join(base_dir, 'Mwic_32.dll'),
                os.path.join(os.path.dirname(base_dir), 'Mwic_32.dll'),
            ]
        for path in candidates:
            if os.path.exists(path):
                return path
        self._last_error = f"DLL 未找到，已搜索路径: {candidates}"
        print(self._last_error)
        return candidates[0] if candidates else ""

    def _get_dll_func(self, name):
        if name not in self._func_cache:
            func = getattr(self._dll, name)
            if name == 'ic_init':
                func.restype = ctypes.c_long
                func.argtypes = [ctypes.c_int16, ctypes.c_ulong]
            elif name == 'ic_exit':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long]
            elif name == 'dv_beep':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16]
            elif name in ('get_status', 'get_status0'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.POINTER(ctypes.c_int16)]
            elif name == 'chk_card':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long]
            elif name == 'srd_ver':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p]
            elif name == 'srd_snr':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p]
            elif name == 'chk_baud':
                func.restype = ctypes.c_int32
                func.argtypes = [ctypes.c_int16]
            elif name == 'auto_chk':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long]
            elif name == 'auto_pull':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long]
            elif name == 'exp_dis':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int16)]
            elif name.startswith('chk_'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long]
            elif name.startswith('srd_24c') or name.startswith('srd_93c'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_int16, ctypes.c_char_p]
            elif name.startswith('swr_24c') or name.startswith('swr_93c'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_int16, ctypes.c_char_p]
            elif name == 'prd_4442':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p]
            elif name == 'pwr_4442':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_int16, ctypes.c_char_p]
            elif name.startswith('rdwpb_44') or name.startswith('wrwpb_44'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_int16, ctypes.c_char_p]
            elif name.startswith('rsc_44') or name.startswith('wsc_44') or name.startswith('csc_44'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p]
            elif name.startswith('rsct_44'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.POINTER(ctypes.c_int16)]
            elif name.startswith('srd_10') or name.startswith('srd_15') or name.startswith('srd_16'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_int16, ctypes.c_int16, ctypes.c_char_p]
            elif name.startswith('swr_10') or name.startswith('swr_15') or name.startswith('swr_16'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_int16, ctypes.c_int16, ctypes.c_char_p]
            elif name.startswith('srd_44'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_int16, ctypes.c_char_p]
            elif name.startswith('swr_44'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_int16, ctypes.c_char_p]
            elif name.startswith('srd_45d041') or name.startswith('srd_dvsc') or name.startswith('srd_ssf1101'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_int16, ctypes.c_char_p]
            elif name.startswith('swr_45d041') or name.startswith('swr_dvsc') or name.startswith('swr_ssf1101'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_int16, ctypes.c_char_p]
            elif name.startswith('srd_s50') or name.startswith('srd_s70'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p, ctypes.c_int16, ctypes.c_char_p]
            elif name.startswith('swr_s50') or name.startswith('swr_s70'):
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int16]
            elif name == 'cpu_reset':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p]
            elif name == 'cpu_comres':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p, ctypes.c_char_p]
            elif name == 'cpu_protocol':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16]
            elif name == 'ic_encrypt':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p, ctypes.c_int16, ctypes.c_char_p]
            elif name == 'ic_decrypt':
                func.restype = ctypes.c_int16
                func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p, ctypes.c_int16, ctypes.c_char_p]
            self._func_cache[name] = func
        return self._func_cache[name]

    def _call_dll(self, func_name: str, args: list = None) -> dict:
        if args is None:
            args = []

        if self._dll is None:
            return {"error": self._last_error}

        with self._mutex:
            try:
                func = self._get_dll_func(func_name)

                if func_name == 'ic_init':
                    result = func(args[0], args[1])
                    return {"result": result}

                elif func_name == 'ic_exit':
                    result = func(args[0])
                    return {"result": result}

                elif func_name == 'dv_beep':
                    result = func(args[0], args[1])
                    return {"result": result}

                elif func_name in ('get_status', 'get_status0'):
                    status = ctypes.c_int16()
                    result = func(args[0], ctypes.byref(status))
                    return {"result": result, "status": status.value}

                elif func_name == 'chk_card':
                    result = func(args[0])
                    return {"result": result}

                elif func_name == 'srd_ver':
                    length = args[1] if len(args) > 1 else 18
                    buf = ctypes.create_string_buffer(length + 1)
                    result = func(args[0], length, buf)
                    return {"result": result, "data": buf.value.decode('ascii', errors='replace')}

                elif func_name == 'srd_snr':
                    length = args[1] if len(args) > 1 else 16
                    buf = ctypes.create_string_buffer(length + 1)
                    result = func(args[0], length, buf)
                    return {"result": result, "data": buf.raw[:length].hex()}

                elif func_name == 'chk_baud':
                    result = func(args[0])
                    return {"result": result}

                elif func_name == 'auto_chk':
                    result = func(args[0])
                    return {"result": result}

                elif func_name == 'auto_pull':
                    result = func(args[0])
                    return {"result": result}

                elif func_name == 'exp_dis':
                    card_type = ctypes.c_int16()
                    filename = args[1].encode('ascii', errors='replace') if len(args) > 1 and args[1] else b''
                    result = func(args[0], filename, ctypes.byref(card_type))
                    return {"result": result, "card_type": card_type.value}

                elif func_name.startswith('chk_'):
                    result = func(args[0])
                    return {"result": result}

                elif func_name.startswith('srd_24c') or func_name.startswith('srd_93c'):
                    offset = args[1] if len(args) > 1 else 0
                    length = args[2] if len(args) > 2 else 32
                    buf = ctypes.create_string_buffer(length)
                    result = func(args[0], offset, length, buf)
                    return {"result": result, "data": buf.raw[:length].hex()}

                elif func_name.startswith('swr_24c') or func_name.startswith('swr_93c'):
                    offset = args[1] if len(args) > 1 else 0
                    data_hex = args[2] if len(args) > 2 else ''
                    data_bytes = bytes.fromhex(data_hex)
                    length = len(data_bytes)
                    buf = ctypes.create_string_buffer(data_bytes, length)
                    result = func(args[0], offset, length, buf)
                    return {"result": result}

                elif func_name == 'prd_4442':
                    length = args[1] if len(args) > 1 else 32
                    buf = ctypes.create_string_buffer(length)
                    result = func(args[0], length, buf)
                    return {"result": result, "data": buf.raw[:length].hex()}

                elif func_name == 'pwr_4442':
                    offset = args[1] if len(args) > 1 else 0
                    data_hex = args[2] if len(args) > 2 else ''
                    data_bytes = bytes.fromhex(data_hex)
                    length = len(data_bytes)
                    buf = ctypes.create_string_buffer(data_bytes, length)
                    result = func(args[0], offset, length, buf)
                    return {"result": result}

                elif func_name.startswith('rdwpb_44'):
                    offset = args[1] if len(args) > 1 else 0
                    length = args[2] if len(args) > 2 else 32
                    buf = ctypes.create_string_buffer(length)
                    result = func(args[0], offset, length, buf)
                    return {"result": result, "data": buf.raw[:length].hex()}

                elif func_name.startswith('wrwpb_44'):
                    offset = args[1] if len(args) > 1 else 0
                    data_hex = args[2] if len(args) > 2 else ''
                    data_bytes = bytes.fromhex(data_hex)
                    length = len(data_bytes)
                    buf = ctypes.create_string_buffer(data_bytes, length)
                    result = func(args[0], offset, length, buf)
                    return {"result": result}

                elif func_name.startswith('rsc_44'):
                    length = args[1] if len(args) > 1 else 4
                    buf = ctypes.create_string_buffer(length)
                    result = func(args[0], length, buf)
                    return {"result": result, "data": buf.raw[:length].hex()}

                elif func_name.startswith('wsc_44'):
                    length = args[1] if len(args) > 1 else 0
                    data_hex = args[2] if len(args) > 2 else ''
                    if not data_hex or length == 0:
                        return {"result": -1, "error": "wsc_44: invalid params"}
                    data_bytes = bytes.fromhex(data_hex)
                    if len(data_bytes) != length:
                        return {"result": -1, "error": f"wsc_44: length mismatch, expected {length}, got {len(data_bytes)}"}
                    buf = ctypes.create_string_buffer(data_bytes, length)
                    result = func(args[0], length, buf)
                    return {"result": result}

                elif func_name.startswith('csc_44'):
                    length = args[1] if len(args) > 1 else 3
                    psc_hex = args[2] if len(args) > 2 else ''
                    if not psc_hex:
                        return {"result": -1, "error": "csc_44: PSC data empty"}
                    psc_bytes = bytes.fromhex(psc_hex)
                    if len(psc_bytes) != length:
                        print(f"[WARNING] csc_44: PSC length mismatch, expected {length}, got {len(psc_bytes)}")
                    psc_buf = ctypes.create_string_buffer(max(length, len(psc_bytes)))
                    ctypes.memmove(psc_buf, psc_bytes, len(psc_bytes))
                    result = func(args[0], length, psc_buf)
                    return {"result": result}

                elif func_name.startswith('srd_10') or func_name.startswith('srd_15') or func_name.startswith('srd_16'):
                    zone = args[1] if len(args) > 1 else 0
                    offset = args[2] if len(args) > 2 else 0
                    length = args[3] if len(args) > 3 else 32
                    buf = ctypes.create_string_buffer(length)
                    result = func(args[0], zone, offset, length, buf)
                    return {"result": result, "data": buf.raw[:length].hex()}

                elif func_name.startswith('swr_10') or func_name.startswith('swr_15') or func_name.startswith('swr_16'):
                    zone = args[1] if len(args) > 1 else 0
                    offset = args[2] if len(args) > 2 else 0
                    data_hex = args[3] if len(args) > 3 else ''
                    data_bytes = bytes.fromhex(data_hex)
                    length = len(data_bytes)
                    buf = ctypes.create_string_buffer(data_bytes, length)
                    result = func(args[0], zone, offset, length, buf)
                    return {"result": result}

                elif func_name.startswith('srd_44'):
                    offset = args[1] if len(args) > 1 else 0
                    length = args[2] if len(args) > 2 else 32
                    buf = ctypes.create_string_buffer(length)
                    result = func(args[0], offset, length, buf)
                    return {"result": result, "data": buf.raw[:length].hex()}

                elif func_name.startswith('swr_44'):
                    offset = args[1] if len(args) > 1 else 0
                    data_hex = args[2] if len(args) > 2 else ''
                    data_bytes = bytes.fromhex(data_hex)
                    length = len(data_bytes)
                    buf = ctypes.create_string_buffer(data_bytes, length)
                    result = func(args[0], offset, length, buf)
                    return {"result": result}

                elif func_name.startswith('srd_45d041') or func_name.startswith('srd_dvsc') or func_name.startswith('srd_ssf1101'):
                    offset = args[1] if len(args) > 1 else 0
                    length = args[2] if len(args) > 2 else 32
                    buf = ctypes.create_string_buffer(length)
                    result = func(args[0], offset, length, buf)
                    return {"result": result, "data": buf.raw[:length].hex()}

                elif func_name.startswith('swr_45d041') or func_name.startswith('swr_dvsc') or func_name.startswith('swr_ssf1101'):
                    offset = args[1] if len(args) > 1 else 0
                    data_hex = args[2] if len(args) > 2 else ''
                    data_bytes = bytes.fromhex(data_hex)
                    length = len(data_bytes)
                    buf = ctypes.create_string_buffer(data_bytes, length)
                    result = func(args[0], offset, length, buf)
                    return {"result": result}

                elif func_name.startswith('rsct_44'):
                    counter = ctypes.c_int16(0)
                    result = func(args[0], ctypes.byref(counter))
                    return {"result": result, "counter": counter.value}

                elif func_name.startswith('srd_s50') or func_name.startswith('srd_s70'):
                    sector = args[1] if len(args) > 1 else 0
                    key_hex = args[2] if len(args) > 2 else 'FFFFFFFFFFFF'
                    key_type = args[3] if len(args) > 3 else 0x60
                    key_bytes = bytes.fromhex(key_hex)
                    key_buf = ctypes.create_string_buffer(key_bytes, 6)
                    data_buf = ctypes.create_string_buffer(48)
                    result = func(args[0], sector, key_buf, key_type, data_buf)
                    return {"result": result, "data": data_buf.raw[:48].hex()}

                elif func_name.startswith('swr_s50') or func_name.startswith('swr_s70'):
                    sector = args[1] if len(args) > 1 else 0
                    key_hex = args[2] if len(args) > 2 else 'FFFFFFFFFFFF'
                    data_hex = args[3] if len(args) > 3 else ''
                    key_type = args[4] if len(args) > 4 else 0x60
                    key_bytes = bytes.fromhex(key_hex)
                    key_buf = ctypes.create_string_buffer(key_bytes, 6)
                    data_bytes = bytes.fromhex(data_hex) if data_hex else b''
                    data_buf = ctypes.create_string_buffer(data_bytes, len(data_bytes)) if data_bytes else None
                    if data_buf:
                        result = func(args[0], sector, key_buf, data_buf, key_type)
                    else:
                        result = -1
                    return {"result": result}

                elif func_name == 'cpu_reset':
                    length = args[1] if len(args) > 1 else 64
                    buf = ctypes.create_string_buffer(length)
                    result = func(args[0], length, buf)
                    return {"result": result, "data": buf.raw[:length].hex()}

                elif func_name == 'cpu_comres':
                    cmd_hex = args[1] if len(args) > 1 else ''
                    cmd_bytes = bytes.fromhex(cmd_hex)
                    cmd_buf = ctypes.create_string_buffer(cmd_bytes, len(cmd_bytes))
                    resp_buf = ctypes.create_string_buffer(256)
                    result = func(args[0], len(cmd_bytes), cmd_buf, resp_buf)
                    return {"result": result, "data": resp_buf.raw[:256].hex()}

                elif func_name == 'cpu_protocol':
                    protocol = args[1] if len(args) > 1 else 0
                    result = func(args[0], protocol)
                    return {"result": result}

                elif func_name == 'ic_encrypt':
                    key_type = args[1] if len(args) > 1 else 0
                    data_hex = args[2] if len(args) > 2 else ''
                    data_bytes = bytes.fromhex(data_hex)
                    length = len(data_bytes)
                    in_buf = ctypes.create_string_buffer(data_bytes, length)
                    out_buf = ctypes.create_string_buffer(length)
                    result = func(args[0], key_type, in_buf, length, out_buf)
                    return {"result": result, "data": out_buf.raw[:length].hex()}

                elif func_name == 'ic_decrypt':
                    key_type = args[1] if len(args) > 1 else 0
                    data_hex = args[2] if len(args) > 2 else ''
                    data_bytes = bytes.fromhex(data_hex)
                    length = len(data_bytes)
                    in_buf = ctypes.create_string_buffer(data_bytes, length)
                    out_buf = ctypes.create_string_buffer(length)
                    result = func(args[0], key_type, in_buf, length, out_buf)
                    return {"result": result, "data": out_buf.raw[:length].hex()}

                else:
                    return {"error": f"unknown function: {func_name}"}

            except Exception as e:
                return {"error": str(e)}

    def ic_usbinit(self) -> int:
        result = self._call_dll('ic_init', [PORT_USB, 0])
        if 'error' in result:
            print(f"ic_usbinit 错误: {result['error']}")
            return IC_ERR_PORT
        handle = result.get('result', -1)
        if handle > 0:
            self.device_handle = handle
            self.port_type = PORT_USB
        return handle

    def ic_init(self, port_type: int, baud_rate: int) -> int:
        result = self._call_dll('ic_init', [port_type, baud_rate])
        if 'error' in result:
            print(f"ic_init 错误: {result['error']}")
            return IC_ERR_PORT
        handle = result.get('result', -1)
        if handle > 0:
            self.device_handle = handle
            self.port_type = port_type
            self.baud_rate = baud_rate
        return handle

    def ic_exit(self, handle: int) -> int:
        result = self._call_dll('ic_exit', [handle])
        self.device_handle = None
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def dv_beep(self, handle: int, duration: int) -> int:
        result = self._call_dll('dv_beep', [handle, duration])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def get_status(self, handle: int) -> Tuple[int, int]:
        result = self._call_dll('get_status', [handle])
        if 'error' in result:
            return IC_ERR, 0
        return result.get('result', IC_ERR), result.get('status', 0)

    def chk_card(self, handle: int) -> int:
        result = self._call_dll('chk_card', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def srd_ver(self, handle: int, length: int = 18) -> Tuple[int, str]:
        result = self._call_dll('srd_ver', [handle, length])
        if 'error' in result:
            return IC_ERR, ""
        return result.get('result', IC_ERR), result.get('data', '')

    def srd_snr(self, handle: int, length: int = 16) -> Tuple[int, str]:
        result = self._call_dll('srd_snr', [handle, length])
        if 'error' in result:
            return IC_ERR, ""
        return result.get('result', IC_ERR), result.get('data', '')

    def chk_baud(self, port: int) -> int:
        result = self._call_dll('chk_baud', [port])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def auto_chk(self, handle: int) -> int:
        result = self._call_dll('auto_chk', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def auto_pull(self, handle: int) -> int:
        result = self._call_dll('auto_pull', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def exp_dis(self, handle: int, filename: str = '') -> Tuple[int, int]:
        result = self._call_dll('exp_dis', [handle, filename])
        if 'error' in result:
            return IC_ERR, 0
        return result.get('result', IC_ERR), result.get('card_type', 0)

    def chk_at88c102(self, handle: int) -> int:
        return IC_ERR if 'error' in (r := self._call_dll('chk_102', [handle])) else r.get('result', IC_ERR)

    def chk_at88c1604(self, handle: int) -> int:
        return IC_ERR if 'error' in (r := self._call_dll('chk_1604', [handle])) else r.get('result', IC_ERR)

    def chk_at88sc153(self, handle: int) -> int:
        return IC_ERR if 'error' in (r := self._call_dll('chk_153', [handle])) else r.get('result', IC_ERR)

    def chk_at88sc1604b(self, handle: int) -> int:
        return IC_ERR if 'error' in (r := self._call_dll('chk_1604b', [handle])) else r.get('result', IC_ERR)

    def prd_4442(self, handle: int, length: int) -> Tuple[int, bytes]:
        result = self._call_dll('prd_4442', [handle, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def pwr_4442(self, handle: int, offset: int, data: bytes) -> int:
        result = self._call_dll('pwr_4442', [handle, offset, data.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def rdwpb_4442(self, handle: int, offset: int, length: int) -> Tuple[int, bytes]:
        result = self._call_dll('rdwpb_4442', [handle, offset, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def wrwpb_4442(self, handle: int, offset: int, data: bytes) -> int:
        result = self._call_dll('wrwpb_4442', [handle, offset, data.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def rsc_4442(self, handle: int, length: int = 4) -> Tuple[int, bytes]:
        result = self._call_dll('rsc_4442', [handle, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def wsc_4442(self, handle: int, data: bytes) -> int:
        print(f"[DEBUG] wsc_4442 调用: handle={handle}, len={len(data)}, data={data.hex().upper()}")
        result = self._call_dll('wsc_4442', [handle, len(data), data.hex()])
        print(f"[DEBUG] wsc_4442 返回: {result}")
        if 'error' in result:
            print(f"[ERROR] wsc_4442 错误: {result['error']}")
            return IC_ERR
        return result.get('result', IC_ERR)

    def csc_4442(self, handle: int, length: int, psc: bytes) -> int:
        result = self._call_dll('csc_4442', [handle, length, psc.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def rsct_4442(self, handle: int) -> Tuple[int, int]:
        result = self._call_dll('rsct_4442', [handle])
        if 'error' in result:
            return IC_ERR, -1
        return result.get('result', IC_ERR), result.get('counter', -1)

    def rdwpb_4428(self, handle: int, offset: int, length: int) -> Tuple[int, bytes]:
        result = self._call_dll('rdwpb_4428', [handle, offset, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def wrwpb_4428(self, handle: int, offset: int, data: bytes) -> int:
        result = self._call_dll('wrwpb_4428', [handle, offset, data.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def rsc_4428(self, handle: int, length: int = 2) -> Tuple[int, bytes]:
        result = self._call_dll('rsc_4428', [handle, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def wsc_4428(self, handle: int, data: bytes) -> int:
        print(f"[DEBUG] wsc_4428 调用: handle={handle}, len={len(data)}, data={data.hex().upper()}")
        result = self._call_dll('wsc_4428', [handle, len(data), data.hex()])
        print(f"[DEBUG] wsc_4428 返回: {result}")
        if 'error' in result:
            print(f"[ERROR] wsc_4428 错误: {result['error']}")
            return IC_ERR
        return result.get('result', IC_ERR)

    def csc_4428(self, handle: int, length: int, psc: bytes) -> int:
        result = self._call_dll('csc_4428', [handle, length, psc.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def rsct_4428(self, handle: int) -> Tuple[int, int]:
        result = self._call_dll('rsct_4428', [handle])
        if 'error' in result:
            return IC_ERR, -1
        return result.get('result', IC_ERR), result.get('counter', -1)

    def rdwpb_4418(self, handle: int, offset: int, length: int) -> Tuple[int, bytes]:
        result = self._call_dll('rdwpb_4418', [handle, offset, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def wrwpb_4418(self, handle: int, offset: int, data: bytes) -> int:
        result = self._call_dll('wrwpb_4418', [handle, offset, data.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def srd_24c(self, handle: int, size: str, offset: int, length: int) -> Tuple[int, bytes]:
        func_name = f'srd_24c{size}'
        result = self._call_dll(func_name, [handle, offset, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def swr_24c(self, handle: int, size: str, offset: int, data: bytes) -> int:
        func_name = f'swr_24c{size}'
        result = self._call_dll(func_name, [handle, offset, data.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def srd_at88c102(self, handle: int, zone: int, offset: int, length: int) -> Tuple[int, bytes]:
        result = self._call_dll('srd_102', [handle, zone, offset, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def swr_at88c102(self, handle: int, zone: int, offset: int, data: bytes) -> int:
        result = self._call_dll('swr_102', [handle, zone, offset, data.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def srd_at88c1604(self, handle: int, zone: int, offset: int, length: int) -> Tuple[int, bytes]:
        result = self._call_dll('srd_1604', [handle, zone, offset, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def swr_at88c1604(self, handle: int, zone: int, offset: int, data: bytes) -> int:
        result = self._call_dll('swr_1604', [handle, zone, offset, data.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def srd_at88sc153(self, handle: int, zone: int, offset: int, length: int) -> Tuple[int, bytes]:
        result = self._call_dll('srd_153', [handle, zone, offset, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def swr_at88sc153(self, handle: int, zone: int, offset: int, data: bytes) -> int:
        result = self._call_dll('swr_153', [handle, zone, offset, data.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def srd_at88sc1604b(self, handle: int, zone: int, offset: int, length: int) -> Tuple[int, bytes]:
        result = self._call_dll('srd_1604b', [handle, zone, offset, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def swr_at88sc1604b(self, handle: int, zone: int, offset: int, data: bytes) -> int:
        result = self._call_dll('swr_1604b', [handle, zone, offset, data.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def srd_at88c1608(self, handle: int, zone: int, offset: int, length: int) -> Tuple[int, bytes]:
        result = self._call_dll('srd_1608', [handle, zone, offset, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def swr_at88c1608(self, handle: int, zone: int, offset: int, data: bytes) -> int:
        result = self._call_dll('swr_1608', [handle, zone, offset, data.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def __getattr__(self, name):
        if name.startswith('chk_') and not hasattr(type(self), name):
            def _chk(handle):
                result = self._call_dll(name, [handle])
                if 'error' in result:
                    return IC_ERR
                return result.get('result', IC_ERR)
            return _chk
        if name.startswith('srd_') and not hasattr(type(self), name):
            def _srd(handle, offset, length):
                result = self._call_dll(name, [handle, offset, length])
                if 'error' in result:
                    return IC_ERR, b''
                data_hex = result.get('data', '')
                return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''
            return _srd
        if name.startswith('swr_') and not hasattr(type(self), name):
            def _swr(handle, offset, data):
                result = self._call_dll(name, [handle, offset, data.hex()])
                if 'error' in result:
                    return IC_ERR
                return result.get('result', IC_ERR)
            return _swr
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def srd_s50(self, handle: int, sector: int, key: bytes, key_type: int = 0x60) -> Tuple[int, bytes]:
        result = self._call_dll('srd_s50', [handle, sector, key.hex(), key_type])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def swr_s50(self, handle: int, sector: int, key: bytes, data: bytes, key_type: int = 0x60) -> int:
        result = self._call_dll('swr_s50', [handle, sector, key.hex(), data.hex(), key_type])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def srd_s70(self, handle: int, sector: int, key: bytes, key_type: int = 0x60) -> Tuple[int, bytes]:
        result = self._call_dll('srd_s70', [handle, sector, key.hex(), key_type])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def swr_s70(self, handle: int, sector: int, key: bytes, data: bytes, key_type: int = 0x60) -> int:
        result = self._call_dll('swr_s70', [handle, sector, key.hex(), data.hex(), key_type])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def cpu_reset(self, handle: int, length: int = 64) -> Tuple[int, bytes]:
        result = self._call_dll('cpu_reset', [handle, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def cpu_comres(self, handle: int, cmd: bytes) -> Tuple[int, bytes]:
        result = self._call_dll('cpu_comres', [handle, cmd.hex()])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def cpu_protocol(self, handle: int, protocol: int = 0) -> int:
        result = self._call_dll('cpu_protocol', [handle, protocol])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def ic_encrypt(self, handle: int, key_type: int, data: bytes) -> Tuple[int, bytes]:
        result = self._call_dll('ic_encrypt', [handle, key_type, data.hex()])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def ic_decrypt(self, handle: int, key_type: int, data: bytes) -> Tuple[int, bytes]:
        result = self._call_dll('ic_decrypt', [handle, key_type, data.hex()])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''