#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""casegen-mini · schema 驱动的测试用例生成 + 三态判定（纯标准库，零依赖）

借鉴思路，但未复制任何代码：
  - keploy/keploy   : 从真实流量自动生成用例 → 本实现只从「接口契约」生成用例
  - schemathesis    : schema-driven 边界/异常变异 → 本实现做确定性变异，不做 property-based

明确不做的（讲取舍用）：eBPF 抓包、录制回放、随机/property-based 生成、
stateful 序列、多协议 parser、真实 HTTP 服务。只保留最小闭环：
    契约 → 用例 → 执行 → 三态判定 → 三级报告

用法：
  python casegen.py
  python casegen.py --spec specs/sample_api.json --out output/report.md
  python casegen.py --json output/results.json
  python casegen.py --fail-on-defect      # CI 里让「抓到缺陷」变成红灯（默认不启用）
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent


# ---------------- 1. 契约 ----------------

@dataclass
class FieldSpec:
    name: str
    type: str                       # str | int | bool | enum
    required: bool = True
    min: int | None = None          # int 下界 / str 最小长度
    max: int | None = None          # int 上界 / str 最大长度
    enum: list[str] = field(default_factory=list)
    example: Any = None


@dataclass
class ApiSpec:
    name: str
    method: str
    path: str
    fields: list[FieldSpec]
    success_status: int = 200
    reject_status: int = 400


def load_spec(path: str | Path) -> ApiSpec:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return ApiSpec(
        name=d["name"],
        method=d.get("method", "POST"),
        path=d.get("path", "/"),
        fields=[FieldSpec(**f) for f in d["fields"]],
        success_status=d.get("success_status", 200),
        reject_status=d.get("reject_status", 400),
    )


# ---------------- 2. 用例生成 ----------------

@dataclass
class Case:
    id: str
    mutation: str                   # 变异类型
    target: str                     # 作用的字段
    payload: dict
    expected_status: int
    rationale: str
    needs_human: bool = False       # 语义质量类，自动判据判不了


def happy_payload(spec: ApiSpec) -> dict:
    out: dict = {}
    for f in spec.fields:
        if f.example is not None:
            v = f.example
        elif f.type == "int":
            v = f.min if f.min is not None else 1
        elif f.type == "bool":
            v = True
        elif f.type == "enum":
            v = f.enum[0] if f.enum else "user"
        else:
            v = "tester"
        out[f.name] = v
    return out


WRONG_TYPE = {"int": "not_a_number", "str": 12345, "bool": "yes", "enum": 12345}


def generate_cases(spec: ApiSpec) -> list[Case]:
    """确定性变异：正常 / 边界 / 缺字段 / 错类型 / 空值 / 超长 / 枚举外值。

    刻意不用随机 —— 同一份契约每次生成完全相同的用例，才能进 CI 做回归。
    """
    base = happy_payload(spec)
    cases: list[Case] = []
    n = 1

    cases.append(Case(f"C{n:03d}", "happy", "-", dict(base), spec.success_status,
                      "正常值，接口应受理"))
    n += 1

    for f in spec.fields:
        if f.required:
            p = dict(base)
            p.pop(f.name, None)
            cases.append(Case(f"C{n:03d}", "missing_required", f.name, p,
                              spec.reject_status, f"缺必填字段 {f.name}，应被拒绝"))
            n += 1

        p = dict(base)
        p[f.name] = WRONG_TYPE[f.type]
        cases.append(Case(f"C{n:03d}", "wrong_type", f.name, p,
                          spec.reject_status, f"{f.name} 类型错误，应被拒绝"))
        n += 1

        p = dict(base)
        p[f.name] = "" if f.type != "int" else None
        cases.append(Case(f"C{n:03d}", "empty", f.name, p,
                          spec.reject_status, f"{f.name} 为空，应被拒绝"))
        n += 1

        if f.type == "int" and f.min is not None and f.max is not None:
            for label, val, expect in [
                ("boundary_min", f.min, spec.success_status),
                ("boundary_max", f.max, spec.success_status),
                ("below_min", f.min - 1, spec.reject_status),
                ("above_max", f.max + 1, spec.reject_status),
            ]:
                p = dict(base)
                p[f.name] = val
                cases.append(Case(f"C{n:03d}", label, f.name, p, expect,
                                  f"{f.name}={val}（{label}），期望 {expect}"))
                n += 1

        if f.type == "str" and f.max is not None:
            p = dict(base)
            p[f.name] = "x" * (f.max + 1)
            cases.append(Case(f"C{n:03d}", "oversize", f.name, p,
                              spec.reject_status,
                              f"{f.name} 超长 {f.max + 1} 字符，应被拒绝"))
            n += 1

        if f.type == "enum" and f.enum:
            p = dict(base)
            p[f.name] = "__invalid_enum__"
            cases.append(Case(f"C{n:03d}", "enum_violation", f.name, p,
                              spec.reject_status, f"{f.name} 取枚举外值，应被拒绝"))
            n += 1

    cases.append(Case(f"C{n:03d}", "error_message_quality", "-", dict(base),
                      spec.reject_status,
                      "被拒绝时错误提示是否可行动（语义质量，自动判据判不了）",
                      needs_human=True))
    return cases


