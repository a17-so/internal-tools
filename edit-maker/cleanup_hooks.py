import json
from pathlib import Path

hooks_file = Path("hooks.json")
with open(hooks_file, "r") as f:
    data = json.load(f)

def clean_hooks(hooks_list):
    new_list = []
    # convert to set for easy lookup of existing "is what" versions
    current_hooks = set(hooks_list)
    
    for hook in hooks_list:
        # Check for the weak pattern "makes you attractive" (without 10x or "is what")
        if hook.endswith("makes you attractive") and "10x" not in hook and "is what" not in hook:
            # Construct the strong version
            # E.g. "a big forehead makes you attractive" -> "a big forehead is what makes you attractive"
            # Replace " makes you attractive" with " is what makes you attractive"
            strong_version = hook.replace(" makes you attractive", " is what makes you attractive")
            
            # If string replacement worked (it should have)
            if strong_version != hook:
                # If the strong version already exists in the list, just drop the weak one
                if strong_version in current_hooks:
                    continue
                else:
                    # If it doesn't exist, replace the weak one with strong one
                    new_list.append(strong_version)
            else:
                new_list.append(hook)
        else:
            new_list.append(hook)
    return new_list

def process_features(feature_dict):
    for key, value in feature_dict.items():
        if "hooks" in value:
            value["hooks"] = clean_hooks(value["hooks"])
        # Handle nested categories if any (hooks.json structure is features -> category -> item)
        # But here 'value' is the item dict.
        # Wait, structure is data['features'][category][item]
        
# Iterate through categories
for category in data["features"]:
    for item_key in data["features"][category]:
        item = data["features"][category][item_key]
        if "hooks" in item:
            item["hooks"] = clean_hooks(item["hooks"])

with open(hooks_file, "w") as f:
    json.dump(data, f, indent=2)
    # Restore newline at end of file
    f.write("\n")

print("Hooks cleaned successfully.")
