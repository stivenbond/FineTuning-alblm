import subprocess
import sys
import logging
from pathlib import Path

def run_command(cmd_list, description):
    logging.info(f"=== Running: {description} ===")
    logging.info(f"Command: {' '.join(cmd_list)}")
    try:
        result = subprocess.run(cmd_list, check=True, text=True, capture_output=True)
        logging.info("SUCCESS")
        if result.stdout.strip():
            logging.info(f"Output:\n{result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"FAILED with exit code {e.returncode}")
        if e.stdout:
            logging.error(f"Stdout:\n{e.stdout}")
        if e.stderr:
            logging.error(f"Stderr:\n{e.stderr}")
        return False

def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    # repo_root here is the project folder: models/albanian_analysis
    repo_root = Path(__file__).parent.parent
    scripts_dir = Path(__file__).parent

    logging.info("Starting Albanian Analysis Model Data Pipeline...")

    # Step 1: Validate Gold Data
    # Note: Using raw_synthetic instead of gold for now since we just scaffolded it.
    # In a real run, this would be data/gold/
    gold_dir = repo_root / "data" / "raw_synthetic"
    if not gold_dir.exists():
        logging.error(f"Data directory {gold_dir} not found. Aborting.")
        sys.exit(1)

    cmd = [sys.executable, str(scripts_dir / "validate_schema.py"), "--input", str(gold_dir)]
    if not run_command(cmd, "Validate Schema"):
        sys.exit(1)

    # Step 2: Augment Data
    cmd = [sys.executable, str(scripts_dir / "augment.py"), "--gold-dir", str(gold_dir)]
    if not run_command(cmd, "Augment Data"):
        sys.exit(1)

    # Step 3: Split Dataset
    cmd = [sys.executable, str(scripts_dir / "split_dataset.py"), "--gold-dir", str(gold_dir)]
    if not run_command(cmd, "Split Dataset"):
        sys.exit(1)

    logging.info("=== Pipeline Completed Successfully ===")
    logging.info("Generated splits are available in data/splits/")

if __name__ == "__main__":
    main()
