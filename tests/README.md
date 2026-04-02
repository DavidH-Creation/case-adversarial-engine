# Tests

仓库测试分成几层：

- `engines/**/tests`
  大部分单元测试。
- `tests/integration/`
  跨模块集成测试。
- `api/tests/`
  API 路由、持久化和恢复语义测试。
- `tests/contracts/`
  contract / compatibility 相关检查。
- `tests/smoke/`
  显式运行的 end-to-end smoke。

默认 `pytest` 走 `pyproject.toml` 里的 `testpaths`，不会自动包含所有 smoke 测试。
