import ctypes
import struct
import time
import threading
import subprocess
import json
import os
import sys
from typing import Optional, Tuple

from .constants import (
    IC_OK, IC_ERR, IC_ERR_NO_CARD, IC_ERR_PORT,
    PORT_USB, PORT_HID,
)
from .types import CardType, DeviceStatus


def _is_32bit_python():
    return struct.calcsize("P") == 4


class _DirectDLLCaller:

    def __init__(self, dll_path: str):
        self._dll = ctypes.WinDLL(dll_path)
        self._func_cache = {}
        self._setup_funcs()

    def _setup_funcs(self):
        self._dll.ic_init.restype = ctypes.c_long
        self._dll.ic_init.argtypes = [ctypes.c_int16, ctypes.c_ulong]

        self._dll.ic_exit.restype = ctypes.c_int16
        self._dll.ic_exit.argtypes = [ctypes.c_long]

        self._dll.dv_beep.restype = ctypes.c_int16
        self._dll.dv_beep.argtypes = [ctypes.c_long, ctypes.c_int16]

    def _get_func(self, name: str):
        if name in self._func_cache:
            return self._func_cache[name]
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
        elif name.startswith('srd_s50') or name.startswith('srd_s70'):
            func.restype = ctypes.c_int16
            func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p, ctypes.c_int16, ctypes.c_char_p]
        elif name.startswith('swr_s50') or name.startswith('swr_s70'):
            func.restype = ctypes.c_int16
            func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int16]
        elif name == 'cpu_reset':
            func.restype = ctypes.c_int16
            func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p]
        elif name == 'cpu_apdu':
            func.restype = ctypes.c_int16
            func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p, ctypes.c_char_p]
        self._func_cache[name] = func
        return func

    def call(self, name: str, args: list) -> dict:
        try:
            func = self._get_func(name)
            if name == 'ic_init':
                result = func(args[0], args[1])
                return {"result": result}
            elif name == 'ic_exit':
                result = func(args[0])
                return {"result": result}
            elif name == 'dv_beep':
                result = func(args[0], args[1])
                return {"result": result}
            elif name in ('get_status', 'get_status0'):
                status = ctypes.c_int16()
                result = func(args[0], ctypes.byref(status))
                return {"result": result, "status": status.value}
            elif name == 'chk_card':
                result = func(args[0])
                return {"result": result}
            elif name == 'srd_ver':
                length = args[1] if len(args) > 1 else 18
                buf = ctypes.create_string_buffer(length + 1)
                result = func(args[0], length, buf)
                return {"result": result, "data": buf.value.decode('ascii', errors='replace')}
            elif name == 'srd_snr':
                length = args[1] if len(args) > 1 else 16
                buf = ctypes.create_string_buffer(length + 1)
                result = func(args[0], length, buf)
                return {"result": result, "data": buf.raw[:length].hex()}
            elif name == 'chk_baud':
                result = func(args[0])
                return {"result": result}
            elif name == 'auto_chk':
                result = func(args[0])
                return {"result": result}
            elif name == 'auto_pull':
                result = func(args[0])
                return {"result": result}
            elif name == 'exp_dis':
                card_type = ctypes.c_int16()
                filename = args[1].encode('ascii', errors='replace') if len(args) > 1 and args[1] else b''
                result = func(args[0], filename, ctypes.byref(card_type))
                return {"result": result, "card_type": card_type.value}
            elif name.startswith('chk_'):
                result = func(args[0])
                return {"result": result}
            elif name.startswith('srd_24c') or name.startswith('srd_93c'):
                offset = args[1] if len(args) > 1 else 0
                length = args[2] if len(args) > 2 else 32
                buf = ctypes.create_string_buffer(length)
                result = func(args[0], offset, length, buf)
                return {"result": result, "data": buf.raw[:length].hex()}
            elif name.startswith('swr_24c') or name.startswith('swr_93c'):
                offset = args[1] if len(args) > 1 else 0
                data_hex = args[2] if len(args) > 2 else ''
                data_bytes = bytes.fromhex(data_hex)
                length = len(data_bytes)
                buf = ctypes.create_string_buffer(data_bytes, length)
                result = func(args[0], offset, length, buf)
                return {"result": result}
            elif name == 'prd_4442':
                length = args[1] if len(args) > 1 else 32
                buf = ctypes.create_string_buffer(length)
                result = func(args[0], length, buf)
                return {"result": result, "data": buf.raw[:length].hex()}
            elif name == 'pwr_4442':
                offset = args[1] if len(args) > 1 else 0
                data_hex = args[2] if len(args) > 2 else ''
                data_bytes = bytes.fromhex(data_hex)
                length = len(data_bytes)
                buf = ctypes.create_string_buffer(data_bytes, length)
                result = func(args[0], offset, length, buf)
                return {"result": result}
            elif name.startswith('rdwpb_44'):
                offset = args[1] if len(args) > 1 else 0
                length = args[2] if len(args) > 2 else 32
                buf = ctypes.create_string_buffer(length)
                result = func(args[0], offset, length, buf)
                return {"result": result, "data": buf.raw[:length].hex()}
            elif name.startswith('wrwpb_44'):
                offset = args[1] if len(args) > 1 else 0
                data_hex = args[2] if len(args) > 2 else ''
                data_bytes = bytes.fromhex(data_hex)
                length = len(data_bytes)
                buf = ctypes.create_string_buffer(data_bytes, length)
                result = func(args[0], offset, length, buf)
                return {"result": result}
            elif name.startswith('rsc_44'):
                length = args[1] if len(args) > 1 else 4
                buf = ctypes.create_string_buffer(length)
                result = func(args[0], length, buf)
                return {"result": result, "data": buf.raw[:length].hex()}
            elif name.startswith('wsc_44'):
                # wsc_4442/wsc_4428: (handle, length, data_hex)
                length = args[1] if len(args) > 1 else 0
                data_hex = args[2] if len(args) > 2 else ''
                if not data_hex or length == 0:
                    return {"result": -1, "error": "wsc_44: 参数错误"}
                data_bytes = bytes.fromhex(data_hex)
                if len(data_bytes) != length:
                    return {"result": -1, "error": f"wsc_44: 数据长度不匹配，期望{length}，实际{len(data_bytes)}"}
                buf = ctypes.create_string_buffer(data_bytes, length)
                result = func(args[0], length, buf)
                return {"result": result}
            elif name.startswith('csc_44'):
                # csc_4442/csc_4428: (handle, length, psc_hex)
                length = args[1] if len(args) > 1 else 3
                psc_hex = args[2] if len(args) > 2 else ''
                if not psc_hex:
                    return {"result": -1, "error": "csc_44: PSC数据不能为空"}
                psc_bytes = bytes.fromhex(psc_hex)
                if len(psc_bytes) != length:
                    print(f"[WARNING] csc_44: PSC数据长度不匹配，期望{length}，实际{len(psc_bytes)}")
                psc_buf = ctypes.create_string_buffer(max(length, len(psc_bytes)))
                ctypes.memmove(psc_buf, psc_bytes, len(psc_bytes))
                result = func(args[0], length, psc_buf)
                return {"result": result}
            elif name.startswith('srd_10') or name.startswith('srd_15') or name.startswith('srd_16'):
                zone = args[1] if len(args) > 1 else 0
                offset = args[2] if len(args) > 2 else 0
                length = args[3] if len(args) > 3 else 32
                buf = ctypes.create_string_buffer(length)
                result = func(args[0], zone, offset, length, buf)
                return {"result": result, "data": buf.raw[:length].hex()}
            elif name.startswith('swr_10') or name.startswith('swr_15') or name.startswith('swr_16'):
                zone = args[1] if len(args) > 1 else 0
                offset = args[2] if len(args) > 2 else 0
                data_hex = args[3] if len(args) > 3 else ''
                data_bytes = bytes.fromhex(data_hex)
                length = len(data_bytes)
                buf = ctypes.create_string_buffer(data_bytes, length)
                result = func(args[0], zone, offset, length, buf)
                return {"result": result}
            elif name.startswith('srd_44'):
                offset = args[1] if len(args) > 1 else 0
                length = args[2] if len(args) > 2 else 32
                buf = ctypes.create_string_buffer(length)
                result = func(args[0], offset, length, buf)
                return {"result": result, "data": buf.raw[:length].hex()}
            elif name.startswith('swr_44'):
                offset = args[1] if len(args) > 1 else 0
                data_hex = args[2] if len(args) > 2 else ''
                data_bytes = bytes.fromhex(data_hex)
                length = len(data_bytes)
                buf = ctypes.create_string_buffer(data_bytes, length)
                result = func(args[0], offset, length, buf)
                return {"result": result}
            elif name.startswith('rsct_44'):
                counter = ctypes.c_int16(0)
                result = func(args[0], ctypes.byref(counter))
                return {"result": result, "counter": counter.value}
            elif name.startswith('srd_s50') or name.startswith('srd_s70'):
                sector = args[1] if len(args) > 1 else 0
                key_hex = args[2] if len(args) > 2 else 'FFFFFFFFFFFF'
                key_type = args[3] if len(args) > 3 else 0x60
                key_bytes = bytes.fromhex(key_hex)
                key_buf = ctypes.create_string_buffer(key_bytes, 6)
                data_buf = ctypes.create_string_buffer(48)
                result = func(args[0], sector, key_buf, key_type, data_buf)
                return {"result": result, "data": data_buf.raw[:48].hex()}
            elif name.startswith('swr_s50') or name.startswith('swr_s70'):
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
            elif name == 'cpu_reset':
                length = args[1] if len(args) > 1 else 64
                buf = ctypes.create_string_buffer(length)
                result = func(args[0], length, buf)
                return {"result": result, "data": buf.raw[:length].hex()}
            elif name == 'cpu_apdu':
                apdu_hex = args[1] if len(args) > 1 else ''
                apdu_bytes = bytes.fromhex(apdu_hex)
                apdu_buf = ctypes.create_string_buffer(apdu_bytes, len(apdu_bytes))
                resp_buf = ctypes.create_string_buffer(256)
                result = func(args[0], len(apdu_bytes), apdu_buf, resp_buf)
                return {"result": result, "data": resp_buf.raw[:64].hex()}
            elif name.startswith('chk_'):
                result = func(args[0])
                return {"result": result}
            else:
                return {"error": f"未知函数: {name}"}
        except Exception as e:
            return {"error": str(e)}


