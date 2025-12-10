
from __future__ import division, print_function


import platform
import logging
import time
import sys
import math
import struct
from functools import partial

from enum import Enum, auto

# Constants
FRAME_HEADER = 0x8668
FRAME_END = 0x55AA
PTYPE_CTRL_SINGLE = 0xA1
PTYPE_CTRL_MULTI = 0xA2
PTYPE_FILE_MD5 = 0xB1
PTYPE_FILE_VIEW = 0xB2
PTYPE_FILE_DATA = 0xB3
PTYPE_FILE_END = 0xB4
PTYPE_FILE_CAN = 0xB5
PTYPE_FILE_RETRY = 0xB6
class RevPacketState(Enum):
    WAIT_HEADER = auto()
    READ_LENGTH = auto()
    READ_DATA = auto()
    CHECK_FOOTER = auto()

class FileTransState(Enum):
    WAIT_MD5 = auto()
    WAIT_FILE_VIEW = auto()
    READ_FILE_DATA = auto()

class XMODEM(object):

    # crctab calculated by Mark G. Mendel, Network Systems Corporation
    crctable = [
        0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
        0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef,
        0x1231, 0x0210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6,
        0x9339, 0x8318, 0xb37b, 0xa35a, 0xd3bd, 0xc39c, 0xf3ff, 0xe3de,
        0x2462, 0x3443, 0x0420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485,
        0xa56a, 0xb54b, 0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d,
        0x3653, 0x2672, 0x1611, 0x0630, 0x76d7, 0x66f6, 0x5695, 0x46b4,
        0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc,
        0x48c4, 0x58e5, 0x6886, 0x78a7, 0x0840, 0x1861, 0x2802, 0x3823,
        0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b,
        0x5af5, 0x4ad4, 0x7ab7, 0x6a96, 0x1a71, 0x0a50, 0x3a33, 0x2a12,
        0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a,
        0x6ca6, 0x7c87, 0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0x0c60, 0x1c41,
        0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49,
        0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0x0e70,
        0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a, 0x9f59, 0x8f78,
        0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f,
        0x1080, 0x00a1, 0x30c2, 0x20e3, 0x5004, 0x4025, 0x7046, 0x6067,
        0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e,
        0x02b1, 0x1290, 0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256,
        0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d,
        0x34e2, 0x24c3, 0x14a0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
        0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e, 0xc71d, 0xd73c,
        0x26d3, 0x36f2, 0x0691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634,
        0xd94c, 0xc96d, 0xf90e, 0xe92f, 0x99c8, 0x89e9, 0xb98a, 0xa9ab,
        0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x08e1, 0x3882, 0x28a3,
        0xcb7d, 0xdb5c, 0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a,
        0x4a75, 0x5a54, 0x6a37, 0x7a16, 0x0af1, 0x1ad0, 0x2ab3, 0x3a92,
        0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdaa, 0xad8b, 0x9de8, 0x8dc9,
        0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83, 0x1ce0, 0x0cc1,
        0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8,
        0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0x0ed1, 0x1ef0,
    ]

    def __init__(self, getc, putc, mode='wifiMode', pad=b'\x1a'):
        self.getc = getc
        self.putc = putc
        self.mode = mode
        self.mode_set = False
        self.pad = pad
        self.log = logging.getLogger('xmodem.XMODEM')
        self.canceled = False
        self.currentState = RevPacketState.WAIT_HEADER
        self.packetData = bytearray()
        self.headerBuffer = bytearray(2)
        self.footerBuffer = bytearray(2)
        self.bytesNeeded = 2
        self.expectedLength = 0
        self.FileRcvState = FileTransState.WAIT_MD5

    def clear_mode_set(self):
        self.mode_set = False

    def abort(self, count=2, timeout=60):
        '''
        Send an abort sequence using CAN bytes.

        :param count: how many abort characters to send
        :type count: int
        :param timeout: timeout in seconds
        :type timeout: int
        '''
        self.SendFileTransCommand(PTYPE_FILE_CAN, b"")


    def crc16_ccitt(self, data: bytes, length: int) -> int:
        """Calculate CRC-16-CCITT checksum using the lookup table method"""
        crc = 0
        for i in range(length):
            tmp = ((crc >> 8) ^ data[i]) & 0xff
            crc = ((crc << 8) ^ self.crctable[tmp]) & 0xffff

        return crc & 0xffff

    def recvPacket(self, timeout=0.5):
        self.currentState = RevPacketState.WAIT_HEADER
        tr = time.time()
        while True:
            byte = self.getc(1, timeout)
            if byte:
                byte = ord(byte)
                if self.currentState == RevPacketState.WAIT_HEADER:
                    self.headerBuffer[0] = self.headerBuffer[1]
                    self.headerBuffer[1] = byte
                    checksum = (self.headerBuffer[0] << 8) | self.headerBuffer[1]
                    if checksum == FRAME_HEADER:
                        self.currentState = RevPacketState.READ_LENGTH
                        self.bytesNeeded = 2
                        self.packetData.clear()

                elif self.currentState == RevPacketState.READ_LENGTH:
                    self.packetData.append(byte)
                    self.bytesNeeded -= 1
                    if self.bytesNeeded == 0:
                        self.expectedLength = (self.packetData[0] << 8) | self.packetData[1]
                        if (self.expectedLength >= 0) and (self.expectedLength <= 8200):
                            self.currentState = RevPacketState.READ_DATA
                            self.bytesNeeded = self.expectedLength
                        else:
                            self.currentState = RevPacketState.WAIT_HEADER

                elif self.currentState == RevPacketState.READ_DATA:
                    self.packetData.append(byte)
                    self.bytesNeeded -= 1
                    while self.bytesNeeded > 0:
                        bytess = self.getc(self.bytesNeeded, timeout)
                        if bytess:
                            self.packetData.extend(bytess)
                            self.bytesNeeded = 0
                        else:
                            return None
                    if self.bytesNeeded == 0:
                        # Last two bytes are CRC
                        self.currentState = RevPacketState.CHECK_FOOTER
                        self.bytesNeeded = 2

                elif self.currentState == RevPacketState.CHECK_FOOTER:
                    self.footerBuffer[0] = self.footerBuffer[1]
                    self.footerBuffer[1] = byte
                    self.bytesNeeded -= 1
                    if self.bytesNeeded == 0:
                        checksum = (self.footerBuffer[0] << 8) | self.footerBuffer[1]
                        self.currentState = RevPacketState.WAIT_HEADER
                        if checksum == FRAME_END:
                            if self.process_packet():
                                return 1
                            else:
                                return None
                        else:
                            return None
            else:
                return None

    def process_packet(self):
        """
        Process a complete packet after it has been received
        """
        if len(self.packetData) < 2:
            self.packetData.clear()
            return  None# Not enough data for CRC check
        # CRC check
        calcCRC = self.crc16_ccitt(self.packetData, len(self.packetData) - 2)
        receivedCRC = (self.packetData[-2] << 8) | self.packetData[-1]
        if calcCRC == receivedCRC:
            if len(self.packetData) >= 3:
                return 1
            else:
                self.packetData.clear()
                return None
        else:
            self.packetData.clear()
            return None


    def SendFileTransCommand(self, Cmdstr, data: bytes) -> bytes:
        """
        封装多字节数据成通信报文
        报文格式: [帧头][数据长度(2字节)][指令类型][数据内容][CRC16][帧尾]

        参数:
            data: 字节类型数据（如 b'\x01\x02\x03'）

        数据长度自动计算: 指令类型(1) + 数据内容(N) + CRC16(2) = N+3 字节
        """
        # 输入校验
        if not isinstance(data, bytes):
            raise TypeError("data 必须是 bytes 类型")

        DATA_LENGTH = 1 + len(data) + 2  # 指令类型(1) + 数据内容(N) + CRC(2)

        # 构造CRC计算部分（长度字段+指令类型+数据内容）
        crc_payload = (
                DATA_LENGTH.to_bytes(2, 'big') +  # 2字节长度（新增）
                bytes([Cmdstr]) +  # 1字节指令类型
                data  # N字节数据
        )

        # 计算CRC（使用您提供的crc16_ccitt函数）
        crc = self.crc16_ccitt(crc_payload,DATA_LENGTH)  # 包含长度字段的CRC

        # 组装完整报文
        packet = (
                FRAME_HEADER.to_bytes(2, 'big') +  # 2字节帧头
                DATA_LENGTH.to_bytes(2, 'big') +  # 2字节长度
                bytes([Cmdstr]) +  # 1字节指令类型
                data +  # N字节数据
                crc.to_bytes(2, 'big') +  # 2字节CRC（小端序）
                FRAME_END.to_bytes(2, 'big')  # 2字节帧尾
        )
        self.putc(packet)


    def recv(self, stream, md5 = '', crc_mode=1, retry=5, timeout=5, delay=0.1, quiet=0, callback=None):
        success_count = 0
        error_count = 0
        totalerr_count = 0
        total_packet = 0
        packet_size = 0
        sequence = 0
        income_size = 0
        while True:
            if self.canceled:
                self.SendFileTransCommand(PTYPE_FILE_CAN, b"")
                self.log.info('Transmission canceled by user.')
                self.canceled = False
                return -1
            result = self.recvPacket(timeout)
            if result:
                cmdType = self.packetData[2]
                if cmdType < PTYPE_FILE_MD5:
                    continue
                if cmdType == PTYPE_FILE_CAN:
                    self.log.info('Transmission canceled by Machine.')
                    self.FileRcvState = FileTransState.WAIT_MD5
                    return None

                if self.FileRcvState == FileTransState.READ_FILE_DATA:
                    if self.packetData:
                        seq = (self.packetData[3] << 24) | (self.packetData[4] << 16) | (self.packetData[5] << 8) | self.packetData[6]
                        if cmdType == PTYPE_FILE_DATA and sequence == seq:
                            data_len = ((self.packetData[0] << 8) | self.packetData[1]) - 7
                            income_size += data_len
                            stream.write(self.packetData[7: (data_len + 7)])
                            if sequence < total_packet:
                                sequence += 1
                                # 转换为4字节的bytes（大端序）
                                data = sequence.to_bytes(4, byteorder='big', signed=False)
                                self.SendFileTransCommand(PTYPE_FILE_DATA, data)  # 请求发送文件下一帧数据
                            success_count = success_count + 1
                            if callable(callback):
                                callback(seq, total_packet)
                            error_count = 0
                            totalerr_count = 0
                            if seq == total_packet:
                                self.SendFileTransCommand(PTYPE_FILE_END, b"")  # 文件发送完成
                                self.FileRcvState = FileTransState.WAIT_MD5
                                self.log.info("Transmission complete, %d bytes",
                                              income_size)

                                self.FileRcvState = FileTransState.WAIT_MD5
                                return income_size
                        else:
                            error_count += 1
                            if error_count >= retry:
                                data = sequence.to_bytes(4, byteorder='big', signed=False)
                                self.SendFileTransCommand(PTYPE_FILE_DATA, data)  # 请求再次发送文件文件上一帧数据
                                totalerr_count += 1


                if self.FileRcvState == FileTransState.WAIT_FILE_VIEW:
                    if self.packetData:
                        if cmdType == PTYPE_FILE_VIEW:
                            total_packet = (self.packetData[3] << 24) | (self.packetData[4] << 16) | (self.packetData[5] << 8) | self.packetData[6]
                            packet_size = (self.packetData[7] << 8) | self.packetData[8]
                            sequence = 1
                            # 转换为4字节的bytes（大端序）
                            data = sequence.to_bytes(4, byteorder='big', signed=False)
                            self.SendFileTransCommand(PTYPE_FILE_DATA, data)  # 请求发送文件数据,第0帧
                            self.FileRcvState = FileTransState.READ_FILE_DATA
                            error_count = 0
                            totalerr_count = 0
                        else:
                            error_count += 1
                            if error_count >= retry:
                                self.SendFileTransCommand(PTYPE_FILE_VIEW, b"")  # 请求发送文件摘要
                                totalerr_count += 1

                if self.FileRcvState == FileTransState.WAIT_MD5:
                    if self.packetData:
                        if cmdType == PTYPE_FILE_MD5:
                            md5new = self.packetData[3: len(self.packetData)-2]
                            if (md5.encode() == md5new) and not (md5 == ''):
                                self.SendFileTransCommand(PTYPE_FILE_CAN, b"")
                                return 0    #MD5校验通过,直接打开本地文件
                            else:
                                self.SendFileTransCommand(PTYPE_FILE_VIEW, b"")
                                self.FileRcvState = FileTransState.WAIT_FILE_VIEW
                                error_count = 0
                                totalerr_count = 0
                        else:
                            error_count += 1
                            if error_count >= retry:
                                self.SendFileTransCommand(PTYPE_FILE_MD5, b"")  #请求发送MD5
                                totalerr_count += 1

                if self.canceled:
                    self.SendFileTransCommand(PTYPE_FILE_CAN, b"")
                    self.log.info('Transmission canceled by user.')
                    self.canceled = False
                    self.FileRcvState = FileTransState.WAIT_MD5
                    return None

                self.packetData.clear()
            else:
                error_count += 1
                if error_count >= 1:
                    totalerr_count += 1
                    self.SendFileTransCommand(PTYPE_FILE_RETRY, b"")
                    self.packetData.clear()

            if totalerr_count >= retry:
                self.SendFileTransCommand(PTYPE_FILE_CAN, b"")
                self.log.info('retry_count reached %d, aborting.', retry)
                self.abort(timeout=timeout)
                self.FileRcvState = FileTransState.WAIT_MD5
                return None

    def send(self, stream, md5, retry=16, timeout=5, quiet=False, callback=None):
        td = float()
        lastseq = 0
        packetno = 0
        try:
            packet_size = dict(
                USBMode=128,
                wifiMode=8192,
            )[self.mode]
        except KeyError:
            raise ValueError("Invalid mode specified: {self.mode!r}" .format(self=self))

        data = md5.encode()
        self.SendFileTransCommand(PTYPE_FILE_MD5, data)
        lastcmd = PTYPE_FILE_MD5
        td = time.time()
        while True:
            if self.canceled:
                self.SendFileTransCommand(PTYPE_FILE_CAN, b"")
                self.log.info('Transmission canceled by user.')
                self.canceled = False
                return None
            result = self.recvPacket(timeout * 8)
            if result:
                td = time.time()
                cmdType = self.packetData[2]
                if cmdType < PTYPE_FILE_MD5:
                    continue
                if cmdType == PTYPE_FILE_CAN:
                    self.log.info('Transmission canceled by Machine.')
                    self.FileRcvState = FileTransState.WAIT_MD5
                    return None
                if cmdType == PTYPE_FILE_RETRY:
                    self.SendFileTransCommand(lastcmd, data)

                if cmdType == PTYPE_FILE_MD5:
                    data = md5.encode()
                    self.SendFileTransCommand(PTYPE_FILE_MD5, data)

                if cmdType == PTYPE_FILE_VIEW:
                    stream.seek(0, 2)  # 移动到文件末尾
                    file_size = stream.tell()  # 获取当前指针位置
                    stream.seek(0)  # 重置指针到文件开头
                    packetno = math.ceil(file_size / packet_size)
                    packetno_bytes = struct.pack('>I', packetno)  # 4字节大端
                    packetsize_bytes = struct.pack('>H', packet_size)  # 2字节大端

                    # 合并为最终的data变量
                    data = packetno_bytes + packetsize_bytes
                    self.SendFileTransCommand(PTYPE_FILE_VIEW, data)
                    lastcmd = PTYPE_FILE_VIEW
                    lastseq = 0

                if cmdType == PTYPE_FILE_DATA:
                    seq = (self.packetData[3] << 24) | (self.packetData[4] << 16) | (self.packetData[5] << 8) | self.packetData[6]
                    if seq == lastseq:
                        self.SendFileTransCommand(PTYPE_FILE_DATA, data)
                    elif seq == lastseq + 1:
                        seq_bytes = struct.pack('>I', seq)  # 4字节大端
                        file_data = stream.read(packet_size)
                        data = seq_bytes + file_data
                        self.SendFileTransCommand(PTYPE_FILE_DATA, data)
                    else:
                        seq_bytes = struct.pack('>I', seq)  # 4字节大端
                        stream.seek((seq-1) * packet_size, 0)  # 从文件开头移动
                        file_data = stream.read(packet_size)
                        data = seq_bytes + file_data
                        self.SendFileTransCommand(PTYPE_FILE_DATA, data)
                    lastcmd = PTYPE_FILE_DATA
                    lastseq = seq
                    #print("file send seq: %d" %seq)
                    if callable(callback):
                        callback(packet_size, seq, 0, 0)

                if cmdType == PTYPE_FILE_END:
                    self.log.info('Transmission successful (FILE end flag received).')
                    return True

            else:
                t = time.time()
                if t - td > 9:
                    self.SendFileTransCommand(PTYPE_FILE_CAN, b"")
                    self.log.info('Info: Controller receive data timeout!')
                    self.FileRcvState = FileTransState.WAIT_MD5
                    return None

    def _verify_recv_checksum(self, crc_mode, data):
        if crc_mode:
            _checksum = bytearray(data[-2:])
            their_sum = (_checksum[0] << 8) + _checksum[1]
            data = data[:-2]

            our_sum = self.calc_crc(data)
            valid = bool(their_sum == our_sum)
            if not valid:
                self.log.warn('recv error: checksum fail '
                              '(theirs=%04x, ours=%04x), ',
                              their_sum, our_sum)
        else:
            _checksum = bytearray([data[-1]])
            their_sum = _checksum[0]
            data = data[:-1]

            our_sum = self.calc_checksum(data)
            valid = their_sum == our_sum
            if not valid:
                self.log.warn('recv error: checksum fail '
                              '(theirs=%02x, ours=%02x)',
                              their_sum, our_sum)
        return valid, data

    def calc_checksum(self, data, checksum=0):
        '''
        Calculate the checksum for a given block of data, can also be used to
        update a checksum.

            >>> csum = modem.calc_checksum('hello')
            >>> csum = modem.calc_checksum('world', csum)
            >>> hex(csum)
            '0x3c'

        '''
        if platform.python_version_tuple() >= ('3', '0', '0'):
            return (sum(data) + checksum) % 256
        else:
            return (sum(map(ord, data)) + checksum) % 256

    def calc_crc(self, data, crc=0):
        '''
        Calculate the Cyclic Redundancy Check for a given block of data, can
        also be used to update a CRC.

            >>> crc = modem.calc_crc('hello')
            >>> crc = modem.calc_crc('world', crc)
            >>> hex(crc)
            '0x4ab3'

        '''
        for char in bytearray(data):
            crctbl_idx = ((crc >> 8) ^ char) & 0xff
            crc = ((crc << 8) ^ self.crctable[crctbl_idx]) & 0xffff
        return crc & 0xffff

