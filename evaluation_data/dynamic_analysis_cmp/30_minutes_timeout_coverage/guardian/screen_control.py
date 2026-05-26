# -*- coding: utf-8 -*-
"""
安卓手机操控
"""
import logging
import time
import os
import random
import base64
import subprocess as subp

DEVICE = "emulator-5554"

class AndroidController:
    """
    安卓手机控制
    """

    def __init__(self, device=DEVICE):
        self.device = device
        self.upperbar = 0
        self.subbar = 0
        self.sleep_time = 0.1

    def start_app(self, app_pkg_name, wait=2):
        """
        启动app
        :param app_pkg_name:
        :return:
        """
        # 每次打开前先关闭，同时保证处在消息界面
        self.stop_app(app_pkg_name)
        subp.Popen(
            f"adb -s {self.device} shell monkey -p {app_pkg_name} -c android.intent.category.LAUNCHER 1",
            shell=True,
            stdout=subp.DEVNULL,
            stderr=subp.DEVNULL,
        )
        logging.debug("start app begin...")
        time.sleep(wait)
        logging.debug("start app end...")

    def stop_app(self, app_pkg_name):
        """
        app杀进程
        :param app_pkg_name:
        :return:
        """
        subp.call(
            f"adb -s {self.device} shell am force-stop {app_pkg_name}",
            shell=True,
            stdout=subp.DEVNULL,
            stderr=subp.DEVNULL,
        )

    def click(self, x, y, wait_time=0.1):
        """
        点击坐标（x,y）
        :param x:
        :param y:
        :return:
        """
        if x < 0 and y < 0:
            self.back()
            return
        subp.call(
            f"adb -s {self.device} shell input tap {int(x)} {int(y) + self.upperbar}",
            shell=True,
            stdout=subp.DEVNULL,
            stderr=subp.DEVNULL,
        )
        time.sleep(wait_time)

    def home(self):
        """
        home键
        :return:
        """
        subp.call(
            f"adb -s {self.device} shell input keyevent KEYCODE_HOME",
            shell=True,
            stdout=subp.DEVNULL,
            stderr=subp.DEVNULL,
        )

    def back(self):
        """
        返回键
        :return:
        """
        subp.call(
            f"adb -s {self.device} shell input keyevent KEYCODE_BACK",
            shell=True,
            stdout=subp.DEVNULL,
            stderr=subp.DEVNULL,
        )
        time.sleep(self.sleep_time)

    def swipe(self, fx, fy, tx, ty, steps=40):
        subp.call(
            f"adb -s {self.device} shell input swipe {int(fx)} {int(fy)} {int(tx)} {int(ty)}",
            shell=True,
            stdout=subp.DEVNULL,
            stderr=subp.DEVNULL,
        )
        time.sleep(self.sleep_time)

    def input(self, text="PKU", clear=True):
        try:
            # TODO: deal with clear here
            print(text)
            text = text.replace(" ", "\\ ")
            os.system(f'adb -s {self.device} shell input text "{text}"')
            time.sleep(0.2)
        except:
            return False
        return True

    def dump(self):
        dump = ""

        subp.call(
            f"adb -s {self.device} shell uiautomator dump /sdcard/dump.xml",
            shell=True,
            stdout=subp.DEVNULL,
            stderr=subp.DEVNULL,
        )

        pull = subp.Popen(
            f"adb -s {self.device} shell cat /sdcard/dump.xml",
            shell=True,
            stdout=subp.PIPE,
        )

        real_dump = pull.communicate()[0].decode().strip()
        if real_dump and real_dump.strip():
            dump = real_dump

        return dump

    def app_info(self):
        pkg, activity = "", ""
        get_current_focus = subp.Popen(
            f"adb -s {self.device} shell dumpsys window | grep mCurrentFocus",
            shell=True,
            stdout=subp.PIPE,
        )
        communicate = get_current_focus.communicate()[0].decode().strip()
        for _split in communicate.split():
            if "/" in _split:
                if "}" in _split:
                    _split = _split.replace("}", "")
                pkg, activity = _split.split("/")

        return pkg, activity

    def get_activity_name(self):
        pkg, activity = self.app_info()
        full_activity = activity
        if pkg not in full_activity:
            full_activity = pkg + activity
        return full_activity


if __name__ == "__main__":
    print(AndroidController("emulator-5554").dump())
