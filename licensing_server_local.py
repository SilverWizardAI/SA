#!/usr/bin/env python3
"""
Local Licensing Server - Development & Testing

Minimal FastAPI server for testing licensing system locally.
Uses SQLite, no external dependencies (except FastAPI).

Usage:
    python licensing_server_local.py
    Server runs at http://localhost:8000

Features:
    - License validation API
    - License generation (for testing)
    - Feature access control
    - Rental management
    - SQLite database (auto-created)
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
import hashlib
import logging
from fastapi import FastAPI, HTTPException, Header, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import our Mac fingerprinting service and config
import sys
sys.path.insert(0, str(Path(__file__).parent))
from mac_fingerprint_service import MacFingerprintService
import licensing_config as config
from feature_bitmap import FeatureBitmap
from license_signing import LicenseSigner
import uuid
import secrets

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIG
# ============================================================================

DB_PATH = Path.home() / ".silver_wizard" / "licensing_test.db"
SERVER_PORT = config.SERVER_PORT
SERVER_HOST = config.SERVER_HOST
LICENSING_API_KEY = config.LICENSING_API_KEY

# ============================================================================
# DATABASE SETUP
# ============================================================================

def init_database():
    """Initialize SQLite database with schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Products
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT,
            base_price_cents INTEGER
        )
    """)

    # Features
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS features (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            slug TEXT NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(product_id, slug),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)

    # License Types
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS license_types (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            slug TEXT NOT NULL,
            name TEXT NOT NULL,
            duration_days INTEGER,
            max_macs INTEGER DEFAULT 1,
            price_cents INTEGER,
            UNIQUE(product_id, slug),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)

    # License Type Features
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS license_type_features (
            id TEXT PRIMARY KEY,
            license_type_id TEXT NOT NULL,
            feature_id TEXT NOT NULL,
            UNIQUE(license_type_id, feature_id),
            FOREIGN KEY(license_type_id) REFERENCES license_types(id),
            FOREIGN KEY(feature_id) REFERENCES features(id)
        )
    """)

    # Licenses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            license_type_id TEXT NOT NULL,
            license_key TEXT UNIQUE NOT NULL,
            mac_fingerprint_hash TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(license_type_id) REFERENCES license_types(id)
        )
    """)

    # Validations (audit log)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS validations (
            id TEXT PRIMARY KEY,
            license_id TEXT NOT NULL,
            mac_fingerprint_hash TEXT,
            result TEXT,
            validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(license_id) REFERENCES licenses(id)
        )
    """)

    # Rentals
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rentals (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            mac_fingerprint_hash TEXT NOT NULL,
            rental_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            rental_end TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'active',
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)

    # ============================================================================
    # PQTI-Specific Schema
    # ============================================================================

    # PQTI Licenses (for offline validation with bitmap features)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pqti_licenses (
            id INTEGER PRIMARY KEY,
            key_id TEXT UNIQUE NOT NULL,
            app TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            mac_fingerprint TEXT,
            features_hex TEXT NOT NULL,
            signature TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Index for fast lookups
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pqti_licenses_key_id
        ON pqti_licenses(key_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pqti_licenses_status
        ON pqti_licenses(status)
    """)

    # PQTI Trial Duration Rules (per app, per feature)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pqti_trial_durations (
            app TEXT NOT NULL,
            feature_idx INTEGER NOT NULL,
            duration_days INTEGER NOT NULL,
            PRIMARY KEY (app, feature_idx)
        )
    """)

    # PQTI Purchases (for Stripe integration)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pqti_purchases (
            id INTEGER PRIMARY KEY,
            token TEXT UNIQUE NOT NULL,
            key_id TEXT NOT NULL,
            app TEXT NOT NULL,
            features_hex TEXT NOT NULL,
            duration TEXT,
            status TEXT DEFAULT 'pending',
            amount_cents INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(key_id) REFERENCES pqti_licenses(key_id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pqti_purchases_token
        ON pqti_purchases(token)
    """)

    # PQTI Audit Log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pqti_audit (
            id INTEGER PRIMARY KEY,
            action TEXT NOT NULL,
            key_id TEXT,
            app TEXT,
            result TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pqti_audit_app_timestamp
        ON pqti_audit(app, timestamp)
    """)

    conn.commit()
    conn.close()

    print(f"✓ Database initialized: {DB_PATH}")
    print(f"✓ PQTI schema created")


