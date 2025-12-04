"""
存储 TA 系统接口规范的原始文本定义。
基于《基金TA系统业务运作指引与接口规范书 (V1.0)》
"""

# --- 系统世界观上下文 ---
SYSTEM_CONTEXT = """
## TA System Business Context (系统运作逻辑 - V1.0)

1. **核心原则: 看穿式账户管理 (Look-through Account Management)**
   - 系统直接穿透登记投资人的账户及份额。
   - **核心约束**: 任何交易指令 (`DIST_TRADE`) 必须包含有效的 `account_id`。
   - **账户来源**: `account_id` 必须存在于 **T-1日数据库 (Setup State)** 中，或者是 **当日T日 (Input Files)** 新申报的开户数据。

2. **每日运作双批次 (Two-Phase Operation)**
   - **第一阶段 (Apply Phase)**: 
     - 重点: 申报与受理。
     - 输入: 销售商发送账户(`ACC`)与交易(`TRADE`)申请；管理人发送净值(`NAV`)。
     - 输出: 
       - TA反馈账户确认(`TO_DIST_ACC_CONFIRM`)
       - TA向管理人发送交易汇总(`TO_MGR_APPLY`)
   - **第二阶段 (Confirm Phase)**:
     - 重点: 确认与回报。
     - 输入: 管理人发送确认回执(`CONFIRM`)。
     - 输出: 
       - TA反馈最终交易回报(`TO_DIST_CONFIRM`)
       - (若有延迟处理的账户确认也可能在此阶段补发)

3. **业务校验规则 (Business Rules)**
   - **开户 (001)**: 证件号 (`id_no`) 全局唯一。若重复，返回 `ID_EXISTS`。
   - **销户 (002)**: 账户必须存在且状态正常。若不存在，返回 `ACCOUNT_NOT_FOUND`。
   - **申购 (Purchase)**: 账户状态必须为 `NORMAL`，金额 > 0。
   - **赎回 (Redeem)**: **强校验可用份额**。若 申请份额 > 可用份额，返回 `INSUFFICIENT_SHARES`。
"""

# 1. 通用规范 (包含存量数据规范)
GENERAL_SPECS = """
## 1. 通用规范 (General Standards)
* **文件格式**: CSV (Comma-Separated Values)
* **表头规范**: **首行为字段名称 (Header Row is Mandatory)**。
* **文件路径**: **相对于系统数据目录 (data/)**。
* **字符编码**: UTF-8
* **文件名日期格式**: `yyyyMMdd` (例如 `20231027`)
* **数值格式**:
    * **金额/份额**: 保留2位或4位小数的浮点数字符串 (Decimal)，例如 `1000.00`。
    * **布尔值**: 使用特定代码（如 1/0 或 true/false 字符串）表示。
* **空值处理**: CSV中两个逗号之间无内容即为空值。

## 4. 存量数据文件 (Setup Data - JSON Schema)
用于 Agent 初始化系统内的老用户数据 (T-1 State)。

### 4.1 账户库 (accounts.json)
| 字段名 | 类型 | 说明 | 示例值 |
| :--- | :--- | :--- | :--- |
| `distributorId` | String | 归属销售商 | `DIST_A` |
| `accountId` | String | TA账号 (主键) | `TA10001` |
| `idNo` | String | 证件号 | `110101198001010000` |
| `name` | String | 姓名 | `OldUser` |
| `status` | String | 状态 | `NORMAL` / `FROZEN` / `CLOSED` |

### 4.2 登记库 (holdings.json)
| 字段名 | 类型 | 说明 | 示例值 |
| :--- | :--- | :--- | :--- |
| `accountId` | String | TA账号 | `TA10001` |
| `fundCode` | String | 基金代码 | `FUND01` |
| `totalShares` | Number | 总份额 | `1000.00` |
| `availableShares`| Number | 可用份额 | `1000.00` (赎回校验时使用此字段) |
"""

