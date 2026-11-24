# casegen-mini · 自动生成用例的判定报告

> 接口：`POST /api/users`（create_user）｜ 用例 17 条
> 由 `casegen.py` 自动生成，判据口径：能客观验证才判 pass/fail，判不了交人工。

## L1 总览

| 指标 | 值 |
|---|---:|
| 用例总数 | 17 |
| pass（客观通过） | 6 |
| fail（客观硬伤） | 10 |
| needs_human（需人工盲评） | 1 |
| 缺陷类型 · false_accept | 10 |

> **needs_human 不等于通过。** 自动判据只判硬伤下限，语义质量一律交人。

## L2 按变异类型聚合

| 变异类型 | 用例 | pass | fail | needs_human |
|---|---:|---:|---:|---:|
| missing_required | 3 | 1 | 2 | 0 |
| wrong_type | 3 | 1 | 2 | 0 |
| empty | 3 | 1 | 2 | 0 |
| happy | 1 | 1 | 0 | 0 |
| oversize | 1 | 0 | 1 | 0 |
| boundary_min | 1 | 1 | 0 | 0 |
| boundary_max | 1 | 1 | 0 | 0 |
| below_min | 1 | 0 | 1 | 0 |
| above_max | 1 | 0 | 1 | 0 |
| enum_violation | 1 | 0 | 1 | 0 |
| error_message_quality | 1 | 0 | 0 | 1 |

## L3 逐条明细（fail 优先）

| 编号 | 变异 | 字段 | 期望 | 实际 | 判定 | 缺陷 | 说明 |
|---|---|---|---:|---|---|---|---|
| C005 | oversize | name | 400 | 200 | `fail` | false_accept | 该拒绝却受理了：实现里缺校验 |
| C006 | missing_required | age | 400 | 200 | `fail` | false_accept | 该拒绝却受理了：实现里缺校验 |
| C007 | wrong_type | age | 400 | 200 | `fail` | false_accept | 该拒绝却受理了：实现里缺校验 |
| C008 | empty | age | 400 | 200 | `fail` | false_accept | 该拒绝却受理了：实现里缺校验 |
| C011 | below_min | age | 400 | 200 | `fail` | false_accept | 该拒绝却受理了：实现里缺校验 |
| C012 | above_max | age | 400 | 200 | `fail` | false_accept | 该拒绝却受理了：实现里缺校验 |
| C013 | missing_required | role | 400 | 200 | `fail` | false_accept | 该拒绝却受理了：实现里缺校验 |
| C014 | wrong_type | role | 400 | 200 | `fail` | false_accept | 该拒绝却受理了：实现里缺校验 |
| C015 | empty | role | 400 | 200 | `fail` | false_accept | 该拒绝却受理了：实现里缺校验 |
| C016 | enum_violation | role | 400 | 200 | `fail` | false_accept | 该拒绝却受理了：实现里缺校验 |
| C017 | error_message_quality | - | 400 | - | `needs_human` | - | 错误提示的可行动性需人工盲评 |
| C001 | happy | - | 200 | 200 | `pass` | - | - |
| C002 | missing_required | name | 400 | 400 | `pass` | - | - |
| C003 | wrong_type | name | 400 | 400 | `pass` | - | - |
| C004 | empty | name | 400 | 400 | `pass` | - | - |
| C009 | boundary_min | age | 200 | 200 | `pass` | - | - |
| C010 | boundary_max | age | 200 | 200 | `pass` | - | - |

## 结论

自动生成的用例抓到 **10 条客观硬伤**，其中 `false_accept` 10 条 —— 说明被测实现存在未做的校验。这些是「用例真的有用」的证据，不是本工具的失败。

> 本报告基于样例实现的确定性离线执行，不是生产指标，不得换算成通过率。
