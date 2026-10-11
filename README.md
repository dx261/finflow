# FinFlow — 个人多账户资金管理与现金流规划平台

FinFlow 用于统一管理多个银行账户、导入银行账单、制定付款计划、推荐资金分配方案，并将计划与实际流水对账。

当前项目以「本地 SQLite + 免登录」作为一键启动的演示方案：数据保存在项目文件夹中，不需要 Docker、PostgreSQL 或 Redis。原有登录注册和 PostgreSQL / Docker 部署代码仍然保留。

> 本项目只管理信息、计划和对账，不会操作真实资金。转账、付款等操作必须由用户在银行端手动完成；演示时无需进行任何真实付款。

## 功能概览

| 模块 | 当前能力 |
| --- | --- |
| 账户管理 | 多银行、多币种账户，最低保留余额、余额快照、虚拟预留和规划可用余额 |
| 账单导入 | 支持 CSV、XLS、XLSX；工商银行、招商银行及通用解析；文件与流水去重、分类、错误记录 |
| 交易查询 | 流水筛选、详情查看，以及内部转账、退款和冲正关联 |
| 计划管理 | 周期付款规则、一次性付款、未来收入和支出 |
| 资金分配 | 分配预览、人工调整、虚拟资金预留、人工执行标记 |
| 对账管理 | 匹配候选流水、人工复核、确认结算并释放预留 |
| 现金流预测 | 7 / 30 / 90 天预测、低余额提示、待归属现金流；不同币种分别展示 |
| 审计与权限 | 操作审计，保留 OWNER / VIEWER 角色及登录注册机制 |

前端包含仪表盘、账户及详情、交易、账单导入、计划管理、付款、分配、对账、现金流预测、审计和设置页面。

三个余额概念分别是：实际余额来自账单或人工记录，虚拟预留表示计划占用，规划可用余额还需扣除最低保留余额。虚拟预留不会冻结银行资金。

## 快速开始：Windows 本地演示

### 1. 准备环境

