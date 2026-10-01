# -*- coding: utf-8 -*-
"""GET 测试用例 - 接口自动化测试"""
import pytest
import requests
import json
import logging

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class TestAPICase:
    """GET 测试用例"""

    def test_case(self):
        """执行接口测试用例: GET 测试用例"""
        logging.info('开始执行用例: GET 测试用例')
        url = '/api/get-endpoint'

        # 请求头
        headers = {}
        logging.info(f'请求头: {headers}')

        # 认证处理

        response = requests.get(url, headers=headers)

        # 记录响应
        logging.info(f'响应状态码: {response.status_code}')
        logging.info(f'响应时间: {response.elapsed.total_seconds() * 1000:.0f}ms')

        # 断言

        logging.info('用例执行通过')


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--log-cli-level=INFO'])