class MWIC32:

    _BRIDGE_SCRIPT = r'''
import ctypes
import json
import sys
import os

dll_path = r'{dll_path}'
try:
    dll = ctypes.WinDLL(dll_path)
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
    sys.exit(1)

_func_cache = {{}}

def get_func(name):
    if name not in _func_cache:
        func = getattr(dll, name)
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
        elif name.startswith('srd_s50') or name.startswith('srd_s70'):
            func.restype = ctypes.c_int16
            func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p, ctypes.c_int16, ctypes.c_char_p]
        elif name.startswith('swr_s50') or name.startswith('swr_s70'):
            func.restype = ctypes.c_int16
            func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int16]
        elif name == 'cpu_reset':
            func.restype = ctypes.c_int16
            func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p]
        elif name == 'cpu_apdu':
            func.restype = ctypes.c_int16
            func.argtypes = [ctypes.c_long, ctypes.c_int16, ctypes.c_char_p, ctypes.c_char_p]
        _func_cache[name] = func
    return _func_cache[name]

def call_func(name, args):
    try:
        func = get_func(name)
        if name == 'ic_init':
            result = func(args[0], args[1])
            return {{"result": result}}
        elif name == 'ic_exit':
            result = func(args[0])
            return {{"result": result}}
        elif name == 'dv_beep':
            result = func(args[0], args[1])
            return {{"result": result}}
        elif name in ('get_status', 'get_status0'):
            status = ctypes.c_int16()
            result = func(args[0], ctypes.byref(status))
            return {{"result": result, "status": status.value}}
        elif name == 'chk_card':
            result = func(args[0])
            return {{"result": result}}
        elif name == 'srd_ver':
            length = args[1] if len(args) > 1 else 18
            buf = ctypes.create_string_buffer(length + 1)
            result = func(args[0], length, buf)
            return {{"result": result, "data": buf.value.decode('ascii', errors='replace')}}
        elif name == 'srd_snr':
            length = args[1] if len(args) > 1 else 16
            buf = ctypes.create_string_buffer(length + 1)
            result = func(args[0], length, buf)
            return {{"result": result, "data": buf.raw[:length].hex()}}
        elif name == 'chk_baud':
            result = func(args[0])
            return {{"result": result}}
        elif name == 'auto_chk':
            result = func(args[0])
            return {{"result": result}}
        elif name == 'auto_pull':
            result = func(args[0])
            return {{"result": result}}
        elif name == 'exp_dis':
            card_type = ctypes.c_int16()
            filename = args[1].encode('ascii', errors='replace') if len(args) > 1 and args[1] else b''
            result = func(args[0], filename, ctypes.byref(card_type))
            return {{"result": result, "card_type": card_type.value}}
        elif name.startswith('chk_'):
            result = func(args[0])
            return {{"result": result}}
        elif name.startswith('srd_24c') or name.startswith('srd_93c'):
            offset = args[1] if len(args) > 1 else 0
            length = args[2] if len(args) > 2 else 32
            buf = ctypes.create_string_buffer(length)
            result = func(args[0], offset, length, buf)
            return {{"result": result, "data": buf.raw[:length].hex()}}
        elif name.startswith('swr_24c') or name.startswith('swr_93c'):
            offset = args[1] if len(args) > 1 else 0
            data_hex = args[2] if len(args) > 2 else ''
            data_bytes = bytes.fromhex(data_hex)
            length = len(data_bytes)
            buf = ctypes.create_string_buffer(data_bytes, length)
            result = func(args[0], offset, length, buf)
            return {{"result": result}}
        elif name == 'prd_4442':
            length = args[1] if len(args) > 1 else 32
            buf = ctypes.create_string_buffer(length)
            result = func(args[0], length, buf)
            return {{"result": result, "data": buf.raw[:length].hex()}}
        elif name == 'pwr_4442':
            offset = args[1] if len(args) > 1 else 0
            data_hex = args[2] if len(args) > 2 else ''
            data_bytes = bytes.fromhex(data_hex)
            length = len(data_bytes)
            buf = ctypes.create_string_buffer(data_bytes, length)
            result = func(args[0], offset, length, buf)
            return {{"result": result}}
        elif name.startswith('rdwpb_44'):
            offset = args[1] if len(args) > 1 else 0
            length = args[2] if len(args) > 2 else 32
            buf = ctypes.create_string_buffer(length)
            result = func(args[0], offset, length, buf)
            return {{"result": result, "data": buf.raw[:length].hex()}}
        elif name.startswith('wrwpb_44'):
            offset = args[1] if len(args) > 1 else 0
            data_hex = args[2] if len(args) > 2 else ''
            data_bytes = bytes.fromhex(data_hex)
            length = len(data_bytes)
            buf = ctypes.create_string_buffer(data_bytes, length)
            result = func(args[0], offset, length, buf)
            return {{"result": result}}
        elif name.startswith('rsc_44'):
            length = args[1] if len(args) > 1 else 4
            buf = ctypes.create_string_buffer(length)
            result = func(args[0], length, buf)
            return {{"result": result, "data": buf.raw[:length].hex()}}
        elif name.startswith('wsc_44'):
            # wsc_4442/wsc_4428: (handle, length, data_hex)
            length = args[1] if len(args) > 1 else 0
            data_hex = args[2] if len(args) > 2 else ''
            if not data_hex or length == 0:
                return {{"result": -1, "error": "wsc_44: 参数错误"}}
            data_bytes = bytes.fromhex(data_hex)
            if len(data_bytes) != length:
                return {{"result": -1, "error": f"wsc_44: 数据长度不匹配，期望{{length}}，实际{{len(data_bytes)}}"}}
            buf = ctypes.create_string_buffer(data_bytes, length)
            result = func(args[0], length, buf)
            return {{"result": result}}
        elif name.startswith('csc_44'):
            # csc_4442/csc_4428: (handle, length, psc_hex)
            length = args[1] if len(args) > 1 else 3
            psc_hex = args[2] if len(args) > 2 else ''
            if not psc_hex:
                return {{"result": -1, "error": "csc_44: PSC数据不能为空"}}
            psc_bytes = bytes.fromhex(psc_hex)
            if len(psc_bytes) != length:
                print(f"[WARNING] csc_44: PSC数据长度不匹配，期望{{length}}，实际{{len(psc_bytes)}}")
            psc_buf = ctypes.create_string_buffer(max(length, len(psc_bytes)))
            ctypes.memmove(psc_buf, psc_bytes, len(psc_bytes))
            result = func(args[0], length, psc_buf)
            return {{"result": result}}
        elif name.startswith('srd_10') or name.startswith('srd_15') or name.startswith('srd_16'):
            zone = args[1] if len(args) > 1 else 0
            offset = args[2] if len(args) > 2 else 0
            length = args[3] if len(args) > 3 else 32
            buf = ctypes.create_string_buffer(length)
            result = func(args[0], zone, offset, length, buf)
            return {{"result": result, "data": buf.raw[:length].hex()}}
        elif name.startswith('swr_10') or name.startswith('swr_15') or name.startswith('swr_16'):
            zone = args[1] if len(args) > 1 else 0
            offset = args[2] if len(args) > 2 else 0
            data_hex = args[3] if len(args) > 3 else ''
            data_bytes = bytes.fromhex(data_hex)
            length = len(data_bytes)
            buf = ctypes.create_string_buffer(data_bytes, length)
            result = func(args[0], zone, offset, length, buf)
            return {{"result": result}}
        elif name.startswith('srd_44'):
            offset = args[1] if len(args) > 1 else 0
            length = args[2] if len(args) > 2 else 32
            buf = ctypes.create_string_buffer(length)
            result = func(args[0], offset, length, buf)
            return {{"result": result, "data": buf.raw[:length].hex()}}
        elif name.startswith('swr_44'):
            offset = args[1] if len(args) > 1 else 0
            data_hex = args[2] if len(args) > 2 else ''
            data_bytes = bytes.fromhex(data_hex)
            length = len(data_bytes)
            buf = ctypes.create_string_buffer(data_bytes, length)
            result = func(args[0], offset, length, buf)
            return {{"result": result}}
        elif name.startswith('rsct_44'):
            counter = ctypes.c_int16(0)
            result = func(args[0], ctypes.byref(counter))
            return {{"result": result, "counter": counter.value}}
        elif name.startswith('srd_s50') or name.startswith('srd_s70'):
            sector = args[1] if len(args) > 1 else 0
            key_hex = args[2] if len(args) > 2 else 'FFFFFFFFFFFF'
            key_type = args[3] if len(args) > 3 else 0x60
            key_bytes = bytes.fromhex(key_hex)
            key_buf = ctypes.create_string_buffer(key_bytes, 6)
            data_buf = ctypes.create_string_buffer(48)
            result = func(args[0], sector, key_buf, key_type, data_buf)
            return {{"result": result, "data": data_buf.raw[:48].hex()}}
        elif name.startswith('swr_s50') or name.startswith('swr_s70'):
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
            return {{"result": result}}
        elif name == 'cpu_reset':
            length = args[1] if len(args) > 1 else 64
            buf = ctypes.create_string_buffer(length)
            result = func(args[0], length, buf)
            return {{"result": result, "data": buf.raw[:length].hex()}}
        elif name == 'cpu_apdu':
            apdu_hex = args[1] if len(args) > 1 else ''
            apdu_bytes = bytes.fromhex(apdu_hex)
            apdu_buf = ctypes.create_string_buffer(apdu_bytes, len(apdu_bytes))
            resp_buf = ctypes.create_string_buffer(256)
            result = func(args[0], len(apdu_bytes), apdu_buf, resp_buf)
            return {{"result": result, "data": resp_buf.raw[:64].hex()}}
        elif name.startswith('chk_'):
            result = func(args[0])
            return {{"result": result}}
    except Exception as e:
        return {{"error": str(e)}}

while True:
    try:
        line = input()
        if not line:
            continue
        req = json.loads(line)
        name = req.get('func', '')
        args = req.get('args', [])
        resp = call_func(name, args)
        print(json.dumps(resp, ensure_ascii=False))
        sys.stdout.flush()
    except EOFError:
        break
    except Exception as e:
        print(json.dumps({{"error": str(e)}}))
        sys.stdout.flush()
'''

    def __init__(self):
        self.device_handle = None
        self.port_type = 0
        self.baud_rate = 9600
        self._mutex = threading.Lock()
        self._bridge_proc = None
        self._dll_path = self._find_dll()
        self._last_error = ""
        self._direct_caller = None
        self._use_direct = False

        if _is_32bit_python():
            try:
                self._direct_caller = _DirectDLLCaller(self._dll_path)
                self._use_direct = True
            except Exception as e:
                self._use_direct = False

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
        return candidates[0]

    def _find_python32(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        candidates = [
            os.path.join(os.path.dirname(base_dir), 'python32', 'python.exe'),
        ]
        if getattr(sys, 'frozen', False):
            candidates.insert(0, os.path.join(os.path.dirname(sys.executable), 'python32', 'python.exe'))
        for path in candidates:
            if os.path.exists(path):
                return path
        return candidates[0]

    def _start_bridge(self) -> bool:
        if self._bridge_proc is not None:
            try:
                self._bridge_proc.poll()
                if self._bridge_proc.returncode is not None:
                    self._bridge_proc = None
            except Exception:
                self._bridge_proc = None

        if self._bridge_proc is not None:
            return True

        python32 = self._find_python32()
        if not os.path.exists(python32):
            self._last_error = f"32位 Python 未找到: {python32}"
            print(self._last_error)
            return False

        if not os.path.exists(self._dll_path):
            self._last_error = f"DLL 未找到: {self._dll_path}"
            print(self._last_error)
            return False

        script = self._BRIDGE_SCRIPT.format(dll_path=self._dll_path)

        try:
            self._bridge_proc = subprocess.Popen(
                [python32, '-u', '-c', script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            return True
        except Exception as e:
            self._last_error = f"启动桥接进程失败: {e}"
            print(self._last_error)
            self._bridge_proc = None
            return False

    def _call_dll(self, func_name: str, args: list = None) -> dict:
        if args is None:
            args = []

        with self._mutex:
            if self._use_direct:
                return self._direct_caller.call(func_name, args)

            if not self._start_bridge():
                return {"error": self._last_error}

            try:
                req = json.dumps({"func": func_name, "args": args})
                self._bridge_proc.stdin.write((req + '\n').encode('utf-8'))
                self._bridge_proc.stdin.flush()

                line = self._bridge_proc.stdout.readline().decode('utf-8').strip()
                if not line:
                    self._bridge_proc = None
                    return {"error": "桥接进程无响应"}

                return json.loads(line)
            except Exception as e:
                self._bridge_proc = None
                return {"error": str(e)}

    def _stop_bridge(self):
        if self._bridge_proc is not None:
            try:
                self._bridge_proc.stdin.close()
            except Exception:
                pass
            try:
                self._bridge_proc.terminate()
                self._bridge_proc.wait(timeout=3)
            except Exception:
                try:
                    self._bridge_proc.kill()
                except Exception:
                    pass
            self._bridge_proc = None

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
        self._stop_bridge()
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

    def get_status0(self, handle: int) -> Tuple[int, int]:
        result = self._call_dll('get_status0', [handle])
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

    def chk_4442(self, handle: int) -> int:
        result = self._call_dll('chk_4442', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_4428(self, handle: int) -> int:
        result = self._call_dll('chk_4428', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_4418(self, handle: int) -> int:
        result = self._call_dll('chk_4418', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_24c(self, handle: int) -> int:
        result = self._call_dll('chk_24c', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_24c01a(self, handle: int) -> int:
        result = self._call_dll('chk_24c01a', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_24c02(self, handle: int) -> int:
        result = self._call_dll('chk_24c02', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_24c04(self, handle: int) -> int:
        result = self._call_dll('chk_24c04', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_24c08(self, handle: int) -> int:
        result = self._call_dll('chk_24c08', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_24c16(self, handle: int) -> int:
        result = self._call_dll('chk_24c16', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_24c32(self, handle: int) -> int:
        result = self._call_dll('chk_24c32', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_24c64(self, handle: int) -> int:
        result = self._call_dll('chk_24c64', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_at88c102(self, handle: int) -> int:
        result = self._call_dll('chk_102', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_at88c1604(self, handle: int) -> int:
        result = self._call_dll('chk_1604', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_at88sc153(self, handle: int) -> int:
        result = self._call_dll('chk_153', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def chk_at88sc1604b(self, handle: int) -> int:
        result = self._call_dll('chk_1604b', [handle])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def srd_4442(self, handle: int, offset: int, length: int) -> Tuple[int, bytes]:
        result = self._call_dll('srd_4442', [handle, offset, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def swr_4442(self, handle: int, offset: int, data: bytes) -> int:
        result = self._call_dll('swr_4442', [handle, offset, data.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

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

    def srd_4428(self, handle: int, offset: int, length: int) -> Tuple[int, bytes]:
        result = self._call_dll('srd_4428', [handle, offset, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def swr_4428(self, handle: int, offset: int, data: bytes) -> int:
        result = self._call_dll('swr_4428', [handle, offset, data.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

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

    def srd_4418(self, handle: int, offset: int, length: int) -> Tuple[int, bytes]:
        result = self._call_dll('srd_4418', [handle, offset, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def swr_4418(self, handle: int, offset: int, data: bytes) -> int:
        result = self._call_dll('swr_4418', [handle, offset, data.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

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

    def srd_93c(self, handle: int, offset: int, length: int) -> Tuple[int, bytes]:
        result = self._call_dll('srd_93c', [handle, offset, length])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def swr_93c(self, handle: int, offset: int, data: bytes) -> int:
        result = self._call_dll('swr_93c', [handle, offset, data.hex()])
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

    def cpu_apdu(self, handle: int, apdu: bytes) -> Tuple[int, bytes]:
        result = self._call_dll('cpu_apdu', [handle, apdu.hex()])
        if 'error' in result:
            return IC_ERR, b''
        data_hex = result.get('data', '')
        return result.get('result', IC_ERR), bytes.fromhex(data_hex) if data_hex else b''

    def wrt_4442_psc(self, handle: int, old_psc: bytes, new_psc: bytes) -> int:
        result = self._call_dll('wsc_4442', [handle, len(new_psc), new_psc.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def wrt_4428_psc(self, handle: int, old_psc: bytes, new_psc: bytes) -> int:
        result = self._call_dll('wsc_4428', [handle, len(new_psc), new_psc.hex()])
        if 'error' in result:
            return IC_ERR
        return result.get('result', IC_ERR)

    def disconnect(self):
        if self.device_handle is not None and self.device_handle > 0:
            try:
                self.ic_exit(self.device_handle)
            except Exception:
                pass
            self.device_handle = None
        self._stop_bridge()
