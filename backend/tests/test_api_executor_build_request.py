"""build_request 单元测试：URL 拼接、变量解析、请求头替换。

build_request 是纯函数（只吃 dict + resolver），不发请求，
所以这里可以放心断言到具体字符串。
"""
from app.services.api_executor import build_request
from app.services.variable_resolver import VariableResolver


def _resolver(variables=None):
    return VariableResolver(global_vars={"base_url": "https://api.example.com", **(variables or {})})


def test_absolute_url_kept_as_is():
    method, url, headers, body, auth, _p = build_request(
        {"method": "get", "url": "https://other.example.com/x"}, {}, _resolver()
    )
    assert method == "GET"
    assert url == "https://other.example.com/x"


def test_relative_url_joined_with_env_base_url():
    _m, url, _h, _b, _a, _p = build_request(
        {"url": "/users/1"}, {"base_url": "https://api.example.com/"}, _resolver()
    )
    assert url == "https://api.example.com/users/1"


def test_base_url_variable_resolved_in_url():
    """${base_url} 要能解析，否则会拼出 https://base/${base_url}/x 这种垃圾地址。"""
    _m, url, _h, _b, _a, _p = build_request(
        {"url": "${base_url}/users"}, {"base_url": "https://api.example.com"}, _resolver()
    )
    assert url == "https://api.example.com/users"


def test_headers_variables_resolved():
    _m, _u, headers, _b, _a, _p = build_request(
        {"url": "https://x.com", "headers_json": {"X-Token": "${token}", "X-Fixed": "1"}},
        {},
        _resolver({"token": "abc"}),
    )
    assert headers["X-Token"] == "abc"
    assert headers["X-Fixed"] == "1"


def test_bearer_auth_fills_authorization_header():
    _m, _u, headers, _b, auth, _p = build_request(
        {"url": "https://x.com", "auth_type": "bearer", "auth_value": "${token}"},
        {},
        _resolver({"token": "abc"}),
    )
    assert headers["Authorization"] == "Bearer abc"
    assert auth is None


def test_query_params_resolved_and_returned():
    """params_json 要能解析变量（数据驱动时常写 ${id}），并原样交给 requests 编码。"""
    _m, _u, _h, _b, _a, params = build_request(
        {"url": "https://x.com", "params_json": {"delay_ms": "42", "token": "${token}"}},
        {},
        _resolver({"token": "abc"}),
    )
    assert params == {"delay_ms": "42", "token": "abc"}


def test_empty_and_blank_query_param_keys_skipped():
    _m, _u, _h, _b, _a, params = build_request(
        {"url": "https://x.com", "params_json": {"": "x", "  ": "y", "ok": "1"}},
        {},
        _resolver(),
    )
    assert params == {"ok": "1"}


def test_json_body_sets_content_type():
    _m, _u, headers, body, _a, _p = build_request(
        {"url": "https://x.com", "method": "POST", "body_type": "json", "body_content": '{"a":1}'},
        {},
        _resolver(),
    )
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert body == '{"a":1}'
