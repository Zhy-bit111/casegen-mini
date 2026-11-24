# casegen-mini

> **借鉴声明（请先读这一行）**：本项目借鉴了 [keploy/keploy](https://github.com/keploy/keploy)
> 「从真实流量自动生成用例」的思路，以及 [schemathesis](https://github.com/schemathesis/schemathesis)
> 「按 schema 做边界/异常变异」的思想，**但没有复制任何一行代码**。
> 本实现是一个约 250 行、零第三方依赖的最小复刻：只读一份接口契约，生成确定性用例，
> 对一个纯函数执行，给出三态判定和三级报告。
> 明确不做：eBPF 抓包、录制回放、随机/property-based 生成、stateful 序列、多协议 parser、真实 HTTP 服务。

一个「把接口描述变成测试用例」的最小闭环。用它来练一件事：
**怎么判断一个测试结果到底可信不可信** —— 而不是只看它有没有报错。

---

## 快速开始（零依赖，Python 3.10+）

```bash
python casegen.py
python casegen.py --json output/results.json
python casegen.py --fail-on-defect        # CI 里让「抓到缺陷」变红灯
```

输出 `output/report.md`。仓库里另存了一份 `docs/sample-report.md` 便于直接查看。

## 它做了什么

```
specs/sample_api.json          接口契约（字段 / 类型 / 必填 / 范围 / 枚举）
        │
        ▼  generate_cases()    确定性变异，共 7 类
   正常 / 边界(min,max,越界) / 缺必填 / 错类型 / 空值 / 超长 / 枚举外值
   + 1 条「错误提示可行动性」语义用例
        │
        ▼  judge()             执行 app_under_test.create_user（纯函数）
   pass         客观通过：实际状态码 == 期望
   fail         客观硬伤：false_accept（该拒没收）/ false_reject（该收却拒）
   needs_human  语义质量自动判不了 → 人工盲评，**不等于通过**
        │
        ▼  build_report()
   L1 总览 / L2 按变异类型聚合 / L3 逐条明细 + 结论
```

`app_under_test.py` 是**故意写坏的靶子**（age/role/name 三处校验缺失），
所以报告会抓到一批 `false_accept`。这正是「用例真的有用」的证据，不是工具的失败。

## 为什么这么设计（面试时讲这四点）

1. **确定性，不随机**：同一份契约每次生成完全相同的用例，才能进 CI 做回归。
   schemathesis 用 Hypothesis 做 property-based 随机生成，很强，但最小实现不需要。
2. **三态，不是二态**：`needs_human` 单列，**不算通过**。
   对应「不能只看 HTTP 200 / 自动指标判通过」—— 判不了就别装作判得了。
3. **输入同构**：用例走的是和真实调用同一个 `create_user(payload)` 入口，
   不另写测试专用分支，避免「测的和跑的不是同一条链路」。
4. **证据化**：每条判定都留下 `期望 / 实际 / 缺陷类型 / 说明`，
   L3 明细可逐条复现，而不是只给一个总分。

## 与岗位、与另一个项目的关系

- 对标的是「按接口契约自动生成正常/边界/异常用例」这类测试效能工作
  （例如把 Go AST 里的参数、枚举、条件分支转成可执行用例）。
- 我的另一个项目 `muxin-local-agent` 里也用了同一套方法论：
  评测集防污染、三态判据、失败归因三级报告、CI 门禁。
  这里是把它**从模型评测搬到接口测试**，规模更小、更容易讲清。

## 没做什么（被问到就这么答）

| 没做 | 为什么 |
|---|---|
| eBPF / 代理抓包、录制回放 | 需要系统权限与多协议解析；最小实现改用「契约 + 纯函数」，先把判定口径讲清 |
| 随机 / property-based 生成 | 换成确定性变异，保证可复现、可进 CI |
| stateful 多步序列 | 只覆盖单请求字段级变异，序列场景留待后续 |
| 真实 HTTP 服务 | 纯函数执行即可验证判据，省掉起服务/装依赖 |
| 覆盖率、P95、生产指标 | 本项目的输出是判定报告，不是性能/覆盖率口径 |

## 目录

```
casegen-mini/
├── casegen.py                  核心：契约 → 用例 → 判定 → 报告（约 250 行）
├── app_under_test.py           被测样例（带 3 处已知缺陷的靶子）
├── specs/sample_api.json       样例接口契约
├── docs/sample-report.md       一次真实运行的报告样例
├── .github/workflows/ci.yml    push/PR 自动跑并输出 Job Summary
└── LICENSE                     MIT
```

## 复现

```bash
python casegen.py --spec specs/sample_api.json --out output/report.md
```

> 报告基于样例实现的确定性离线执行，**不是生产指标**，不得换算成通过率对外宣称。
