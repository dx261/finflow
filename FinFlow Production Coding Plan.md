# FinFlow — Personal Treasury Management System

## AI Coding Agent Implementation Plan

---

# 0. 项目定位

## 0.1 项目名称

**FinFlow — Personal Treasury Management System**

中文：

**FinFlow — 个人多账户资金管理与现金流规划平台**

---

## 0.2 项目目标

FinFlow 是一个供个人长期使用的资金管理系统。

系统负责：

- 多银行账户统一管理
- 银行 Excel / CSV 流水导入
- 异构账单自动解析
- 银行交易标准化
- 收支分类
- 内部转账识别
- 付款计划管理
- 周期性付款管理
- 多账户资金分配建议
- 虚拟资金预占
- 最低余额保护
- 现金流预测
- 人工银行操作记录
- 银行流水自动对账
- 退款 / 冲正关联
- 历史交易检索
- 账户余额趋势
- 财务 Dashboard
- 审计日志

系统**绝不直接操作真实银行账户**。

---

# 1. Hard Safety Boundary

以下功能明确禁止实现：

```text
真实银行自动登录

真实银行账号密码存储

短信验证码自动读取

OTP 自动处理

USB Key 自动控制

真实银行网页自动点击

真实银行客户端 RPA

自动转账

自动付款

自动修改真实银行资金

绕过银行安全认证

抓取银行私有接口
```

FinFlow 的职责结束在：

```text
资金规划
    ↓
资金分配建议
    ↓
用户人工确认
    ↓
用户自行前往银行操作
    ↓
FinFlow 记录“已人工执行”
    ↓
导入银行流水
    ↓
自动对账
```

FinFlow 是：

> Treasury Decision & Reconciliation System

而不是：

> Banking Execution System

---

# 2. 核心业务流程

系统最终必须支持如下完整流程：

```text
银行导出 Excel / CSV
        ↓
上传 FinFlow
        ↓
自动识别银行账单格式
        ↓
解析交易
        ↓
统一 Transaction Schema
        ↓
账户余额更新
        ↓
创建未来付款计划
        ↓
资金分配算法
        ↓
生成 Recommended Funding Plan
        ↓
虚拟预占资金
        ↓
用户人工完成真实支付
        ↓
用户点击“已人工执行”
        ↓
之后再次导入银行流水
        ↓
自动匹配真实交易
        ↓
Reconciliation
        ↓
SETTLED
```

---

# 3. 技术架构原则

本项目不采用过度微服务化。

采用：

# Modular Monolith + Async Worker

整体架构：

```text
                     Browser
                        │
                        ▼
                   ┌─────────┐
                   │  Nginx  │
                   └────┬────┘
                        │
            ┌───────────┴──────────┐
            │                      │
            ▼                      ▼
       Vue Static              /api/*
        Frontend                  │
                                  ▼
                            ┌───────────┐
                            │ FastAPI   │
                            │ Backend   │
                            └─────┬─────┘
                                  │
                    ┌─────────────┼──────────────┐
                    │             │              │
                    ▼             ▼              ▼
               PostgreSQL       Redis        File Storage
                                   │
                                   ▼
                            Celery Worker
                                   │
                    ┌──────────────┼─────────────┐
                    ▼              ▼             ▼
               Excel Parse    Reconcile     Forecast
```

---

# 4. Technology Stack

## Frontend

```text
Vue 3
TypeScript
Vite
Element Plus
Pinia
Vue Router
Axios
ECharts
Day.js
```

---

## Backend

```text
Python 3.12+
FastAPI
Pydantic v2
SQLAlchemy 2.x
Alembic
PostgreSQL
Redis
Celery
Pandas
NumPy
python-calamine
openpyxl
RapidFuzz
```

原则：

读取 Excel 优先：

```text
python-calamine
```

生成 Excel：

```text
openpyxl
```

金额：

```text
Decimal
```

禁止使用：

```text
float
```

处理财务金额。

---

# 5. Infrastructure

Docker Compose 至少运行：

```text
nginx
api
worker
beat
postgres
redis
```

架构：

```text
Docker Compose

├── nginx
│
├── api
│   └── FastAPI
│
├── worker
│   └── Celery Worker
│
├── beat
│   └── Celery Beat
│
├── postgres
│
└── redis
```

---

# 6. Repository Structure

```text
finflow/
│
├── frontend/
│   ├── src/
│   └── Dockerfile
│
├── backend/
│   ├── app/
│   │
│   ├── tests/
│   ├── alembic/
│   └── Dockerfile
│
├── nginx/
│   ├── nginx.conf
│   └── Dockerfile
│
├── sample-data/
│   ├── statements/
│   └── demo/
│
├── scripts/
│
├── docker-compose.yml
├── docker-compose.dev.yml
│
├── .env.example
├── README.md
├── CODING_PLAN.md
└── Makefile
```

---

# 7. Backend Modular Architecture

Backend：

