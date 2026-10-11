# FinFlow 全流程模拟数据包

这组文件对应一条完整的业务链路，可用于 UI 手工演示，也可用
`finflow-workflow.http` 逐个发送 API 请求。

免登录演示模式下，请直接打开前端，不需要执行注册或登录；API 操作改用
`finflow-demo-workflow.http`，其中保留同样的业务步骤，但不依赖 Token。
原有注册文件和带认证的请求示例保留，关闭演示模式后可继续使用。

## 文件与操作步骤

1. `01-register-owner.json`：空数据库首次注册 OWNER。
2. `02-account-cny.json`：创建人民币主账户。
3. `03-account-usd.json`：创建美元账户，用于验证不同币种不会直接相加。
4. `04-recurring-rent.json`：创建每月房租规则。
5. `05-cashflow-salary.json`：创建未来工资收入计划。
6. `06-payment-rent.json`：创建一次性房租付款计划。
7. `07-opening-statement.csv`：导入付款前账单，将人民币账户余额更新为 50,000。
8. `08-payment-statement.csv`：用户在银行完成真实付款后导入，包含 8,000 元房租流水。
9. `09-older-statement.csv`：最后导入，用于验证旧账单不会覆盖较新的账户余额。
10. `finflow-workflow.http`：串起以上步骤的可执行 API 示例。

## UI 演示顺序

1. 直接进入演示系统（非演示模式需登录），在“账户”中新建 CNY 和 USD 账户，字段参考 02、03 JSON。
2. 在“账单导入”选择 CNY 账户，上传 `07-opening-statement.csv`。
3. 在“计划管理”创建周期房租和未来工资，字段参考 04、05 JSON。
4. 在“付款”新建房租计划，进入“去分配”，生成方案并确认预留。
5. 在真实银行环境中这一步应由用户手工转账；演示时直接在付款页标记人工执行。
6. 上传 `08-payment-statement.csv`，等待导入状态变为成功。
7. 回到付款页点击“发起对账”，在“对账”页面核对候选流水并确认。
8. 打开“现金流预测”，验证 CNY、USD 分币种展示，未指定账户的项目进入“待归属现金流”。
9. 上传 `09-older-statement.csv`，确认余额仍保持较新账单的 42,000，而不是旧文件中的 99,999。

注意：样例只包含模拟数据，不包含真实卡号、密码、Token 或个人信息。