def get_db() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def validate_api_key(x_api_key: Optional[str] = Header(None)):
    """
    Validate API key from X-API-Key header.

    Raises HTTPException(401) if missing or invalid.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    if x_api_key != LICENSING_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return x_api_key


# ============================================================================
# PQTI Helper Functions
# ============================================================================

def generate_key_id(app: str) -> str:
    """Generate a unique license key ID."""
    from datetime import datetime
    year = datetime.now().year
    random_suffix = secrets.token_hex(3).upper()  # 6 hex chars
    return f"LIC-{year}-{random_suffix}"


def log_audit(action: str, key_id: str = None, app: str = None, result: str = "success", details: str = None):
    """Log audit event."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO pqti_audit (action, key_id, app, result, details)
        VALUES (?, ?, ?, ?, ?)
    """, (action, key_id, app, result, json.dumps(details or {})))

    conn.commit()
    conn.close()


# ============================================================================
# TEST DATA SETUP
# ============================================================================

def setup_test_products():
    """Create test products and features."""
    conn = get_db()
    cursor = conn.cursor()

    # Check if already set up
    cursor.execute("SELECT COUNT(*) as count FROM products")
    if cursor.fetchone()["count"] > 0:
        conn.close()
        return

    print("Setting up test products and features...")

    # MacR-PyQt product
    cursor.execute("""
        INSERT INTO products (id, name, version, base_price_cents)
        VALUES ('macr-pyqt', 'Mac Retriever', '0.9.0', 4999)
    """)

    # Features for MacR
    features = [
        ("macr-search", "macr-pyqt", "search", "Email & File Search"),
        ("macr-export", "macr-pyqt", "export", "Export Emails"),
        ("macr-ai", "macr-pyqt", "ai_classify", "AI Classification"),
        ("macr-cloud", "macr-pyqt", "cloud_sync", "Cloud Sync"),
    ]

    for feat_id, prod_id, slug, name in features:
        cursor.execute("""
            INSERT INTO features (id, product_id, slug, name)
            VALUES (?, ?, ?, ?)
        """, (feat_id, prod_id, slug, name))

    # License types
    license_types = [
        ("perpetual", "macr-pyqt", "perpetual", "Perpetual License", None, 1, 4999),
        ("trial-7", "macr-pyqt", "7day_trial", "7-Day Trial", 7, 1, 0),
        ("rental-30", "macr-pyqt", "30day_rental", "30-Day Rental", 30, 1, 999),
        ("sub-yearly", "macr-pyqt", "yearly_sub", "Yearly Subscription", 365, 1, 6999),
    ]

    for lt_id, prod_id, slug, name, days, macs, price in license_types:
        cursor.execute("""
            INSERT INTO license_types (id, product_id, slug, name, duration_days, max_macs, price_cents)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (lt_id, prod_id, slug, name, days, macs, price))

    # Link features to license types
    feature_links = [
        # Perpetual gets all features
        ("perpetual", "macr-search"),
        ("perpetual", "macr-export"),
        ("perpetual", "macr-ai"),
        ("perpetual", "macr-cloud"),
        # Trial gets only search
        ("trial-7", "macr-search"),
        # Rental gets search + export
        ("rental-30", "macr-search"),
        ("rental-30", "macr-export"),
        # Subscription gets search + export + cloud
        ("sub-yearly", "macr-search"),
        ("sub-yearly", "macr-export"),
        ("sub-yearly", "macr-cloud"),
    ]

    for lt_id, feat_id in feature_links:
        link_id = f"{lt_id}_{feat_id}"
        cursor.execute("""
            INSERT INTO license_type_features (id, license_type_id, feature_id)
            VALUES (?, ?, ?)
        """, (link_id, lt_id, feat_id))

    conn.commit()
    conn.close()

    print("✓ Test products and features created")