```text
backend/app/
│
├── main.py
│
├── core/
│   ├── config.py
│   ├── database.py
│   ├── redis.py
│   ├── security.py
│   ├── logging.py
│   └── exceptions.py
│
├── modules/
│
│   ├── auth/
│   ├── accounts/
│   ├── statements/
│   ├── transactions/
│   ├── categories/
│   ├── payments/
│   ├── recurring/
│   ├── allocation/
│   ├── reconciliation/
│   ├── forecast/
│   ├── transfers/
│   ├── retrieval/
│   ├── dashboard/
│   ├── audit/
│   └── settings/
│
├── workers/
│
└── shared/
```

每个模块采用：

```text
module/
├── router.py
├── schemas.py
├── models.py
├── repository.py
├── service.py
└── exceptions.py
```

必须遵循：

```text
Router
   ↓
Service
   ↓
Repository
   ↓
Database
```

Router 中禁止实现核心业务算法。

---

# 8. Docker Architecture

`docker-compose.yml`

至少包含：

## nginx

职责：

```text
HTTPS termination
Frontend static files
Reverse proxy
Compression
Request limit
Security headers
```

---

## api

运行：

```text
uvicorn app.main:app
```

---

## worker

运行：

```text
celery -A app.workers.celery_app worker
```

负责：

```text
Excel parsing
CSV parsing
Transaction normalization
Reconciliation
Forecast recalculation
Large exports
Statistics calculation
```

---

## beat

负责周期任务：

```text
生成周期付款

检查过期付款计划

重新计算未来现金流

清理临时文件

更新统计缓存
```

---

## redis

承担：

```text
Celery Broker

Celery Results

Cache

Distributed Lock

Idempotency Key

Rate Limit State
```

---

## postgres

保存全部核心财务数据。

---

# 9. Nginx Routing

外部只开放：

```text
80
443
```

禁止直接暴露：

```text
PostgreSQL
Redis
FastAPI internal port
```

Nginx：

```text
/
    → Vue

/api/
    → FastAPI

/docs/
    → FastAPI Swagger
```

生产环境可选择关闭：

```text
/docs
```

---

# 10. Authentication

虽然是个人系统，也必须设计用户系统。

## User

```text
id
username
email
password_hash
status
created_at
updated_at
```

角色：

```text
OWNER
VIEWER
```

OWNER：

全部权限。

VIEWER：

只读。

认证：

```text
JWT Access Token
Refresh Token
```

密码：

```text
Argon2 / bcrypt
```

---

# 11. Bank Model

## Bank

```text
id

code
name

country
logo

statement_parser_type

created_at
```

例如：

```text
ICBC
CMB
CCB
BOC
ALIPAY
WECHAT
GENERIC
```

这里只代表：

> 数据来源

不代表系统与银行建立 API 连接。

---

# 12. Account Model

## Account

```text
id
user_id
bank_id

name

masked_account_no

account_type

currency

actual_balance

balance_as_of

minimum_balance

include_in_allocation

status

created_at
updated_at
```

account_type：

```text
CHECKING
SAVINGS
CREDIT_CARD
CASH
E_WALLET
OTHER
```

---

# 13. 三种余额概念

必须严格区分：

## Actual Balance

最近一次银行流水 / 用户手工确认的实际余额。

```text
actual_balance
```

---

## Reserved Amount

FinFlow 根据未来付款计划进行的：

> 虚拟资金预占

不是银行真实冻结。

```text
reserved_amount
```

---

## Available For Planning

计算：

```text
planning_available
=
actual_balance
-
reserved_amount
-
minimum_balance
```

例如：

```text
actual_balance    30,000
reserved_amount    5,000
minimum_balance   10,000
```

那么：

```text
planning_available = 15,000
```

注意：

`planning_available` 应优先动态计算。

不要把所有派生值重复持久化。

---

# 14. Balance Snapshot

建立：

## AccountBalanceSnapshot

```text
id
account_id

balance
available_balance

snapshot_date

source

created_at
```

source：

```text
STATEMENT
MANUAL
IMPORT
```

用于绘制：

```text
Balance Trend
```

---

# 15. Statement Import

## StatementImport

```text
id

account_id

original_filename

stored_filename

file_hash

file_type

status

statement_start_date
statement_end_date

total_rows
success_rows
failed_rows

created_at
completed_at
```

状态：

```text
UPLOADED
QUEUED
PARSING
PARTIAL_SUCCESS
SUCCESS
FAILED
```

---

# 16. 文件导入流程

用户上传：

```text
ICBC_2026_09.xlsx
```

FastAPI 不同步解析。

流程：

```text
Upload
   ↓
Calculate SHA256
   ↓
Create StatementImport
   ↓
Save File
   ↓
Push Celery Job
   ↓
Return 202 Accepted
```

Worker：

```text
Read File
   ↓
Identify Parser
   ↓
Extract Metadata
   ↓
Detect Table
   ↓
Normalize Transactions
   ↓
Duplicate Detection
   ↓
Database Insert
   ↓
Reconciliation Trigger
```

---

# 17. Duplicate File Protection

使用：

```text
SHA256
```

如果：

```text
same user
same account
same file hash
```

重复上传：

返回：

