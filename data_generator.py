import os
import csv
import datetime

today_str = datetime.datetime.now().strftime('%Y%m%d')
print(f"Generating Look-through data for date: {today_str}")

base_dir = "./data"
dirs = {
    "mgr": os.path.join(base_dir, "inbox", "manager"),
    "dist": os.path.join(base_dir, "inbox", "distributor"),
    "out": os.path.join(base_dir, "outbox"),
    "db": os.path.join(base_dir, "db")
}
for d in dirs.values():
    os.makedirs(d, exist_ok=True)

def write_csv(folder, filename, headers, rows):
    path = os.path.join(folder, filename)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(headers); w.writerows(rows)
    print(f" -> Created: {path}")

# --- A. Manager Files ---
write_csv(dirs["mgr"], f"NAV_FUND01_{today_str}.csv", ["fund_code", "nav", "date"], [["FUND01", "1.0000", today_str]])
write_csv(dirs["mgr"], f"NAV_FUND02_{today_str}.csv", ["fund_code", "nav", "date"], [["FUND02", "2.0000", today_str]])

# 确认文件：必须包含确认份额和确认净值
# 假设: TX_001 是申购 1000元，净值1.0 -> 1000份
# 假设: TX_002 是赎回 100份，净值1.0 -> 确认份额100
write_csv(dirs["mgr"], f"CONFIRM_{today_str}.csv", 
          ["trans_id", "status", "confirmed_amount", "confirmed_shares", "confirmed_nav"], 
          [
              ["TX_001", "1", "1000.00", "1000.00", "1.0000"], # 申购确认
              ["TX_002", "1", "100.00", "100.00", "1.0000"]     # 赎回确认
          ])

# --- B. Distributor Files ---
write_csv(dirs["dist"], f"DIST_A_ACC_{today_str}.csv",
    ["request_no", "biz_code", "investor_name", "id_no"],
    [["REQ001", "001", "NewUser", "320101199901011111"]]
)

# 交易文件 (看穿式): 增加 type 和 account_id
# 假设 TA10001 是存量账户 (在 accounts.json 里)
# TX_001: 申购 1000元
# TX_002: 赎回 100份 (需要 holdings.json 里有持仓)
write_csv(dirs["dist"], f"DIST_A_TRADE_FUND01_{today_str}.csv",
    ["trans_id", "fund_code", "type", "amount_or_shares", "account_id"],
    [
        ["TX_001", "FUND01", "PURCHASE", "1000.00", "TA10001"],
        ["TX_002", "FUND01", "REDEEM",   "100.00",  "TA10001"]
    ]
)
# 一个异常交易测试 (账户不存在)
write_csv(dirs["dist"], f"DIST_A_TRADE_FUND02_{today_str}.csv",
    ["trans_id", "fund_code", "type", "amount_or_shares", "account_id"],
    [
        ["TX_ERR", "FUND02", "PURCHASE", "5000.00", "TA_INVALID_999"]
    ]
)

print("\nMake sure 'accounts.json' contains TA10001 and 'holdings.json' contains TA10001_FUND01")