# ============================================================================
# FASTAPI SERVER
# ============================================================================

app = FastAPI(title="Silver Wizard Licensing Server (Local)", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check."""
    return {
        "status": "ok",
        "service": "Silver Wizard Licensing Server",
        "version": "0.1.0",
        "database": str(DB_PATH),
        "environment": config.ENV.value,
        "endpoints": {
            "MacR (Legacy)": {
                "POST /api/validate-license": "Validate a license key",
                "POST /api/check-rental": "Check if rental is active",
            },
            "PQTI (v1)": {
                "POST /api/v1/licenses/generate": "Generate license with feature bitmap",
                "POST /api/v1/licenses/refresh": "Refresh/extend license",
                "POST /api/v1/licenses/purchase": "Initiate feature purchase",
                "POST /api/v1/licenses/revoke": "Revoke license",
                "GET /api/v1/licenses/purchase/{token}": "Check purchase status",
            }
        }
    }


# ============================================================================
# PQTI API v1 Endpoints
# ============================================================================

@app.post("/api/v1/licenses/generate")
async def generate_pqti_license(
    request_data: Dict[str, Any] = Body(...),
    x_api_key: Optional[str] = Header(None)
):
    """
    Generate a new PQTI license with feature bitmap.

    Request:
    {
        "app": "pqti",
        "access_levels": {
            "0": 15,        // VIDEO_RECORDING: perpetual
            "2": 4,         // MUTATION_TESTING: custom trial
            "4": 6          // SESSION_RECORDING: basic paid
        },
        "mac_fingerprint": "optional",
        "trial_durations": {
            "2": 30,        // MUTATION_TESTING: 30-day trial
            "4": 14         // SESSION_RECORDING: 14-day trial
        }
    }

    Response (200):
    {
        "key_id": "LIC-2026-ABC123",
        "app": "pqti",
        "issued_at": "2026-03-12",
        "mac_fingerprint": "...",
        "features_hex": "F0123456789ABCDEF0123456789ABCD",
        "signature": "hmac_sha256_hex"
    }
    """
    try:
        # Validate API key
        validate_api_key(x_api_key)

        # Extract request data
        app = request_data.get("app")
        access_levels = request_data.get("access_levels", {})
        mac_fingerprint = request_data.get("mac_fingerprint")
        trial_durations = request_data.get("trial_durations", {})

        # Validate app
        if not app:
            raise HTTPException(status_code=400, detail="Missing app")
        if app not in ["pqti", "macr", "iatv"]:
            raise HTTPException(status_code=400, detail=f"Unknown app: {app}")

        # Convert string keys to int in access_levels
        access_levels_int = {}
        for key, value in access_levels.items():
            try:
                feature_idx = int(key)
                if not isinstance(value, int):
                    value = int(value)
                access_levels_int[feature_idx] = value
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail=f"Invalid access_levels format")

        # Encode features
        try:
            features_hex = FeatureBitmap.encode(access_levels_int)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Generate key ID and issue date
        key_id = generate_key_id(app)
        issued_at = datetime.now().strftime("%Y-%m-%d")

        # Create license dict for signing
        license_dict = LicenseSigner.create_license_dict(
            key_id=key_id,
            app=app,
            issued_at=issued_at,
            features_hex=features_hex,
            mac_fingerprint=mac_fingerprint
        )

        # Sign license
        signer = LicenseSigner(config.PQTI_SECRET_KEY)
        signature = signer.sign(license_dict)

        # Store in database
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO pqti_licenses (key_id, app, issued_at, mac_fingerprint, features_hex, signature, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
        """, (key_id, app, issued_at, mac_fingerprint, features_hex, signature))

        conn.commit()
        conn.close()

        # Log audit
        log_audit(
            "generate",
            key_id=key_id,
            app=app,
            result="success",
            details={"features_count": len(access_levels_int), "is_single_user": mac_fingerprint is not None}
        )

        return {
            "key_id": key_id,
            "app": app,
            "issued_at": issued_at,
            "mac_fingerprint": mac_fingerprint,
            "features_hex": features_hex,
            "signature": signature
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate license: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/licenses/refresh")
async def refresh_pqti_license(
    request_data: Dict[str, Any] = Body(...),
    x_api_key: Optional[str] = Header(None)
):
    """
    Refresh/extend PQTI license (new signature with updated issued_at).

    Request:
    {
        "key_id": "LIC-2026-ABC123",
        "app": "pqti",
        "features_hex": "F0123456789ABCDEF0123456789ABCD"
    }

    Response (200): Same as generate
    """
    try:
        validate_api_key(x_api_key)

        key_id = request_data.get("key_id")
        app = request_data.get("app")
        features_hex = request_data.get("features_hex")

        if not key_id or not app or not features_hex:
            raise HTTPException(status_code=400, detail="Missing key_id, app, or features_hex")

        # Find license
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM pqti_licenses WHERE key_id = ? AND app = ?
        """, (key_id, app))

        license_row = cursor.fetchone()
        if not license_row:
            raise HTTPException(status_code=404, detail="License not found")

        # Check status
        if license_row["status"] != "active":
            raise HTTPException(status_code=409, detail=f"License is {license_row['status']}")

        # Refresh with new issued_at
        issued_at = datetime.now().strftime("%Y-%m-%d")
        mac_fingerprint = license_row["mac_fingerprint"]

        # Create updated license dict
        license_dict = LicenseSigner.create_license_dict(
            key_id=key_id,
            app=app,
            issued_at=issued_at,
            features_hex=features_hex,
            mac_fingerprint=mac_fingerprint
        )

        # Sign
        signer = LicenseSigner(config.PQTI_SECRET_KEY)
        signature = signer.sign(license_dict)

        # Update database
        cursor.execute("""
            UPDATE pqti_licenses
            SET issued_at = ?, features_hex = ?, signature = ?
            WHERE key_id = ?
        """, (issued_at, features_hex, signature, key_id))

        conn.commit()
        conn.close()

        # Log audit
        log_audit("refresh", key_id=key_id, app=app)

        return {
            "key_id": key_id,
            "app": app,
            "issued_at": issued_at,
            "mac_fingerprint": mac_fingerprint,
            "features_hex": features_hex,
            "signature": signature
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh license: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/licenses/purchase")
async def purchase_pqti_features(
    request_data: Dict[str, Any] = Body(...),
    x_api_key: Optional[str] = Header(None)
):
    """
    Initiate a feature purchase for existing license.

    Request:
    {
        "key_id": "LIC-2026-ABC123",
        "app": "pqti",
        "features_to_add": [0, 1, 2],
        "duration": "1year"
    }

    Response (200):
    {
        "token": "purch-uuid",
        "status": "pending",
        "payment_url": "https://stripe.com/...",
        "amount_cents": 4999
    }
    """
    try:
        validate_api_key(x_api_key)

        key_id = request_data.get("key_id")
        app = request_data.get("app")
        features_to_add = request_data.get("features_to_add", [])
        duration = request_data.get("duration", "1year")

        if not key_id or not app:
            raise HTTPException(status_code=400, detail="Missing key_id or app")

        # Find license
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM pqti_licenses WHERE key_id = ? AND app = ?
        """, (key_id, app))

        license_row = cursor.fetchone()
        if not license_row:
            raise HTTPException(status_code=404, detail="License not found")

        if license_row["status"] != "active":
            raise HTTPException(status_code=409, detail=f"Cannot purchase for {license_row['status']} license")

        # Merge new features with existing
        existing_features = FeatureBitmap.decode(license_row["features_hex"])
        new_features = {idx: 6 for idx in features_to_add}  # Add as "basic paid"

        merged_features = {}
        for idx in set(list(existing_features.keys()) + list(new_features.keys())):
            merged_features[idx] = max(existing_features.get(idx, 0), new_features.get(idx, 0))

        merged_hex = FeatureBitmap.encode(merged_features)

        # Generate purchase token
        token = f"purch-{str(uuid.uuid4()).lower()}"
        amount_cents = 4999  # Mock pricing

        # Store purchase
        cursor.execute("""
            INSERT INTO pqti_purchases (token, key_id, app, features_hex, duration, status, amount_cents)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (token, key_id, app, merged_hex, duration, amount_cents))

        conn.commit()
        conn.close()

        # Log audit
        log_audit("purchase_initiated", key_id=key_id, app=app)

        return {
            "token": token,
            "status": "pending",
            "payment_url": f"http://localhost:8000/stripe/mock?token={token}",
            "amount_cents": amount_cents
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate purchase: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/licenses/revoke")
async def revoke_pqti_license(
    request_data: Dict[str, Any] = Body(...),
    x_api_key: Optional[str] = Header(None)
):
    """
    Revoke a license (disable it).

    Request:
    {
        "key_id": "LIC-2026-ABC123",
        "reason": "payment_failed"
    }

    Response (200):
    {
        "status": "revoked",
        "key_id": "LIC-2026-ABC123"
    }
    """
    try:
        validate_api_key(x_api_key)

        key_id = request_data.get("key_id")
        reason = request_data.get("reason", "admin_revoke")

        if not key_id:
            raise HTTPException(status_code=400, detail="Missing key_id")

        # Find and revoke
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM pqti_licenses WHERE key_id = ?
        """, (key_id,))

        license_row = cursor.fetchone()
        if not license_row:
            raise HTTPException(status_code=404, detail="License not found")

        # Update status
        cursor.execute("""
            UPDATE pqti_licenses SET status = 'revoked' WHERE key_id = ?
        """, (key_id,))

        conn.commit()
        conn.close()

        # Log audit
        log_audit("revoke", key_id=key_id, app=license_row["app"], details={"reason": reason})

        return {
            "status": "revoked",
            "key_id": key_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke license: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/licenses/purchase/{token}")
async def check_purchase_status(
    token: str,
    x_api_key: Optional[str] = Header(None)
):
    """
    Check purchase status and retrieve updated license if paid.

    Response (200, if pending):
    {
        "status": "pending",
        "token": "purch-uuid"
    }

    Response (200, if paid):
    {
        "status": "paid",
        "token": "purch-uuid",
        "license": { ... }
    }
    """
    try:
        validate_api_key(x_api_key)

        # Find purchase
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM pqti_purchases WHERE token = ?
        """, (token,))

        purchase_row = cursor.fetchone()
        if not purchase_row:
            raise HTTPException(status_code=404, detail="Purchase not found")

        if purchase_row["status"] == "pending":
            conn.close()
            return {
                "status": "pending",
                "token": token
            }

        elif purchase_row["status"] == "paid":
            # Get license details
            cursor.execute("""
                SELECT * FROM pqti_licenses WHERE key_id = ?
            """, (purchase_row["key_id"],))

            license_row = cursor.fetchone()
            if not license_row:
                conn.close()
                raise HTTPException(status_code=404, detail="Associated license not found")

            # Check if purchase not yet applied
            applied_purchase = cursor.execute("""
                SELECT status FROM pqti_purchases WHERE token = ? AND status = 'applied'
            """, (token,)).fetchone()

            if not applied_purchase:
                # Apply new features to license
                # Update license with new features
                cursor.execute("""
                    UPDATE pqti_licenses
                    SET features_hex = ?
                    WHERE key_id = ?
                """, (purchase_row["features_hex"], purchase_row["key_id"]))

                # Mark purchase as applied
                cursor.execute("""
                    UPDATE pqti_purchases SET status = 'applied' WHERE token = ?
                """, (token,))

                conn.commit()

                # Re-sign the license
                license_dict = LicenseSigner.create_license_dict(
                    key_id=license_row["key_id"],
                    app=license_row["app"],
                    issued_at=license_row["issued_at"],
                    features_hex=purchase_row["features_hex"],
                    mac_fingerprint=license_row["mac_fingerprint"]
                )

                signer = LicenseSigner(config.PQTI_SECRET_KEY)
                new_signature = signer.sign(license_dict)

                # Update signature
                cursor.execute("""
                    UPDATE pqti_licenses SET signature = ? WHERE key_id = ?
                """, (new_signature, purchase_row["key_id"]))

                conn.commit()
            else:
                # Already applied, get current signature
                sig_row = cursor.execute("""
                    SELECT signature FROM pqti_licenses WHERE key_id = ?
                """, (purchase_row["key_id"],)).fetchone()
                new_signature = sig_row["signature"]

            conn.close()

            return {
                "status": "paid",
                "token": token,
                "license": {
                    "key_id": purchase_row["key_id"],
                    "app": license_row["app"],
                    "issued_at": license_row["issued_at"],
                    "mac_fingerprint": license_row["mac_fingerprint"],
                    "features_hex": purchase_row["features_hex"],
                    "signature": new_signature
                }
            }
        else:
            conn.close()
            return {"status": purchase_row["status"], "token": token}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check purchase: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/products")
async def list_products():
    """List all available products."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"products": products}


@app.get("/api/products/{product_id}/features")
async def get_product_features(product_id: str):
    """Get all features for a product."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM features WHERE product_id = ?", (product_id,))
    features = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"product_id": product_id, "features": features}


@app.post("/api/validate-license")
async def validate_license(
    mac_fingerprint: str,
    license_key: str,
    product_id: str,
    app_version: Optional[str] = None
):
    """
    Validate a license key against Mac fingerprint.

    Request:
        {
            "mac_fingerprint": "a1b2c3d4...",
            "license_key": "SW-XXXX-XXXX-XXXX",
            "product_id": "macr-pyqt",
            "app_version": "0.9.0"
        }

    Response (valid):
        {
            "valid": true,
            "license_type": "perpetual",
            "expires_at": null,
            "features": ["search", "export", "ai_classify"],
            "days_remaining": null
        }

    Response (invalid):
        {
            "valid": false,
            "reason": "expired|not_found|invalid_mac",
            "days_remaining": -5
        }
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Find license
        cursor.execute("""
            SELECT l.*, lt.slug, lt.duration_days
            FROM licenses l
            JOIN license_types lt ON l.license_type_id = lt.id
            WHERE l.license_key = ? AND l.product_id = ?
        """, (license_key, product_id))

        license_row = cursor.fetchone()

        if not license_row:
            # Log validation attempt
            validation_id = hashlib.md5(f"{license_key}_{mac_fingerprint}".encode()).hexdigest()
            cursor.execute("""
                INSERT INTO validations (id, license_id, mac_fingerprint_hash, result)
                VALUES (?, ?, ?, ?)
            """, (validation_id, "unknown", mac_fingerprint, "not_found"))
            conn.commit()
            conn.close()

            return JSONResponse(
                status_code=400,
                content={
                    "valid": False,
                    "reason": "not_found",
                    "message": "License key not found"
                }
            )

        # Check Mac fingerprint
        if license_row["mac_fingerprint_hash"] != mac_fingerprint:
            # Log validation attempt
            validation_id = hashlib.md5(f"{license_key}_{mac_fingerprint}".encode()).hexdigest()
            cursor.execute("""
                INSERT INTO validations (id, license_id, mac_fingerprint_hash, result)
                VALUES (?, ?, ?, ?)
            """, (validation_id, license_row["id"], mac_fingerprint, "invalid_mac"))
            conn.commit()
            conn.close()

            return JSONResponse(
                status_code=400,
                content={
                    "valid": False,
                    "reason": "invalid_mac",
                    "message": "License not valid for this Mac"
                }
            )

        # Check expiration
        if license_row["expires_at"]:
            expires = datetime.fromisoformat(license_row["expires_at"])
            if datetime.now() > expires:
                # Log validation attempt
                validation_id = hashlib.md5(f"{license_key}_{mac_fingerprint}".encode()).hexdigest()
                cursor.execute("""
                    INSERT INTO validations (id, license_id, mac_fingerprint_hash, result)
                    VALUES (?, ?, ?, ?)
                """, (validation_id, license_row["id"], mac_fingerprint, "expired"))
                conn.commit()
                conn.close()

                days_remaining = (expires - datetime.now()).days
                return JSONResponse(
                    status_code=400,
                    content={
                        "valid": False,
                        "reason": "expired",
                        "expires_at": license_row["expires_at"],
                        "days_remaining": days_remaining
                    }
                )

            days_remaining = (expires - datetime.now()).days
        else:
            days_remaining = None

        # Get features for this license type
        cursor.execute("""
            SELECT f.slug FROM features f
            JOIN license_type_features ltf ON f.id = ltf.feature_id
            WHERE ltf.license_type_id = ?
        """, (license_row["license_type_id"],))

        features = [row["slug"] for row in cursor.fetchall()]

        # Log successful validation
        validation_id = hashlib.md5(f"{license_key}_{mac_fingerprint}".encode()).hexdigest()
        cursor.execute("""
            INSERT INTO validations (id, license_id, mac_fingerprint_hash, result)
            VALUES (?, ?, ?, ?)
        """, (validation_id, license_row["id"], mac_fingerprint, "valid"))
        conn.commit()

        return {
            "valid": True,
            "license_type": license_row["slug"],
            "expires_at": license_row["expires_at"],
            "features": features,
            "days_remaining": days_remaining
        }

    finally:
        conn.close()


@app.post("/api/check-rental")
async def check_rental(mac_fingerprint: str, product_id: str):
    """
    Check if Mac has an active rental for product.

    Response (active rental):
        {
            "is_rental": true,
            "days_remaining": 15,
            "expires_at": "2026-03-26T...",
            "can_renew": true
        }

    Response (no rental):
        {
            "is_rental": false
        }
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT * FROM rentals
            WHERE mac_fingerprint_hash = ? AND product_id = ? AND status = 'active'
            ORDER BY rental_end DESC LIMIT 1
        """, (mac_fingerprint, product_id))

        rental = cursor.fetchone()

        if not rental:
            return {"is_rental": False}

        rental_end = datetime.fromisoformat(rental["rental_end"])
        days_remaining = (rental_end - datetime.now()).days

        if days_remaining <= 0:
            # Rental expired, mark as inactive
            cursor.execute(
                "UPDATE rentals SET status = ? WHERE id = ?",
                ("expired", rental["id"])
            )
            conn.commit()

            return {
                "is_rental": False,
                "message": "Rental expired"
            }

        return {
            "is_rental": True,
            "days_remaining": days_remaining,
            "expires_at": rental["rental_end"],
            "can_renew": True
        }

    finally:
        conn.close()


