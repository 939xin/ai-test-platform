# -*- coding: utf-8 -*-
"""
=============================================================================
  123 - Web 自动化测试
=============================================================================
【用例编号】   TC_WEB_0023
【模　　块】   (请填写模块)
【用例标题】   123
【优　先级】   P2
【前置条件】   浏览器: Chrome | 起始URL: www.baidu.com
【是否可自动】 是
=============================================================================
"""
import pytest
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


@pytest.fixture
def driver():
    """创建浏览器驱动"""
    options = webdriver.ChromeOptions()
    drv = webdriver.Chrome(options=options)
    drv.maximize_window()
    yield drv
    drv.quit()


class TestWebCase:
    """123 / TC_WEB_0023"""

    def test_case(self, driver):
        """执行 Web 测试用例: 123"""
        logging.info('=' * 60)
        logging.info('开始执行: 123')
        logging.info('用例编号: TC_WEB_0023')
        logging.info('前置条件: 浏览器: Chrome | 起始URL: www.baidu.com')
        logging.info('=' * 60)

        # ------------------------------------------------------------------
        # Step 1: 打开浏览器，访问 http://www.baidu.com
        # 预期: 页面 http://www.baidu.com 成功加载
        # ------------------------------------------------------------------
        driver.get('http://www.baidu.com')
        logging.info('Step 1: 打开浏览器，访问 http://www.baidu.com')

        # ------------------------------------------------------------------
        # Step 2: 等待 3.0 秒
        # 预期: 等待完成，页面无异常
        # ------------------------------------------------------------------
        import time; time.sleep(1)
        logging.info('Step 2: 等待 3.0 秒')

        logging.info('=' * 60)
        logging.info('用例执行完成: 123')
        logging.info('=' * 60)

