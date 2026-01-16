#!/usr/bin/python

from __future__ import absolute_import
from __future__ import print_function

import os
import re
import sys
import time
import threading
import webbrowser
import gettext
from datetime import datetime
from __main__ import tr
try:
    from Queue import *
except ImportError:
    from queue import *

from CNC import CNC
from kivy.utils import platform as kivy_platform
if kivy_platform != "ios":
    from USBStream import USBStream
from WIFIStream import WIFIStream
from XMODEM import EOT, CAN
from kivy.app import App
import Utils

STREAM_POLL = 0.3 # s
DIAGNOSE_POLL = 0.5  # s


GPAT = re.compile(r"[A-Za-z]\s*[-+]?\d+.*")
FEEDPAT = re.compile(r"^(.*)[fF](\d+\.?\d+)(.*)$")

STATUSPAT = re.compile(r"^<(\w*?),MPos:([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),WPos:([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),?(.*)>$")
POSPAT	  = re.compile(r"^\[(...):([+\-]?\d*\.\d*),([+\-]?\d*\.\d*),([+\-]?\d*\.\d*):?(\d*)\]$")
TLOPAT	  = re.compile(r"^\[(...):([+\-]?\d*\.\d*)\]$")
DOLLARPAT = re.compile(r"^\[G\d* .*\]$")
SPLITPAT  = re.compile(r"[:,]")
VARPAT    = re.compile(r"^\$(\d+)=(\d*\.?\d*) *\(?.*")


WIKI = "https://github.com/vlachoudis/bCNC/wiki"

CONNECTED = "Wait"
NOT_CONNECTED = "N/A"

STATECOLORDEF = (155/255, 155/255, 155/255, 1)  # Default color for unknown types or not connected
STATECOLOR = {
    "Idle":         (52/255, 152/255, 219/255, 1),
    "Run":          (34/255, 153/255, 84/255, 1),
    "Tool":        (34/255, 153/255, 84/255, 1),
    "Alarm":        (231/255, 76/255, 60/255, 1),
    "Home":         (247/255, 220/255, 111/255, 1),
    "Hold":         (34/255, 153/255, 84/255, 1),
    'Wait':         (247/255, 220/255, 111/255, 1),
    'Disable':      (100/255, 100/255, 100/255, 1),
    'Sleep':        (220/255, 220/255, 220/255, 1),
    'Pause':        (52/255, 152/255, 219/255, 1),
    NOT_CONNECTED:  (155/255, 155/255, 155/255, 1)
}

LOAD_DIR   = 1
LOAD_RM    = 2
LOAD_MV    = 3
LOAD_MKDIR = 4
LOAD_WIFI  = 7
LOAD_CONN_WIFI = 8

SEND_FILE = 1

CONN_USB = 0
CONN_WIFI = 1

# 协议字段定义
FRAME_HEADER = 0x8668  # 2字节帧头
FRAME_END = 0x55AA  # 2字节帧尾
PTYPE_CTRL_SINGLE = 0xA1  # 单字节指令类型
PTYPE_CTRL_MULTI = 0xA2  # 多字节指令类型（与单字节区分）
PTYPE_FILE_START = 0xB0 # 文件传输指令（上传或下载文件,文件传输起始命令)
MAX_DATA_LEN = 1024
PTYPE_STATUS_RES = 0x81 #状态查询响应
PTYPE_DIAG_RES = 0x82   #诊断查询响应
PTYPE_LOAD_INFO = 0x83
PTYPE_LOAD_FINISH = 0x84
PTYPE_LOAD_ERROR = 0x85
PTYPE_NORMAL_INFO = 0x90 #主动上送的信息，在MDI窗口中显示的信息


from enum import Enum, auto
class RevPacketState(Enum):
    WAIT_HEADER = auto()
    READ_LENGTH = auto()
    READ_DATA = auto()
    CHECK_FOOTER = auto()


