# -*- coding: utf-8 -*-
"""搜索 - Web 自动化测试"""
import pytest
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
    """搜索"""

    def test_case(self, driver):
        driver.get('https://www.baidu.com/')

        elem = driver.find_element(By.ID, 'chat-textarea')
        elem.clear()
        elem.send_keys('123')

        driver.find_element(By.ID, 'chat-submit-button').click()

        import time; time.sleep(1)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])