```text
DUPLICATE_IMPORT
```

除非用户明确：

```text
force_import=true
```

---

# 18. Floating Coordinate Anchor Parser

核心目录：

```text
modules/statements/parsers/
│
├── base.py
├── normalizer.py
├── anchor_detector.py
├── table_detector.py
├── validators.py
├── generic.py
├── icbc.py
├── cmb.py
└── factory.py
```

---

# 19. Normalization

实现：

```python
normalize_text(value)
```

处理：

```text
空格
换行
\u200b
英文冒号
中文冒号
大小写
Unicode
```

例如：

```text
" Posting Date： "
```

→

```text
postingdate
```

---

# 20. Anchor Detection

支持：

```text
account number
statement date
currency
balance
```

例如：

```python
ANCHORS = {
    "balance": [
        "balance",
        "余额",
        "账户余额",
        "可用余额",
    ]
}
```

Anchor 找到后：

```text
Right Search
Down Search
Validator
```

---

# 21. Dynamic Transaction Table Detection

禁止：

```python
header_row = 5
```

这类硬编码。

每一行计算：

```text
Header Coverage Score
```

例如：

```text
交易日期
摘要
金额
余额
```

匹配 4 个字段：

```text
score = 4
```

选择最高合法 Score。

---

# 22. Transaction Model

## Transaction

```text
id

account_id
statement_import_id

external_reference

transaction_date
posting_date

direction

amount
currency

counterparty_name
counterparty_account_masked

description

balance_after

category_id

transaction_type

reconciliation_status

raw_data

fingerprint

created_at
```

direction：

```text
DEBIT
CREDIT
```

---

# 23. Transaction Fingerprint

用于去重。

Fingerprint 可以由：

```text
account_id
transaction_date
amount
direction
description
external_reference
```

生成 Hash。

不允许单纯依赖：

```text
金额 + 日期
```

因为可能存在合法重复消费。

---

# 24. Transaction Categories

## Category

例如：

```text
Salary

Rent

Food

Transport

Shopping

Education

Subscription

Medical

Investment

Transfer

Refund

Credit Card Repayment

Other
```

允许用户自定义。

---

# 25. Rule-Based Classification

第一阶段不要急于加入 AI。

采用：

```text
keyword rules

counterparty rules

amount rules

account rules
```

例如：

```text
NETFLIX
→ Subscription
```

规则表：

## ClassificationRule

```text
id

priority

field
operator
value

category_id

enabled
```

后续再考虑 ML / LLM。

---

# 26. Internal Transfer Detection

这是核心功能。

例如：

账户 A：

```text
-5000
```

账户 B：

```text
+5000
```

如果满足：

```text
amount equal

time close

different owned accounts
```

则识别：

```text
INTERNAL_TRANSFER
```

创建：

## TransferLink

```text
id

out_transaction_id
in_transaction_id

confidence

status

created_at
```

内部转账不计入：

```text
Income

Expense
```

统计。

---

# 27. Payment Plan

## PaymentPlan

```text
id

name
description

payee_name

amount
currency

planned_date

priority

preferred_account_id

status

manual_execution_at
manual_execution_note

created_at
updated_at
```

状态：

```text
DRAFT

PLANNED

ALLOCATED

RESERVED

WAITING_MANUAL_EXECUTION

MANUALLY_EXECUTED

RECONCILING

SETTLED

EXCEPTION

CANCELLED
```

---

# 28. Payment State Machine

正常：

```text
DRAFT
   ↓
PLANNED
   ↓
ALLOCATED
   ↓
RESERVED
   ↓
WAITING_MANUAL_EXECUTION
   ↓
MANUALLY_EXECUTED
   ↓
RECONCILING
   ↓
SETTLED
```

异常：

```text
MANUALLY_EXECUTED
    ↓
EXCEPTION
```

取消：

```text
PLANNED
RESERVED
WAITING_MANUAL_EXECUTION
        ↓
CANCELLED
```

禁止：

```text
SETTLED → DRAFT
```

Router 禁止：

```python
payment.status = ...
```

统一通过：

```python
PaymentStateService.transition()
```

---

# 29. Manual Execution

FinFlow 不执行付款。

用户在真实银行完成操作以后：

点击：

```text
Mark as Manually Executed
```

用户可填写：

```text
实际执行日期

实际执行账户

备注

银行参考号（可选）
```

API：

```text
POST /api/v1/payments/{id}/manual-execution
```

系统只记录：

```text
USER CLAIMED EXECUTED
```

不能直接把 Payment 标记：

```text
SETTLED
```

必须等待真实流水匹配。

---

# 30. Funding Pool

Funding Pool 不代表真正冻结的银行资金。

它只是：

> Planning View

## FundingPool

```text
id

account_id

available_from
available_until

planning_amount

priority

enabled
```

第一阶段也允许直接根据：

```text
Account
```

动态生成 Funding Pool。

不一定持久化。

---

# 31. Allocation

## FundAllocation

```text
id

payment_id
account_id

allocated_amount

status

algorithm_version

created_at
released_at
settled_at
```