# ==============================================================================
# Controller class
# ==============================================================================
class Controller:
    MSG_NORMAL = 0
    MSG_ERROR = 1
    MSG_INTERIOR = 2

    stop = threading.Event()
    usb_stream = None
    wifi_stream = None
    stream = None
    modem = None
    connection_type = CONN_WIFI

    def __init__(self, cnc, callback):
        if kivy_platform == "ios":
            self.usb_stream =  None
        else:
            self.usb_stream = USBStream()
        self.wifi_stream = WIFIStream()

        # Global variables
        self.history = []
        self._historyPos = None

        # CNC.loadConfig(Utils.config)
        self.cnc = cnc

        self.execCallback = callback

        self.log = Queue()  # Log queue returned from GRBL
        self.queue = Queue()  # Command queue to be send to GRBL
        self.load_buffer = Queue()
        self.load_buffer_size = 0
        self.total_buffer_size = 0

        self.loadNUM = 0
        self.loadEOF = False
        self.loadERR = False
        self.loadCANCEL = False
        self.loadCANCELSENT = False

        self.sendNUM = 0
        self.sendEOF = False
        self.sendCANCEL = False

        self.thread = None

        self.posUpdate = False  # Update position
        self.diagnoseUpdate = False
        self._probeUpdate = False  # Update probe
        self._gUpdate = False  # Update $G
        self._update = None  # Generic update

        self.cleanAfter = False
        self._runLines = 0
        self._quit = 0  # Quit counter to exit program
        self._stop = False  # Raise to stop current run
        self._pause = False  # machine is on Hold
        self._alarm = True  # Display alarm message if true
        self._msg = None
        self._sumcline = 0
        self._lastFeed = 0
        self._newFeed = 0

        self._onStart = ""
        self._onStop = ""

        self.paused = False
        self.pausing = False

        self.diagnosing = False


        self.currentState = RevPacketState.WAIT_HEADER
        self.packetData = bytearray()
        self.headerBuffer = bytearray(2)
        self.footerBuffer = bytearray(2)
        self.bytesNeeded = 2
        self.expectedLength = 0

    # ----------------------------------------------------------------------
    def quit(self, event=None):
        pass

    # ----------------------------------------------------------------------
    def loadConfig(self):
        pass

    # ----------------------------------------------------------------------
    def saveConfig(self):
        pass

    def crc16_ccitt(self,data: bytes,length: int) -> int:
        crc_table = [
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

        crc = 0
        if length == 0:
            for byte in data:  # byte 自动转为 0~255 的整数
                tmp = ((crc >> 8) ^ byte) & 0xFF
                crc = ((crc << 8) ^ crc_table[tmp]) & 0xFFFF
        else:
            for i in range(length):
                tmp = ((crc >> 8) ^ data[i]) & 0xff
                crc = ((crc << 8) ^ crc_table[tmp]) & 0xFFFF
        return crc


    # ----------------------------------------------------------------------
    # New Communication protocol
    # [帧头][数据长度][指令类型][数据内容][CRC16][帧尾]
    # 单字节命令
    # ----------------------------------------------------------------------
    def executeSingleCharCommand(self, char: int):
        app = App.get_running_app()
        if app.root.oldfirmware == False:
            """
            将单个字符封装成通信报文
            报文格式: [帧头][数据长度][指令类型][数据内容][CRC16][帧尾]
            - 帧头: 0x8668 (2字节，不参与CRC计算)
            - 数据长度: 数据内容长度 (2字节)
            - 指令类型: 0xA1 (1字节)
            - 数据内容: char (1字节)
            - CRC16: 计算范围(数据长度 + 指令类型 + 数据内容) (2字节)
            - 帧尾: 0x55AA (2字节，不参与CRC计算)
            """

            # 数据内容长度（4字节）
            data_length = 4         # 指令类型(1) + 数据内容(1) + CRC(2) = 4字节

            # 构造CRC计算部分（数据长度2字节 + 指令类型1字节 + 数据内容1字节）
            crc_data = (
                    data_length.to_bytes(2, 'big') +  # 2字节数据长度
                    PTYPE_CTRL_SINGLE.to_bytes(1, 'big') +  # 1字节指令类型
                    char.to_bytes(1, 'big')  # 1字节数据内容
            )
            crc = self.crc16_ccitt(crc_data, 0)

            # 构造完整报文（字节序：大端）
            packet = (
                    FRAME_HEADER.to_bytes(2, byteorder='big') +  # 帧头（2字节）
                    crc_data +  # 数据长度 + 指令类型 + 数据内容（4字节）
                    crc.to_bytes(2, byteorder='big') +  # CRC16（2字节）
                    FRAME_END.to_bytes(2, byteorder='big')  # 帧尾（2字节）
            )

            self.stream.send(packet)
        else:
            line = chr(char)
            self.stream.send(line.encode())

    def executeMultiCharCommand(self, data: bytes) -> bytes:
        app = App.get_running_app()
        if app.root.oldfirmware == False:
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
                    bytes([PTYPE_CTRL_MULTI]) +  # 1字节指令类型
                    data  # N字节数据
            )

            # 计算CRC（使用您提供的crc16_ccitt函数）
            crc = self.crc16_ccitt(crc_payload, 0)  # 包含长度字段的CRC

            # 组装完整报文
            packet = (
                    FRAME_HEADER.to_bytes(2, 'big') +  # 2字节帧头
                    DATA_LENGTH.to_bytes(2, 'big') +  # 2字节长度
                    bytes([PTYPE_CTRL_MULTI]) +  # 1字节指令类型
                    data +  # N字节数据
                    crc.to_bytes(2, 'big') +  # 2字节CRC（小端序）
                    FRAME_END.to_bytes(2, 'big')  # 2字节帧尾
            )

            self.stream.send(packet)
        else:
            text = data.decode('utf-8')
            if text[-1] != '\n':
                text += "\n"
            self.stream.send(text.encode())

    def executeFileCommand(self, data: bytes) -> bytes:
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
                bytes([PTYPE_FILE_START]) +  # 1字节指令类型
                data  # N字节数据
        )

        # 计算CRC（使用您提供的crc16_ccitt函数）
        crc = self.crc16_ccitt(crc_payload, 0)  # 包含长度字段的CRC

        # 组装完整报文
        packet = (
                FRAME_HEADER.to_bytes(2, 'big') +  # 2字节帧头
                DATA_LENGTH.to_bytes(2, 'big') +  # 2字节长度
                bytes([PTYPE_FILE_START]) +  # 1字节指令类型
                data +  # N字节数据
                crc.to_bytes(2, 'big') +  # 2字节CRC（小端序）
                FRAME_END.to_bytes(2, 'big')  # 2字节帧尾
        )

        self.stream.send(packet)

    # ----------------------------------------------------------------------
    # Execute a single command
    # ----------------------------------------------------------------------
    def executeCommand(self, line, nodisplay = False):
        #if self.sio_status != False or self.sio_diagnose != False:      #wait for the ? or * command
        #    time.sleep(0.5)
        if self.stream and line:
            try:
                #if line[-1] != '\n':
                #    line += "\n"
                self.executeMultiCharCommand(line.encode())
                if self.execCallback:
                    if not nodisplay:
                        self.execCallback(line)
            except:
                self.log.put((Controller.MSG_ERROR, str(sys.exc_info()[1])))

    # ----------------------------------------------------------------------
    # Execute transfer file  command
    # ----------------------------------------------------------------------
    def executeTransfileCommand(self, line, nodisplay=False):
        # if self.sio_status != False or self.sio_diagnose != False:      #wait for the ? or * command
        #    time.sleep(0.5)
        app = App.get_running_app()
        if self.stream and line:
            try:
                if line[-1] != '\n':
                    line += "\n"
                if app.root.oldfirmware == False:
                    self.executeFileCommand(line.encode())
                else:
                    if line[-1] != '\n':
                        line += "\n"
                    self.stream.send(line.encode())
                if self.execCallback:
                    # 检查文件名是否以 ".lz" 结尾
                    if line.endswith(".lz\n"):
                        # 删除 ".lz" 后缀
                        new_line = line[:-4] + "\n"
                    else:
                        # 如果没有 ".lz" 后缀，直接赋值
                        new_line = line
                    if not nodisplay:
                        self.execCallback(new_line)
            except:
                self.log.put((Controller.MSG_ERROR, str(sys.exc_info()[1])))

    # ----------------------------------------------------------------------
    def autoCommand(self, margin=False, zprobe=False, zprobe_abs=False, leveling=False, goto_origin=False, z_probe_offset_x=0, z_probe_offset_y=0, i=3, j=3, h=5, buffer=False):
        if not (margin or zprobe or leveling or goto_origin):
            return
        if abs(CNC.vars['xmin']) > CNC.vars['worksize_x'] or abs(CNC.vars['ymin']) > CNC.vars['worksize_y']:
            return
        app = App.get_running_app()
        cmd = "M495 X%gY%g" % (CNC.vars['xmin'], CNC.vars['ymin'])
        if margin:
            cmd = cmd + "C%gD%g" % (CNC.vars['xmax'], CNC.vars['ymax'])
        if zprobe:
            if zprobe_abs:
                cmd = cmd + "O0"
            else:
                cmd = cmd + "O%gF%g" % (z_probe_offset_x, z_probe_offset_y)
        else:
            if zprobe_abs:
                cmd = cmd + "R0"
        if leveling:
            cmd = cmd + "A%gB%gI%dJ%dH%d" % (CNC.vars['xmax'] - CNC.vars['xmin'], CNC.vars['ymax'] - CNC.vars['ymin'], i, j, h)
        if goto_origin:
            cmd = cmd + "P1"

        cmd = cmd + "\n"
        if buffer:
            cmd = "buffer " + cmd
        self.executeCommand(cmd)

    def xyzProbe(self, height=9.0, diameter=3.175, buffer=False):
        cmd = "M495.3 H%g D%g" % (height, diameter)
        if buffer:
            cmd = "buffer " + cmd
        self.executeCommand(cmd)

    def pairWP(self):
        self.executeCommand("M471")

    def syncTime(self, *args):
        self.executeCommand("time " + str(int(time.time()) - time.timezone))

    def echo(self, *args):
        self.executeCommand("echo", True)

    def queryTime(self, *args):
        self.executeCommand("time", True)

    def queryVersion(self, *args):
        self.executeCommand("version", True)

    def queryModel(self, *args):
        self.executeCommand("model", True)

    def queryFtype(self, *args):
        self.executeCommand("ftype", True)


    # # ----------------------------------------------------------------------
    # def zProbeCommand(self, c=0, d=0, buffer=False):
    #     cmd = "M494 X%gY%gC%gD%g\n" % (CNC.vars['xmin'], CNC.vars['ymin'], c, d)
    #     if buffer:
    #         cmd = "buffer " + cmd
    #     self.executeCommand(cmd)

    # def autoLevelCommand(self, i=3, j=3, buffer=False):
    #     cmd = "M495 X%gY%gA%gB%gI%dJ%d\n" % (CNC.vars['xmin'], CNC.vars['ymin'], CNC.vars['xmax'] - CNC.vars['xmin'], CNC.vars['ymax'] - CNC.vars['ymin'], i, j)
    #     if buffer:
    #         cmd = "buffer " + cmd
    #     self.executeCommand(cmd)

    # def probeLevelCommand(self, i=3, j=3, buffer=False):
    #     cmd = "M496 X%gY%gA%gB%gI%dJ%d\n" % (CNC.vars['xmin'], CNC.vars['ymin'], CNC.vars['xmax'] - CNC.vars['xmin'], CNC.vars['ymax'] - CNC.vars['ymin'], i, j)
    #     if buffer:
    #         cmd = "buffer " + cmd
    #     self.executeCommand(cmd)

    def gotoPosition(self, position, buffer=False):
        if position is None:
            return
        cmd = ""
        if position == tr._('Clearance'):
            cmd = "M496.1\n"
        elif position == tr._('Work Origin'):
            cmd = "M496.2\n"
        elif position == tr._('Anchor1'):
            cmd = "M496.3\n"
        elif position == tr._('Anchor2'):
            cmd = "M496.4\n"
        elif position == tr._('Path Origin'):
            if abs(CNC.vars['xmin']) <= CNC.vars['worksize_x'] and abs(CNC.vars['ymin']) <= CNC.vars['worksize_y']:
                cmd = "M496.5 X%gY%g\n" % (CNC.vars['xmin'], CNC.vars['ymin'])
        if buffer:
            cmd = "buffer " + cmd
        self.executeCommand(cmd)

    def reset(self):
        self.executeCommand("reset")

    def change(self):
        self.executeCommand("M490.2")

    def setFeedScale(self, scale):
        self.executeCommand("M220 S%d" % (scale))

    def setLaserScale(self, scale):
        self.executeCommand("M325 S%d" % (scale))

    def setSpindleScale(self, scale):
        self.executeCommand("M223 S%d" % (scale))

    def clearAutoLeveling(self):
        self.executeCommand("M370")

    def setSpindleSwitch(self, switch, rpm):
        if switch:
            self.executeCommand("M3 S%d" % (rpm))
        else:
            self.executeCommand("M5")

    def setVacuumSwitch(self, switch, power):
        if switch:
            if power<20:
                power = 20
            self.executeCommand("M801 S%d" % (power))
        else:
            self.executeCommand("M802")

    def setSpindlefanSwitch(self, switch, power):
        if switch:
            if power<20:
                power = 20
            self.executeCommand("M811 S%d" % (power))
        else:
            self.executeCommand("M812")

    def setLaserSwitch(self, switch, power):
        if switch:
            if power<5:
                power = 5
            self.executeCommand("M3 S%g" % (power * 1.0 / 100))
        else:
            self.executeCommand("M5")

    def setLightSwitch(self, switch):
        if switch:
            self.executeCommand("M821")
        else:
            self.executeCommand("M822")

    def setToolSensorSwitch(self, switch):
        if switch:
            self.executeCommand("M831")
        else:
            self.executeCommand("M832")

    def setAirSwitch(self, switch):
        if switch:
            self.executeCommand("M7")
        else:
            self.executeCommand("M9")

    def setPWChargeSwitch(self, switch):
        if switch:
            self.executeCommand("M841")
        else:
            self.executeCommand("M842")

    def setExtoutSwitch(self, switch, power):
        if switch:
            if power<5:
                power = 5
            self.executeCommand("M851 S%g" % (power))
        else:
            self.executeCommand("M852")

    def setVacuumMode(self, mode):
        if mode:
            self.executeCommand("M331")
        else:
            self.executeCommand("M332")

    def setBlowingMode(self, mode, s_value):
        if mode:
        #    if s_value >=0 and s_value <= 100:
        #        cmd = f"M331.1 S{s_value}"
        #        self.executeCommand(cmd)
            self.executeCommand("M331.1")
        else:
            self.executeCommand("M332.1")

    def setBedCleanMode(self, mode):
        if mode:
            self.executeCommand("M331.2")
        else:
            self.executeCommand("M332.2")

    def setExtoutMode(self, mode):
        if mode:
            self.executeCommand("M331.3")
        else:
            self.executeCommand("M332.3")

    def setLaserMode(self, mode):
        if mode:
            self.executeCommand("M321")
        else:
            self.executeCommand("M322")

    def setLaserTest(self, test):
        if test:
            self.executeCommand("M323")
        else:
            self.executeCommand("M324")

    def setConfigValue(self, key, value):
        if key and value:
            self.executeCommand("config-set sd %s %s" % (key, value))


    def dropToolCommand(self):
        self.executeCommand("M6T-1")

    def calibrateToolCommand(self):
        self.executeCommand("M491")

    def changeToolCommand(self, tool):
        if tool == tr._("Probe"):
            self.executeCommand("M6T0")
        elif tool == tr._("Laser"):
            self.executeCommand("M6T8888")
        else:
            if tool.startswith('Tool: '):
                tool = tool[6:]
            self.executeCommand("M6T%s" % tool)

    def setToolCommand(self, tool):
        if tool == tr._("Probe"):
            self.executeCommand("M493.2T0")
        elif tool == tr._("Laser"):
            self.executeCommand("M493.2T8888")
        elif tool == tr._("Empty"):
            self.executeCommand("M493.2T-1")
        else:
            if tool.startswith('Tool: '):
                tool = tool[6:]
            self.executeCommand("M493.2T%s" % tool)

    def bufferChangeToolCommand(self, tool):
        self.executeCommand("buffer M6T%s" % tool)

    # ------------------------------------------------------------------------------
    # escape special characters
    # ------------------------------------------------------------------------------
    def escape(self, value):
        return value.replace('?', '\x02').replace('*', '\x03').replace('!', '\x04').replace('~', '\x05')

    def lsCommand(self, ls_dir):
        ls_command = "ls -e -s %s" % ls_dir.replace(' ', '\x01')
        if '\\' in ls_dir:
            ls_command = "ls -e -s %s" % '/'.join(ls_dir.split('\\')).replace(' ', '\x01')
        self.executeCommand(self.escape(ls_command))

    def catCommand(self, filename):
        cat_command = "cat %s -e" % filename.replace(' ', '\x01')
        if '\\' in filename:
            cat_command = "cat %s -e" % '/'.join(filename.split('\\')).replace(' ', '\x01')
        self.executeCommand(self.escape(cat_command))

    def rmCommand(self, filename):
        rm_command = "rm %s -e" % filename.replace(' ', '\x01')
        if '\\' in filename:
            rm_command = "rm %s -e" % '/'.join(filename.split('\\')).replace(' ', '\x01')
        self.executeCommand(self.escape(rm_command))

    def mvCommand(self, file, newfile):
        mv_command = "mv %s %s -e" % (file.replace(' ', '\x01'), newfile.replace(' ', '\x01'))
        if '\\' in file or '\\' in newfile:
            mv_command = "mv %s %s -e" % ('/'.join(file.split('\\')).replace(' ', '\x01'), '/'.join(newfile.split('\\')).replace(' ', '\x01'))
        self.executeCommand(self.escape(mv_command))

    def mkdirCommand(self, dirname):
        mkdir_command = "mkdir %s -e" % dirname.replace(' ', '\x01')
        if '\\' in dirname:
            mkdir_command = "mkdir %s -e" % '/'.join(dirname.split('\\')).replace(' ', '\x01')
        self.executeCommand(self.escape(mkdir_command))

    def md5Command(self, filename):
        md5_command = "md5sum %s -e" % filename.replace(' ', '\x01')
        if '\\' in filename:
            md5_command = "md5sum %s -e" % '/'.join(filename.split('\\')).replace(' ', '\x01')
        self.executeCommand(self.escape(md5_command))

    def loadWiFiCommand(self):
        self.executeCommand("wlan -e")

    def disconnectWiFiCommand(self):
        self.executeCommand("wlan -d disconnect")

    def connectWiFiCommand(self, ssid, password):
        wifi_command = "wlan %s %s -e" % (ssid.replace(' ', '\x01'), password.replace(' ', '\x01'))
        self.executeCommand(self.escape(wifi_command))

    def loadConfigCommand(self):
        self.executeCommand("config-get-all -e")

    def restoreConfigCommand(self):
        self.executeCommand("config-restore")

    def defaultConfigCommand(self):
        self.executeCommand("config-default")

    def uploadCommand(self, filename):
        upload_command = "upload %s" % filename.replace(' ', '\x01')
        if '\\' in filename:
            upload_command = "upload %s" % '/'.join(filename.split('\\')).replace(' ', '\x01')
        self.executeTransfileCommand(self.escape(upload_command))

    def downloadCommand(self, filename):
        download_command = "download %s" % filename.replace(' ', '\x01')
        if '\\' in filename:
            download_command = "download %s" % '/'.join(filename.split('\\')).replace(' ', '\x01')
        self.executeTransfileCommand(self.escape(download_command))

    def suspendCommand(self):
        self.executeCommand("suspend")

    def resumeCommand(self):
        self.executeCommand("resume")

    def playCommand(self, filename):
        play_command = "play %s" % filename.replace(' ', '\x01')
        if '\\' in filename:
            play_command = "play %s" % '/'.join(filename.split('\\')).replace(' ', '\x01')
        self.executeCommand(self.escape(play_command))

    def abortCommand(self):
        self.executeCommand("abort")

    def feedholdCommand(self):
        if self.stream:
            self.executeSingleCharCommand(ord('!'))

    def toggleFeedholdCommand(self, holding):
        if self.stream:
            if holding:
                self.executeSingleCharCommand(ord('~'))
            else:
                self.executeSingleCharCommand(ord('!'))

    def cyclestartCommand(self):
        if self.stream:
            self.executeSingleCharCommand(ord('~'))

    def estopCommand(self):
        if self.stream:
            self.executeSingleCharCommand(0x18)

    # ----------------------------------------------------------------------
    def hardResetPre(self):
        #self.stream.send(b"reset\n")
        self.executeMultiCharCommand(b"reset\n")

    def hardResetAfter(self):
        time.sleep(6)

    def parseBracketAngle(self, line,):
        # <Idle|MPos:68.9980,-49.9240,40.0000,12.3456|WPos:68.9980,-49.9240,40.0000,5.3|F:12345.12,100.0|S:1.2,100.0|T:1|L:0>
        # F: Feed, overide | S: Spindle RPM
        ln = line[1:-1]  # strip off < .. >

        # split fields
        l = ln.split('|')

        # strip off status
        CNC.vars["state"] = l[0]

        # strip of rest into a dict of name: [values,...,]
        d = {a: [float(y) for y in b.split(',')] for a, b in [x.split(':') for x in l[1:]]}
        if 'C' in d:
            CNC.vars["MachineModel"] = int(d['C'][0])
            CNC.vars["FuncSetting"] = int(d['C'][1])
            CNC.vars["inch_mode"] = int(d['C'][2])
            CNC.vars["absolute_mode"] = int(d['C'][3])

        if(CNC.vars["inch_mode"] != 999):
            if (CNC.vars["inch_mode"] == 1):
                CNC.UnitScale = 25.4
            else:
                CNC.UnitScale = 1
        else:
            CNC.UnitScale = 1
        CNC.vars["mx"] = float(d['MPos'][0]) * CNC.UnitScale
        CNC.vars["my"] = float(d['MPos'][1]) * CNC.UnitScale
        CNC.vars["mz"] = float(d['MPos'][2]) * CNC.UnitScale
        if len(d['MPos']) > 3:
            CNC.vars["ma"] = float(d['MPos'][3])
        else:
            CNC.vars["ma"] = 0.0
        CNC.vars["wx"] = float(d['WPos'][0]) * CNC.UnitScale
        CNC.vars["wy"] = float(d['WPos'][1]) * CNC.UnitScale
        CNC.vars["wz"] = float(d['WPos'][2]) * CNC.UnitScale
        if len(d['WPos']) > 3:
            CNC.vars["wa"] = float(d['WPos'][3])
        else:
            CNC.vars["wa"] = 0.0
        CNC.vars["wcox"] = round(CNC.vars["mx"] - CNC.vars["wx"], 3)
        CNC.vars["wcoy"] = round(CNC.vars["my"] - CNC.vars["wy"], 3)
        CNC.vars["wcoz"] = round(CNC.vars["mz"] - CNC.vars["wz"], 3)
        CNC.vars["wcoa"] = round(CNC.vars["mz"] - CNC.vars["wz"], 3)
        if 'F' in d:
           CNC.vars["curfeed"] = float(d['F'][0])
           CNC.vars["tarfeed"] = float(d['F'][1])
           CNC.vars["OvFeed"]  = int(d['F'][2])
        if 'S' in d:
            CNC.vars["curspindle"]  = float(d['S'][0])
            CNC.vars["tarspindle"]  = float(d['S'][1])
            CNC.vars["OvSpindle"]   = float(d['S'][2])
            if len(d['S']) > 3:
                CNC.vars["vacuummode"] = int(d['S'][3])
            if len(d['S']) > 4:
                CNC.vars["spindletemp"] = float(d['S'][4])
            if len(d['S']) > 5:
                CNC.vars["powertemp"] = float(d['S'][5])
            if len(d['S']) > 6:
                CNC.vars["blowingmode"] = float(d['S'][6])
            if len(d['S']) > 7:
                CNC.vars["bedcleanmode"] = float(d['S'][7])
            if len(d['S']) > 8:
                CNC.vars["extoutmode"] = float(d['S'][8])
        if 'T' in d:
            CNC.vars["tool"] = int(d['T'][0])
            CNC.vars["tlo"] = float(d['T'][1])
            if len(d['T']) > 2:
                CNC.vars["target_tool"] = int(d['T'][2])
            else:
                CNC.vars["target_tool"] = -1
        else:
            CNC.vars["tool"] = -1
            CNC.vars["tlo"] = 0.0
            CNC.vars["target_tool"] = -1
        if 'W' in d:
            CNC.vars["wpvoltage"] = float(d['W'][0])
        if 'L' in d:
            CNC.vars["lasermode"]  = int(d['L'][0])
            CNC.vars["laserstate"] = int(d['L'][1])
            CNC.vars["lasertesting"] = int(d['L'][2])
            CNC.vars["laserpower"] = float(d['L'][3])
            CNC.vars["laserscale"] = float(d['L'][4])
        if 'P' in d:
            CNC.vars["playedlines"] = int(d['P'][0])
            CNC.vars["playedpercent"] = int(d['P'][1])
            CNC.vars["playedseconds"] = int(d['P'][2])
        else:
            # not playing file
            CNC.vars["playedlines"] = -1

        if 'A' in d:
            CNC.vars["atc_state"] = int(d['A'][0])
        else:
            CNC.vars["atc_state"] = 0

        if 'O' in d:
            CNC.vars["max_delta"] = float(d['O'][0])
        else:
            CNC.vars["max_delta"] = 0.0

        if 'H' in d:
            CNC.vars["halt_reason"] = int(d['H'][0])


        self.posUpdate = True

    def parseBigParentheses(self, line):
        # {S:0,5000|L:0,0|F:1,0|V:0,1|G:0|T:0|E:0,0,0,0,0,0|P:0,0|A:1,0}
        ln = line[1:-1]  # strip off < .. >

        # split fields
        l = ln.split('|')

        # strip of rest into a dict of name: [values,...,]
        d = {a: [int(y) for y in b.split(',')] for a, b in [x.split(':') for x in l]}
        if 'A' in d:
            CNC.vars["st_atc_home"] = int(d['A'][0])
            CNC.vars["st_tool_sensor"] = int(d['A'][1])
        if 'C' in d:
            CNC.vars["sw_wp_charge_pwr"] = int(d['C'][0])
        if 'E' in d:
            CNC.vars["st_x_min"] = int(d['E'][0])
            CNC.vars["st_x_max"] = int(d['E'][1])
            CNC.vars["st_y_min"] = int(d['E'][2])
            CNC.vars["st_y_max"] = int(d['E'][3])
            CNC.vars["st_z_max"] = int(d['E'][4])
            CNC.vars["st_cover"] = int(d['E'][5])
            if len(d['E']) > 6:
                CNC.vars["st_a_max"] = int(d['E'][6])
            if len(d['E']) > 7:
                CNC.vars["st_c_max"] = int(d['E'][7])
        if 'F' in d:
            CNC.vars["sw_spindlefan"] = int(d['F'][0])
            CNC.vars["sl_spindlefan"] = int(d['F'][1])
        if 'G' in d:
            CNC.vars["sw_light"] = int(d['G'][0])
            if len(d['G']) > 1:
                CNC.vars["st_ExtInput"] = int(d['G'][2])
                CNC.vars["sw_ExtOut"] = int(d['G'][3])
                CNC.vars["sl_ExtOut"] = int(d['G'][4])
        if 'I' in d:
            CNC.vars["st_e_stop"] = int(d['I'][0])
        if 'L' in d:
            CNC.vars["sw_laser"]  = int(d['L'][0])
            CNC.vars["sl_laser"]  = int(d['L'][1])
        if 'P' in d:
            CNC.vars["st_probe"] = int(d['P'][0])
            CNC.vars["st_calibrate"] = int(d['P'][1])
        if 'R' in d:
            CNC.vars["sw_air"] = int(d['R'][0])
        if 'S' in d:
            CNC.vars["sw_spindle"] = int(d['S'][0])
            CNC.vars["sl_spindle"] = int(d['S'][1])
        if 'T' in d:
            CNC.vars["sw_tool_sensor_pwr"] = int(d['T'][0])
        if 'V' in d:
            CNC.vars["sw_vacuum"] = int(d['V'][0])
            CNC.vars["sl_vacuum"] = int(d['V'][1])
        if 'RSSI' in d:
            CNC.vars["RSSI"] = int(d['RSSI'][0])



        self.diagnoseUpdate = True

    # ----------------------------------------------------------------------
    def help(self, event=None):
        webbrowser.open(WIKI, new=2)

    # ----------------------------------------------------------------------
    # Open serial port or wifi connect
    # ----------------------------------------------------------------------
    def open(self, conn_type, address):
        # init connection
        if conn_type == CONN_USB:
            self.stream = self.usb_stream
        else:
            self.stream = self.wifi_stream

        if self.stream.open(address):
            CNC.vars["state"] = CONNECTED
            CNC.vars["color"] = STATECOLOR[CNC.vars["state"]]
            self.log.put((self.MSG_NORMAL, 'Connected to machine!'))
            self._gcount = 0
            self._alarm = True
            try:
                self.clearRun()
            except:
                self.log.put((self.MSG_ERROR, 'Controller clear thread error!'))
                return False
            self.thread = threading.Thread(target=self.streamIO)
            self.thread.start()
            return True
        else:
            self.log.put((self.MSG_ERROR, 'Connection Failed!'))
            return False

    # ----------------------------------------------------------------------
    # Close connection port
    # ----------------------------------------------------------------------
    def close(self):
        if self.stream is None: return
        try:
            self.stopRun()
        except:
            self.log.put((self.MSG_ERROR, 'Controller stop thread error!'))
        self._runLines = 0
        time.sleep(0.5)
        self.thread = None
        try:
            self.stream.close()
        except:
            self.log.put((self.MSG_ERROR, 'Controller close stream error!'))
        self.stream = None
        CNC.vars["state"] = NOT_CONNECTED
        CNC.vars["color"] = STATECOLOR[CNC.vars["state"]]
        CNC.vars["playedlines"] = 0
    # ----------------------------------------------------------------------
    def stopRun(self):
        self.stop.set()

    # ----------------------------------------------------------------------
    def clearRun(self):
        self.stop.clear()

    # ----------------------------------------------------------------------
    # Send to controller a gcode or command
    # WARNING: it has to be a single line!
    # ----------------------------------------------------------------------
    def sendGCode(self, cmd):
        self.executeCommand(cmd)

    # ----------------------------------------------------------------------
    def sendHex(self, hexcode):
        if self.stream is None: return
        #self.stream.send(chr(int(hexcode, 16)))
        self.executeMultiCharCommand(chr(int(hexcode, 16)))
        self.stream.flush()

    def viewStatusReport(self, sio_status):
        if self.loadNUM == 0 and self.sendNUM == 0:
            self.executeSingleCharCommand(ord('?'))
            self.sio_status = sio_status

    def viewDiagnoseReport(self, sio_diagnose):
        if self.loadNUM == 0 and self.sendNUM == 0:
            self.executeMultiCharCommand(b"diagnose\n")
            self.sio_diagnose = sio_diagnose

    # ----------------------------------------------------------------------
    def hardReset(self):
        self.busy()
        if self.stream is not None:
            self.hardResetPre()
            self.openClose()
            self.hardResetAfter()
        self.openClose()
        self.stopProbe()
        self._alarm = False
        CNC.vars["_OvChanged"] = True  # force a feed change if any
        self.notBusy()

    def unlock(self, clearAlarm=True):
        if clearAlarm:
            self._alarm = False
            app = App.get_running_app()
            app.root.alarm_triggered = False
        self.sendGCode("$X")

    def home(self, event=None):
        self.sendGCode("$H")

    def viewSettings(self):
        pass

    def viewParameters(self):
        self.sendGCode("$#")

    def viewState(self):
        self.sendGCode("$G")

    def viewBuild(self):
        #self.stream.send(b"version\n")
        self.executeMultiCharCommand(b"version\n")
        self.sendGCode("$I")

    def viewStartup(self):
        pass

    def checkGcode(self):
        pass

    def grblHelp(self):
        #self.stream.send(b"help\n")
        self.executeMultiCharCommand(b"help\n")

    def grblRestoreSettings(self):
        pass

    def grblRestoreWCS(self):
        pass

    def grblRestoreAll(self):
        pass

    # ----------------------------------------------------------------------
    def jog(self, _dir, step, ABAxis = False):
        if not ABAxis:
            self.executeCommand("G91G0{}{:.6f}".format(_dir, float(step)/CNC.UnitScale))
        else:
            self.executeCommand("G91G0{}{:.6f}".format(_dir, float(step)))

    # ----------------------------------------------------------------------
    def goto(self, x=None, y=None, z=None):
        cmd = "G90G0"
        if x is not None: cmd += "X%g" % (x)
        if y is not None: cmd += "Y%g" % (y)
        if z is not None: cmd += "Z%g" % (z)
        self.sendGCode("%s" % (cmd))

    def wcsSetA(self, a = None):
        cmd = "G92.4"
        if a is not None and abs(a) < 3600000.0: cmd += "A" + str(round(a, 5))

        self.sendGCode(cmd)

    def shrinkA(self):
        self.sendGCode("G92.4 A0 S0")

    def RapMoveA(self, a = None):
        cmd = "G90G0"
        cmd += "X"  + str(round(a, 5))
        cmd = "G92.4"
        cmd += " A " + str(round(a, 5)) + " R0"
        if a is not None and abs(a) < 3600000.0: self.sendGCode(cmd)

    def wcsSet(self, x = None, y = None, z = None, a = None):
        cmd = "G10L20P0"

        pos = ""
        if x is not None and abs(x) < 10000.0: pos += "X" + str(round(x/CNC.UnitScale, 4))
        if y is not None and abs(y) < 10000.0: pos += "Y" + str(round(y/CNC.UnitScale, 4))
        if z is not None and abs(z) < 10000.0: pos += "Z" + str(round(z/CNC.UnitScale, 4))
        if a is not None and abs(a) < 3600000.0: pos += "A" + str(round(a, 4))
        cmd += pos

        self.sendGCode(cmd)

    def wcsSetM(self, x = None, y = None, z = None, a = None):
        # p = WCS.index(CNC.vars["WCS"])
        cmd = "G10L2P0"

        pos = ""
        if x is not None and abs(x) < 10000.0: pos += "X" + str(round(x/CNC.UnitScale, 4))
        if y is not None and abs(y) < 10000.0: pos += "Y" + str(round(y/CNC.UnitScale, 4))
        if z is not None and abs(z) < 10000.0: pos += "Z" + str(round(z/CNC.UnitScale, 4))
        if a is not None and abs(a) < 3600000.0: pos += "A" + str(round(a, 4))
        cmd += pos

        self.sendGCode(cmd)

    def feedHold(self, event=None):
        if event is not None and not self.acceptKey(True): return
        if self.stream is None: return
        self.executeSingleCharCommand(ord('!'))
        self.stream.flush()
        self._pause = True

    def resume(self, event=None):
        if event is not None and not self.acceptKey(True): return
        if self.stream is None: return
        self.executeSingleCharCommand(ord('~'))
        self.stream.flush()
        self._alarm = False
        self._pause = False

    def pause(self, event=None):
        if self.stream is None: return
        if self._pause:
            self.resume()
        else:
            self.feedHold()

    # ----------------------------------------------------------------------
    def parseLine(self, line):
        if not line:
            return True
        elif line[0] == "<":
            self.parseBracketAngle(line)
            self.sio_status = False
        elif line[0] == "{":
            self.parseBigParentheses(line)
            self.sio_diagnose = False
        elif line[0] == "#":
            self.log.put((self.MSG_INTERIOR, line))
        elif "error" in line.lower() or "alarm" in line.lower():
            self.log.put((self.MSG_ERROR, line))
        else:
            self.log.put((self.MSG_NORMAL, line))

    # ----------------------------------------------------------------------
    def g28Command(self):
        self.sendGCode("G28.1")  # FIXME: ???

    def g30Command(self):
        self.sendGCode("G30.1")  # FIXME: ???

    # ----------------------------------------------------------------------
    def emptyQueue(self):
        while self.queue.qsize() > 0:
            try:
                self.queue.get_nowait()
            except Empty:
                break

    def pauseStream(self, wait_s):
        self.pausing = True
        time.sleep(wait_s)
        self.paused = True
        self.pausing = False

    def resumeStream(self):
        self.paused = False
        self.pausing = False

    def process_packet(self):
        """
        Process a complete packet after it has been received
        """
        if len(self.packetData) < 2:
            self.packetData.clear()
            return None  # Not enough data for CRC check
        # CRC check
        calcCRC = self.crc16_ccitt(self.packetData, len(self.packetData) - 2)
        receivedCRC = (self.packetData[-2] << 8) | self.packetData[-1]
        if calcCRC == receivedCRC:
            if len(self.packetData) >= 3:
                return self.packetData[2]
            else:
                self.packetData.clear()
                return None
        else:
            self.packetData.clear()
            return None

    # ----------------------------------------------------------------------
    # thread performing I/O on serial line
    # ----------------------------------------------------------------------
    def streamIO(self):
        self.sio_status = False
        self.sio_diagnose = False
        dynamic_delay = 0.1
        tr = td = time.time()
        line = b''
        last_error = ''

        while not self.stop.is_set():
            if not self.stream or self.paused:
                time.sleep(1)
                continue
            t = time.time()
            # refresh machine position?
            running = self.sendNUM > 0 or self.loadNUM > 0 or self.pausing
            try:
                app = App.get_running_app()
                if not running and app.root.echosended:
                    if t - tr > STREAM_POLL:
                        self.viewStatusReport(True)
                        tr = t
                    if self.diagnosing and t - td > DIAGNOSE_POLL:
                        self.viewDiagnoseReport(True)
                        td = t
                else:
                    tr = t
                    td = t

                if self.stream.waiting_for_recv():
                    if app.root.oldfirmware == False:
                        received = [bytes([b]) for b in self.stream.recv()]
                        for byte in received:
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
                                        cmd = self.process_packet()
                                        if cmd == PTYPE_STATUS_RES or cmd == PTYPE_DIAG_RES or  cmd == PTYPE_NORMAL_INFO:
                                            line = self.packetData[3:-3]    #去除报文前面的长度+报文类型字段，去除报文最后的CRC字段
                                            self.parseLine(line.decode(errors='ignore'))
                                        elif cmd == PTYPE_LOAD_FINISH:
                                            self.loadEOF = True
                                        elif cmd == PTYPE_LOAD_ERROR:
                                            self.loadERR = True
                                        else:
                                            line = self.packetData[3:-3]  # 去除报文前面的长度+报文类型字段，去除报文最后的CRC字段
                                            if self.loadNUM == 0:
                                                self.parseLine(line.decode(errors='ignore'))
                                            else:
                                                # 将字节串解码为字符串
                                                decoded_line = line.decode(errors='ignore')
                                                # 使用正则表达式去除以"<"开头，以">"结尾的部分
                                                cleaned_line = re.sub(r'<.*?>', '', decoded_line)
                                                # 去除多余的空格（如果需要）
                                                cleaned_line = cleaned_line.strip()
                                                if len(cleaned_line) != 0:
                                                    split_lines = cleaned_line.replace('\r\n', '\n').split('\n')
                                                    for line2 in split_lines:
                                                        self.load_buffer.put(line2)
                                                        self.load_buffer_size += len(line2) + 1
                        dynamic_delay = 0
                    else:
                        received = [bytes([b]) for b in self.stream.recv()]
                        for c in received:
                            if c == EOT or c == CAN:
                                # Ctrl + Z means transmission complete, Ctrl + D means transmission cancel or error
                                if len(line) > 0:
                                    self.load_buffer.put(line.decode(errors='ignore'))
                                    if self.loadNUM > 0:
                                        self.load_buffer_size += len(line)
                                line = b''
                                if c == EOT:
                                    self.loadEOF = True
                                else:
                                    self.loadERR = True
                            else:
                                if c == b'\n':
                                    # (line.decode(errors='ignore'))
                                    if self.loadNUM == 0 or '|MPos' in line.decode(errors='ignore'):
                                        self.parseLine(line.decode(errors='ignore'))
                                    else:
                                        # 将字节串解码为字符串
                                        decoded_line = line.decode(errors='ignore')
                                        # 使用正则表达式去除以"<"开头，以">"结尾的部分
                                        cleaned_line = re.sub(r'<.*?>', '', decoded_line)
                                        # 去除多余的空格（如果需要）
                                        cleaned_line = cleaned_line.strip()
                                        if len(cleaned_line) != 0:
                                            self.load_buffer.put(cleaned_line)
                                            self.load_buffer_size += len(cleaned_line) + 1
                                    line = b''
                                else:
                                    line += c
                        dynamic_delay = 0
                else:
                    if self.sendNUM == 0 and self.loadNUM == 0:
                        dynamic_delay = (0.1 if dynamic_delay >= 0.09 else dynamic_delay + 0.01)
                    else:
                        dynamic_delay = 0

            except:
                if last_error != str(sys.exc_info()[1]):
                    self.log.put((Controller.MSG_ERROR, str(sys.exc_info()[1])))
                    last_error = str(sys.exc_info()[1])

            if dynamic_delay > 0:
                time.sleep(dynamic_delay)