# ---------------- 3. 执行与三态判定 ----------------

@dataclass
class Result:
    case_id: str
    mutation: str
    target: str
    expected: int
    actual: str
    verdict: str                    # pass | fail | needs_human
    defect: str                     # false_accept | false_reject | unexpected | ""
    note: str


def judge(case: Case, spec: ApiSpec, handler: Callable[[dict], dict]) -> Result:
    """三态判据：能客观验证的才判 pass/fail，判不了的一律 needs_human。

    needs_human 不等于通过 —— 和「只看 HTTP 200 就判通过」是同一个反命题。
    """
    if case.needs_human:
        return Result(case.id, case.mutation, case.target, case.expected_status, "-",
                      "needs_human", "", "错误提示的可行动性需人工盲评")

    try:
        resp = handler(case.payload)
        actual: Any = resp.get("status")
    except Exception as e:                                  # noqa: BLE001
        actual = f"EXC:{type(e).__name__}"

    if actual == case.expected_status:
        return Result(case.id, case.mutation, case.target, case.expected_status,
                      str(actual), "pass", "", "")

    if case.expected_status == spec.reject_status and actual == spec.success_status:
        defect = "false_accept"
        note = "该拒绝却受理了：实现里缺校验"
    elif case.expected_status == spec.success_status and actual == spec.reject_status:
        defect = "false_reject"
        note = "该受理却拒绝了：校验过严"
    else:
        defect = "unexpected_status"
        note = f"期望 {case.expected_status}，实际 {actual}"

    return Result(case.id, case.mutation, case.target, case.expected_status,
                  str(actual), "fail", defect, note)


# ---------------- 4. 三级报告 ----------------

