from ftplib import FTP
from ftplib import error_perm
import socket
import os
import time
from utils.time_utils import run_time
import sys
import math
from utils import file_util

"""
FTP Manager
"""


class FTPManager(object):
    """
    FTP Manager
    """

    def __init__(self, ftp_ip, ftp_port, ftp_user, ftp_pwd):
        self.ftp_ip = ftp_ip
        self.ftp_port = ftp_port
        self.ftp_user = ftp_user
        self.ftp_pwd = ftp_pwd

    def ftp_connect(self):
        """
        connect ftp
        :return:
        """
        ftp = FTP()
        ftp.connect(host=self.ftp_ip, port=self.ftp_port)
        ftp.encoding = 'utf-8'

        try:
            ftp.login(self.ftp_user, self.ftp_pwd)
            self.db_log.info(
                '[{}]login ftp {}'.format(
                    self.ftp_user,
                    ftp.getwelcome()))  # print welcome info

        except(socket.error, socket.gaierror):  # ftp connection error
            self.db_log.warn(
                "ERROR: cannot connect [{}:{}]".format(
                    self.ftp_ip, self.ftp_port))
            return None

        except error_perm:  # user login error
            self.db_log.warn("ERROR: user Authentication failed ")
            return None
        except Exception as e:
            print(e)
            return None
        return ftp

    @run_time
    def upload_file(self, ftp: FTP, remotepath: str,
                    localpath: str, file: str):
        """
         # 从本地上传文件到ftp
        :param ftp: ftp对象
        :param remotepath: ftp远程路径
        :param localpath: 本地
        :return:
        """
        flag = False
        buffer_size = 10240  # 默认是8192
        print(ftp.getwelcome())  # 显示登录ftp信息

        fp = open(os.path.join(localpath, file), 'rb')

        try:
            ftp.cwd(remotepath)  # 进入远程目录
            self.db_log.info(
                "found folder [{}] in ftp server, upload processing.".format(remotepath))
            print('进入目录', ftp.pwd())
            # 将传输模式改为二进制模式 ,避免提示 ftplib.error_perm: 550 SIZE not allowed in
            # ASCII
            ftp.voidcmd('TYPE I')
            ftp.storbinary('STOR ' + file, fp, buffer_size)
            ftp.set_debuglevel(0)
            self.db_log.info("上传文件 [{}] 成功".format(file))
            flag = True
        except error_perm as e:
            self.db_log.warn('文件[{}]传输有误,{}'.format(file, str(e)))
        except TimeoutError:
            self.db_log.warn('文件[{}]传输超时'.format(file))
            pass
        except Exception as e:
            self.db_log.warn('文件[{}]传输异常'.format(file, str(e)))
            pass
        finally:
            fp.close()

        return {'file_name': file, 'flag': flag}

    def download_file(self, ftp_file_path, dst_file_path):
        """
        从ftp下载文件到本地
        :param ftp_file_path: ftp下载文件
        :param dst_file_path: 本地存放
        :return:
        """
        buffer_size = 10240  # 默认是8192
        ftp = self.ftp_connect()
        print(ftp.getwelcome())  # 显示登录ftp信息

        # 将传输模式改为二进制模式 ,避免提示 ftplib.error_perm: 550 SIZE not allowed in ASCII
        ftp.voidcmd('TYPE I')
        remote_file_size = ftp.size(ftp_file_path)  # 文件总大小

        print('remote filesize [{}]'.format(remote_file_size))
        cmpsize = 0  # 下载文件初始大小
        lsize = 0
        # check local file isn't exists and get the local file size
        if os.path.exists(dst_file_path):
            lsize = os.stat(dst_file_path).st_size
        if lsize >= remote_file_size:
            print('local file is bigger or equal remote file')
            return
        start = time.time()
        conn = ftp.transfercmd('RETR {0}'.format(ftp_file_path), lsize)

        f = open(dst_file_path, "ab")
        while True:
            data = conn.recv(buffer_size)
            if not data:
                break
            f.write(data)
            cmpsize += len(data)
            self.progressbar(cmpsize, remote_file_size)
            # print(
            #      '\b'*30, 'download process:%.2f%%' %
            #     (float(cmpsize) / remote_file_size * 100))
            # ftp.retrbinary(
            #     'RETR {0}'.format(ftp_file_path),
            #     f.write,
            #     buffer_size)
        f.close()
        try:
            ftp.voidcmd('NOOP')
            print('keep alive cmd success')
            ftp.voidresp()
            print('No loop cmd')
            conn.close()
            ftp.quit()
        except Exception as e:
            pass
        finally:
            end = time.time()
            print('consume time [{}]'.format(end - start))
            file_size = os.stat(dst_file_path).st_size
            print('local filesize [{}] md5:[{}]'.format(
                file_size, file_util.get_md5(dst_file_path)))

        def progressbar(cur, total):
            """
              进度条显示
              cur表示当前的数值，total表示总的数值。
            :param cur:
            :param total:
            :return:
            """
            percent = '{:.2%}'.format(cur / total)
            sys.stdout.write('\r')
            sys.stdout.write('[%-50s] %s' %
                             ('=' * int(math.floor(cur * 50 / total)), percent))
            sys.stdout.flush()
            if cur == total:
                sys.stdout.write('\n')


if __name__ == '__main__':
    host = "10.0.0.1"
    username = "test"
    password = "test"
    port = "21"
    ftp_file_path = "/data/an/1.zip"
    dst_file_path = "/data/tmp/1.zip"
    ftp = FTP_OPS(host=host, username=username, password=password, port=port)
    ftp.download_file(ftp_file_path=ftp_file_path, dst_file_path=dst_file_path)