"""
                if self.stream.waiting_for_recv():
                    received = [bytes([b]) for b in self.stream.recv()]
                    for c in received:
                        if c == EOT or c == CAN:
                            # Ctrl + Z means transmission complete, Ctrl + D means transmission cancel or error
                            if len(line) > 0:
                                self.load_buffer.put(line.decode(errors='ignore'))
                                if self.loadNUM > 0:
                                    self.load_buffer_size += len(line)
                            line = b''
                            if c == EOT:
                                self.loadEOF = True
                            else:
                                self.loadERR = True
                        else:
                            if c == b'\n':
                                # (line.decode(errors='ignore'))
                                if self.loadNUM == 0 or '|MPos' in line.decode(errors='ignore'):
                                    self.parseLine(line.decode(errors='ignore'))
                                else:
                                    # 将字节串解码为字符串
                                    decoded_line = line.decode(errors='ignore')
                                    # 使用正则表达式去除以"<"开头，以">"结尾的部分
                                    cleaned_line = re.sub(r'<.*?>', '', decoded_line)
                                    # 去除多余的空格（如果需要）
                                    cleaned_line = cleaned_line.strip()
                                    if len(cleaned_line) != 0:
                                        self.load_buffer.put(cleaned_line)
                                        self.load_buffer_size += len(cleaned_line) + 1
                                line = b''
                            else:
                                line += c
                    dynamic_delay = 0
                else:
                    if self.sendNUM == 0 and self.loadNUM == 0:
                        dynamic_delay = (0.1 if dynamic_delay >= 0.09 else dynamic_delay + 0.01)
                    else:
                        dynamic_delay = 0

            except:
                line = b''
                if last_error != str(sys.exc_info()[1]) :
                    self.log.put((Controller.MSG_ERROR, str(sys.exc_info()[1])))
                    last_error = str(sys.exc_info()[1])

            if dynamic_delay > 0:
                time.sleep(dynamic_delay)
"""



