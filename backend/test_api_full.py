"""完整的 API 冒烟测试脚本，跑完输出报告。"""
import json
import time
import traceback
from datetime import date, timedelta
from urllib.request import Request, urlopen
from urllib.parse import urlencode

BASE = "http://127.0.0.1:8000"
API = BASE + "/api/v1"

passed = []
failed = []
warnings = []

def http(method: str, path: str, body=None, query=None, expect_status=None):
    url = API + path
    if query:
        url += "?" + urlencode(query)
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, method=method.upper(), headers=headers)
    try:
        with urlopen(req, timeout=30) as r:
            status = r.status
            raw = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, str(e)
    try:
        payload = json.loads(raw) if raw else None
    except Exception:
        payload = raw
    if expect_status and status != expect_status:
        return status, payload
    return status, payload

def record(name, status_ok, detail=""):
    if status_ok:
        passed.append(name)
        print(f"  ✅ {name} {detail}")
    else:
        failed.append((name, detail))
        print(f"  ❌ {name} — {detail}")

print("=" * 60)
print(" 【1/5】 参数管理（Params）")
print("=" * 60)

status, payload = http("GET", "/params")
has_params = isinstance(payload, list) and len(payload) > 0
record("GET /params", status == 200 and has_params, f"status={status}, count={len(payload) if has_params else 0}")

# 找到第一个可写参数（数值 / 字符串 / 布尔）
if has_params:
    target = None
    for p in payload:
        t = type(p.get("value")).__name__
        if t in ("int", "str", "bool", "float"):
            target = p
            break
    if target is None:
        warnings.append("没有找到可写入的标量参数，跳过 PUT 测试")
    else:
        key = target["key"]
        orig = target["value"]
        new_val = 123 if type(orig).__name__ == "int" else (1.5 if type(orig).__name__ == "float" else (not orig if type(orig).__name__ == "bool" else "test-value"))
        s, p = http("PUT", f"/params/{key}", body={"value": new_val, "reason": "api-test"})
        record(f"PUT /params/{key}", s == 200, f"status={s}, body={p!r}")

        # history
        s2, p2 = http("GET", f"/params/{key}/history")
        record(f"GET /params/{key}/history", s2 == 200, f"status={s2}, len={len(p2) if isinstance(p2, list) else 'n/a'}")

        # 还原
        http("PUT", f"/params/{key}", body={"value": orig, "reason": "restore-after-test"})
else:
    warnings.append("参数列表为空，跳过写入测试")

print()
print("=" * 60)
print(" 【2/5】 审计日志（Audit）")
print("=" * 60)

s, p = http("GET", "/audit/logs")
record("GET /audit/logs", s == 200 and isinstance(p, dict), f"status={s}, top_keys={list(p.keys()) if isinstance(p, dict) else p!r}")

print()
print("=" * 60)
print(" 【3/5】 行情数据（Market）")
print("=" * 60)

s, p = http("GET", "/market/status")
record("GET /market/status", s == 200 and isinstance(p, dict), f"status={s}, primary={p.get('primary', {}).get('name') if isinstance(p, dict) else 'n/a'}")

s, p = http("GET", "/market/summary")
record("GET /market/summary", s == 200, f"status={s}, body={p!r}")

s, p = http("GET", "/market/range/600519.SH")
record("GET /market/range/{symbol}", s == 200 or s == 404, f"status={s}, body={p!r}")

# 手动触发采集：小范围 + 短时间（近5天）
yest = date.today() - timedelta(days=1)
start = (yest - timedelta(days=5)).isoformat()
s, p = http("POST", "/market/fetch", body={"symbols": ["600519.SH", "000001.SZ"], "start_date": start, "end_date": yest.isoformat()})
record("POST /market/fetch", s == 200, f"status={s}, body={p!r}")

s, p = http("GET", "/market/logs")
record("GET /market/logs", s == 200, f"status={s}, body_type={type(p).__name__}")

s, p = http("GET", "/market/daily/600519.SH", query={"start_date": start, "end_date": yest.isoformat(), "freq": "daily"})
record("GET /market/daily/{symbol}", s == 200, f"status={s}, type={type(p).__name__}, sample={json.dumps(p)[:200] if isinstance(p, (dict, list)) else str(p)[:200]}")