def _send(mode='USBMode', filename=None, timeout=30):
    '''Send a file (or stdin) using the selected mode.'''

    if filename is None:
        si = sys.stdin
    else:
        si = open(filename, 'rb')

    # TODO(maze): make this configurable, serial out, etc.
    so = sys.stdout

    def _getc(size, timeout=timeout):
        read_ready, _, _ = select.select([so], [], [], timeout)
        if read_ready:
            data = stream.read(size)
        else:
            data = None
        return data

    def _putc(data, timeout=timeout):
        _, write_ready, _ = select.select([], [si], [], timeout)
        if write_ready:
            si.write(data)
            si.flush()
            size = len(data)
        else:
            size = None
        return size

    xmodem = XMODEM(_getc, _putc, mode)
    return xmodem.send(si)


def run():
    '''Run the main entry point for sending and receiving files.'''
    import argparse
    import serial
    import sys

    platform = sys.platform.lower()

    if platform.startswith('win'):
        default_port = 'COM1'
    else:
        default_port = '/dev/ttyS0'

    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default=default_port,
                        help='serial port')
    parser.add_argument('-r', '--rate', default=9600, type=int,
                        help='baud rate')
    parser.add_argument('-b', '--bytesize', default=serial.EIGHTBITS,
                        help='serial port transfer byte size')
    parser.add_argument('-P', '--parity', default=serial.PARITY_NONE,
                        help='serial port parity')
    parser.add_argument('-S', '--stopbits', default=serial.STOPBITS_ONE,
                        help='serial port stop bits')
    parser.add_argument('-m', '--mode', default='USBMode',
                        help='XMODEM mode (USBMode, wifiMode)')
    parser.add_argument('-t', '--timeout', default=30, type=int,
                        help='I/O timeout in seconds')

    subparsers = parser.add_subparsers(dest='subcommand')
    send_parser = subparsers.add_parser('send')
    send_parser.add_argument('filename', nargs='?',
                             help='filename to send, empty reads from stdin')
    recv_parser = subparsers.add_parser('recv')
    recv_parser.add_argument('filename', nargs='?',
                             help='filename to receive, empty sends to stdout')

    options = parser.parse_args()

    if options.subcommand == 'send':
        return _send(options.mode, options.filename, options.timeout)
    elif options.subcommand == 'recv':
        return _recv(options.mode, options.filename, options.timeout)


