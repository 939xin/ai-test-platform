"""
数据库模型定义和初始化
使用 SQLite 存储所有测试用例、环境配置、执行结果
"""
import sqlite3
import os
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
DB_PATH = os.path.join(DB_DIR, 'test_tool.db')


def get_connection():
    """获取数据库连接"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")  # WAL 模式：读写不互斥，防止锁库
    conn.execute("PRAGMA busy_timeout=5000")  # 繁忙等待 5 秒
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_connection()
    cursor = conn.cursor()

    # 环境管理
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS environments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL DEFAULT '',
            description TEXT DEFAULT '',
            variables TEXT DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    ''')

    # 全局变量
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_variables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            value TEXT NOT NULL DEFAULT '',
            description TEXT DEFAULT '',
            environment_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE
        )
    ''')

    # 接口测试用例
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            url TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT 'GET',
            body_type TEXT DEFAULT 'none',
            body_content TEXT DEFAULT '',
            auth_type TEXT DEFAULT 'none',
            auth_value TEXT DEFAULT '',
            environment_id INTEGER,
            timeout INTEGER DEFAULT 30,
            is_relative_url INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE SET NULL
        )
    ''')

    # 接口请求头
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_headers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL DEFAULT '',
            enabled INTEGER DEFAULT 1,
            FOREIGN KEY (case_id) REFERENCES api_test_cases(id) ON DELETE CASCADE
        )
    ''')

    # 接口断言条件
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_assertions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            assertion_type TEXT NOT NULL DEFAULT 'status_code',
            target TEXT DEFAULT '',
            operator TEXT NOT NULL DEFAULT 'eq',
            expected_value TEXT NOT NULL DEFAULT '',
            enabled INTEGER DEFAULT 1,
            FOREIGN KEY (case_id) REFERENCES api_test_cases(id) ON DELETE CASCADE
        )
    ''')

    # Web 测试用例
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS web_test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            browser TEXT NOT NULL DEFAULT 'chrome',
            headless INTEGER DEFAULT 0,
            start_url TEXT DEFAULT '',
            environment_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE SET NULL
        )
    ''')

    # Web 测试步骤
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS web_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            step_order INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            input_value TEXT DEFAULT '',
            wait_seconds REAL DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            description TEXT DEFAULT '',
            FOREIGN KEY (case_id) REFERENCES web_test_cases(id) ON DELETE CASCADE
        )
    ''')

    # Web 步骤的元素定位信息
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS web_step_locators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            step_id INTEGER NOT NULL,
            locator_type TEXT NOT NULL DEFAULT 'xpath',
            locator_value TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (step_id) REFERENCES web_steps(id) ON DELETE CASCADE
        )
    ''')

    # 测试执行结果
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_type TEXT NOT NULL,
            case_id INTEGER NOT NULL,
            case_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            duration_ms REAL DEFAULT 0,
            executed_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            environment_name TEXT DEFAULT '',
            browser TEXT DEFAULT '',
            headless INTEGER DEFAULT 0
        )
    ''')

    # 执行结果详情（含日志、截图）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_result_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id INTEGER NOT NULL,
            step_order INTEGER DEFAULT 0,
            step_description TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pass',
            message TEXT DEFAULT '',
            screenshot_path TEXT DEFAULT '',
            request_url TEXT DEFAULT '',
            request_method TEXT DEFAULT '',
            request_headers TEXT DEFAULT '',
            request_body TEXT DEFAULT '',
            response_status INTEGER DEFAULT 0,
            response_headers TEXT DEFAULT '',
            response_body TEXT DEFAULT '',
            expected_value TEXT DEFAULT '',
            actual_value TEXT DEFAULT '',
            log_output TEXT DEFAULT '',
            FOREIGN KEY (result_id) REFERENCES test_results(id) ON DELETE CASCADE
        )
    ''')

    # 截图存储表（存储 Base64，用于报告嵌入）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_detail_id INTEGER,
            name TEXT NOT NULL DEFAULT '',
            image_base64 TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (result_detail_id) REFERENCES test_result_details(id) ON DELETE SET NULL
        )
    ''')

    conn.commit()
    conn.close()


# 常用 CRUD 操作封装
class DBManager:
    """数据库管理类，提供常用操作"""

    @staticmethod
    def execute(sql, params=None):
        conn = get_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            conn.commit()
            last_id = cursor.lastrowid
            return last_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def fetch_all(sql, params=None):
        conn = get_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def fetch_one(sql, params=None):
        conn = get_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def insert(table, data):
        # 过滤掉值为 None 的字段，让数据库默认值生效
        filtered = {k: v for k, v in data.items() if v is not None}
        keys = ', '.join(filtered.keys())
        placeholders = ', '.join(['?' for _ in filtered])
        values = list(filtered.values())
        return DBManager.execute(
            f"INSERT INTO {table} ({keys}) VALUES ({placeholders})",
            values
        )

    @staticmethod
    def get_raw_conn():
        """获取原始连接（用于多步事务操作）"""
        return get_connection()

    @staticmethod
    def update(table, data, where_clause, where_params=None):
        set_clause = ', '.join([f"{k}=?" for k in data.keys()])
        values = list(data.values())
        if where_params:
            values.extend(where_params)
        return DBManager.execute(
            f"UPDATE {table} SET {set_clause} WHERE {where_clause}",
            values
        )

    @staticmethod
    def delete(table, where_clause, params=None):
        return DBManager.execute(
            f"DELETE FROM {table} WHERE {where_clause}",
            params
        )
