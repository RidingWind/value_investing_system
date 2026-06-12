import ast, sys

files = [
    'app/main.py',
    'app/core/config.py',
    'app/core/data/market/fallback.py',
    'app/core/data/market/storage.py',
    'app/core/data/market/base.py',
    'app/core/data/market/scheduler.py',
    'app/core/data/market/akshare_adapter.py',
    'app/core/data/market/baostock_adapter.py',
    'app/core/data/market/tushare_adapter.py',
    'app/core/data/financial/models.py',
    'app/core/data/financial/storage.py',
    'app/core/data/financial/dynamic_adapter.py',
    'app/core/data/financial/indicator_engine.py',
    'app/core/data/financial/dependency_parser.py',
    'app/core/data/financial/scheduler.py',
    'app/core/plugins/market_plugin.py',
    'app/core/plugins/param_plugin.py',
    'app/core/plugins/financial_plugin.py',
    'app/core/params/service.py',
    'app/core/params/redis_impl.py',
    'app/core/params/mock_impl.py',
    'app/core/params/definitions.py',
    'app/api/v1/market.py',
    'app/api/v1/params.py',
    'app/api/v1/financial.py',
    'app/api/v1/financial_config.py',
    'app/api/v1/audit.py',
    'app/api/v1/search.py',
]
errors = []
for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as fp:
            ast.parse(fp.read())
        print('  OK ', f)
    except SyntaxError as e:
        errors.append((f, e))
        print('  ERR', f, ':', e)

if errors:
    print(f'\n总错误数: {len(errors)}')
    sys.exit(1)
else:
    print('\n全部语法检查通过')