def runx():
    import optparse
    import subprocess

    parser = optparse.OptionParser(
        usage='%prog [<options>] <send|recv> filename filename')
    parser.add_option('-m', '--mode', default='USBMode',
                      help='XMODEM mode (USBMode, wifiMode)')

    options, args = parser.parse_args()
    if len(args) != 3:
        parser.error('invalid arguments')
        return 1

    elif args[0] not in ('send', 'recv'):
        parser.error('invalid mode')
        return 1

    def _func(so, si):
        import select

        print(('si', si))
        print(('so', so))
        def getc(size, timeout=3):
            read_ready, _, _ = select.select([so], [], [], timeout)
            if read_ready:
                data = so.read(size)
            else:
                data = None

            print(('getc(', repr(data), ')'))
            return data

        def putc(data, timeout=3):
            _, write_ready, _ = select.select([], [si], [], timeout)
            if write_ready:
                si.write(data)
                si.flush()
                size = len(data)
            else:
                size = None

            print(('putc(', repr(data), repr(size), ')'))
            return size

        return getc, putc

    def _pipe(*command):
        pipe = subprocess.Popen(command,
                                stdout=subprocess.PIPE,
                                stdin=subprocess.PIPE)
        return pipe.stdout, pipe.stdin

    if args[0] == 'recv':
        getc, putc = _func(*_pipe('sz', '--xmodem', args[2]))
        stream = open(args[1], 'wb')
        xmodem = XMODEM(getc, putc, mode=options.mode)
        status = xmodem.recv(stream, retry=8)
        assert status, ('Transfer failed, status is', False)
        stream.close()

    elif args[0] == 'send':
        getc, putc = _func(*_pipe('rz', '--xmodem', args[2]))
        stream = open(args[1], 'rb')
        xmodem = XMODEM(getc, putc, mode=options.mode)
        sent = xmodem.send(stream, retry=8)
        assert sent is not None, ('Transfer failed, sent is', sent)
        stream.close()


if __name__ == '__main__':
    sys.exit(run())