状态：

```text
PROPOSED
RESERVED
RELEASED
SETTLED
```

---

# 32. Virtual Reservation

这里非常重要：

FinFlow 的 Reserve 只是软件内部状态。

并不代表银行冻结资金。

例如：

账户：

```text
Actual Balance
30,000
```

Payment：

```text
Tuition
20,000
```

Reserve 后：

```text
Actual Balance
30,000

Virtual Reserved
20,000

Available For Planning
10,000
```

真实银行仍然：

```text
30,000
```

---

# 33. Money Representation

数据库：

```text
NUMERIC(18, 2)
```

Python：

```python
Decimal
```

核心算法可转换：

```text
Cent Integer
```

例如：

```text
123.45
```

→

```text
12345
```

避免浮点误差。

---

# 34. Allocation Algorithm V1

第一版：

# Constraint-Aware Greedy Allocation

输入：

```text
Payments

Accounts

Minimum Balances

Reserved Amounts

Preferred Accounts
```

约束：

```text
currency match

available balance > 0

minimum balance cannot be violated

disabled account cannot be used
```

---

# 35. Payment Sorting

建议：

```text
priority DESC

planned_date ASC

amount ASC

id ASC
```

---

# 36. Account Sorting

建议：

```text
preferred account first

available amount ASC

account priority DESC
```

---

# 37. Algorithm Example

账户：

```text
CMB

Actual           8,000
Minimum          1,000
Available         7,000
```

ICBC：

```text
Actual          20,000
Reserved         3,000
Minimum          5,000
Available        12,000
```

Payment：

```text
Rent            10,000
```

算法：

```text
CMB      7,000
ICBC     3,000
```

结果只是：

```text
Recommended Funding Plan
```

---

# 38. Allocation Preview

点击：

```text
Auto Allocate
```

第一步只生成：

```text
PROPOSED
```

前端显示：

```text
Rent ¥10,000

CMB        ¥7,000
ICBC       ¥3,000
```

用户点击：

```text
Accept Plan
```

才变：

```text
RESERVED
```

这样用户可以人工调整。

---

# 39. Manual Allocation

必须允许用户覆盖算法。

例如：

```text
系统建议：

CMB 7000
ICBC 3000
```

用户改成：

```text
CMB 5000
ICBC 5000
```

系统重新验证：

```text
余额
最低余额
币种
总金额
```

通过才能保存。

---

# 40. Minimum Balance Protection

Account：

```text
minimum_balance
```

默认：

```text
0
```

例如：

```text
ICBC Saving

Balance          50,000
Minimum Reserve  20,000
```

算法最大只能使用：

```text
30,000
```

---

# 41. Reconciliation Engine

核心用途：

确认用户是否真的完成了付款。

输入：

```text
PaymentPlan

Bank Transaction
```

输出：

```text
MATCH
REVIEW
NO_MATCH
```

---

# 42. Reconciliation Model

## Reconciliation

```text
id

payment_id
transaction_id

total_score

amount_score
date_score
counterparty_score
reference_score
account_score

status

confirmed_by
confirmed_at

created_at
```

状态：

```text
AUTO_MATCHED

REVIEW_REQUIRED

CONFIRMED

REJECTED
```

---

# 43. Matching Score

默认：

```text
Amount          45%

Account         20%

Date            15%

Counterparty    15%

Reference        5%
```

配置存放：

```text
settings
```

禁止硬编码。

---

# 44. Amount Matching

金额完全一致：

```text
1.0
```

如果金额不同：

快速降低。

默认情况下：

金额必须是非常强的匹配信号。

---

# 45. Date Matching

例如：

```text
same day       1.0

±1 day         0.9

±3 days        0.7

>7 days        0.2
```

配置化。

---

# 46. Counterparty Matching

使用：

```text
RapidFuzz
```

支持：

```text
房东张三

张三

ZHANG SAN
```

等轻微差异。

---

# 47. Reconciliation Trigger

每次完成：

```text
Statement Import
```

自动触发：

```text
reconciliation job
```

查找：

```text
MANUALLY_EXECUTED

RECONCILING
```

状态付款。

---

# 48. Auto Settlement

只有满足：

```text
score >= auto_match_threshold
```

才能：

```text
Payment → SETTLED
```

同时：

```text
FundAllocation → SETTLED
```

否则：

```text
REVIEW_REQUIRED
```

---

# 49. Reconciliation Workbench

前端：

```text
Payment
────────────────────────

Rent
¥8,000
Manually executed:
2026-09-05


Suggested Match
────────────────────────

2026-09-05
-¥8,000
Zhang San

Score:
97%
```

按钮：

```text
Confirm

Reject

Select Another Transaction
```

---

# 50. Failed Manual Execution

如果用户实际付款失败：

用户点击：

```text
Execution Failed
```

则：

```text
RESERVED
    ↓
RELEASE
    ↓
PLANNED
```

或者：

```text
CANCELLED
```

由用户选择。

---

# 51. Recurring Payment

## RecurringPayment