# 2. 输入接口定义 (Strictly match V1.0 Spec)
FILE_SPECS = {
    # --- 销售商报送 ---
    "DIST_ACC": """
### 2.3 销售商账户申请文件 (DIST_ACC)
* **来源**: 销售机构
* **文件名**: `{DistID}_ACC_{Date}.csv`
* **文件路径**: `inbox/distributor/{file_name}`
* **用途**: 提交投资人的开户、销户请求。
* **CSV Header**: `request_no,biz_code,investor_name,id_no`
* **字段说明**:
  - `request_no`: 申请单号 (String(32), 必填, 销售商侧唯一)
  - `biz_code`: 业务代码 (String(3), 必填, 001=开户, 002=销户)
  - `investor_name`: 投资人姓名 (String(64), 必填)
  - `id_no`: 证件号码 (String(32), 必填, 唯一索引)
""",

    "DIST_TRADE": """
### 2.4 销售商交易申请文件 (DIST_TRADE)
* **来源**: 销售机构
* **文件名**: `{DistID}_TRADE_{FundCode}_{Date}.csv`
* **文件路径**: `inbox/distributor/{file_name}`
* **用途**: 提交看穿式交易申请。
* **CSV Header**: `trans_id,fund_code,type,amount_or_shares,account_id`
* **字段说明**:
  - `trans_id`: 交易流水号 (String(32), 必填, 全局唯一)
  - `fund_code`: 基金代码 (String(10), 必填)
  - `type`: 交易类型 (String(10), 必填, PURCHASE=申购, REDEEM=赎回)
  - `amount_or_shares`: 申请数值 (Decimal(18,2), 必填, 申购为金额, 赎回为份额)
  - `account_id`: TA账号 (String(32), 必填, 必须存在于系统)
""",

    # --- 管理人报送 ---
    "MGR_NAV": """
### 2.1 管理人净值文件 (MGR_NAV)
* **来源**: 基金管理人
* **文件名**: `NAV_{FundCode}_{Date}.csv`
* **文件路径**: `inbox/manager/{file_name}`
* **用途**: 提供当日基金净值。
* **CSV Header**: `fund_code,nav,date`
* **字段说明**:
  - `fund_code`: 基金代码 (String(10), 必填)
  - `nav`: 单位净值 (Decimal(10,4), 必填, >0)
  - `date`: 行情日期 (String(8), 必填, yyyyMMdd)
""",

    "MGR_CONFIRM": """
### 2.2 管理人确认回执文件 (MGR_CONFIRM)
* **来源**: 基金管理人
* **文件名**: `CONFIRM_{Date}.csv`
* **文件路径**: `inbox/manager/{file_name}`
* **用途**: 反馈Batch 1提交的交易申请的最终确认结果。
* **CSV Header**: `trans_id,status,confirmed_amount,confirmed_shares,confirmed_nav`
* **字段说明**:
  - `trans_id`: 交易流水号 (String(32), 必填)
  - `status`: 确认状态 (String(1), 必填, 1=成功, 0=失败)
  - `confirmed_amount`: 确认金额 (Decimal(18,2), 选填)
  - `confirmed_shares`: 确认份额 (Decimal(18,2), 选填)
  - `confirmed_nav`: 确认净值 (Decimal(10,4), 选填)
"""
}

# 3. 输出文件规范 (用于 Agent 预测 output_files)
OUTPUT_SPECS = {
    "TO_MGR_APPLY": """
### 3.1 发送给管理人-交易申请汇总 (TO_MGR_APPLY)
* **文件名**: `TO_MGR_APPLY_{FundCode}_{Date}.csv`
* **文件路径**: `outbox/manager/{file_name}`
* **CSV Header**: `trans_id,fund_code,type,amount,shares,apply_time`
* **字段说明**:
  - `amount`: 申请金额 (Decimal(18,2), 申购时有值)
  - `shares`: 申请份额 (Decimal(18,2), 赎回时有值)
  - `apply_time`: 申报时间 (DateTime)
""",

    "TO_DIST_ACC_CONFIRM": """
### 3.2 发送给销售商-账户业务确认 (TO_DIST_ACC_CONFIRM)
* **文件名**: `TO_DIST_ACC_CONFIRM_{Date}.csv`
* **文件路径**: `outbox/distributor/{file_name}`
* **CSV Header**: `request_no,biz_code,ta_account_id,status,message,confirm_time`
* **字段说明**:
  - `ta_account_id`: TA账号 (String(32), 成功时生成)
  - `status`: 1=成功, 0=失败
  - `message`: 失败原因 (String(128))
""",

    "TO_DIST_CONFIRM": """
### 3.3 发送给销售商-交易业务确认 (TO_DIST_CONFIRM)
* **文件名**: `TO_DIST_CONFIRM_{Date}.csv`
* **文件路径**: `outbox/distributor/{file_name}`
* **CSV Header**: `trans_id,fund_code,account_id,type,status,confirmed_shares,confirmed_nav,message`
* **字段说明**:
  - `status`: CONFIRMED, REJECTED, TA_REJECTED
  - `message`: 备注/原因 (如 INSUFFICIENT_SHARES)
  - `confirmed_shares`: 确认份额 (Decimal(18,2))
"""
}