- Python 3.12 或以上版本，以及 [uv](https://docs.astral.sh/uv/)。
- Node.js 24（与项目 CI 使用的版本一致，安装时同时安装 npm）。
- Git for Windows：启动 BAT 需要 Git Bash，默认从标准安装目录查找。
- 首次安装依赖需要网络；SQLite 演示不需要启动 Docker Desktop。

在项目根目录打开 PowerShell，可先检查：

```powershell
uv --version
node --version
npm --version
```

### 前端依赖怎么安装（npm install）

本项目已经配置好 [frontend/package.json](frontend/package.json) 和 [package-lock.json](frontend/package-lock.json)，不需要执行 npm init，也不用逐个安装 Vue、Element Plus 或其他已有依赖。安装命令必须在 frontend 目录执行，而不是项目根目录或 backend 目录。

从项目根目录打开 PowerShell，执行：

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --strictPort
```

npm install 会安装 package.json 中的业务依赖和开发依赖，将包放到 frontend/node_modules/。开发和构建都需要开发依赖，不要使用 --omit=dev。前端启动后访问 http://127.0.0.1:5173；页面调用接口还需要同时启动后端。

使用一键 BAT 时，若 node_modules 尚不存在，脚本会自动执行 npm install。已有依赖目录时脚本会跳过这一步；拉取新的依赖配置后，请先停止前端，再进入 frontend 重新安装。

两种安装方式任选其一，不需要每次都连续执行：

- npm install：日常开发安装，依赖配置变化时可能更新 package-lock.json。
- npm ci：克隆后或 CI 中按已有锁文件安装；要求 package.json 与锁文件一致，不修改它们，并先清理已有 node_modules。因此前文首次体验可用 npm install，后面的复现与测试示例使用 npm ci。

说明依据：[npm install 官方文档](https://docs.npmjs.com/cli/v11/commands/npm-install/)和 [npm ci 官方文档](https://docs.npmjs.com/cli/v11/commands/npm-ci/)。

只有需要新增依赖时才使用以下命令，将“实际包名”替换为所需包名；运行本项目无需执行这些示例：

```powershell
# 业务代码使用的包，记录到 dependencies
npm install 实际包名

# 测试、类型检查等开发工具，记录到 devDependencies
npm install -D 实际包名
```

依赖变更后提交 package.json 和 package-lock.json，不提交 node_modules；不要把 Vite 等项目工具全局安装来代替本地依赖，也不要随意删除锁文件或使用 --force 掩盖安装错误。

安装常见问题：

- 提示找不到 npm / node：检查 Node.js 安装及 PATH，安装后重新打开终端。
- PowerShell 提示禁止运行 npm.ps1：可使用 npm.cmd install、npm.cmd ci 或 npm.cmd run dev，无需修改系统执行策略。
- 网络超时：先用 npm config get registry 查看当前源，检查网络和代理。需要指定官方源时可对本次命令使用 npm install --registry=https://registry.npmjs.org/，不必改动全局配置；不要关闭 SSL 校验。
- 包提示 Node.js 版本不兼容：切换到本项目使用的 Node.js 24 后重新安装，不要忽略版本要求。

### 2. 启动项目

双击根目录的 [start-dev.bat](start-dev.bat)，或在项目根目录执行：

```powershell
.\start-dev.bat
```

首次启动会自动安装依赖；当不存在 backend/.env 时，会从 [演示配置模板](backend/.env.demo.example) 创建配置，建立 SQLite 数据库并填充虚构样例，随后启动后端和前端。

已有配置不会被覆盖，重复启动不会自动清空已有演示数据。如果保留的是之前的 PostgreSQL 配置，请先停止服务，再按下一节修改 backend/.env。

| 入口 | 地址 |
| --- | --- |
| 前端页面 | http://127.0.0.1:5173 |
| 后端接口文档 | http://127.0.0.1:8000/docs |
| 就绪检查 | http://127.0.0.1:8000/api/v1/health/ready |
| 当前演示配置 | http://127.0.0.1:8000/api/v1/auth/config |

默认无需登录。样例包含 5 个账户（CNY / USD）、5 条周期规则、6 笔不同状态的付款、未来收入，以及模拟账单和交易。演示日期按初始化时间生成。

前端通过 FastAPI 读写 SQLite，并非由浏览器直接读取数据库文件。账单在后端同步解析，不需要 Celery worker。

### 3. 停止与查看日志

双击 [stop-dev.bat](stop-dev.bat)，或执行：

```powershell
.\stop-dev.bat
```

日志在 .run/logs/，本地演示主要查看 backend.log 和 frontend.log。停止脚本不会删除数据库，也不会停止已有 Docker 容器。

只启动后端时，可以使用：

```powershell
.\start-dev.bat --no-front
```

> 注意：普通启动已经会初始化样例，不需要加 --demo。start-dev.bat --demo 会删除并重建演示用户的数据，丢失对该演示工作区的修改；使用前请备份。

## 本地配置与免登录机制

本机后端读取固定位置 backend/.env，不受终端当前目录影响；进程环境变量优先于该文件。根目录 .env 是 Docker Compose 配置，两者不是同一份文件。

当前 SQLite 演示配置如下：

```dotenv
APP_ENV=development
DEMO_MODE=true
LOCAL_DEMO=true
DATABASE_URL=sqlite+aiosqlite:///./data/demo.sqlite3
DATA_DIR=./data/demo
STATEMENT_IMPORT_ASYNC=false
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```

| 配置 | 含义 |
| --- | --- |
| LOCAL_DEMO=true | 使用持久化 SQLite，禁用 Redis 依赖与异步账单导入，不启动 worker / beat |
| DEMO_MODE=true | 开放匿名访问，共享独立的演示 OWNER；暂时禁用登录、注册和令牌刷新 |
| DATABASE_URL | 本地演示相对路径以 backend/ 为基准 |
| DATA_DIR | 上传文件目录的根路径；本地演示相对路径同样以 backend/ 为基准 |

两个开关相互独立：LOCAL_DEMO 决定基础设施模式，DEMO_MODE 决定是否免登录。SQLite 本地模式不允许用于 APP_ENV=production。

### 恢复登录注册

将 backend/.env 中的 DEMO_MODE 改为 false，停止并重新启动后端，再刷新前端即可；无需删除登录注册代码，也无需配置前端演示开关。保留 LOCAL_DEMO=true 时仍然使用 SQLite。

关闭演示后需要使用真实注册账号，演示数据不会自动转移到该账号，也不会被删除。默认免登录展示不需要 demoowner / demo123456；该普通测试账号仅由认证开启时运行的演示数据生成脚本创建。不要在正式环境使用这种公开的样例密码。

### 演示安全边界

- 访客共享同一份可修改的演示数据，不具备彼此隔离的私有空间。
- 演示用户与原有用户的账户、账单和付款数据分开；同一数据库中的银行、分类等全局目录仍共享。
- 不要导入真实银行账单，不要存放银行卡密码、短信验证码、网银凭据或其他敏感信息。
- 项目不包含银行自动登录、网银 RPA、自动转账或真实资金冻结能力。
- 当前权限设计面向单一工作区，不应将它当作成熟的多租户金融系统。

## 完整业务演示与模拟文件

[全流程模拟数据包](sample-data/workflow/README.md) 提供每个步骤所需的 JSON、CSV 和 HTTP 请求文件。建议新建一组样例账户，避免与预置数据混用。

1. 创建 CNY / USD 账户，参考 02、03 JSON。
2. 导入 07-opening-statement.csv，将样例人民币账户余额更新为 50,000。
3. 创建周期房租、未来工资和一次性房租付款，参考 04、05、06 JSON。
4. 将付款纳入计划，预览分配方案并确认虚拟预留。
5. 演示时直接标记人工执行，不进行真实银行转账。
6. 导入 08-payment-statement.csv，得到模拟的 8,000 元房租流水。
7. 发起对账，核对候选流水并确认结算。
8. 查看分币种现金流预测和待归属项目。
9. 导入 09-older-statement.csv，验证旧账单不会把较新余额 42,000 覆盖为 99,999。

免登录接口演示使用 [finflow-demo-workflow.http](sample-data/workflow/finflow-demo-workflow.http)；启用认证后使用 [finflow-workflow.http](sample-data/workflow/finflow-workflow.http)，注册请求参考 01-register-owner.json。

SQLite 模式没有定时调度器。新增周期规则后，可在接口文档调用 POST /api/v1/recurring/generate，指定 from_date 和 to_date 手动生成计划；当前“计划管理”页面没有生成按钮。PostgreSQL 模式由 Celery beat 定时触发。

## 数据存储、备份与重置

默认本地文件位置：

| 内容 | 路径 |
| --- | --- |
| SQLite 数据库 | backend/data/demo.sqlite3 |
| 演示上传文件 | backend/data/demo/uploads/ |
| 本机后端配置 | backend/.env |
| 启动日志与进程记录 | .run/ |

演示使用 SQLite 建表初始化，不运行 PostgreSQL 专用 Alembic 迁移。初始化会保留已有数据，但不会自动迁移已有表结构；升级模型后应先备份，再处理结构变化。

备份前停止本项目后端，确认没有其他进程写数据库，然后复制整个 backend/data/ 目录；配置文件另行安全保存。SQLite 使用 WAL 模式，不要在运行中仅复制 demo.sqlite3 而遗漏辅助文件和上传账单。恢复时也先停止应用，并保留当前数据的备份。

手动初始化不会重置已有演示工作区：

```powershell
cd backend
uv run python ../scripts/init_demo.py
```

只有确认可以丢弃演示修改时，才在停止服务后执行以下重置命令。它删除并重建当前配置对应的演示用户及数据，不是备份命令：

```powershell
cd backend
uv run python ../scripts/demo_data.py --reset
```

SQLite 与原有 PostgreSQL 是独立的数据源。切换模式不会自动复制、合并或迁移业务数据。

## 手动启动：两个终端

如不使用 BAT，可在项目根目录打开两个 PowerShell 终端。已存在 backend/.env 时先检查配置，不要覆盖。

后端终端：

```powershell
cd backend
if (!(Test-Path .env)) { Copy-Item .env.demo.example .env }
uv sync
uv run python ../scripts/init_demo.py
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端终端：

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --strictPort
```

使用 Ctrl+C 分别停止。后端代码调试时可给 uvicorn 增加 --reload；配置变更后仍建议完整重启。

## 可选：PostgreSQL / Docker 开发模式

仅想展示项目时无需阅读本节。需要 PostgreSQL、异步导入和定时任务时，安装并启动 Docker Desktop，然后停止本项目的本地服务。

在项目根目录创建 Compose 配置（已有文件不覆盖）：

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

备份并编辑 backend/.env，切换为：

```dotenv
APP_ENV=development
DEMO_MODE=false
LOCAL_DEMO=false
DATABASE_URL=postgresql+asyncpg://finflow:finflow@127.0.0.1:5432/finflow
REDIS_URL=redis://127.0.0.1:6379/0
DATA_DIR=./data
STATEMENT_IMPORT_ASYNC=true
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```

以上连接参数对应开发默认值。如根目录 .env 中更改了数据库用户、密码、库名或端口，必须同步调整 backend/.env 的连接地址。

运行 start-dev.bat 后，脚本会使用 [docker-compose.dev.yml](docker-compose.dev.yml) 启动 PostgreSQL 16 和 Redis 7，应用 Alembic 迁移，再启动 API、Celery worker、Celery beat 和前端。开发 Compose 仅包含数据库与 Redis，应用进程运行在宿主机。

此模式就绪检查要求数据库和 Redis 可用；SQLite 模式中 redis: disabled 是正常结果。认证模式下空数据库需要先注册，首次真实注册账号成为 OWNER。

需要在 PostgreSQL 中免登录展示时，可将 DEMO_MODE 改为 true 并重启。该模式不会自动填充样例；迁移完成后可从 backend/ 运行 uv run python ../scripts/demo_data.py，或使用模拟数据包。

手动启动 Windows worker 时需设置 DATABASE_POOLCLASS=null，并使用 --pool=solo，避免跨事件循环复用数据库连接。

## 可选：Docker 完整部署

[docker-compose.yml](docker-compose.yml) 包含 PostgreSQL、Redis、API、worker、beat 和 Nginx，前端构建后由 Nginx 提供。此方案使用 PostgreSQL，不使用项目内的 SQLite 文件。

创建根目录 .env 后，部署前至少配置：

- POSTGRES_PASSWORD：修改默认密码。
- SECRET_KEY：非默认、非占位值，至少 32 个字符。
- REGISTRATION_TOKEN：非占位值，至少 16 个字符，用于生产注册邀请。
- CORS_ORIGINS：实际访问前端的来源，例如本机 HTTP 部署的 ["http://localhost"]。
- DEMO_MODE：真实数据部署保持 false；开启匿名展示时只使用独立的虚构数据库。

```powershell
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 api
```

默认 HTTP 入口是 http://localhost，可通过 HTTP_PORT 修改端口。生产 Compose 显式禁用 LOCAL_DEMO，API 启动时执行数据库迁移；PostgreSQL 和 Redis 不映射宿主机端口。

HTTPS 默认未启用：需要挂载证书到 /etc/nginx/ssl/，并启用 [Nginx 配置](nginx/nginx.conf) 中的 HTTPS 段。映射 443 端口不等于已启用 TLS。

开发与完整部署使用不同的 Compose 项目和持久化卷，不会自动共享数据。普通 docker compose down 保留卷；不要随意使用 down -v，它会删除卷及其中的数据。

### PostgreSQL 备份与恢复

[scripts/backup.sh](scripts/backup.sh) 和 [scripts/restore.sh](scripts/restore.sh) 只用于 Docker / PostgreSQL，不用于 SQLite。在 Git Bash 中从根目录执行：

```bash
# 完整部署备份；不指定 COMPOSE_FILE 时默认选择开发环境
COMPOSE_FILE=docker-compose.yml ./scripts/backup.sh

# 恢复会覆盖现有数据库与上传文件，先备份并核实目标
COMPOSE_FILE=docker-compose.yml ./scripts/restore.sh "backups/finflow-backup-实际时间戳.tar.gz"
```

将恢复示例中的文件名替换为实际备份文件名后执行。开发模式恢复前还需停止宿主机上的本项目 API、worker 和 beat，避免同时写入。若更改了数据库用户或库名，需为脚本显式设置 POSTGRES_USER / POSTGRES_DB，脚本不会自动将根目录 .env 导出为 shell 变量。

备份包括 PostgreSQL 导出、可取得的上传文件及尽力保存的 Redis 快照。请检查脚本警告并核实备份完整性；Redis 快照不会被恢复脚本自动回灌。

## 技术栈与目录

| 层次 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Element Plus、Pinia、ECharts |
| 后端 | Python、FastAPI、Pydantic、SQLAlchemy、Alembic |
| 本地演示 | SQLite、aiosqlite，同步账单解析 |
| PostgreSQL 模式 | PostgreSQL 16、Redis 7、Celery worker / beat |
| 金额处理 | 后端使用 Decimal；PostgreSQL 使用 NUMERIC(18,2) |

SQLite 用于单机展示，不替代 PostgreSQL 的生产存储、并发与迁移方案。

```text
backend/                  后端应用、测试、数据库迁移及本地数据
frontend/                 前端页面与测试
nginx/                    静态文件服务与反向代理
sample-data/workflow/     全流程虚构样例和接口请求
scripts/                  启停、初始化、演示数据、备份与恢复
docs/                     项目说明文档
docker-compose.dev.yml    开发数据库与 Redis
docker-compose.yml        完整 Docker 部署
start-dev.bat              Windows 一键启动
stop-dev.bat               Windows 停止入口
```

## 测试与代码检查

后端（从项目根目录执行，测试不需要手动启动数据库或 Redis）：

```powershell
cd backend
uv sync --all-groups
uv run ruff check app tests
uv run black --check app tests alembic/versions
uv run mypy app
uv run pytest -q
```

前端（另开终端，从项目根目录执行）：

```powershell
cd frontend
npm ci
npm run lint:check
npm run test
npm run build
```

[CI 配置](.github/workflows/ci.yml) 还使用 PostgreSQL 检查 Alembic 迁移。测试结果以实际执行输出为准，不将历史测试数量或本地演示通过等同于生产部署验收。

## 提交到 GitHub 时

提交源码、依赖锁文件、Dockerfile / Compose、配置模板、迁移文件以及虚构模拟数据。不要提交实际 .env、SQLite 文件、真实账单、上传目录、运行日志或备份。

相关本地文件已由 [.gitignore](.gitignore) 排除，但提交前仍应检查 git status；已跟踪过的敏感文件不会因新增忽略规则自动消失。实际密钥如曾上传，应更换密钥并处理泄露记录。

GitHub 保存部署代码，不运行本机 Docker 容器，也不保存其卷数据。其他人克隆后可通过一键启动重新建立 SQLite 演示；需要保留自定义数据时，另行安全传递备份。

## 常见问题

- **BAT 提示乱码或“不是内部或外部命令”？** 使用仓库中的完整 BAT 文件，不要复制补丁的加号；保持 CRLF 换行并确认 Git Bash 已安装在标准目录。当前 BAT 使用 ASCII 内容调用 Bash。
- **修改配置后仍然是旧模式？** 启动脚本会跳过已经运行的服务，不会自动重启；先 stop-dev.bat，再启动并刷新页面。如为手动启动，也要停止对应终端中的进程。
- **端口占用或服务启动失败？** 查看 .run/logs/，检查 8000 / 5173 是否被其他服务占用；不要直接终止不属于本项目的进程。
- **切换 SQLite 后原数据库不见了？** 数据源改变不等于数据删除；原 PostgreSQL 和 Docker 卷仍独立保留，SQLite 中看不到其数据。
- **免登录下注册接口返回 403？** 这是演示模式的预期行为；展示直接进入前端，恢复认证后再注册。