```text
id

name

amount

currency

frequency

day_of_month

start_date
end_date

preferred_account_id

priority

enabled

created_at
```

frequency：

```text
WEEKLY

MONTHLY

QUARTERLY

YEARLY
```

例如：

```text
Rent

¥8,000

MONTHLY

Day 1
```

---

# 52. Celery Beat

每天检查：

```text
未来 N 天
```

RecurringPayment。

生成：

```text
PaymentPlan
```

必须保证：

```text
idempotent
```

不能重复生成同一个月份的房租。

---

# 53. Cash Flow Forecast

这是整个系统第二核心能力。

预测：

```text
Actual Balance

+ Scheduled Income

- Planned Payments

- Reserved Payments
```

输出未来：

```text
7 days

30 days

90 days
```

现金流。

---

# 54. Forecast Model

不用提前生成每天记录。

可以动态计算。

输出：

```text
date

starting_balance

expected_income

expected_expense

ending_balance
```

---

# 55. Forecast Example

```text
Sept 05
¥50,000

Sept 10
Rent
-¥8,000

Sept 15
Salary
+¥15,000

Sept 20
Credit Card
-¥12,000

Expected Sept 30

¥45,000
```

---

# 56. Low Balance Warning

如果未来余额：

```text
forecast_balance < minimum_balance
```

生成：

```text
WARNING
```

例如：

```text
预计 9 月 20 日 ICBC 余额将低于最低保留资金 ¥10,000。
```

---

# 57. Planned Income

建立：

## CashFlowPlan

```text
id

type

name

amount

date

account_id

status
```

type：

```text
INCOME
EXPENSE
```

PaymentPlan 属于更完整的 Expense 模型。

---

# 58. Refund & Reversal

Transaction：

支持：

```text
NORMAL

REFUND

REVERSAL

TRANSFER

FEE

INTEREST
```

---

# 59. Transaction Relation

## TransactionRelation

```text
id

source_transaction_id
target_transaction_id

relation_type

confidence

created_at
```

类型：

```text
REFUND

REVERSAL

INTERNAL_TRANSFER

CORRECTION
```

---

# 60. Historical Retrieval

不要单独拆微服务。

实现：

```text
modules/retrieval/
```

支持：

```text
date range

account

amount range

counterparty

description

category

transaction type

payment status
```

---

# 61. Advanced Search

API：

```text
GET /api/v1/transactions
```

支持：

```text
?page=

&page_size=

&account_id=

&date_from=

&date_to=

&min_amount=

&max_amount=

&category=

&keyword=

&direction=
```

---

# 62. PostgreSQL Full Text

第一版可使用：

```text
ILIKE
```

后续升级：

```text
PostgreSQL Full Text Search
```

针对：

```text
description

counterparty

notes
```

---

# 63. Dashboard

核心 Dashboard：

```text
Net Cash

Total Account Balance

Planning Available

Virtual Reserved

Upcoming Payments

Monthly Income

Monthly Expense

Cash Flow Forecast

Balance Distribution

Category Distribution

Recent Transactions
```

---

# 64. Dashboard Redis Cache

Dashboard 聚合计算可以缓存：

```text
dashboard:{user_id}
```

TTL：

```text
30~120 seconds
```

每次：

```text
transaction import

payment update

allocation update
```

失效缓存。

---

# 65. Redis Distributed Lock

以下操作使用锁：

```text
statement parsing

reconciliation batch

allocation confirmation

recurring payment generation
```

避免任务重复运行。

---

# 66. Idempotency

POST 操作支持：

```text
Idempotency-Key
```

重点：

```text
statement upload

manual execution

allocation confirm

reconciliation confirm
```

---

# 67. File Storage

第一阶段使用：

```text
Docker Volume
```

例如：

```text
/app/data/uploads
```

目录：

```text
uploads/

statements/

exports/

temp/
```

文件名不得直接使用用户原始文件名。

使用：

```text
UUID
```

防止：

```text
path traversal
```

---

# 68. Import Error

## ImportError

```text
id

statement_import_id

row_number

field

raw_value

error_code

message

created_at
```

即使部分行失败：

其他合法行仍然导入。

---

# 69. 207 Multi-Status

导入结果：

```json
{
  "status": "PARTIAL_SUCCESS",
  "total": 100,
  "success": 97,
  "failed": 3
}
```

---

# 70. Audit Log

所有关键操作记录：

## AuditLog

```text
id

user_id

action

resource_type
resource_id

before_data
after_data

trace_id

created_at
```

包括：

```text
创建 Payment

确认资金分配

释放资金预占

标记人工执行

确认对账

修改实际余额

删除交易
```

---

# 71. Application Settings

## UserSettings

支持：

```text
base_currency

default_forecast_days

auto_match_threshold

review_threshold

default_minimum_balance

date_format
```

---

# 72. Base Currency

第一版可以只支持：

```text
CNY
```

数据结构必须支持：

```text
currency
```

以后扩展：

```text
JPY

USD

EUR
```

---

# 73. Exchange Rate

如果未来实现多币种：

Exchange Rate 只能用于：

