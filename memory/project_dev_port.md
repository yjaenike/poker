---
name: project_dev_port
description: The dev server runs on port 5002 — macOS AirPlay Receiver occupies port 5000
metadata:
  type: project
---

App runs on port 5002 (configured in `app.py`).

**Why:** macOS AirPlay Receiver holds port 5000, so the default was changed.

**How to apply:** Always use `http://localhost:5002` for local dev. Don't suggest port 5000.
