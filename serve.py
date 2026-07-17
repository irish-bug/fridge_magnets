"""Production entry point. Run with: python serve.py
Uses waitress instead of Flask's dev server, since this gets exposed to the
internet via router port forwarding."""

from waitress import serve

from app import app, ensure_csv_header

if __name__ == "__main__":
    ensure_csv_header()
    serve(app, host="0.0.0.0", port=8080)