```text
Dashboard conversion

Forecast display
```

不能修改原始交易金额。

---

# 74. Frontend Pages

```text
/login

/dashboard

/accounts

/accounts/:id

/statements

/transactions

/payments

/payments/:id

/recurring

/allocation

/reconciliation

/forecast

/transfers

/reports

/settings

/audit
```

---

# 75. Accounts Page

显示：

```text
Bank

Account

Actual Balance

Virtual Reserved

Minimum Balance

Planning Available
```

---

# 76. Account Detail

显示：

```text
Balance History

Recent Transactions

Upcoming Payments

Reserved Allocations

Income / Expense Trend
```

---

# 77. Statement Import UI

流程：

```text
Drag File

Select Account

Preview

Upload

Queued

Parsing

Completed
```

显示：

```text
100 rows

97 successful

3 errors
```

允许：

```text
Download Error Report
```

---

# 78. Payments UI

展示：

```text
Upcoming

Waiting Execution

Executed

Reconciliation Required

Settled

Cancelled
```

---

# 79. Manual Execution UI

付款详情：

```text
FinFlow Recommendation

Pay From:
CMB ¥5,000
ICBC ¥3,000
```

下方醒目提示：

```text
FinFlow will not execute this payment.

Please complete the payment manually through your bank.
```

之后点击：

```text
I Have Completed This Payment
```

---

# 80. Allocation Visualizer

重点 Demo 页面。

例如：

```text
Tuition
¥20,000

        ┌── ICBC Savings ¥15,000
        │
Payment ┤
        │
        └── CMB Checking ¥5,000
```

同时显示：

```text
Before

After Planning

Minimum Balance
```

---

# 81. Forecast UI

ECharts：

```text
30-Day Expected Balance
```

展示：

```text
Current Balance

Forecast Balance

Minimum Balance Line
```

---

# 82. Reports

支持导出：

```text
Monthly Cash Flow

Account Summary

Expense Breakdown

Payment History

Transaction List
```

导出：

```text
CSV

XLSX
```

---

# 83. Security

必须实现：

```text
JWT validation

password hashing

input validation

upload size limit

extension validation

MIME validation

path traversal protection

CORS

rate limiting

secure headers
```

---

# 84. Sensitive Data Policy

禁止保存：

```text
银行卡完整卡号

网上银行密码

支付密码

身份证号码

短信验证码

银行 Cookie

Bank Session Token
```

账户只保存：

```text
****1234
```

---

# 85. Nginx Security Headers

配置：

```text
X-Content-Type-Options

X-Frame-Options

Referrer-Policy

Content-Security-Policy
```

生产环境：

```text
HTTPS
```

---

# 86. Database Transaction Boundary

以下操作必须原子化：

```text
Allocation Confirm

Reservation

Reservation Release

Settlement

Reconciliation Confirmation
```

例如：

```text
BEGIN

Create Allocation

Update Payment State

Create Audit Log

COMMIT
```

任何一步失败：

```text
ROLLBACK
```

---

# 87. Concurrency

虽然个人系统并发低，但仍要正确。

资金预占时：

```text
SELECT ... FOR UPDATE
```

锁定涉及账户。

防止双重预占。

---

# 88. Database Index

至少：

```text
Transaction(account_id, transaction_date)

Transaction(fingerprint)

Transaction(external_reference)

PaymentPlan(status, planned_date)

FundAllocation(payment_id)

FundAllocation(account_id)

StatementImport(account_id, created_at)

Reconciliation(payment_id)

AuditLog(resource_type, resource_id)
```

---

# 89. Alembic

所有 Schema 修改：

```text
Alembic Migration
```

禁止长期依赖：

```python
Base.metadata.create_all()
```

---

# 90. Logging

采用：

```text
Structured JSON Logging
```

例如：

```json
{
  "timestamp": "...",
  "level": "INFO",
  "trace_id": "...",
  "module": "allocation",
  "event": "allocation_confirmed",
  "payment_id": "..."
}
```

---

# 91. Trace ID

Nginx / FastAPI：

传播：

```text
X-Request-ID
```

每次 Request 都有 Trace ID。

Celery Task 同样传递。

---

# 92. Error Format

统一：

```json
{
  "code": "INSUFFICIENT_PLANNING_FUNDS",
  "message": "Planning funds are insufficient.",
  "trace_id": "..."
}
```

前端不能收到：

```text
Python traceback
```

---

# 93. Testing Strategy

## Unit Tests

覆盖：

```text
Normalizer

Anchor Detection

Transaction Table Detection

Money Conversion

Transaction Fingerprint

Internal Transfer Detection

Allocation Algorithm

Minimum Balance

Payment State Machine

Reconciliation Score

Forecast Engine
```

---

# 94. Allocation Tests

## Exact

```text
Account 100

Payment 100
```

↓

```text
100 allocated
```

---

## Split

```text
Account A 50
Account B 50

Payment 80
```

↓

```text
50 + 30
```

---

## Minimum Reserve

```text
Balance 100

Minimum 40

Payment 80
```

↓

