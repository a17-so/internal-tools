
import os
import yaml
import sys

def get_searchapi_key():
    try:
        # Path relative to script location in repo
        script_dir = os.path.dirname(os.path.abspath(__file__)) # api/scripts
        api_dir = os.path.dirname(script_dir) # api
        env_path = os.path.join(api_dir, "envs", "env.yaml")
        
        if not os.path.exists(env_path):
            print("", end="")
            return

        with open(env_path, "r") as f:
            data = yaml.safe_load(f)
            
        key = data.get("SEARCHAPI_KEY", "")
        # Also check env_variables legacy format just in case
        if not key and "env_variables" in data:
            key = data["env_variables"].get("SEARCHAPI_KEY", "")
            
        print(key, end="")
    except Exception as e:
        sys.stderr.write(f"Error extracting key: {e}\n")
        print("", end="")

if __name__ == "__main__":
    get_searchapi_key()
