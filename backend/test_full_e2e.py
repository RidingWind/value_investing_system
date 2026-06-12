"""
完整端到端 API 测试脚本（mock 数据源模式下）

使用方法：
    1. 启动后端：
       cd /workspace/backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    2. 运行测试：
       python3 test_full_e2e.py [--base http://localhost:8000] [--symbol 600519.SH]

设计原则：
    - 每个端点至少有"正常路径"测试；部分端点会覆盖"参数缺失/404"等异常路径
    - 断言只关心 HTTP 状态码、顶层 JSON 结构、关键字段的类型，不依赖具体数值
    - 测试之间互相独立；失败的测试不会阻塞后续测试
    - 最终输出汇总表格（PASS / FAIL / SKIP）及失败原因
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional

import requests


# ---------- 配置 ----------

DEFAULT_BASE = "http://localhost:8000"
API = "/api/v1"
REQUEST_TIMEOUT = 15  # 秒

# 健康检查用的超时保护（比 API 总时间更紧）
HEALTH_TIMEOUT = 10


@dataclass
class Result:
    name: str
    status: str          # "PASS" / "FAIL" / "SKIP"
    detail: str = ""
    elapsed: float = 0.0


@dataclass
class Suite:
    results: list[Result] = field(default_factory=list)

    def add(self, r: Result) -> None:
        self.results.append(r)
        icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⚠️"}.get(r.status, "?")
        mark = f"{icon} {r.name}"
        if r.elapsed:
            mark += f"  [{r.elapsed:.2f}s]"
        if r.detail:
            mark += f"  — {r.detail}"
        print(mark)

    def summary(self) -> None:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        skipped = sum(1 for r in self.results if r.status == "SKIP")
        print("")
        print("=" * 60)
        print(f" 总计: {total}   通过: {passed}   失败: {failed}   跳过: {skipped}")
        if failed:
            print("  失败列表：")
            for r in self.results:
                if r.status == "FAIL":
                    print(f"    • {r.name} — {r.detail}")
        print("=" * 60)
        return failed == 0


def run_test(
    suite: Suite,
    name: str,
    fn: Callable[[], None],
) -> None:
    start = time.time()
    try:
        fn()
        suite.add(Result(name=name, status="PASS", elapsed=time.time() - start))
    except AssertionError as e:
        suite.add(Result(name=name, status="FAIL", detail=str(e), elapsed=time.time() - start))
    except Exception as e:
        tb = traceback.format_exc(limit=2)
        suite.add(Result(
            name=name,
            status="FAIL",
            detail=f"{type(e).__name__}: {e}",
            elapsed=time.time() - start,
        ))


# ---------- HTTP 工具 ----------

def http(session: requests.Session, method: str, url: str, **kw: Any) -> requests.Response:
    kw.setdefault("timeout", REQUEST_TIMEOUT)
    resp = session.request(method, url, **kw)
    return resp


def expect_ok(resp: requests.Response, min_code: int = 200, max_code: int = 299, note: str = "") -> dict:
    """断言响应在 2xx 范围内并返回 JSON。"""
    if not (min_code <= resp.status_code <= max_code):
        raise AssertionError(
            f"期望 {min_code}-{max_code}，实际 {resp.status_code} "
            f"{resp.request.method} {resp.request.url}{' — ' + note if note else ''}\n"
            f"body: {resp.text[:500]}"
        )
    try:
        return resp.json()
    except Exception:
        raise AssertionError(f"响应不是 JSON: {resp.text[:300]}")


# ---------- 测试主体 ----------

def main() -> int:
    parser = argparse.ArgumentParser(description="ValueAgent 后端完整端到端测试")
    parser.add_argument("--base", default=DEFAULT_BASE, help="后端地址")
    parser.add_argument("--symbol", default="600519.SH", help="测试用的股票代码")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    symbol = args.symbol

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    suite = Suite()

    print(f"Target:    {base}")
    print(f"Date:      {datetime.now().isoformat(timespec='seconds')}")
    print(f"Test SUID: {symbol}")
    print("-" * 60)

    # 先用 /health 或根路径确认服务已起来
    try:
        r = session.get(f"{base}/", timeout=5)
        assert r.status_code < 500, f"根路径返回 {r.status_code}"
    except Exception as e:
        print(f"⚠️  无法连接后端 {base}（{e}）。请先启动后端。")
        return 2

    # ============= 1. params =============
    def test_params_list():
        body = expect_ok(http(session, "GET", f"{base}{API}/params"))
        assert isinstance(body, list), "应返回数组"
        assert len(body) >= 3, "至少能拿到 3 条参数配置"
        keys = {row.get("key") for row in body}
        for must in ("data.primary_source", "data.market.cron"):
            assert must in keys, f"应包含参数 {must}，实际只看到 {sorted(keys)[:10]}"

    def test_params_update_and_history():
        # 更新一个可热加载的参数
        key = "data.market.cron"
        r = http(session, "PUT", f"{base}{API}/params/{key}",
                 json={"value": "0 16 * * 1-5", "reason": "e2e-temp"})
        body = expect_ok(r)
        # 历史记录可拿到
        body2 = expect_ok(http(session, "GET", f"{base}{API}/params/{key}/history"))
        assert isinstance(body2, list), "history 应返回数组"

    run_test(suite, "params.1  GET /params  列出所有参数", test_params_list)
    run_test(suite, "params.2  PUT /params/{key} + GET history", test_params_update_and_history)

    # ============= 2. audit =============
    def test_audit_logs():
        body = expect_ok(http(session, "GET", f"{base}{API}/audit/logs"))
        assert isinstance(body.get("logs"), list) or isinstance(body.get("items"), list) or isinstance(body, list), \
            f"响应结构异常: {list(body.keys())[:10] if isinstance(body, dict) else body}"

    run_test(suite, "audit.1   GET /audit/logs", test_audit_logs)

    # ============= 3. market =============
    def test_market_status():
        body = expect_ok(http(session, "GET", f"{base}{API}/market/status"),
                         note="/market/status 超时通常是数据源在阻塞健康检查")
        # 响应可能是 dict（含 primary/backups/overall），也可能是扁平结构；
        # 不假设固定字段，只要能反序列化即可。
        assert isinstance(body, dict) or isinstance(body, list), \
            f"status 响应既非 dict 也非 list: {type(body)}"

    def test_market_symbols():
        body = expect_ok(http(session, "GET", f"{base}{API}/market/symbols"))
        assert isinstance(body, list) or (isinstance(body, dict) and "symbols" in body), \
            f"symbols 响应异常: {type(body)}"

    def test_market_summary_and_fetch():
        # 先触发一次 fetch，把行情写进库里；mock 模式下几乎瞬时完成
        payload = {"symbols": [symbol, "000001.SZ"],
                   "start": (date.today() - timedelta(days=30)).isoformat(),
                   "end": date.today().isoformat()}
        body = expect_ok(http(session, "POST", f"{base}{API}/market/fetch", json=payload))
        assert isinstance(body, dict), "fetch 应返回 dict"

        summary = expect_ok(http(session, "GET", f"{base}{API}/market/summary"))
        assert isinstance(summary, (dict, list)), f"summary 响应异常: {type(summary)}"

    def test_market_range_and_daily():
        rng = expect_ok(http(session, "GET", f"{base}{API}/market/range/{symbol}"))
        assert isinstance(rng, dict), f"range 响应异常: {type(rng)}"

        daily = expect_ok(http(session, "GET", f"{base}{API}/market/daily/{symbol}"))
        assert isinstance(daily, dict), f"daily 响应异常: {type(daily)}"

    def test_market_range_404():
        # 用一个明显不存在的股票代码，验证 404 / 空数据行为
        resp = http(session, "GET", f"{base}{API}/market/range/NOSUCH.SH")
        # 期望 200（空数据）或 404；禁止 500
        if resp.status_code == 500:
            raise AssertionError(f"查不存在的 symbol 不应 500，body: {resp.text[:300]}")

    def test_market_logs():
        body = expect_ok(http(session, "GET", f"{base}{API}/market/logs"))
        assert isinstance(body, list) or (isinstance(body, dict) and "logs" in body), \
            f"logs 响应异常: {type(body)}"

    run_test(suite, "market.1   GET /market/status",  test_market_status)
    run_test(suite, "market.2   GET /market/symbols", test_market_symbols)
    run_test(suite, "market.3   POST /market/fetch + GET summary", test_market_summary_and_fetch)
    run_test(suite, "market.4   GET /market/range/{symbol} + GET /market/daily/{symbol}",
             test_market_range_and_daily)
    run_test(suite, "market.5   GET /market/range/NOSUCH.SH (边界)", test_market_range_404)
    run_test(suite, "market.6   GET /market/logs",    test_market_logs)

    # ============= 4. financial_config =============
    def test_fc_apis_and_indicators():
        apis = expect_ok(http(session, "GET", f"{base}{API}/financial/config/apis"))
        assert isinstance(apis, list) or (isinstance(apis, dict) and "items" in apis), \
            f"apis 响应异常: {type(apis)}"

        indicators = expect_ok(http(session, "GET", f"{base}{API}/financial/config/indicators"))
        assert isinstance(indicators, list) or (isinstance(indicators, dict) and "items" in indicators), \
            f"indicators 响应异常: {type(indicators)}"

    def test_fc_create_api_then_indicator_idempotent():
        """幂等性测试：重复写入唯一键不应 500。"""
        new_api = {
            "source": "mock",
            "function_name": "e2e_profit_sheet",  # 唯一键 (source, function_name)
            "chinese_name": "E2E 测试利润表",
            "input_params": {"symbol": "{symbol}"},
            "date_column": "REPORT_DATE",
            "filter_condition": "REPORT_TYPE == '1'",
        }
        first = expect_ok(http(session, "POST", f"{base}{API}/financial/config/apis", json=new_api))
        api_id = None
        if isinstance(first, dict):
            api_id = first.get("id")
        second = http(session, "POST", f"{base}{API}/financial/config/apis", json=new_api)
        assert second.status_code != 500, \
            f"重复 API 插入不应 500，body: {second.text[:300]}"

        new_ind = {
            "standard_field": "e2e_mock_revenue",
            "chinese_name": "E2E 测试营业收入",
            "report_group": "income",
            "unit": "元",
            "formula": "api('mock_profit_sheet').col('OPERATE_INCOME')",
        }
        expect_ok(http(session, "POST", f"{base}{API}/financial/config/indicators", json=new_ind))
        dup = http(session, "POST", f"{base}{API}/financial/config/indicators", json=new_ind)
        assert dup.status_code != 500, \
            f"重复指标插入不应 500，body: {dup.text[:300]}"

        if api_id is not None:
            deps = expect_ok(http(session, "GET", f"{base}{API}/financial/config/deps/affected/{api_id}"))
            _ = deps

    run_test(suite, "fin_cfg.1  GET /financial/config/apis + /indicators", test_fc_apis_and_indicators)
    run_test(suite, "fin_cfg.2  POST /financial/config/apis + /indicators 幂等性", test_fc_create_api_then_indicator_idempotent)

    # ============= 5. financial 指标数据 =============
    def test_financial_fetch_and_summary():
        body = expect_ok(http(session, "POST", f"{base}{API}/financial/fetch",
                              json={"symbols": [symbol], "num_quarters": 2}))
        assert isinstance(body, dict), f"financial/fetch 响应异常: {type(body)}"

        summary = expect_ok(http(session, "GET", f"{base}{API}/financial/summary"))
        assert isinstance(summary, (dict, list)), f"summary 响应异常: {type(summary)}"

    def test_financial_range():
        body = expect_ok(http(session, "GET", f"{base}{API}/financial/range/{symbol}"))
        assert isinstance(body, dict), f"range 响应异常: {type(body)}"

    def test_financial_logs():
        body = expect_ok(http(session, "GET", f"{base}{API}/financial/logs"))
        assert isinstance(body, list) or (isinstance(body, dict) and "logs" in body), \
            f"logs 响应异常: {type(body)}"

    run_test(suite, "fin.1     POST /financial/fetch + GET /financial/summary",
             test_financial_fetch_and_summary)
    run_test(suite, "fin.2     GET /financial/range/{symbol}", test_financial_range)
    run_test(suite, "fin.3     GET /financial/logs",          test_financial_logs)

    # ============= 6. search =============
    def test_search_stocks():
        body = expect_ok(http(session, "GET", f"{base}{API}/search/stocks",
                              params={"keyword": "银行", "limit": 10}))
        assert isinstance(body, list) or (isinstance(body, dict) and "results" in body), \
            f"search/stocks 响应异常: {type(body)}"

    def test_search_refresh_cache():
        # 离线模式下 akshare 不可用 —— 接口应要么 200（用缓存），
        # 要么返回明确错误状态（!= 500），禁止因外部依赖不可用就崩。
        r = http(session, "POST", f"{base}{API}/search/stocks/refresh-cache")
        assert r.status_code in (200, 201, 404, 502, 503), \
            f"不应返回其他状态码，实际: {r.status_code} {r.text[:200]}"

    run_test(suite, "search.1  GET /search/stocks?q=银行", test_search_stocks)
    run_test(suite, "search.2  POST /search/stocks/refresh-cache", test_search_refresh_cache)

    # ============= 汇总 =============
    ok = suite.summary()
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n被中断")
        sys.exit(130)
