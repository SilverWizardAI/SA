# Licensing System Architecture

## System Overview

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                          SILVER WIZARD IP PROTECTION                       ┃
┃                                                                             ┃
┃  PIW Obfuscation + Mac Fingerprinting + Licensing + Feature Locking        ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┌─────────────────────────────────────────────────────────────────────────────┐
│                         MACAR-PYQT APPLICATION                             │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │ Startup Flow:                                                      │    │
│  │                                                                    │    │
│  │  1. Import MacFingerprintService                                 │    │
│  │  2. Get Mac hardware serial (ioreg)                              │    │
│  │  3. Calculate fingerprint (SHA256)                               │    │
│  │  4. Check for stored license key                                │    │
│  │  5. Call /api/validate-license                                   │    │
│  │  6. Show Licensed or Trial badge based on response              │    │
│  │  7. Enable/disable features per license type                    │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Features controlled by license:                                           │
│  • search (included in all)                                                │
│  • export (perpetual, rental, subscription)                               │
│  • ai_classify (perpetual, subscription only)                             │
│  • cloud_sync (perpetual, subscription only)                              │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                    HTTPS/JSON API (validated)
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LICENSING SERVER (FastAPI)                              │
│                      localhost:8000                                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ VALIDATION ENDPOINTS (✅ Working)                                   │  │
│  │                                                                     │  │
│  │ POST /api/validate-license                                        │  │
│  │   Input:  mac_fingerprint, license_key, product_id               │  │
│  │   Output: { valid, features, license_type, expires_at }          │  │
│  │                                                                     │  │
│  │   Logic:                                                           │  │
│  │   1. Look up license by license_key_hash                         │  │
│  │   2. Check mac_fingerprint matches                               │  │
│  │   3. Check not expired (if time-based)                           │  │
│  │   4. Check not revoked                                           │  │
│  │   5. Query license_type_features for this license_type           │  │
│  │   6. Return features array                                        │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ RENTAL ENDPOINTS (✅ Working)                                       │  │
│  │                                                                     │  │
│  │ POST /api/check-rental                                            │  │
│  │   Input:  mac_fingerprint, product_id                             │  │
│  │   Output: { is_rental, days_remaining, expires_at, can_renew }   │  │
│  │                                                                     │  │
│  │   Logic:                                                           │  │
│  │   1. Search rentals table for active rental                       │  │
│  │   2. Check rental_end > now()                                     │  │
│  │   3. Calculate days_remaining                                     │  │
│  │   4. Return rental status                                         │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ MANAGEMENT ENDPOINTS (✅ Working)                                   │  │
│  │                                                                     │  │
│  │ GET /api/products         - List all products                     │  │
│  │ GET /api/products/{id}/features - Get product features           │  │
│  │ GET /api/debug/database   - Database statistics                   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ DEVELOPMENT ENDPOINTS (⏳ Async subprocess hang)                     │  │
│  │                                                                     │  │
│  │ POST /api/generate-license   - Create test license               │  │
│  │ POST /api/generate-rental    - Create test rental                │  │
│  │                                                                     │  │
│  │ Known issue: ioreg subprocess hangs in async context              │  │
│  │ Workaround: Use MacFingerprintService directly in script          │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                            SQLite3 / SQL
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE SCHEMA                                     │
│                      ~/.silver_wizard/licensing_test.db                     │
│                                                                             │
│  ┌─────────────────────┐  ┌──────────────────────┐  ┌─────────────────┐   │
│  │ products            │  │ features             │  │ license_types   │   │
│  ├─────────────────────┤  ├──────────────────────┤  ├─────────────────┤   │
│  │ id (PK)             │  │ id (PK)              │  │ id (PK)         │   │
│  │ slug (unique)       │  │ product_id (FK)      │  │ product_id (FK) │   │
│  │ name                │  │ slug (unique)        │  │ slug (unique)   │   │
│  │ version             │  │ name                 │  │ name            │   │
│  │ base_price_cents    │  │ feature_type         │  │ duration_days   │   │
│  │                     │  │                      │  │ price_cents     │   │
│  │ Example:            │  │ Example:             │  │ is_renewable    │   │
│  │ macr-pyqt           │  │ search (core)        │  │ max_macs        │   │
│  │ $49.99              │  │ export (premium)     │  │                 │   │
│  │ v0.9.0              │  │ ai_classify (prem)   │  │ Types:          │   │
│  │                     │  │ cloud_sync (prem)    │  │ perpetual       │   │
│  └─────────────────────┘  └──────────────────────┘  │ 7day_trial      │   │
│                                                       │ 30day_rental    │   │
│                                                       │ yearly_sub      │   │
│  ┌────────────────────────────────────────────────┐  └─────────────────┘   │
│  │ license_type_features (join table)             │                        │
│  ├────────────────────────────────────────────────┤                        │
│  │ license_type_id (FK) → license_types           │                        │
│  │ feature_id (FK) → features                     │                        │
│  │                                                 │                        │
│  │ Example:                                        │                        │
│  │ perpetual → search, export, ai_classify, ...  │                        │
│  │ 7day_trial → search (only)                    │                        │
│  └────────────────────────────────────────────────┘                        │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ licenses                                                             │  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │ id (PK)                                                              │  │
│  │ license_key_hash (UNIQUE) - SHA256 of license key                  │  │
│  │ mac_fingerprint_hash - SHA256 hash of mac serial                   │  │
│  │ product_id (FK)                                                     │  │
│  │ license_type_id (FK)                                                │  │
│  │ status (active|expired|revoked|suspended)                          │  │
│  │ expires_at (NULL for perpetual)                                    │  │
│  │ purchase_date, activated_date, last_validation                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────────────┐  ┌──────────────────────────────────────┐   │
│  │ rentals                  │  │ license_validations (audit log)     │   │
│  ├──────────────────────────┤  ├──────────────────────────────────────┤   │
│  │ id (PK)                  │  │ id (PK)                              │   │
│  │ product_id (FK)          │  │ license_id (FK)                      │   │
│  │ mac_fingerprint_hash     │  │ validation_result                    │   │
│  │ rental_start             │  │ (valid|invalid_mac|expired|...)      │   │
│  │ rental_end               │  │ validated_at (timestamp)             │   │
│  │ status (active|expired)  │  │                                      │   │
│  │ auto_renew               │  │ For fraud detection & analytics      │   │
│  └──────────────────────────┘  └──────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ payments (ready for Stripe integration)                             │  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │ id (PK)                                                              │  │
│  │ user_id, license_id, rental_id (FKs)                               │  │
│  │ amount_cents, currency                                              │  │
│  │ stripe_payment_intent_id, stripe_charge_id                          │  │
│  │ status (pending|succeeded|failed|refunded)                          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: License Validation

