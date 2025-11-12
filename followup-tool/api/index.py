from flask import Flask, request, jsonify
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path to import followup_gmail
_parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(_parent_dir))

# Import followup_gmail
import importlib.util
_followup_path = _parent_dir / "followup_gmail.py"
spec = importlib.util.spec_from_file_location("followup_gmail", _followup_path)
followup_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(followup_module)
GmailFollowUp = followup_module.GmailFollowUp

app = Flask(__name__)

def load_templates():
    """Load all follow-up templates (level 1, 2, 3)."""
    base_path = Path(__file__).parent.parent
    templates = {}
    
    for level in [1, 2, 3]:
        template_path = base_path / f"followup_template_level{level}.txt"
        if template_path.exists():
            templates[level] = template_path.read_text().strip()
        else:
            print(f"⚠ Template file not found: {template_path}")
            if level == 1:
                # Fallback to default template for level 1
                templates[1] = """hey {username},

following up on my email about the {app_name} paid promo opportunity!

we think you'd be a great fit and would love to work with you. let me know if you're interested!

also, your audience looks to you for guidance—{app_name} makes that guidance tangible.

-{from_name} from the {app_name} App ({link_url})
"""
    
    return templates if templates else None

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"ok": True, "service": "followup-tool-api"})

@app.route("/followup", methods=["POST"])
def followup():
    """
    Run the Gmail follow-up process.
    
    Expected JSON body:
    {
        "profile": "pretti" (optional, defaults to config default),
        "max_emails": 100 (optional, None = all emails),
        "dry_run": false (optional, default false)
    }
    """
    try:
        data = request.get_json() or {}
        
        profile = data.get("profile")
        max_emails = data.get("max_emails")
        dry_run = data.get("dry_run", False)
        config_path = data.get("config_path")
        
        # Load templates
        templates = load_templates()
        if not templates:
            return jsonify({
                "ok": False,
                "error": "Follow-up templates not found"
            }), 500
        
        # Check if we're in cloud (no Arc available) or local (Arc available)
        # In cloud, we need to launch a browser. Locally, we can use Arc.
        use_arc = os.environ.get("USE_ARC", "false").lower() == "true"
        arc_debug_port = int(os.environ.get("ARC_DEBUG_PORT", "9222"))
        
        # Run the follow-up process
        async def run_followup():
            tool = GmailFollowUp(
                use_arc=use_arc,
                arc_debug_port=arc_debug_port,
                profile=profile,
                config_path=config_path,
                headless=True if not use_arc else False,  # Headless in cloud
            )
            
            await tool.run(
                followup_templates=templates,
                dry_run=dry_run,
                max_emails=max_emails
            )
            
            return {
                "ok": True,
                "message": f"Follow-up process completed (dry_run={dry_run})"
            }
        
        # Run async function
        result = asyncio.run(run_followup())
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8001))
    app.run(host="0.0.0.0", port=port, debug=True)

