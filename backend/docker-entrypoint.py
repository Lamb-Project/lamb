#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

import config


def replace_string(text: str, key: str, value: str) -> tuple[str, int]:
    pattern = rf"({re.escape(key)}\s*:\s*)(?:'[^']*'|\"[^\"]*\")"
    replacement = rf"\1{json.dumps(value)}"
    return re.subn(pattern, replacement, text, count=1)


def replace_bool(text: str, key: str, value: bool) -> tuple[str, int]:
    pattern = rf"({re.escape(key)}\s*:\s*)(?:true|false)"
    replacement = rf"\1{'true' if value else 'false'}"
    return re.subn(pattern, replacement, text, count=1)


def patch_frontend_config() -> None:
    frontend_build_path = os.getenv("LAMB_FRONTEND_BUILD_PATH", "/app/frontend/build")
    config_js_path = Path(frontend_build_path) / "config.js"
    config_js_path.parent.mkdir(parents=True, exist_ok=True)

    base_url = config.LAMB_FRONTEND_BASE_URL
    lamb_server = config.LAMB_FRONTEND_LAMB_SERVER
    openwebui_server = config.LAMB_FRONTEND_OPENWEBUI_SERVER
    enable_openwebui = config.LAMB_ENABLE_OPENWEBUI
    enable_debug = config.LAMB_ENABLE_DEBUG

    if not config_js_path.exists():
        config_payload = {
            "api": {
                "baseUrl": base_url,
                "lambServer": lamb_server,
                "openWebUiServer": openwebui_server,
            },
            "assets": {"path": "/static"},
            "features": {
                "enableOpenWebUi": enable_openwebui,
                "enableDebugMode": enable_debug,
            },
        }
        config_js_path.write_text("window.LAMB_CONFIG = " + json.dumps(config_payload, indent=2) + ";\n", encoding="utf-8")
        return

    text = config_js_path.read_text(encoding="utf-8")
    updates = [
        ("baseUrl", base_url, replace_string),
        ("lambServer", lamb_server, replace_string),
        ("openWebUiServer", openwebui_server, replace_string),
        ("enableOpenWebUi", enable_openwebui, replace_bool),
        ("enableDebugMode", enable_debug, replace_bool),
    ]

    for key, value, replacer in updates:
        text, changed = replacer(text, key, value)
        if changed == 0:
            print(f"Warning: key '{key}' not found in {config_js_path}")

    config_js_path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_frontend_config()
    if len(sys.argv) > 1:
        os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