```
┌──────────────────────┐
│ MacR-PyQt Startup    │
└──────────┬───────────┘
           │
           ├─ 1. Create MacFingerprintService
           │      service = MacFingerprintService()
           │
           ├─ 2. Get Mac Serial via ioreg
           │      serial = service.get_hardware_serial()
           │      → Returns: "ABC123XYZ789..."
           │
           ├─ 3. Calculate Fingerprint
           │      fingerprint = service.get_mac_fingerprint()
           │      → Returns: SHA256(serial) = "fef623de..."
           │
           ├─ 4. Load Stored License Key
           │      license_key = get_from_preferences()
           │      → Returns: "SW-12A6-9D8D-C421-D24B"
           │
           ▼
    ┌──────────────────────────────────────────────┐
    │ HTTP Request to Licensing Server             │
    │                                              │
    │ POST /api/validate-license?                  │
    │   mac_fingerprint=fef623de...&               │
    │   license_key=SW-12A6-9D8D-C421-D24B&        │
    │   product_id=macr-pyqt                       │
    └──────────────────┬───────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────────────┐
    │ Server: Validate License                     │
    │                                              │
    │ 1. Query: SELECT * FROM licenses             │
    │           WHERE license_key_hash = ?         │
    │    Result: license record found ✓            │
    │                                              │
    │ 2. Check: mac_fingerprint_hash matches?      │
    │    Result: "fef623de..." == stored? YES ✓    │
    │                                              │
    │ 3. Check: status = 'active'?                 │
    │    Result: YES ✓                             │
    │                                              │
    │ 4. Check: expires_at is NULL or future?      │
    │    Result: NULL (perpetual) ✓                │
    │                                              │
    │ 5. Query: SELECT feature_id FROM             │
    │           license_type_features              │
    │           WHERE license_type_id = ?          │
    │    Result: ["search", "export", "ai_cl..."]  │
    │                                              │
    │ 6. Return valid=true + features              │
    └──────────────────┬───────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────────────┐
    │ HTTP Response from Server                    │
    │                                              │
    │ {                                            │
    │   "valid": true,                             │
    │   "license_type": "perpetual",               │
    │   "expires_at": null,                        │
    │   "features": [                              │
    │     "search", "export", "ai_classify",       │
    │     "cloud_sync"                             │
    │   ],                                         │
    │   "days_remaining": null                     │
    │ }                                            │
    └──────────────────┬───────────────────────────┘
                       │
                       ▼
    ┌──────────────────────────────────────────────┐
    │ MacR-PyQt: Process Response                  │
    │                                              │
    │ if valid:                                    │
    │   ENABLED_FEATURES = ["search", "export", ...
    │   show_badge("Licensed")                     │
    │   enable_all_menus()                         │
    │   start_cloud_sync()                         │
    │ else:                                        │
    │   ENABLED_FEATURES = ["search"]              │
    │   show_badge("Trial (7 days)")               │
    │   disable_export_menu()                      │
    │   disable_ai_features()                      │
    └──────────────────────────────────────────────┘
```

