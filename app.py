"""
Medal Export to Immich — app.py
Main entry point. Launches the sync engine in a background thread
and serves the live dashboard on the configured port.
"""

import sys
import threading

import config
from sync_engine import run_export
from dashboard import app


def main():
    # Validate config
    errors = config.validate()
    if errors:
        print("\n❌  Configuration errors:\n")
        for e in errors:
            print(f"   • {e}")
        print("\n   Copy .env.example → .env and fill in your Immich details.\n")
        sys.exit(1)

    print(f"""
  ⚡ Medal Export to Immich
  ─────────────────────────
  Immich:     {config.IMMICH_URL}
  Medal Path: {config.MEDAL_PATH}
  Album:      {config.ALBUM_NAME}
  Dashboard:  http://localhost:{config.DASHBOARD_PORT}
  ─────────────────────────
""")

    # Start export in background thread
    t = threading.Thread(target=run_export, daemon=True)
    t.start()

    # Start dashboard (blocking)
    app.run(host="0.0.0.0", port=config.DASHBOARD_PORT, debug=False)


if __name__ == "__main__":
    main()
