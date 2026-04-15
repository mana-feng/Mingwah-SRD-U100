"""
协议实现模块
包含命令协议、Mifare 协议、EEPROM 协议、SLE4442 协议等
"""

import struct
from typing import Tuple, Optional
from ..core.constants import (
    FRAME_STX, FRAME_ETX,
    RESP_OK, RESP_ERR, RESP_TIMEOUT, RESP_NO_CARD, RESP_CRC_ERR,
    IC_OK, IC_ERR, IC_ERR_NO_CARD,
    MIFARE_REQA, MIFARE_ANTICOLL,
    EEPROM_READ,
    SLE4442_READ_MEMORY
)


class CommandProtocol:
    """读写器命令协议"""
    
    @staticmethod
    def build_command(cmd: int, data: bytes = b'') -> bytes:
        """
        构建命令帧
        
        帧格式：[STX][LEN][CMD][DATA][CHK][ETX]
        STX = 0x02, ETX = 0x03
        LEN = 数据长度 + 2 (CMD + CHK)
        CHK = (CMD + DATA) 的累加和取低字节
        
        Args:
            cmd: 命令字
            data: 数据域
            
        Returns:
            完整的命令帧
        """
        length = len(data) + 2  # CMD + CHK
        chk = (cmd + sum(data)) & 0xFF
        
        frame = struct.pack('<BBBB', FRAME_STX, length, cmd, chk)
        frame += data
        frame += struct.pack('<B', FRAME_ETX)
        
        return frame
    
    @staticmethod
    def parse_response(response: bytes) -> Tuple[int, bytes]:
        """
        解析响应帧
        
        Args:
            response: 响应数据
            
        Returns:
            (status, data) 元组
        """
        if len(response) < 6:
            return (RESP_ERR, b'')
        
        stx, length, cmd, chk = struct.unpack('<BBBB', response[:4])
        data = response[4:-1]
        etx = response[-1]
        
        # 验证帧头帧尾
        if stx != FRAME_STX or etx != FRAME_ETX:
            return (RESP_ERR, b'')
        
        # 验证长度
        if length != len(data) + 2:
            return (RESP_ERR, b'')
        
        # 验证校验和
        calc_chk = (cmd + sum(data)) & 0xFF
        if calc_chk != chk:
            return (RESP_CRC_ERR, b'')
        
        return (cmd, data)
    
    @staticmethod
    def calculate_checksum(cmd: int, data: bytes) -> int:
        """
        计算校验和
        
        Args:
            cmd: 命令字
            data: 数据域
            
        Returns:
            校验和
        """
        return (cmd + sum(data)) & 0xFF


class MifareProtocol:
    """Mifare 卡片协议"""
    
    @staticmethod
    def request_atr(serial_port) -> Tuple[int, bytes]:
        """
        发送 REQA 命令获取 ATR
        
        Args:
            serial_port: 串口对象
            
        Returns:
            (status, data) 元组
        """
        cmd = struct.pack('<B', MIFARE_REQA)
        serial_port.write(cmd)
        
        response = serial_port.read(2)
        if len(response) == 2:
            return (IC_OK, response)
        return (IC_ERR_NO_CARD, b'')
    
    @staticmethod
    def anticoll(serial_port) -> Tuple[int, bytes]:
        """
        防冲突获取卡片序列号
        
        Args:
            serial_port: 串口对象
            
        Returns:
            (status, snr) 元组
        """
        cmd = struct.pack('<B', MIFARE_ANTICOLL)
        serial_port.write(cmd)
        
        response = serial_port.read(5)  # 4 字节序列号 + 1 字节校验
        if len(response) == 5:
            return (IC_OK, response[:4])
        return (IC_ERR, b'')
    
    @staticmethod
    def snr_to_string(snr_bytes: bytes) -> str:
        """
        将序列号字节转换为十六进制字符串
        
        Args:
            snr_bytes: 序列号字节
            
        Returns:
            十六进制字符串
        """
        return snr_bytes.hex().upper()


class EEPROMProtocol:
    """EEPROM 卡片协议 (AT24C 系列)"""
    
    @staticmethod
    def read_eeprom(serial_port, offset: int, length: int) -> Tuple[int, bytes]:
        """
        读取 EEPROM 数据
        
        Args:
            serial_port: 串口对象
            offset: 读取偏移
            length: 读取长度
            
        Returns:
            (status, data) 元组
        """
        cmd = struct.pack('<BBH', EEPROM_READ, offset, length)
        serial_port.write(cmd)
        
        response = serial_port.read(length + 2)
        if len(response) >= length:
            return (IC_OK, response[:length])
        return (IC_ERR, b'')
    
    @staticmethod
    def write_eeprom(serial_port, offset: int, data: bytes) -> int:
        """
        写入 EEPROM 数据
        
        Args:
            serial_port: 串口对象
            offset: 写入偏移
            data: 写入数据
            
        Returns:
            状态码
        """
        # 简化实现，实际需要根据具体协议
        return IC_OK


class SLE4442Protocol:
    """SLE4442 卡片协议"""
    
    @staticmethod
    def read_memory(serial_port, offset: int, length: int) -> Tuple[int, bytes]:
        """
        读取主存储器
        
        Args:
            serial_port: 串口对象
            offset: 读取偏移
            length: 读取长度
            
        Returns:
            (status, data) 元组
        """
        cmd = struct.pack('<BBH', SLE4442_READ_MEMORY, offset, length)
        serial_port.write(cmd)
        
        response = serial_port.read(length + 2)
        if len(response) >= length:
            return (IC_OK, response[:length])
        return (IC_ERR, b'')
    
    @staticmethod
    def verify_psc(serial_port, psc: bytes) -> int:
        """
        验证密码
        
        Args:
            serial_port: 串口对象
            psc: 密码数据
            
        Returns:
            状态码
        """
        # 简化实现
        return IC_OK