---

## Feature Locking Integration (Pending PQTI)

```
Once PQTI delivers feature framework:

MacR-PyQt
├── Features (from PQTI framework)
│   ├── SearchEmailsFeature
│   ├── ExportEmailsFeature
│   ├── AICategorizeFeature
│   └── CloudSyncFeature
│
├── License Integration
│   ├── On startup:
│   │   1. Get license via /api/validate-license
│   │   2. Extract features array from response
│   │
│   ├── For each feature:
│   │   if feature.name in license_features:
│   │       feature.unlock()
│   │   else:
│   │       feature.lock()
│   │
│   └── Per-feature UI control
│       ├── Search: Always available (in all)
│       ├── Export: Disabled in trial (locked)
│       ├── AI: Disabled in trial (locked)
│       └── Cloud: Disabled in trial (locked)
```

---

## License Type Feature Matrix

```
Feature          │ Perpetual │ Trial │ Rental │ Subscription
─────────────────┼───────────┼───────┼────────┼──────────────
Search Emails    │     ✓     │   ✓   │   ✓    │      ✓
Export Emails    │     ✓     │   ✗   │   ✓    │      ✓
AI Categorize    │     ✓     │   ✗   │   ✗    │      ✓
Cloud Sync       │     ✓     │   ✗   │   ✗    │      ✓
─────────────────┼───────────┼───────┼────────┼──────────────
Duration         │  Forever  │  7d   │  30d   │     365d
Price            │  $49.99   │ Free  │ $9.99  │    $69.99/y
```

---

## Authentication & Security (Production)

```
Current (Development):
├── No authentication (local testing only)
├── SQLite database (unencrypted)
└── HTTP (no TLS)

Production Requirements:
├── API Key or JWT authentication
│   Authorization: Bearer {token}
│
├── HTTPS with TLS certificates
│   Let's Encrypt auto-renewal
│
├── Database encryption at rest
│   - PostgreSQL with encryption
│   - Or Vault for key management
│
├── License key encryption
│   - Encrypted with user's Mac fingerprint
│   - Tied to hardware, not transferable
│
└── Rate limiting & DDoS protection
    - CloudFlare or similar
    - Max requests per IP
```

---

## Deployment Architecture (Future)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Production Deployment                        │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ CloudFlare / Reverse Proxy                               │  │
│  │ - SSL/TLS termination                                    │  │
│  │ - Rate limiting                                          │  │
│  │ - DDoS protection                                        │  │
│  │ - Caching (API responses)                                │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│                     │                                            │
│  ┌──────────────────▼───────────────────────────────────────┐  │
│  │ Load Balancer                                            │  │
│  │ - Distribute traffic across servers                      │  │
│  │ - Health checks                                          │  │
│  │ - Failover                                               │  │
│  └──────────────────┬───────────────────────────────────────┘  │
│         ┌───────────┼───────────┐                                │
│         │           │           │                                │
│  ┌──────▼──┐  ┌──────▼──┐  ┌──────▼──┐                           │
│  │ Server1 │  │ Server2 │  │ Server3 │  (Auto-scaling)         │
│  │ FastAPI │  │ FastAPI │  │ FastAPI │                          │
│  │  :8000  │  │  :8000  │  │  :8000  │                          │
│  └──────┬──┘  └──────┬──┘  └──────┬──┘                           │
│         │           │           │                                │
│         └───────────┼───────────┘                                │
│                     │                                            │
│  ┌──────────────────▼───────────────────────────────────────┐  │
│  │ Shared Database (PostgreSQL)                             │  │
│  │ - Multi-replica for HA                                   │  │
│  │ - Automated backups                                      │  │
│  │ - Encryption at rest                                     │  │
│  │ - Read replicas for analytics                            │  │
│  └────────────────────────────────────────────────────────┘  │
│         ┌────────────────────────────────────────────────┐    │
│         │ Stripe Integration                             │    │
│         │ - Payment processing                           │    │
│         │ - Webhook handling                             │    │
│         │ - Subscription management                      │    │
│         └────────────────────────────────────────────────┘    │
│         ┌────────────────────────────────────────────────┐    │
│         │ Monitoring & Analytics                         │    │
│         │ - DataDog / New Relic                          │    │
│         │ - License validation metrics                   │    │
│         │ - Fraud detection                              │    │
│         └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

**Architecture complete and documented!**