```text
Maximum Allocation 60

Shortage 20
```

---

## Reserved Funds

```text
Balance 100

Reserved 30

Minimum 20
```

Planning Available：

```text
50
```

---

# 95. Internal Transfer Tests

```text
Account A

-5000

Account B

+5000
```

时间：

```text
within 1 day
```

结果：

```text
INTERNAL_TRANSFER
```

不进入：

```text
Income / Expense
```

---

# 96. Reconciliation Tests

Payment：

```text
¥8000

Account A

Sept 5
```

Transaction：

```text
-¥8000

Account A

Sept 5
```

结果：

```text
AUTO_MATCHED
```

---

# 97. Parser Test Files

创建：

```text
sample-data/statements/
```

包含：

```text
icbc_standard.xlsx

icbc_shifted.xlsx

icbc_extra_row.xlsx

cmb_standard.xlsx

cmb_chinese_colon.xlsx

generic.xlsx

malformed.xlsx

duplicate.xlsx
```

---

# 98. Integration Test

必须覆盖：

```text
Create Account

Upload Statement

Parse Transaction

Create Payment

Run Allocation

Confirm Allocation

Mark Manual Execution

Upload New Statement

Auto Reconcile

Settle Payment
```

这是核心：

# Golden Path Test

---

# 99. Docker Test

CI 中：

```text
docker compose up
```

必须验证：

```text
GET /api/v1/health
```

返回：

```json
{
  "status": "ok"
}
```

---

# 100. Health Checks

分别检查：

```text
API

Postgres

Redis

Worker
```

API：

```text
/api/v1/health
```

返回：

```json
{
  "status": "ok",
  "database": "ok",
  "redis": "ok"
}
```

---

# 101. Development Docker Compose

开发：

```text
docker-compose.dev.yml
```

可以运行：

```text
postgres

redis
```

本地：

```text
FastAPI

Vite
```

方便热更新。

---

# 102. Production Docker Compose

生产：

```text
nginx

api

worker

beat

postgres

redis
```

全部使用：

```text
restart: unless-stopped
```

设置：

```text
healthcheck
```

---

# 103. Persistent Volumes

必须持久化：

```text
postgres_data

redis_data

uploads_data
```

数据库绝不能因为：

```text
docker compose down
```

丢失。

---

# 104. Backup

创建：

```text
scripts/backup.sh
```

备份：

```text
PostgreSQL

Uploads
```

创建：

```text
scripts/restore.sh
```

---

# 105. Makefile

提供：

```text
make dev

make up

make down

make logs

make test

make lint

make migrate

make backup

make restore
```

---

# 106. Demo Data Generator

实现：

```text
scripts/generate_demo_data.py
```

生成：

```text
5 Banks

8 Accounts

1000 Transactions

30 Payments

12 Recurring Payments

20 Reconciliations
```

---

# 107. Demo Scenario

Accounts：

```text
ICBC Checking
¥12,000

ICBC Savings
¥30,000

CMB Checking
¥8,000

CCB Checking
¥5,000
```

Minimum：

```text
ICBC Savings
¥10,000
```

---

Payments：

```text
Rent
¥8,000

Credit Card
¥12,000

Tuition
¥20,000

Subscription
¥1,500
```

---

Allocation：

```text
Rent

CMB
¥8,000
```

```text
Credit Card

ICBC Checking
¥12,000
```

```text
Tuition

ICBC Savings
¥20,000
```

```text
Subscription

CCB
¥1,500
```

---

用户人工支付：

```text
Rent

Credit Card
```

然后：

```text
Mark Manually Executed
```

---

导入新流水：

```text
CMB -8000

ICBC -12000
```

FinFlow：

```text
AUTO MATCH
```

Payment：

```text
SETTLED
```

---

# 108. AI Coding Agent Rules

AI Agent 必须遵循：

### Rule 1

禁止一次性生成完整系统。

---

### Rule 2

每次只实现一个 Task。

---

### Rule 3

开始 Task 前：

```text
Inspect existing repository
```

---

### Rule 4

每个 Task：

```text
Implementation

Tests

Run Tests

Fix Errors

Update Documentation
```

---

### Rule 5

禁止：

```text
TODO placeholder
```

出现在关键业务路径。

---

### Rule 6

不得擅自改变：

```text
Domain Model

State Machine

Safety Boundary
```

---

### Rule 7

不得加入任何：

```text
真实银行自动操作代码
```

---

# 109. Coding Standards

Python：

```text
ruff

black

mypy

pytest
```

Frontend：

```text
eslint

prettier

vue-tsc
```

---

# 110. Git Commit Rules

每个 Task：

独立 Commit。

例如：

```text
feat(accounts): implement account management

feat(statements): add floating anchor parser

feat(allocation): implement allocation engine

feat(reconciliation): implement transaction matching
```

---

# 111. Development Phases

## Phase 1 — Infrastructure

```text
TASK-001 Repository Bootstrap

TASK-002 Docker Compose

TASK-003 PostgreSQL

TASK-004 Redis

TASK-005 Nginx

TASK-006 FastAPI Core

TASK-007 Vue Core
```