def build_report(spec: ApiSpec, results: list[Result]) -> str:
    total = len(results)
    pass_n = sum(1 for r in results if r.verdict == "pass")
    fail_n = sum(1 for r in results if r.verdict == "fail")
    human_n = sum(1 for r in results if r.verdict == "needs_human")
    defects: dict[str, int] = {}
    for r in results:
        if r.defect:
            defects[r.defect] = defects.get(r.defect, 0) + 1

    L: list[str] = []
    L.append("# casegen-mini · 自动生成用例的判定报告")
    L.append("")
    L.append(f"> 接口：`{spec.method} {spec.path}`（{spec.name}）｜ 用例 {total} 条")
    L.append("> 由 `casegen.py` 自动生成，判据口径：能客观验证才判 pass/fail，判不了交人工。")
    L.append("")
    L.append("## L1 总览")
    L.append("")
    L.append("| 指标 | 值 |")
    L.append("|---|---:|")
    L.append(f"| 用例总数 | {total} |")
    L.append(f"| pass（客观通过） | {pass_n} |")
    L.append(f"| fail（客观硬伤） | {fail_n} |")
    L.append(f"| needs_human（需人工盲评） | {human_n} |")
    for d, c in sorted(defects.items(), key=lambda x: -x[1]):
        L.append(f"| 缺陷类型 · {d} | {c} |")
    L.append("")
    L.append("> **needs_human 不等于通过。** 自动判据只判硬伤下限，语义质量一律交人。")
    L.append("")
    L.append("## L2 按变异类型聚合")
    L.append("")
    L.append("| 变异类型 | 用例 | pass | fail | needs_human |")
    L.append("|---|---:|---:|---:|---:|")
    groups: dict[str, list[Result]] = {}
    for r in results:
        groups.setdefault(r.mutation, []).append(r)
    for m, rs in sorted(groups.items(), key=lambda x: -len(x[1])):
        L.append(f"| {m} | {len(rs)} | "
                 f"{sum(1 for r in rs if r.verdict == 'pass')} | "
                 f"{sum(1 for r in rs if r.verdict == 'fail')} | "
                 f"{sum(1 for r in rs if r.verdict == 'needs_human')} |")
    L.append("")
    L.append("## L3 逐条明细（fail 优先）")
    L.append("")
    L.append("| 编号 | 变异 | 字段 | 期望 | 实际 | 判定 | 缺陷 | 说明 |")
    L.append("|---|---|---|---:|---|---|---|---|")
    order = {"fail": 0, "needs_human": 1, "pass": 2}
    for r in sorted(results, key=lambda r: (order[r.verdict], r.case_id)):
        L.append(f"| {r.case_id} | {r.mutation} | {r.target} | {r.expected} | "
                 f"{r.actual} | `{r.verdict}` | {r.defect or '-'} | {r.note or '-'} |")
    L.append("")
    L.append("## 结论")
    L.append("")
    if fail_n:
        L.append(f"自动生成的用例抓到 **{fail_n} 条客观硬伤**，"
                 f"其中 `false_accept` {defects.get('false_accept', 0)} 条 —— "
                 "说明被测实现存在未做的校验。这些是「用例真的有用」的证据，"
                 "不是本工具的失败。")
    else:
        L.append("本轮未抓到客观硬伤；但 `needs_human` 仍不等于通过，语义质量需人工盲评。")
    L.append("")
    L.append("> 本报告基于样例实现的确定性离线执行，不是生产指标，不得换算成通过率。")
    L.append("")
    return "\n".join(L)


# ---------------- 5. CLI ----------------

def main() -> int:
    ap = argparse.ArgumentParser(description="schema 驱动的用例生成 + 三态判定")
    ap.add_argument("--spec", default="specs/sample_api.json")
    ap.add_argument("--out", default="output/report.md")
    ap.add_argument("--json", default="", help="额外输出机器可读明细")
    ap.add_argument("--fail-on-defect", action="store_true",
                    help="抓到 fail 时返回非零退出码（CI 用；默认关闭）")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    spec_path = Path(args.spec)
    if not spec_path.is_absolute():
        spec_path = ROOT / spec_path
    spec = load_spec(spec_path)

    from app_under_test import create_user       # 被测样例（纯函数，不启服务）

    cases = generate_cases(spec)
    results = [judge(c, spec, create_user) for c in cases]
    report = build_report(spec, results)

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    if args.json:
        jp = Path(args.json)
        if not jp.is_absolute():
            jp = ROOT / jp
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps([asdict(r) for r in results],
                                 ensure_ascii=False, indent=2), encoding="utf-8")

    fail_n = sum(1 for r in results if r.verdict == "fail")
    human_n = sum(1 for r in results if r.verdict == "needs_human")
    print(f"[casegen] {spec.method} {spec.path} | 用例 {len(cases)} 条 | "
          f"pass {len(cases) - fail_n - human_n} / fail {fail_n} / needs_human {human_n}")
    print(f"[casegen] 报告: {out_path}")
    if fail_n:
        print(f"[casegen] 抓到 {fail_n} 条客观硬伤（false_accept "
              f"{sum(1 for r in results if r.defect == 'false_accept')} 条）")
    return 1 if args.fail_on_defect and fail_n else 0


if __name__ == "__main__":
    sys.exit(main())