print()
print("=" * 60)
print(" 【4/5】 财务数据（Financial）")
print("=" * 60)

s, p = http("GET", "/financial/summary")
record("GET /financial/summary", s == 200, f"status={s}, body={p!r}")

s, p = http("GET", "/financial/range/600519.SH")
record("GET /financial/range/{symbol}", s == 200 or s == 404, f"status={s}, body={p!r}")

# 触发财务采集（1只股票，仅最近两个报告期）
s, p = http("POST", "/financial/fetch", body={"symbols": ["600519.SH"], "quarters": 1})
record("POST /financial/fetch", s == 200, f"status={s}, body={p!r}")

s, p = http("GET", "/financial/logs")
record("GET /financial/logs", s == 200, f"status={s}, body_type={type(p).__name__}")

print()
print("=" * 60)
print(" 【5/5】 财务配置（Financial Config）")
print("=" * 60)

s, p = http("GET", "/financial/config/apis")
apis_ok = s == 200 and isinstance(p, list)
record("GET /financial/config/apis", apis_ok, f"status={s}, count={len(p) if isinstance(p, list) else 0}")

# 创建一个测试 API
new_api = {
    "source": "akshare",
    "function_name": "stock_a_indicator_em",
    "chinese_name": "测试-A股指标",
    "input_params": {"symbol": "SH600519"},
    "date_column": "日期",
}
s, p = http("POST", "/financial/config/apis", body=new_api)
record("POST /financial/config/apis", s == 200, f"status={s}, body={p!r}")

s, p = http("GET", "/financial/config/indicators")
inds_ok = s == 200 and isinstance(p, list)
record("GET /financial/config/indicators", inds_ok, f"status={s}, count={len(p) if isinstance(p, list) else 0}")

# 创建一个测试指标
test_ind = {
    "standard_field": "test_revenue",
    "chinese_name": "测试_营业收入",
    "report_group": "income",
    "formula": "1",
    "unit": "元",
    "deps": [],
}
s, p = http("POST", "/financial/config/indicators", body=test_ind)
record("POST /financial/config/indicators", s == 200, f"status={s}, body={p!r}")

# 测试指标引擎（通过真实 API 拉取 + 公式计算）
if isinstance(p, dict) and p.get("id"):
    ind_id = p["id"]
    s2, p2 = http("GET", f"/financial/config/indicators/{ind_id}/deps")
    record(f"GET /financial/config/indicators/{ind_id}/deps", s2 == 200, f"status={s2}, body={p2!r}")

    s3, p3 = http("PUT", f"/financial/config/indicators/{ind_id}/deps", body=[])
    record(f"PUT /financial/config/indicators/{ind_id}/deps", s3 == 200, f"status={s3}, body={p3!r}")

# 获取 API 影响指标（找一个已有的 API id）
if isinstance(p, dict) and p.get("id"):
    pass
if apis_ok and len(p) > 0 and isinstance(p, list):
    api_id = p[0]["id"] if p and isinstance(p[0], dict) and "id" in p[0] else None
    if api_id is not None:
        s4, p4 = http("GET", f"/financial/config/deps/affected/{api_id}")
        record(f"GET /financial/config/deps/affected/{api_id}", s4 == 200, f"status={s4}, body_type={type(p4).__name__}")

print()
print("=" * 60)
print(" 【搜索 / Search】")
print("=" * 60)

s, p = http("GET", "/search/stocks", query={"keyword": "茅台"})
record("GET /search/stocks", s == 200, f"status={s}, body_type={type(p).__name__}, len={len(p) if isinstance(p, list) else 'n/a'}")

s, p = http("POST", "/search/stocks/refresh-cache")
record("POST /search/stocks/refresh-cache", s == 200, f"status={s}, body={p!r}")

print()
print("=" * 60)
print(" 测试报告")
print("=" * 60)
print(f"通过: {len(passed)}")
print(f"失败: {len(failed)}")
if warnings:
    print(f"警告: {len(warnings)}")
    for w in warnings:
        print(f"  ⚠  {w}")
if failed:
    print("\n失败详情:")
    for name, detail in failed:
        print(f"  - {name}: {detail}")
print()
print("Done.")
