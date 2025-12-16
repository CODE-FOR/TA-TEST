import os
import subprocess
import time
import glob
import sys

def verify_all():
    base_dir = "/Users/liuzhenwei/SourceCode/TA-test/Agent/test_data/generated_batches"
    # Find all test cases
    test_cases = []
    for batch_path in glob.glob(os.path.join(base_dir, "batch_*")):
        batch_id = os.path.basename(batch_path)
        for case_path in glob.glob(os.path.join(batch_path, "TC_*")):
            case_id = os.path.basename(case_path)
            test_cases.append((batch_id, case_id))
    
    test_cases.sort()
    
    results = []
    
    print(f"Found {len(test_cases)} test cases.")
    
    for i, (batch_id, case_id) in enumerate(test_cases):
        print(f"\n[{i+1}/{len(test_cases)}] Verifying {case_id} ...", end="", flush=True)
        
        # 1. Load data
        try:
            cmd_load = ["python3", "load_test_case.py", batch_id, case_id]
            subprocess.run(cmd_load, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print(f" LOAD ERROR")
            results.append({"batch": batch_id, "case": case_id, "status": "LOAD_ERROR"})
            continue
        
        # 2. Run container
        try:
            subprocess.run(["/bin/bash", "run.sh"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            print(f" RUN ERROR")
            results.append({"batch": batch_id, "case": case_id, "status": "RUN_ERROR"})
            continue
            
        # 3. Monitor
        # Give it a bit more time for build + run (e.g. 30s total, assuming build is cached)
        # Check every 1s
        status = "STUCK"
        for _ in range(30): 
            # Check if container 'ta' is running
            res = subprocess.run(["docker", "ps", "-q", "-f", "name=ta"], capture_output=True, text=True)
            if not res.stdout.strip():
                # Container is gone
                status = "PASS"
                break
            time.sleep(1)
            
        if status == "STUCK":
            print(" STUCK")
            # Kill it to be clean for next run (run.sh does it too, but good practice)
            subprocess.run(["docker", "stop", "ta"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            print(" PASS")
            
        results.append({
            "batch": batch_id,
            "case": case_id,
            "status": status
        })
        
    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    print(f"{'Case ID':<40} | {'Status':<10}")
    print("-" * 60)
    for r in results:
        print(f"{r['case']:<40} | {r['status']:<10}")
        
    stuck_count = sum(1 for r in results if r['status'] == 'STUCK')
    print("-" * 60)
    print(f"Total: {len(results)}, Passed: {len(results) - stuck_count}, Stuck: {stuck_count}")

if __name__ == "__main__":
    verify_all()
