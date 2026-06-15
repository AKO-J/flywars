# FlyWars 常用命令
#
# CI: lint → test → verify
# Dev: install → run → test → lint
#
# Windows 用户: 直接运行 python main.py 或参考 tools/ 中的脚本

PYTHON     ?= python
RUFF       ?= ruff
TEST       ?= pytest

.PHONY: install run test test-all lint format check clean

# ---- 安装 ----

install:                        ## 安装项目（含测试依赖）
	$(PYTHON) -m pip install -e ".[test]"

install-dev:                    ## 安装完整开发环境
	$(PYTHON) -m pip install -e ".[dev]"

# ---- 运行 ----

run:                            ## 启动游戏
	$(PYTHON) main.py

server:                         ## 启动多人游戏服务器
	$(PYTHON) server/server.py

# ---- 测试 ----

test:                           ## 运行测试
	$(PYTHON) -m $(TEST) --tb=short

test-all:                       ## 运行所有测试（含较长测试）
	$(PYTHON) -m $(TEST) -v --tb=long

test-coverage:                  ## 运行测试并生成覆盖率报告
	$(PYTHON) -m pip install coverage
	$(PYTHON) -m coverage run -m $(TEST)
	$(PYTHON) -m coverage report -m
	$(PYTHON) -m coverage html

# ---- 代码质量 ----

lint:                           ## 运行 ruff 检查
	$(RUFF) check .

format:                         ## 格式化代码
	$(RUFF) format .

format-check:                   ## 检查格式（CI 使用）
	$(RUFF) format --check .

check: lint format-check test   ## 完整检查（lint + format + test）

# ---- 清理 ----

clean:                          ## 清理产物
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

clean-logs:                     ## 清理日志
	rm -f logs/*.jsonl logs/*.log

# ---- 帮助 ----

help:                           ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
