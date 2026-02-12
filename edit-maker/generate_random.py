import json
import random
import subprocess
import sys
import os

def generate_random_videos(count=6):
    # Load hooks.json to get available features
    try:
        with open('hooks.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: hooks.json not found.")
        return

    features_list = []
    for category, features in data.get('features', {}).items():
        for feature_id in features:
            features_list.append((category, feature_id))

    if not features_list:
        print("No features found in hooks.json")
        return

    print(f"Found {len(features_list)} available features.")

    # Select random features
    selected_features = random.sample(features_list, min(count, len(features_list)))

    print(f"\nSelected {len(selected_features)} random features:")
    for cat, feat in selected_features:
        print(f" - {cat}: {feat}")

    print("\nStarting generation...")
    
    successful = 0
    python_executable = sys.executable 
    # Use the venv python if available/detected, but we'll assume the script is run with the correct python
    if os.path.exists(".venv/bin/python"):
        python_executable = ".venv/bin/python"

    for i, (category, feature) in enumerate(selected_features):
        print(f"\n[{i+1}/{count}] Generating video for {category} -> {feature}...")
        try:
            cmd = [python_executable, "main.py", "generate", category, feature]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✓ Success: {category}/{feature}")
                # Extract output path from stdout if possible
                for line in result.stdout.splitlines():
                    if "Video saved to:" in line:
                        print(f"  {line.strip()}")
                successful += 1
            else:
                print(f"✗ Failed: {category}/{feature}")
                print(f"  Error: {result.stderr.strip()}")
                
        except Exception as e:
            print(f"✗ Error executing command: {e}")

    print(f"\nCompleted. {successful}/{count} videos generated successfully.")

if __name__ == "__main__":
    generate_random_videos()
