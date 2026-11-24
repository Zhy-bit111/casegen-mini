#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""被测样例实现：故意保留 3 处校验缺失，用来验证「自动生成的用例是否真能抓到缺陷」。

这不是一个正确的接口实现，而是一个带已知缺陷的靶子。
用例的价值，恰恰体现在它能把这 3 处缺失逐条指出来。

已知缺陷：
  1. age 未校验类型与范围（"abc" / -1 / 999 都会被受理）
  2. role 未校验枚举（"__invalid_enum__" 会被受理）
  3. name 未校验最大长度（超 32 字符会被受理）
"""


def create_user(payload):
    """纯函数，不启 HTTP 服务、不连数据库 —— 让用例生成与判定可以完全离线复现。"""
    if not isinstance(payload, dict):
        return {"status": 400, "error": "payload must be object"}

    name = payload.get("name")
    if not name or not isinstance(name, str):
        return {"status": 400, "error": "name required"}

    # ↓↓↓ 缺陷 1/2/3：以下三个字段都没有做校验 ↓↓↓
    return {
        "status": 200,
        "data": {
            "id": 1,
            "name": name,
            "age": payload.get("age"),
            "role": payload.get("role"),
        },
    }
