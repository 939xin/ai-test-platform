# -*- coding: utf-8 -*-
"""GET 测试用例 - 接口自动化测试"""
import pytest
import requests
import json


class TestAPICase:
    """GET 测试用例"""

    def test_case(self):
        url = '/api/get-endpoint'

        # 请求头
        headers = {}

        # 认证处理

        response = requests.get(url, headers=headers)

        # 断言


if __name__ == '__main__':
    pytest.main([__file__, '-v'])