# ============================================================================
# TEST/DEVELOPMENT ENDPOINTS (Local Only)
# ============================================================================

@app.post("/api/generate-license")
async def generate_license(product_id: str = "macr-pyqt", license_type: str = "perpetual"):
    """
    Generate a test license for this Mac (LOCAL DEVELOPMENT ONLY).

    Useful for:
    - Testing on this machine
    - Generating licenses for family/test Macs
    - Quick iteration during development

    Usage:
        curl -X POST http://localhost:8000/api/generate-license?product_id=macr-pyqt&license_type=perpetual
    """
    try:
        # Get this Mac's fingerprint
        fingerprint_service = MacFingerprintService(use_cache=True)
        mac_fingerprint = fingerprint_service.get_mac_fingerprint()
        serial_suffix = fingerprint_service.get_hardware_serial()[-6:]

        conn = get_db()
        cursor = conn.cursor()

        # Verify product and license type exist
        cursor.execute(
            "SELECT id FROM products WHERE id = ?",
            (product_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

        cursor.execute(
            "SELECT id, duration_days FROM license_types WHERE product_id = ? AND slug = ?",
            (product_id, license_type)
        )
        lt_row = cursor.fetchone()
        if not lt_row:
            raise HTTPException(status_code=404, detail=f"License type {license_type} not found")

        # Generate license key
        license_key = fingerprint_service.generate_license_key(product_id, "0.9.0", license_type)

        # Calculate expiration
        expires_at = None
        if lt_row["duration_days"]:
            expires_at = (datetime.now() + timedelta(days=lt_row["duration_days"])).isoformat()

        # Create license
        license_id = hashlib.md5(f"{license_key}_{mac_fingerprint}".encode()).hexdigest()
        cursor.execute("""
            INSERT INTO licenses (id, product_id, license_type_id, license_key, mac_fingerprint_hash, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (license_id, product_id, lt_row["id"], license_key, mac_fingerprint, expires_at))
        conn.commit()
        conn.close()

        return {
            "generated": True,
            "license_key": license_key,
            "product_id": product_id,
            "license_type": license_type,
            "mac_serial_suffix": serial_suffix,
            "expires_at": expires_at,
            "message": "✓ License generated for this Mac (LOCAL DEVELOPMENT)"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-rental")
async def generate_rental(product_id: str = "macr-pyqt", days: int = 7):
    """
    Generate a test rental for this Mac (LOCAL DEVELOPMENT ONLY).

    Usage:
        curl -X POST http://localhost:8000/api/generate-rental?product_id=macr-pyqt&days=7
    """
    try:
        fingerprint_service = MacFingerprintService(use_cache=True)
        mac_fingerprint = fingerprint_service.get_mac_fingerprint()
        serial_suffix = fingerprint_service.get_hardware_serial()[-6:]

        conn = get_db()
        cursor = conn.cursor()

        # Verify product exists
        cursor.execute("SELECT id FROM products WHERE id = ?", (product_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

        # Create rental
        rental_id = hashlib.md5(f"{product_id}_{mac_fingerprint}".encode()).hexdigest()
        rental_end = (datetime.now() + timedelta(days=days)).isoformat()

        cursor.execute("""
            INSERT INTO rentals (id, product_id, mac_fingerprint_hash, rental_end)
            VALUES (?, ?, ?, ?)
        """, (rental_id, product_id, mac_fingerprint, rental_end))
        conn.commit()
        conn.close()

        return {
            "generated": True,
            "product_id": product_id,
            "days": days,
            "rental_end": rental_end,
            "mac_serial_suffix": serial_suffix,
            "message": f"✓ Rental generated for {days} days"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/debug/database")
async def debug_database():
    """Debug endpoint: show database contents (LOCAL ONLY)."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM licenses")
    license_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM rentals WHERE status = 'active'")
    rental_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM validations")
    validation_count = cursor.fetchone()["count"]

    conn.close()

    return {
        "database": str(DB_PATH),
        "stats": {
            "licenses": license_count,
            "active_rentals": rental_count,
            "validations": validation_count
        }
    }


# ============================================================================
# STARTUP
# ============================================================================

def initialize_fingerprint_cache():
    """Initialize Mac fingerprint cache at server startup (non-blocking)."""
    try:
        fingerprint_service = MacFingerprintService(use_cache=True)
        # Call once to populate disk cache
        # This ensures subsequent calls don't block async context
        fingerprint = fingerprint_service.get_mac_fingerprint()
        logger.info(f"✓ Fingerprint cache initialized: {fingerprint[:16]}...")
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize fingerprint cache: {e}")
        logger.warning("   Fingerprint will be fetched on first request (may block)")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔐 Silver Wizard Licensing Server (Local Development)")
    print("="*70)

    # Validate configuration
    config.validate_config()

    # Initialize database
    init_database()

    # Setup test data
    setup_test_products()

    # Initialize fingerprint cache (to avoid async blocking later)
    initialize_fingerprint_cache()

    print(f"\n✓ Starting server on http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"✓ Database: {DB_PATH}")
    print(f"✓ Environment: {config.ENV.value}")
    print("\n📍 Key endpoints:")
    print(f"  POST http://localhost:8000/api/validate-license")
    print(f"  POST http://localhost:8000/api/check-rental")
    print(f"  POST http://localhost:8000/api/generate-license (local only)")
    print(f"  POST http://localhost:8000/api/generate-rental (local only)")
    print(f"  GET  http://localhost:8000/api/debug/database (local only)")
    print("\n📖 Docs: http://localhost:8000/docs")
    print("="*70 + "\n")

    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
