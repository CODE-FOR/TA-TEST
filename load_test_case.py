import os
import sys
import shutil
import re
from datetime import datetime

def load_test_case(batch_id, test_case_id):
    project_root = os.getcwd()
    source_base = os.path.join(project_root, 'Agent', 'test_data', 'generated_batches', batch_id, test_case_id)
    target_base = os.path.join(project_root, 'data')
    
    if not os.path.exists(source_base):
        print(f"Error: Source directory {source_base} does not exist.")
        return

    # Clear data directory
    print("Clearing data directory...")
    # We want to clear contents of subdirectories, or recreate them.
    # The structure seems to be data/{db, inbox, outbox}
    
    dirs_to_clear = ['inbox', 'outbox', 'db']
    
    for subdir in dirs_to_clear:
        target_dir = os.path.join(target_base, subdir)
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        os.makedirs(target_dir, exist_ok=True)
    
    # Ensure inbox subdirectories exist
    os.makedirs(os.path.join(target_base, 'inbox', 'manager'), exist_ok=True)
    os.makedirs(os.path.join(target_base, 'inbox', 'distributor'), exist_ok=True)

    # Copy input_files/inbox to data/inbox
    source_inbox = os.path.join(source_base, 'input_files', 'inbox')
    if os.path.exists(source_inbox):
        print(f"Copying inbox from {source_inbox} to {os.path.join(target_base, 'inbox')}...")
        if os.path.isdir(source_inbox):
             shutil.copytree(source_inbox, os.path.join(target_base, 'inbox'), dirs_exist_ok=True)
             
             # Rename files to match today's date
             today_str = datetime.now().strftime("%Y%m%d")
             # Pattern to match _YYYYMMDD.csv at end of string
             date_pattern = re.compile(r'_20\d{6}\.csv$')
             
             print(f"Scanning for files to rename with date: {today_str}")
             for root, dirs, files in os.walk(os.path.join(target_base, 'inbox')):
                 for file in files:
                     if date_pattern.search(file):
                         new_name = date_pattern.sub(f'_{today_str}.csv', file)
                         if new_name != file:
                             old_path = os.path.join(root, file)
                             new_path = os.path.join(root, new_name)
                             print(f"Renaming: {file} -> {new_name}")
                             os.rename(old_path, new_path)

    else:
        print(f"Warning: {source_inbox} does not exist.")

    # Copy db_snapshot to data/db
    source_db = os.path.join(source_base, 'db_snapshot')
    if os.path.exists(source_db):
        print(f"Copying db_snapshot from {source_db} to {os.path.join(target_base, 'db')}...")
        for filename in os.listdir(source_db):
            s = os.path.join(source_db, filename)
            if os.path.isfile(s):
                # Rename to lowercase for consistency
                d = os.path.join(target_base, 'db', filename.lower())
                shutil.copy2(s, d)
    else:
        print(f"Warning: {source_db} does not exist.")
        
    # --- Check and create missing monitored files ---
    print("Checking for missing monitored files...")
    today_str = datetime.now().strftime("%Y%m%d")
    
    # Define monitored files and their headers
    # Mapping: (subdir, filename_pattern) -> header
    # filename_pattern uses {date} placeholder
    monitored_files = [
        # Manager Files
        {
            "subdir": "manager",
            "filename": f"NAV_FUND01_{today_str}.csv",
            "header": "fund_code,nav",
            "default_content": "FUND01,1.0000"
        },
        {
            "subdir": "manager",
            "filename": f"NAV_FUND02_{today_str}.csv",
            "header": "fund_code,nav",
            "default_content": "FUND02,1.0000"
        },
        {
            "subdir": "manager",
            "filename": f"CONFIRM_{today_str}.csv",
            "header": "trans_id,status,confirmed_shares,confirmed_nav"
        },
        # Distributor Files (DIST_A)
        {
            "subdir": "distributor",
            "filename": f"DIST_A_ACC_{today_str}.csv",
            "header": "request_no,biz_code,investor_name,id_no"
        },
        {
            "subdir": "distributor",
            "filename": f"DIST_A_TRADE_FUND01_{today_str}.csv",
            "header": "trans_id,fund_code,type,amount_or_shares,account_id"
        },
        {
            "subdir": "distributor",
            "filename": f"DIST_A_TRADE_FUND02_{today_str}.csv",
            "header": "trans_id,fund_code,type,amount_or_shares,account_id"
        }
    ]

    for item in monitored_files:
        subdir = item["subdir"]
        filename = item["filename"]
        header = item["header"]
        default_content = item.get("default_content", "")
        
        file_path = os.path.join(target_base, 'inbox', subdir, filename)
        if not os.path.exists(file_path):
            print(f"Creating missing monitored file: {filename}")
            with open(file_path, 'w') as f:
                f.write(header + "\n")
                if default_content:
                    f.write(default_content + "\n")

    print(f"Successfully loaded test case {test_case_id} from {batch_id}.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python load_test_case.py <batch_id> <test_case_id>")
        sys.exit(1)
    
    batch_id = sys.argv[1]
    test_case_id = sys.argv[2]
    load_test_case(batch_id, test_case_id)
