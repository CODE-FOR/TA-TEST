import os
import json
import csv
import glob
import re
from datetime import datetime

# --- Helper: Java String hashCode implementation in Python ---
def java_string_hashcode(s):
    h = 0
    for c in s:
        h = (31 * h + ord(c)) & 0xFFFFFFFF
    return ((h + 0x80000000) & 0xFFFFFFFF) - 0x80000000

def generate_acc_id(id_no):
    # Matches Java: "TA" + Math.abs(idNo.hashCode())
    return "TA" + str(abs(java_string_hashcode(id_no)))

# --- Main Analysis Class ---
class TestCaseAnalyzer:
    def __init__(self, batch_path, case_id):
        self.batch_path = batch_path
        self.case_id = case_id
        self.path = os.path.join(batch_path, case_id)
        self.meta = self._load_json("meta.json")
        self.accounts = self._load_db_accounts()
        self.holdings = self._load_db_holdings()
        self.new_accounts = set()
        
        # Stats
        self.total_txns = 0
        self.invalid_acc_refs = 0
        self.invalid_holding_refs = 0
        self.insufficient_shares = 0
        
        # Intent
        self.is_negative_case = self._determine_intent()
        
    def _load_json(self, filename):
        p = os.path.join(self.path, filename)
        if os.path.exists(p):
            with open(p, 'r') as f:
                return json.load(f)
        return {}
    
    def _load_db_accounts(self):
        # Returns set of account_ids
        p = os.path.join(self.path, "db_snapshot", "Accounts.json")
        accs = set()
        if os.path.exists(p):
            try:
                with open(p, 'r') as f:
                    data = json.load(f)
                    for a in data:
                        accs.add(a.get("accountId"))
            except: pass
        return accs

    def _load_db_holdings(self):
        # Returns dict: "accountId_fundCode" -> float(shares)
        p = os.path.join(self.path, "db_snapshot", "Holdings.json")
        h_map = {}
        if os.path.exists(p):
            try:
                with open(p, 'r') as f:
                    data = json.load(f)
                    for h in data:
                        key = f"{h.get('accountId')}_{h.get('fundCode')}"
                        h_map[key] = float(h.get("availableShares", 0))
            except: pass
        return h_map

    def _determine_intent(self):
        # Heuristic: True if Negative Case
        keywords = ["REJECT", "FAIL", "NEGATIVE", "INSUFFICIENT", "DUPLICATE", "MISSING", "NOT_FOUND", "ABNORMAL", "CONFLICT", "CLOSED"]
        
        # Check ID
        if any(k in self.case_id.upper() for k in keywords):
            return True
            
        # Check Description
        desc = self.meta.get("description", "").upper()
        if any(k in desc for k in keywords):
            return True

        # Check Expected Keyword
        exp = self.meta.get("expected_keyword", "").upper()
        if any(k in exp for k in keywords):
            return True
            
        return False

    def process_new_accounts(self):
        # Scan DIST_A_ACC files for new account openings (biz_code=001)
        inbox = os.path.join(self.path, "input_files", "inbox", "distributor")
        if not os.path.exists(inbox): return
        
        for fname in os.listdir(inbox):
            if fname.startswith("DIST_A_ACC") and fname.endswith(".csv"):
                with open(os.path.join(inbox, fname), 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get("biz_code") == "001":
                            id_no = row.get("id_no")
                            if id_no:
                                new_id = generate_acc_id(id_no)
                                self.new_accounts.add(new_id)

    def validate_trades(self):
        inbox = os.path.join(self.path, "input_files", "inbox", "distributor")
        if not os.path.exists(inbox): return

        all_valid_accounts = self.accounts.union(self.new_accounts)

        for fname in os.listdir(inbox):
            if fname.startswith("DIST_A_TRADE") and fname.endswith(".csv"):
                with open(os.path.join(inbox, fname), 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        self.total_txns += 1
                        
                        acc_id = row.get("account_id")
                        fund_code = row.get("fund_code")
                        txn_type = row.get("type") # PURCHASE or REDEEM
                        try:
                            amount_or_shares = float(row.get("amount_or_shares", 0))
                        except:
                            amount_or_shares = 0
                        
                        # Check 1: Account Existence
                        if acc_id not in all_valid_accounts:
                            self.invalid_acc_refs += 1
                            # If account missing, can't check holdings properly (conceptually)
                            # But we continue to record specific errors
                        
                        # Check 2: Holding Sufficiency (only for REDEEM)
                        if txn_type == "REDEEM":
                            key = f"{acc_id}_{fund_code}"
                            available = self.holdings.get(key, 0.0)
                            
                            # If holding entry missing OR shares insufficient
                            # Note: If account is missing, holding is likely missing too.
                            if available < amount_or_shares:
                                self.insufficient_shares += 1

    def get_consistency_status(self):
        # "Consistent" means valid from a HAPPY PATH perspective.
        # i.e., Data satisfies all dependencies.
        if self.invalid_acc_refs > 0:
            return "BROKEN_LINK_ACC"
        if self.insufficient_shares > 0:
            return "INSUFFICIENT_HOLDING"
        return "CONSISTENT"

def analyze_all():
    base_dir = "/Users/liuzhenwei/SourceCode/TA-test/Agent/test_data/generated_batches"
    
    results = []
    
    print(f"{'Case ID':<35} | {'Intent':<8} | {'Txns':<4} | {'AccErr':<6} | {'HoldErr':<7} | {'DataState':<18} | {'Verdict'}")
    print("-" * 110)
    
    tp = 0 # Positive Case + Consistent Data
    tn = 0 # Negative Case + Inconsistent Data
    fp = 0 # Negative Case + Consistent Data (Test won't trigger failure!)
    fn = 0 # Positive Case + Inconsistent Data (Test will fail unexpectedly!)
    
    batch_paths = glob.glob(os.path.join(base_dir, "batch_*"))
    for batch_path in sorted(batch_paths):
        for case_path in sorted(glob.glob(os.path.join(batch_path, "TC_*"))):
            case_id = os.path.basename(case_path)
            
            analyzer = TestCaseAnalyzer(batch_path, case_id)
            analyzer.process_new_accounts()
            analyzer.validate_trades()
            
            state = analyzer.get_consistency_status()
            intent = "NEG" if analyzer.is_negative_case else "POS"
            
            verdict = ""
            if intent == "POS":
                if state == "CONSISTENT":
                    verdict = "OK (True Pos)"
                    tp += 1
                else:
                    verdict = "FAIL (False Neg)" # Bad data generation for happy path
                    fn += 1
            else: # NEG
                if state != "CONSISTENT":
                    verdict = "OK (True Neg)" # Correctly generated bad data
                    tn += 1
                else:
                    verdict = "WARN (False Pos)" # Negative test but data looks valid?
                    # Special case: Maybe the negative test is about something else (e.g. duplicate ID)?
                    # If so, consistent data is fine. 
                    # But for "Trade" tests, usually we want data errors.
                    fp += 1
            
            print(f"{case_id:<35} | {intent:<8} | {analyzer.total_txns:<4} | {analyzer.invalid_acc_refs:<6} | {analyzer.insufficient_shares:<7} | {state:<18} | {verdict}")
            
    print("-" * 110)
    print(f"Summary Statistics:")
    print(f"Total Cases: {tp+tn+fp+fn}")
    print(f"Valid Generation (TP+TN): {tp+tn}")
    print(f"Generation Issues (FN):   {fn}  <-- Priority Fix (Happy paths with broken data)")
    print(f"Potential Weak Tests (FP):{fp}  <-- Negative tests with valid data (might pass unexpectedly)")

if __name__ == "__main__":
    analyze_all()
