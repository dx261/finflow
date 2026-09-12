# FinFlow 项目上手指南

> 一份帮助你从零开始熟悉 FinFlow 的文档：先讲清楚"它是什么、解决了什么问题"（业务），再带你一步步把环境跑起来、读代码、跑测试、做部署（技术）。读完你应该能独立改一个功能、修一个 bug、跑通一条完整业务链路。

---

## 目录

1. [项目概览](#1-项目概览)
2. [业务模型：核心概念](#2-业务模型核心概念)
3. [核心业务流程](#3-核心业务流程)
4. [技术架构](#4-技术架构)
5. [本地环境：一步步跑起来](#5-本地环境一步步跑起来)
6. [后端代码地图](#6-后端代码地图)
7. [前端代码地图](#7-前端代码地图)
8. [测试体系](#8-测试体系)
9. [生产部署与运维](#9-生产部署与运维)
10. [常见坑与经验](#10-常见坑与经验)
11. [推荐学习路线](#11-推荐学习路线)

---

## 1. 项目概览

**FinFlow — 个人多账户资金管理与现金流规划平台**。面向个人长期使用，把分散在多家银行的钱统一管起来：导入银行流水、规划未来付款、决定用哪个账户的钱去付、虚拟预留资金、事后对账核销、预测未来现金流。

> **一句话定位：FinFlow 管信息、做规划、做对账、做决策支持，绝不碰真实资金。**

所有真实世界的资金操作（转账、付款、冻结）**100% 由用户在自己的银行完成**。FinFlow 的输出是一个"建议 + 事后核验"，而不是一次真实交易。这是系统最重要的设计约束，也是代码里反复出现的安全边界（Safety Boundary）。

### 1.1 系统的功能全景

| 能力 | 说明 |
| --- | --- |
| 多银行账户管理 | 统一管理招行、工行、建行等多个账户，记录实际余额 |
| 银行流水导入 | 上传银行导出的 Excel/CSV，自动解析成标准化交易 |
| 收支分类 | 规则引擎自动给交易打分类，支持内部转账识别、去重 |
| 付款计划 | 规划未来的付款（金额、日期、优先级、期望账户） |
| 智能分配 | 引擎推荐"用哪个账户的多少钱来付"，尊重最低留存 |
| 虚拟预留 | 确认分配后虚拟冻结资金，不影响真实账户 |
| 手动执行 + 对账 | 用户到银行手动付款后登记，系统与银行交易自动匹配核销 |
| 现金流预测 | 7/30/90 天账户余额预测与低余额预警 |
| 审计日志 | 关键资金操作不可篡改的记录 |

### 1.2 安全边界（红线，不可逾越）

以下在代码中**明确禁止**实现（详见 `CODING_PLAN.md` §1）：

- 真实银行自动登录、保存银行密码/凭据
- 短信验证码 / OTP 处理
- USB Key 控制、银行网页 RPA
- 自动转账、自动付款、修改真实银行资金
- 绕过银行安全机制、爬取银行私有接口

**敏感数据政策**：不存储完整卡号、银行密码、身份证号、短信验证码。账户只存掩码账号（`masked_account_no`）。

> 改动任何代码前，先想一遍：这个功能会不会越界？会 → 不做。这也是 `CODING_PLAN.md` 中 Rule 6/7 的来源。

### 1.3 实现进度

项目按 `CODING_PLAN.md`（4224 行、8 个阶段 / 62 个 Task）逐任务增量实现，**当前 8 个阶段全部完成**：

- 后端：206 个单元/集成测试通过，ruff / black / mypy 干净，Alembic 迁移就绪
- 前端：12 个页面，vue-tsc / eslint / build 通过
- E2E：24 项检查全部通过（真实 PostgreSQL + Redis + Celery）
- 生产化：docker compose 全栈（api / worker / beat / nginx）+ 备份恢复 + demo 数据

---

## 2. 业务模型：核心概念

这一节是全项目的业务地基。所有代码、数据库表、API 都是这几个概念的投影。**务必先读透再碰代码。**

### 2.1 三种余额（§13）

每个账户同时存在三个"余额"概念，对应代码中三个来源：

```
actual_balance     实际余额      （存在数据库里，来自最新账单/手动录入）
reserved_amount    预留金额      （派生值 = 该账户上所有 RESERVED 状态分配的合计）
planning_available 可规划金额    （实时计算 = actual - reserved - minimum）
```

- `planning_available` 不落库，**每次读取时实时算**（`AccountService.planning_available()`）。
- `minimum_balance` 是最低留存，防止分配引擎把账户掏空。
- 前端账户页显示三者；分配引擎只认 `planning_available`。

代码位置：`backend/app/modules/accounts/service.py`、`backend/app/modules/allocation/service.py:60`（`_planning_available`）。

### 2.2 账户与银行

- **Bank**：银行目录（代码、名称、国家、解析器类型 ICBC/CMB/GENERIC），系统启动时自动播种默认银行（`seed_default_banks`）。
- **Account**：用户的具体账户（属于哪个银行、账户类型 CHECKING/SAVINGS、币种、实际余额、最低留存、是否参与分配、掩码账号）。
- **AccountBalanceSnapshot**：余额时点快照，用于趋势图。

### 2.3 账单导入（Statement Import）

用户上传银行流水文件 → 系统解析成标准化交易。完整状态机：

```
UPLOADED → QUEUED → PARSING → SUCCESS / PARTIAL_SUCCESS / FAILED
```

流程（同步上传 + 异步 worker 处理）：
1. 上传文件（`.xlsx` / `.xls` / `.csv`），保存到磁盘，算 SHA-256
2. **重复文件检测**：同一账户 + 相同哈希 → 拒绝或强制导入
3. 返回 `202`，异步丢给 Celery 任务 `statements.process_import`
4. Worker 执行：**解析**（ICBC/CMB/GENERIC 解析器 + 浮动锚点 + 动态表格识别）→ **去重**（交易指纹）→ **规则分类** → **内部转账识别** → **入库** → **更新账户余额**

### 2.4 付款计划与状态机（§19，核心中的核心）

`PaymentPlan`（付款计划）贯穿"规划 → 分配 → 预留 → 执行 → 对账"全生命周期。状态机定义在 `backend/app/modules/payments/state_machine.py`，**所有状态转换必须经过它校验**：

```
DRAFT ──► PLANNED ──► ALLOCATED ──► RESERVED ──► WAITING_MANUAL_EXECUTION ──► MANUALLY_EXECUTED ──► RECONCILING ──► SETTLED
              │             │            │  ▲                  │  ▲                     │
              │             │            │  └──(释放预留)───────┘  └──(回到规划)───────────┘
              └─────────────┴────────────┴──────────────► CANCELLED
                                                                            └──► EXCEPTION（异常，终态）
```

| 状态 | 含义 | 触发方式 |
| --- | --- | --- |
| DRAFT | 草稿 | 创建付款 |
| PLANNED | 已规划 | `transition` 接口，或周期性账单自动生成 |
| ALLOCATED | 已分配（有分配方案，未预留） | 生成分配预览 / 手动覆盖 |
| RESERVED | 已预留（资金虚拟冻结） | `allocations/confirm` |
| WAITING_MANUAL_EXECUTION | 等手动执行 | transition |
| MANUALLY_EXECUTED | 已在银行执行 | `manual-execution`（需提供账户/流水号/备注） |
| RECONCILING | 对账中 | 匹配到疑似交易 |
| SETTLED | 已结算（终态） | 对账确认 |
| EXCEPTION | 异常（终态） | 对账标记异常 |
| CANCELLED | 已取消（终态） | 取消，预留自动释放 |

**关键约束**：`TRANSITIONS` 字典是**只读设计约束**（Rule 6：不得修改状态机）。加状态转换 = 改设计，需要先过计划文档。

### 2.5 分配引擎（§34-37）

`backend/app/modules/allocation/engine.py` — 一个**纯函数**，输入付款列表 + 账户列表，输出推荐资金方案。

算法要点（约束感知的贪心分配）：
1. 付款按 `优先级(URGENT>HIGH>NORMAL>LOW) → 计划日期 → 金额` 排序，先满足紧急的
2. 每个付款，从"可参与分配的账户"中取钱；**首选账户优先**，其余按"可规划金额从小到大"依次掏（小账户先用，保住大额储备）
3. 约束：币种匹配、`include_in_allocation=True`、`planning_available > 0`（最低留存已折算在内）
4. 不够的部分记 `shortage`（缺口），前端显示"未覆盖"灰色段

三个动作：
- `preview`：跑引擎，存为 PROPOSED 方案，**不冻结资金**
- `override`：手动调整各账户金额
- `confirm`：把方案落成 RESERVED 预留 → 付款进入 RESERVED，资金被虚拟冻结

### 2.6 对账（§42-46）

付款执行后，把系统里的付款和银行流水里的真实交易配对：
- **加权评分**：金额 0.45 / 账户 0.20 / 日期 0.15 / 对方 0.15 / 流水号 0.05，权重可在配置调
- 阈值：`auto_match_threshold=0.80`（自动匹配）、`review_threshold=0.60`（进人工工作台）
- 工作台：`/reconciliations/pending` 列出待处理，可 `select-transaction`（指定配对）、`confirm`（确认并结算，释放预留）、`reject`
- 支持退款 / 冲正关系（`relations` 模块）

### 2.7 现金流预测

`GET /forecast?days=7|30|90`：把未来到期的付款（含周期性账单生成的）投影到各账户每日余额，产出逐账户预测 + 低余额预警 + 汇总。另支持手工维护的 `cashflow-plans` 计划。

### 2.8 角色权限

| 角色 | 权限 |
| --- | --- |
| OWNER | 全部：增删改账户/银行/付款、分配、执行、导入、对账 |
| VIEWER | 只读：看仪表盘/账户/交易/预测/审计 |

注册规则：**第一个注册的用户自动成为 OWNER**，之后都是 VIEWER。后端用依赖注入 `require_owner` 拦截写操作，返回 `403 FORBIDDEN`。demo 用户 `demoowner` 会被强制为 OWNER（保证演示确定性）。

---

## 3. 核心业务流程

把上面的概念串成三条完整链路（建议照着前端页面走一遍 demo 数据来体会）：

### 链路 A：从账单到交易
```
上传银行 CSV/Excel
  → 202 Accepted（异步）
  → worker: 解析(ICBC/CMB/GENERIC) → 交易去重 → 规则分类 → 内部转账识别
  → 生成 Transaction 记录 + 更新账户 actual_balance
  → 前端「交易」页 / 仪表盘看到
```

### 链路 B：从规划到结算（付款全生命周期）
```
创建付款(DRAFT) → 规划(PLANNED)
  → 生成分配方案(ALLOCATED，preview/override)
  → 确认预留(RESERVED，资金虚拟冻结)
  → 等手动执行(WAITING_MANUAL_EXECUTION)
  → 用户去银行手动付款后，在系统登记执行(MANUALLY_EXECUTED)
  → 自动/人工对账(RECONCILING)
  → 确认结算(SETTLED，预留释放)
  （任何一步取消 → CANCELLED，预留释放）
```

### 链路 C：预测
```
周期账单(recurring) → beat 定时任务 recurring.generate_plans
  → 生成未来到期的付款
  → forecast 引擎把付款投影到账户余额
  → 7/30/90 天预测 + 低余额预警
```

---

## 4. 技术架构

### 4.1 架构总览

```
浏览器
  │  (Vue 3 SPA, :5173 dev / :80 生产)
  ▼
Nginx ──────────► /api/* 反代到 FastAPI
  │                  │
  │            FastAPI (Python 3.12 + SQLAlchemy 2 async)
  │                  │                        │
  │            PostgreSQL 16             Redis 7
  │                  │                        │
  │            Alembic 迁移              Celery broker/result
  │                  │                        │
  ▼              worker（异步解析/生成）  beat（定时）
（生产仅 Nginx :80/:443 对外暴露）
```

分层：**模块化单体（Modular Monolith）+ 异步 Worker**。不拆微服务，但按业务领域清晰分模块；耗时任务（账单解析）由 Celery 异步执行。

### 4.2 技术栈

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 前端 | Vue 3 + TypeScript + Vite 8 | Element Plus UI、Pinia 状态、Vue Router、Axios、ECharts |
| 后端 | Python 3.12 + FastAPI | Pydantic v2、SQLAlchemy 2 async、Alembic |
| 异步 | Celery 5 + Redis | worker（账单解析）+ beat（周期账单） |
| 数据 | PostgreSQL 16（生产）/ SQLite（测试） | asyncpg / aiosqlite 双轨 |
| 金额 | `Decimal` / `NUMERIC(18,2)` | **禁止 float** |
| 工具 | uv（后端依赖）、npm（前端）、Docker Compose | 本机无 make，用 uv/npm 原始命令 |

### 4.3 仓库结构

```
├── backend/                    # FastAPI 应用（uv 管理）
│   ├── app/
│   │   ├── main.py             # 入口：中间件、路由、启动种子
│   │   ├── api/router.py       # 版本化路由聚合 /api/v1
│   │   ├── core/               # config、database、redis、exceptions、middleware、logging
│   │   ├── modules/            # 14 个业务模块（见下）
│   │   ├── workers/            # Celery app + 任务
│   │   └── models.py           # 注册所有 ORM 模型
│   ├── alembic/                # 数据库迁移
│   └── tests/                  # 29 个测试文件 / 206 用例
├── frontend/                   # Vue 3 应用
│   └── src/
│       ├── api/client.ts       # Axios 实例 + 统一错误处理
│       ├── router/             # 路由 + 登录守卫
│       ├── stores/             # Pinia（auth 等）
│       ├── layouts/AppLayout.vue
│       └── views/              # 12 个页面
├── nginx/                      # 生产反代 + 静态托管 + 安全头
├── scripts/                    # 启动/停止/备份/恢复/demo/E2E
├── sample-data/                # 示例账单文件
├── docker-compose.yml          # 生产全栈
├── docker-compose.dev.yml      # 本地开发基础设施（PG + Redis）
├── CODING_PLAN.md              # 设计文档 + 62 个 Task 计划
└── Makefile                    # 便捷命令（本机无 make 则用原始命令）
```

### 4.4 后端模块地图（14 个业务模块）

| 模块 | 职责 | 主要 API |
| --- | --- | --- |
| `auth` | 用户、注册登录、JWT、角色 | `/auth/*` |
| `banks` | 银行目录 | `/banks` |
| `accounts` | 账户 + 三种余额 + 余额快照 | `/accounts`、`/accounts/{id}/balances` |
| `statements` | 账单导入/解析/去重/分类/交易 | `/statements` |
| `categories` | 交易分类规则 | （启动播种） |
| `payments` | 付款计划 + 状态机 | `/payments`、`/payments/{id}/transition`、`/manual-execution` |
| `recurring` | 周期性账单 → 自动生成付款 | `/recurring` |
| `allocation` | 分配引擎 + 预览/覆盖/预留 | `/payments/{id}/allocations/*` |
| `reconciliation` | 对账工作台 + 加权评分 | `/reconciliations/*` |
| `relations` | 退款 / 冲正关系 | （对账内部使用） |
| `forecast` | 现金流预测 | `/forecast`、`/cashflow-plans` |
| `retrieval` | 交易检索 | `/transactions` |
| `transfers` | 内部转账识别 | （导入管线使用） |
| `audit` | 审计日志 | `/audit` |

每个模块内部统一为 `models.py / schemas.py / repository.py / service.py / router.py` 五件套（`payments` 还有 `state_machine.py`）。

---

## 5. 本地环境：一步步跑起来

### 5.1 前置条件

| 工具 | 版本 | 获取 |
| --- | --- | --- |
| Docker Desktop | 最新 | 需在运行中（提供 PostgreSQL + Redis） |
| uv | 最新 | https://docs.astral.sh/uv/ |
| Node.js | 20+ | 前端构建 |
| Git Bash | - | Windows 上跑脚本用 |

> 注意：`make` 未安装，所有命令请用 uv / npm / 脚本的原始形式。

### 5.2 方式 A：一键脚本（推荐）

**Windows 双击** `start-dev.bat`（停止用 `stop-dev.bat`），或任意终端：

```bash
./scripts/start-dev.sh            # 一键：基础设施 + 迁移 + 后端 + worker + 前端
./scripts/start-dev.sh --demo     # 附带生成演示数据
./scripts/start-dev.sh --no-front # 只要后端 + worker
./scripts/stop-dev.sh             # 停止脚本拉起的进程
```

脚本会做：拉起 Docker 里 PostgreSQL(:5432) + Redis(:6379) → 等健康 → `alembic upgrade head` → 后端(:8000) → Celery worker → 前端(:5173)。**幂等**：已在跑的服务跳过。日志统一在 `.run/logs/`。

启动后：
- 前端：http://localhost:5173
- 后端 API：http://localhost:8000 ，接口文档 http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/v1/health （返回 `{"status":"ok","database":"ok","redis":"ok"}`）

### 5.3 方式 B：手动逐步启动

```bash
# 1. 基础设施（PostgreSQL + Redis）
docker compose -f docker-compose.dev.yml up -d

# 2. 后端依赖 + 迁移
cd backend
uv sync
uv run alembic upgrade head

# 3. 后端 API（热重载）
uv run uvicorn app.main:app --reload --port 8000

# 4. Celery worker（账单导入必需；两处配置缺一不可，见 §10）
DATABASE_POOLCLASS=null uv run celery -A app.workers.celery_app worker

# 5. 前端（另开终端）
cd frontend
npm install
npm run dev    # → :5173，/api 自动代理到 :8000
```

### 5.4 演示数据

```bash
cd backend
uv run python ../scripts/demo_data.py --reset    # 重建 demo 数据
```

登录：**`demoowner` / `demo123456`**。生成的内容：4 个账户（工资卡 128530.42 / 房贷 85200 / 日常消费 32410.80 / 备用储蓄 200000，各有最低留存）、5 条周期账单、6 笔覆盖状态机各阶段的付款（DRAFT / PLANNED / ALLOCATED / RESERVED / WAITING / MANUALLY_EXECUTED，其中两笔跑过真实分配引擎）。

### 5.5 体验建议路线

1. 打开 `:5173`，用 demoowner 登录 → 仪表盘
2. 「账户」页看三种余额
3. 「付款」页找 `季度物业费`（RESERVED）→ 看分配可视化
4. 「账单导入」页上传 `sample-data/statements/` 里的 CSV → 观察状态轮询到 SUCCESS
5. 「交易」页看到新导入的交易、「对账」页试试确认

---

## 6. 后端代码地图

### 6.1 启动链路（自顶向下读）

```
main.py: create_app()
  ├── configure_logging()
  ├── lifespan: seed_default_banks + seed_default_categories（best-effort，DB 挂了也能启动）
  ├── TraceIDMiddleware（X-Request-ID → trace_id 贯穿日志与错误响应）
  ├── CORSMiddleware
  ├── register_exception_handlers → 统一错误格式 {"code","message","trace_id"}
  └── include_router(api_router)  → 聚合 12 个模块 router，前缀 /api/v1
```

### 6.2 一次请求的旅程

```
HTTP → TraceIDMiddleware（生成/透传 trace_id）
     → 路由匹配 /api/v1/accounts
     → 依赖注入：get_db() 开 AsyncSession + 鉴权（CurrentUser）
     → Router → Service（业务逻辑）→ Repository（SQL 封装）→ ORM → PostgreSQL
     → 异常 → 统一错误信封；成功 → Pydantic 序列化
```

依赖注入约定（`backend/app/modules/auth/deps.py`）：
- `CurrentUser`：从 JWT 解析当前用户（读写都要）
- `OwnerUser`：额外要求 OWNER 角色，否则 403

### 6.3 统一错误格式（所有接口一致）

```json
{ "code": "FORBIDDEN", "message": "Insufficient permissions.", "trace_id": "..." }
```

常用错误码（`core/exceptions.py`）：`BAD_REQUEST` `UNAUTHORIZED` `FORBIDDEN` `NOT_FOUND` `CONFLICT` `VALIDATION_ERROR` `INVALID_STATE_TRANSITION` `INSUFFICIENT_PLANNING_FUNDS` `DUPLICATE_IMPORT` … 前端 `errorMessage()` 统一解析展示。

### 6.4 数据库

- **双轨**：生产 `postgresql+asyncpg://...`，测试 conftest 用环境变量覆盖为 SQLite（`sqlite+aiosqlite`）+ Redis 不可达端口 → 单测无需起服务
- **连接池**：API 用默认队列池；**Celery worker 必须 `DATABASE_POOLCLASS=null`**（见 §10）
- **迁移**：`uv run alembic revision --autogenerate -m "..."` → `uv run alembic upgrade head`
  > 坑：`alembic downgrade base` 会因未命名外键报错，重置用 `DROP SCHEMA public CASCADE; CREATE SCHEMA public` 再 upgrade
- **金额铁律**：所有钱都是 `Decimal` + `Numeric(18,2)`，任何地方禁止 float（`ruff` 配置也拦）

### 6.5 Celery worker

- `app/workers/celery_app.py`：broker/backend = Redis，`include=["app.workers.tasks"]`
- 任务：
  - `statements.process_import`：账单异步解析（上传 → 202 → worker 干活）
  - `recurring.generate_plans`：beat 每天生成未来 30 天到期的周期付款
- 任务内部用 `asyncio.run()` 包异步服务，所以连接池要 NullPool（每个任务独立连接）

### 6.6 一个典型模块长什么样（以 `payments` 为例）

```
models.py        # ORM：PaymentPlan + PaymentStatus/PaymentPriority 枚举 + 状态机源
state_machine.py # TRANSITIONS 字典（唯一事实源）+ assert_transition()
schemas.py       # Pydantic：PaymentCreate/PaymentRead/ManualExecution...
repository.py    # 数据访问封装
service.py       # 业务：create_payment / transition / manual_execution ...
router.py        # HTTP 层：依赖注入 + 权限 + 响应模型
```

---

## 7. 前端代码地图

### 7.1 启动链路

```
index.html → src/main.ts
  ├── createApp(App) → 全局注册 Element Plus 图标
  ├── createPinia()
  ├── router（含登录守卫 beforeEach：restore() + 未登录跳 /login）
  └── mount('#app')

App.vue → <router-view/>（路由决定 LoginView 或 AppLayout 壳）
router：/login 独立页；/ 下挂 AppLayout，children = 10 个业务页
```

### 7.2 目录

```
src/
├── api/client.ts     # Axios 实例：baseURL=/api/v1，请求带 Bearer token，
│                     # 401 时清会话跳登录；errorMessage() 统一取错误
├── stores/auth.ts    # Pinia：token/user、login/register/fetchMe/restore/logout
├── router/index.ts   # 12 个路由 + 守卫 + 标题
├── layouts/AppLayout.vue  # 侧栏导航(10项) + 顶栏(角色/用户/退出) + <router-view/>
├── views/            # 12 个页面（见下）
├── types/index.ts    # 与后端 schema 对应的 TS 类型
```

### 7.3 页面清单

| 页面 | 路由 | 要点 |
| --- | --- | --- |
| 登录 | `/login` | 注册/登录 |
| 仪表盘 | `/dashboard` | 汇总卡片、趋势图（ECharts） |
| 账户 | `/accounts`、`/accounts/:id` | 三种余额、余额快照趋势 |
| 交易 | `/transactions` | 检索、筛选、详情 |
| 账单导入 | `/statements` | 拖拽上传 + 进度轮询 + 错误详情 |
| 付款 | `/payments` | 列表 + 状态流转 + 手动执行登记 |
| 分配 | `/allocations` | 资金分配可视化（堆叠条、缺口灰色段）、手动调整 |
| 对账 | `/reconciliation` | 待处理列表、配对、确认/拒绝 |
| 现金流预测 | `/forecast` | 逐账户/汇总预测 + 低余额预警 |
| 审计 | `/audit` | 操作日志 |
| 设置 | `/settings` | 个人资料 + OWNER 管理银行目录 |

> 前端开发注意：所有金额以字符串（`"90000.00"`）从后端返回，前端展示即可，**不要做浮点运算**；计算一律交给后端引擎。

---

## 8. 测试体系

### 8.1 后端单元/集成测试

```bash
cd backend
uv run pytest            # 206 用例，29 个文件
uv run pytest -q -x      # 快速失败，方便调试
```

- 测试用 SQLite（aiosqlite），**不需要起 PostgreSQL/Redis**（conftest 覆盖 `DATABASE_URL` 和 `REDIS_URL`）
- 覆盖：状态机、分配引擎（纯函数）、账单解析器、去重、分类、对账评分、付款生命周期、鉴权权限、API 错误格式……
- 关键测试文件：`test_allocation_engine.py`（引擎纯逻辑）、`test_state_machine.py`（转移合法性）、`test_payments.py`（全生命周期）、`test_recon_scoring.py`

### 8.2 端到端测试

```bash
# 前提：后端 + worker 正在运行
cd backend
uv run python ../scripts/e2e_test.py      # 24 项检查，真实 PG + Redis + Celery
```

E2E 会真实走一遍：健康检查 → 注册/登录/角色 → OWNER 建账户（断言 `planning_available`）→ 建付款 → 状态流转 → 分配预览+确认 → 手动执行 → 上传真实 CSV → 轮询导入到 SUCCESS → 交易检索 → 预测 → VIEWER 越权 403。

### 8.3 前端检查

```bash
cd frontend
npm run type-check   # vue-tsc
npm run lint         # eslint
npm run build        # 类型检查 + 生产构建
```

### 8.4 回归清单（改完代码后跑什么）

```bash
# 后端
uv run pytest && uv run ruff check backend/app backend/tests
# 前端（如改了前端）
cd frontend && npm run type-check && npm run build
# 全链路（有 worker 在跑时）
uv run python ../scripts/e2e_test.py
```

---

## 9. 生产部署与运维

### 9.1 生产栈

```bash
cp .env.example .env     # 设一个强 SECRET_KEY（至少 32 字节），review 各连接串
docker compose up -d --build
```

6 个服务：`postgres` / `redis` / `api`（启动时自动 `alembic upgrade head`）/ `worker` / `beat` / `nginx`。**只有 nginx 暴露 :80（可选 :443）**。每个服务都有 healthcheck。`SECRET_KEY` 缺失会直接拒绝启动（`${SECRET_KEY:?}`）。

### 9.2 nginx 要点

- 安全头：`X-Content-Type-Options` / `X-Frame-Options: DENY` / CSP / `Referrer-Policy` / `Permissions-Policy`
- `/api` 反代到 api:8000，300s 超时，透传 `X-Request-ID`
- `/assets/` 长缓存（内容哈希文件名）
- TLS：挂证书到 `/etc/nginx/ssl/` 并取消注释 HTTPS server 块

### 9.3 备份与恢复

```bash
./scripts/backup.sh                                    # → ./backups/finflow-backup-<时间戳>.tar.gz
COMPOSE_FILE=docker-compose.yml ./scripts/backup.sh    # 生产栈
./scripts/restore.sh backups/finflow-backup-<时间戳>.tar.gz
```

备份包含：PostgreSQL 逻辑备份 + Redis 快照（尽力而为）+ 上传的账单文件。

### 9.4 其他运维脚本

| 脚本 | 用途 |
| --- | --- |
| `scripts/demo_data.py [--reset]` | 生成/重建演示数据 |
| `scripts/e2e_test.py` | 端到端测试 |
| `Makefile` | 便捷目标（`make test` / `make lint` / `make up`…，需 make） |

---

## 10. 常见坑与经验

这些是本项目实测踩过、且最容易被"环境问题"浪费时间的点：

### 10.1 Celery worker 必须两个配置一起上（Windows / 脚本场景）

1. **`DATABASE_POOLCLASS=null`**：任务用 `asyncio.run()` 每任务新事件循环，默认连接池跨循环复用会报 `Event loop is closed`，账单导入约每 2 次挂 1 次。
2. **`--pool=solo`**（仅 Windows + 从脚本 detach 启动时）：billiard 的 prefork 池在 detached 进程里共享内存读不了，报 `PermissionError [WinError 5]`。

```bash
DATABASE_POOLCLASS=null uv run celery -A app.workers.celery_app worker --pool=solo
```
`start-dev.sh` 已内置这两个配置；手动起 worker 时别漏。**该 bug 只在 asyncpg 上复现，SQLite 单测测不出来**（aiosqlite 不绑定事件循环）。

### 10.2 vite 8 在 Windows 上的构建问题

`build.emptyOutDir` 在 dist 已存在时会**静默杀死构建**（exit 127 / 0，什么都不写）。已在 `vite.config.ts` 设 `build.emptyOutDir: false` 绕开。如需彻底干净输出：`rm -rf dist` 后再 build。

### 10.3 Windows 下 curl 中文 body 会 400

`curl -d "中文"` 在 Windows 上常报 `400 error parsing the body`。用 ASCII 内容、或通过浏览器/axios（自动 UTF-8）发请求，或写文件上传。

### 10.4 alembic downgrade base 会挂

未命名外键导致 `CompileError`。重置数据库：
```sql
DROP SCHEMA public CASCADE; CREATE SCHEMA public;
```
再 `alembic upgrade head`。（`scripts/demo_data.py --reset` 内部按外键安全顺序删除，不需要动 schema。）

### 10.5 demo 数据重置是幂等的，且强制 OWNER

`--reset` 会删掉 demo 用户及其全部数据（按外键安全顺序），重建后强制 `demoowner` 为 OWNER —— 这是开发工具的数据操作，不是模型改动。

### 10.6 docker.io 拉镜像偶发超时

网络抖动会失败，重试即可（脚本/命令再跑一次）。

### 10.7 改了状态机/领域模型 = 改设计

`TRANSITIONS`、三种余额公式、分配引擎约束、安全边界都是**设计约束**。改它们前先回 `CODING_PLAN.md` 确认，而不是直接在代码里动。

---

## 11. 推荐学习路线

如果你是新接手这个项目，建议按这个顺序：

1. **先读 `README.md` + 本文 §1-2**：搞清楚"是什么、红线在哪、三个核心概念"（半天）
2. **跑起来 + 走一遍 demo 数据**（§5）：建立体感（半天）
3. **跟一次真实请求**：读 `main.py` → `api/router.py` → 挑 `accounts` 模块五件套，看一次 GET /accounts 的完整旅程（1 天）
4. **吃透两个核心算法**：`state_machine.py`（状态机）+ `allocation/engine.py`（分配引擎）—— 这是业务的"大脑"（1 天）
5. **跟一条异步链路**：`statements/router.py` 上传 → celery 任务 → `parse/` 解析 → 分类 → 入库（1 天）
6. **跑一遍测试**（§8），读懂 `conftest.py` 的双轨机制（半天）
7. **按需深入**：对账评分、预测引擎、前端各页面（各半天到 1 天）

**常见改动入口速查**：
- 想加一个 API：模块里建/改 `router.py` + `schemas.py` + `service.py`，别忘 `api/router.py` 挂载 + 测试
- 想改前端页面：改对应 `views/*View.vue`，类型在 `types/index.ts`
- 想加一个 Celery 任务：`workers/tasks.py` + `celery_app.py` 的 `include`，别忘 `DATABASE_POOLCLASS=null`
- 想加一个数据库字段：`models.py` + `alembic revision --autogenerate` + 迁移

---

*这份文档与代码保持同步维护。若发现某处与代码不符，以代码和 `CODING_PLAN.md` 为准，并更新本文。*