---

# 112. Phase 2 — Foundation

```text
TASK-008 Authentication

TASK-009 Bank Model

TASK-010 Account Model

TASK-011 Account Balance Snapshot

TASK-012 Audit Log
```

---

# 113. Phase 3 — Transactions

```text
TASK-013 Statement Upload

TASK-014 Celery Import Pipeline

TASK-015 Generic Excel Parser

TASK-016 Anchor Detection

TASK-017 Dynamic Table Detection

TASK-018 Bank-Specific Parser

TASK-019 Transaction Normalization

TASK-020 Transaction Deduplication

TASK-021 Category Engine

TASK-022 Internal Transfer Detection
```

---

# 114. Phase 4 — Treasury

```text
TASK-023 Payment Plan

TASK-024 Payment State Machine

TASK-025 Recurring Payment

TASK-026 Account Planning Balance

TASK-027 Allocation Engine

TASK-028 Minimum Balance Constraint

TASK-029 Allocation Preview

TASK-030 Manual Allocation Override

TASK-031 Virtual Reservation

TASK-032 Manual Execution Confirmation
```

---

# 115. Phase 5 — Reconciliation

```text
TASK-033 Reconciliation Scoring

TASK-034 Auto Matching

TASK-035 Review Workbench

TASK-036 Settlement

TASK-037 Reservation Release

TASK-038 Refund / Reversal Relations
```

---

# 116. Phase 6 — Forecast

```text
TASK-039 Cash Flow Model

TASK-040 Forecast Engine

TASK-041 Low Balance Warning

TASK-042 30 / 90 Day Forecast
```

---

# 117. Phase 7 — Frontend

```text
TASK-043 Dashboard

TASK-044 Accounts

TASK-045 Account Detail

TASK-046 Statement Import

TASK-047 Transaction Explorer

TASK-048 Payments

TASK-049 Allocation Visualizer

TASK-050 Manual Execution UI

TASK-051 Reconciliation Workbench

TASK-052 Forecast Dashboard

TASK-053 Settings

TASK-054 Audit Log
```

---

# 118. Phase 8 — Productionization

```text
TASK-055 End-to-End Tests

TASK-056 Nginx Production Config

TASK-057 Docker Health Checks

TASK-058 Backup & Restore

TASK-059 Structured Logging

TASK-060 Security Hardening

TASK-061 Demo Data

TASK-062 Documentation
```

---

# 119. TASK-001

AI Agent 第一个任务：

```text
Initialize FinFlow repository.

Create:

frontend/
backend/
nginx/
sample-data/
scripts/

Initialize FastAPI backend.

Initialize Vue 3 + TypeScript frontend.

Create root Docker Compose configuration.

Create PostgreSQL and Redis containers.

Do not implement business logic.

Create:

GET /api/v1/health

Configure:

Ruff
Black
MyPy
Pytest
ESLint
Prettier

Add:

.env.example
.gitignore
README.md
Makefile

Run tests.

Verify backend health endpoint.

Report:

files created

commands executed

tests executed

issues encountered
```

---

# 120. TASK-002

```text
Create production Docker infrastructure.

Services:

nginx
api
worker
beat
postgres
redis

Add persistent volumes.

Add Docker healthchecks.

Configure internal Docker network.

Expose only Nginx externally.

Do not expose PostgreSQL or Redis.

Verify:

docker compose up -d

GET /api/v1/health

returns HTTP 200.
```

---

# 121. TASK-003

```text
Implement database infrastructure.

Configure:

SQLAlchemy 2.x

AsyncSession

PostgreSQL

Alembic

Base model

UUID primary keys

created_at

updated_at

database transaction utilities

Create first migration.

Add database health check.

Write integration tests.
```

---

# 122. Definition of Done

一个 Task 只有满足：

```text
Code complete

Tests written

Tests passing

Type checking passing

Lint passing

Docker still starts

No regression

Documentation updated
```

才能标记：

```text
DONE
```

---

# 123. Final Acceptance

最终必须可以完整完成：

```text
Login
    ↓
Create Accounts
    ↓
Upload Bank Statement
    ↓
Async Parse
    ↓
Normalize Transactions
    ↓
Detect Internal Transfers
    ↓
Create Payment Plans
    ↓
Generate Allocation Proposal
    ↓
User Accepts
    ↓
Virtual Reserve
    ↓
User Manually Operates Bank
    ↓
Mark Manually Executed
    ↓
Upload New Statement
    ↓
Automatic Reconciliation
    ↓
Settlement
    ↓
Balance / Forecast Update
```

---

# 124. Final Product Principle

整个项目始终遵循：

> FinFlow manages information, planning, reconciliation and financial decision support.

> FinFlow never moves real money.

系统负责：

```text
看清楚钱在哪里

知道未来要花多少钱

规划应该从哪里出钱

提醒什么时候可能缺钱

记录用户人工进行了什么操作

验证真实流水是否与计划一致
```

而所有真实资金操作：

```text
100% 由用户本人在银行端完成。
```