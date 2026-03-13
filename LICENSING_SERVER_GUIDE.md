# Local Licensing Server - Running Guide

This guide shows how to run the licensing server locally for development and testing.

## ⚡ Quick Start

### 1. Start the Server

```bash
cd /Users/stevedeighton/Library/CloudStorage/Dropbox/A_Coding/SA
python licensing_server_local.py
```

**Expected output:**
```
INFO:     Started server process [PID]
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

The server will:
- Create SQLite database at `~/.silver_wizard/licensing_test.db`
- Auto-initialize with MacR-PyQt product and test data
- Enable CORS for MacR-PyQt integration
- Auto-reload when code changes

### 2. Test the Server (in separate terminal)

```bash
cd /Users/stevedeighton/Library/CloudStorage/Dropbox/A_Coding/SA
python test_licensing_server.py
```

This will run a complete test suite showing:
- ✓ Server connectivity
- ✓ Generating licenses (perpetual, trial)
- ✓ Validating licenses
- ✓ Testing Mac fingerprinting
- ✓ Rental functionality
- ✓ Feature access control
- ✓ Database statistics

---

## 📋 API Endpoints

### Core Endpoints (Production)

#### POST `/api/validate-license`
Validate a license key for this Mac.

**Request:**
```json
{
  "mac_fingerprint": "a1b2c3d4e5f6...",
  "license_key": "SW-XXXX-XXXX-XXXX-XXXX",
  "product_id": "macr-pyqt",
  "app_version": "0.9.0"
}
```

**Response (valid):**
```json
{
  "valid": true,
  "license_type": "perpetual",
  "expires_at": null,
  "features": ["search", "export", "ai_classify", "cloud_sync"],
  "days_remaining": null,
  "mac_serial_suffix": "ABC123",
  "last_check": "2026-03-11T10:30:00"
}
```

**Response (invalid):**
```json
{
  "valid": false,
  "reason": "expired",
  "days_remaining": -5,
  "can_renew": true,
  "renewal_url": "https://licensing.silverwizard.io/renew?license_id=..."
}
```

**cURL example:**
```bash
curl -X POST http://localhost:8000/api/validate-license \
  -H "Content-Type: application/json" \
  -d '{
    "mac_fingerprint": "abc123...",
    "license_key": "SW-1234-5678-9ABC-DEF0",
    "product_id": "macr-pyqt"
  }'
```

---

#### POST `/api/check-rental`
Check if Mac has active rental for product.

**Request:**
```json
{
  "mac_fingerprint": "a1b2c3d4e5f6...",
  "product_id": "macr-pyqt"
}
```

**Response (active rental):**
```json
{
  "is_rental": true,
  "days_remaining": 15,
  "expires_at": "2026-03-26T10:30:00",
  "can_renew": true,
  "renewal_price_cents": 999
}
```

**Response (no rental):**
```json
{
  "is_rental": false,
  "days_remaining": 0
}
```

**cURL example:**
```bash
curl -X POST http://localhost:8000/api/check-rental \
  -H "Content-Type: application/json" \
  -d '{
    "mac_fingerprint": "abc123...",
    "product_id": "macr-pyqt"
  }'
```

---

#### GET `/api/products`
List all available products.

**Response:**
```json
[
  {
    "id": "uuid...",
    "slug": "macr-pyqt",
    "name": "Mac Retriever",
    "base_price_cents": 4999,
    "features": ["search", "export", "ai_classify", "cloud_sync"],
    "license_types": ["perpetual", "7day_trial", "30day_rental", "yearly_sub"]
  }
]
```

**cURL example:**
```bash
curl http://localhost:8000/api/products
```

---

#### GET `/api/products/{product_id}/features`
Get features for a product.

**Response:**
```json
{
  "product_id": "macr-pyqt",
  "features": [
    {
      "slug": "search",
      "name": "Email Search",
      "type": "core"
    },
    {
      "slug": "export",
      "name": "Export Emails",
      "type": "premium"
    }
  ]
}
```

**cURL example:**
```bash
curl http://localhost:8000/api/products/macr-pyqt/features
```

---

### Development Endpoints (Local Only)

#### POST `/api/generate-license`
Generate a test license for this Mac.

**Request:**
```json
{
  "product_id": "macr-pyqt",
  "license_type": "perpetual"
}
```

⚠️ **Note:** `mac_fingerprint` is auto-detected from this Mac

**Response:**
```json
{
  "license_key": "SW-1234-5678-9ABC-DEF0",
  "mac_serial_suffix": "ABC123",
  "product_id": "macr-pyqt",
  "license_type": "perpetual",
  "expires_at": null,
  "features": ["search", "export", "ai_classify", "cloud_sync"]
}
```

**cURL example:**
```bash
curl -X POST http://localhost:8000/api/generate-license \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "macr-pyqt",
    "license_type": "perpetual"
  }'
```

---

#### POST `/api/generate-rental`
Generate a test rental for this Mac.

**Request:**
```json
{
  "product_id": "macr-pyqt",
  "duration_days": 7
}
```

⚠️ **Note:** `mac_fingerprint` is auto-detected from this Mac

**Response:**
```json
{
  "rental_id": "uuid...",
  "product_id": "macr-pyqt",
  "expires_at": "2026-03-18T10:30:00",
  "days_remaining": 7,
  "features": ["search", "export", "ai_classify", "cloud_sync"]
}
```

**cURL example:**
```bash
curl -X POST http://localhost:8000/api/generate-rental \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "macr-pyqt",
    "duration_days": 7
  }'
```

---

#### GET `/api/debug/database`
Get database statistics (development only).

**Response:**
```json
{
  "db_path": "/Users/user/.silver_wizard/licensing_test.db",
  "products": 1,
  "features": 4,
  "license_types": 4,
  "licenses": 5,
  "validations": 12,
  "rentals": 2
}
```

**cURL example:**
```bash
curl http://localhost:8000/api/debug/database
```

---

## 🎯 PQTI API v1 (Bitmap + Signature)

The PQTI API provides feature bitmaps (128-bit, 32 hex chars) and HMAC-SHA256 signatures for offline license validation.

### POST `/api/v1/licenses/generate`
Generate a new PQTI license with feature bitmap.

**Headers:**
```
X-API-Key: dev-key-12345
```

**Request:**
```json
{
  "app": "pqti",
  "access_levels": {
    "0": 15,  // VIDEO_RECORDING: perpetual (0-15 = access level)
    "2": 4,   // MUTATION_TESTING: custom trial
    "4": 6    // SESSION_RECORDING: basic paid
  },
  "mac_fingerprint": "optional_fingerprint_for_single_user",
  "trial_durations": {
    "2": 30,  // days
    "4": 14
  }
}
```

**Response (200):**
```json
{
  "key_id": "LIC-2026-ABC123",
  "app": "pqti",
  "issued_at": "2026-03-12",
  "mac_fingerprint": "...",
  "features_hex": "F0123456789ABCDEF0123456789ABCD",
  "signature": "hmac_sha256_hex_here"
}
```

**Access Level Meanings:**
- 0 = No access
- 1-4 = Trial (days configurable)
- 5 = Free tier
- 6-9 = Paid tier
- 15 = Perpetual/Unlimited

**Feature Indices:**
- 0: VIDEO_RECORDING
- 1: OFFLINE_STORAGE
- 2: MUTATION_TESTING
- 3: REMOTE_EXECUTION
- 4: SESSION_RECORDING

**cURL example:**
```bash
curl -X POST http://localhost:8000/api/v1/licenses/generate \
  -H "X-API-Key: dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "app": "pqti",
    "access_levels": {
      "0": 15,
      "2": 4,
      "4": 6
    },
    "mac_fingerprint": "abc123...",
    "trial_durations": {"2": 30, "4": 14}
  }'
```

---

### POST `/api/v1/licenses/refresh`
Refresh/extend license (updates issued_at and regenerates signature).

**Headers:**
```
X-API-Key: dev-key-12345
```

**Request:**
```json
{
  "key_id": "LIC-2026-ABC123",
  "app": "pqti",
  "features_hex": "F0123456789ABCDEF0123456789ABCD"
}
```

**Response (200):** Same as generate (with new issued_at and signature)

**Use case:** Client calls server to extend trial duration or update features

---

### POST `/api/v1/licenses/purchase`
Initiate a feature purchase (payment pending).

**Headers:**
```
X-API-Key: dev-key-12345
```

**Request:**
```json
{
  "key_id": "LIC-2026-ABC123",
  "app": "pqti",
  "features_to_add": [1, 3],
  "duration": "1year"
}
```

**Response (200):**
```json
{
  "token": "purch-uuid",
  "status": "pending",
  "payment_url": "https://stripe.com/...",
  "amount_cents": 4999
}
```

---

### POST `/api/v1/licenses/revoke`
Revoke a license (disable it permanently).

**Headers:**
```
X-API-Key: dev-key-12345
```

**Request:**
```json
{
  "key_id": "LIC-2026-ABC123",
  "reason": "payment_failed"
}
```

**Response (200):**
```json
{
  "status": "revoked",
  "key_id": "LIC-2026-ABC123"
}
```

---

### GET `/api/v1/licenses/purchase/{token}`
Check purchase status and get updated license if paid.

**Headers:**
```
X-API-Key: dev-key-12345
```

**Response (200, if pending):**
```json
{
  "status": "pending",
  "token": "purch-uuid"
}
```

**Response (200, if paid):**
```json
{
  "status": "paid",
  "token": "purch-uuid",
  "license": {
    "key_id": "LIC-2026-ABC123",
    "app": "pqti",
    "issued_at": "2026-03-12",
    "mac_fingerprint": "...",
    "features_hex": "F0123456789ABCDEF0123456789ABCD",
    "signature": "hmac_sha256_hex"
  }
}
```

---

### 🔐 Offline License Validation (Client-Side)

PQTI clients validate licenses locally without calling the server:

```python
from license_signing import LicenseSigner
from feature_bitmap import FeatureBitmap

# Load license from storage
license_data = load_local_license()  # {"key_id": "...", "features_hex": "...", "signature": "..."}

# Verify signature (offline)
signer = LicenseSigner("shared-secret-key")
is_valid = signer.verify(license_data, license_data["signature"])

if is_valid:
    # Extract features
    features = FeatureBitmap.decode(license_data["features_hex"])

    # Check if feature is available
    if FeatureBitmap.has_feature(license_data["features_hex"], feature_idx=2):
        print("MUTATION_TESTING enabled!")
    else:
        print("Feature not available")
else:
    print("License signature invalid - revoked or tampered with")
```

**Feature Bitmap Format:**
- 128 bits total (32 hex characters)
- 4 bits per feature (indices 0-31)
- Each nibble (4 bits) = access level 0-15
- Example: `F0123456789ABCDEF0123456789ABCD` means:
  - Feature 0 (VIDEO_RECORDING): level 15 (perpetual)
  - Feature 1 (OFFLINE_STORAGE): level 0 (no access)
  - etc.

---

## 🧪 Testing Workflows

### Test 1: Generate and Validate a Perpetual License

```bash
# Get this Mac's fingerprint (needed for validation)
python3 -c "from mac_fingerprint_service import MacFingerprintService; s = MacFingerprintService(); print('Fingerprint:', s.get_mac_fingerprint())"

# Generate license
curl -X POST http://localhost:8000/api/generate-license \
  -H "Content-Type: application/json" \
  -d '{"product_id": "macr-pyqt", "license_type": "perpetual"}'

# Validate license (use fingerprint and license_key from above)
curl -X POST http://localhost:8000/api/validate-license \
  -H "Content-Type: application/json" \
  -d '{
    "mac_fingerprint": "YOUR_FINGERPRINT_HERE",
    "license_key": "SW-YOUR-KEY-HERE",
    "product_id": "macr-pyqt"
  }'
```

### Test 2: Generate Trial License

```bash
curl -X POST http://localhost:8000/api/generate-license \
  -H "Content-Type: application/json" \
  -d '{"product_id": "macr-pyqt", "license_type": "7day_trial"}'
```

### Test 3: Generate and Check Rental

```bash
# Generate 7-day rental
curl -X POST http://localhost:8000/api/generate-rental \
  -H "Content-Type: application/json" \
  -d '{"product_id": "macr-pyqt", "duration_days": 7}'

# Check rental status
curl -X POST http://localhost:8000/api/check-rental \
  -H "Content-Type: application/json" \
  -d '{"mac_fingerprint": "YOUR_FINGERPRINT_HERE", "product_id": "macr-pyqt"}'
```

---

## 🔍 Monitoring

### Check Database

```bash
# View database stats
curl http://localhost:8000/api/debug/database

# Direct SQLite inspection
sqlite3 ~/.silver_wizard/licensing_test.db

# List licenses created
sqlite3 ~/.silver_wizard/licensing_test.db "SELECT license_key, license_type, status, created_at FROM licenses ORDER BY created_at DESC LIMIT 10;"

# List rentals
sqlite3 ~/.silver_wizard/licensing_test.db "SELECT * FROM rentals ORDER BY created_at DESC LIMIT 5;"
```

### Monitor Server Logs

The server logs all activity. Watch for:
- License validations
- Rental checks
- Database operations
- Errors

```bash
# Server logs validation activity
# Look for: "License validation: ...", "Rental check: ...", etc.
```

---

## 🚀 Integration with MacR-PyQt

Once server is running locally, MacR-PyQt can call:

```python
import requests

# Check if license is valid
response = requests.post(
    "http://localhost:8000/api/validate-license",
    json={
        "mac_fingerprint": mac_service.get_mac_fingerprint(),
        "license_key": stored_license_key,
        "product_id": "macr-pyqt",
        "app_version": "0.9.0"
    }
)

if response.json()["valid"]:
    # License valid - enable all features
    enabled_features = response.json()["features"]
else:
    # License invalid or expired
    handle_invalid_license(response.json())
```

---

## 📊 Database Schema

```
Database: ~/.silver_wizard/licensing_test.db

Core Tables:
  - products (id, slug, name, base_price_cents)
  - features (id, product_id, slug, name, type)
  - license_types (id, product_id, slug, name, duration_days, price_cents)
  - license_type_features (license_type_id, feature_id)
  - licenses (id, user_id, product_id, license_type_id, license_key_hash, mac_fingerprint_hash, status)
  - rentals (id, user_id, product_id, mac_fingerprint_hash, rental_start, rental_end, status)
  - license_validations (id, license_id, mac_fingerprint_hash, validation_result)

See: LICENSING_WEBSITE_SCHEMA.md for full schema details
```

---

## ⚠️ Important Notes

1. **Local Testing Only**
   - This server is for development testing
   - Database is NOT encrypted (use `.silver_wizard/licensing_test.db`)
   - Test data includes working licenses for all types

2. **Mac Fingerprinting**
   - Uses `ioreg -l | grep IOPlatformSerialNumber`
   - Unique per Mac hardware
   - Cached for performance (clear with `service.clear_cache()`)

3. **License Key Format**
   - Format: `SW-XXXX-XXXX-XXXX-XXXX`
   - Based on MD5(serial + product_id + version + license_type)
   - Tied to Mac fingerprint

4. **Feature Access Control**
   - Features are determined by license_type
   - Example: perpetual includes all 4 features
   - Trial includes only "search" feature
   - Rental includes all 4 features (time-limited)

---

## 🔧 Troubleshooting

### Server won't start

```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill existing process
kill -9 <PID>

# Try again
python licensing_server_local.py
```

### Database errors

```bash
# Reset database
rm ~/.silver_wizard/licensing_test.db

# Server will recreate on next start
python licensing_server_local.py
```

### Can't import MacFingerprintService

```bash
# Make sure both files are in same directory
ls -la /Users/stevedeighton/Library/CloudStorage/Dropbox/A_Coding/SA/

# Should show:
# licensing_server_local.py
# mac_fingerprint_service.py
# test_licensing_server.py
```

### Test script shows "Cannot connect to server"

```bash
# Server must be running in separate terminal
# Terminal 1:
python licensing_server_local.py

# Terminal 2:
python test_licensing_server.py
```

---

## 🚢 Production Deployment

### Set Environment Variables

```bash
export LICENSING_ENV=production
export LICENSING_SECRET_KEY="your-32-char-secret-key-here"
export LICENSING_API_KEY="your-api-key-here"
export LICENSING_SERVER_HOST="0.0.0.0"
export LICENSING_DATABASE_URL="postgresql://user:pass@localhost/licensing"
```

### Start Server in Production

```bash
LICENSING_ENV=production python licensing_server_local.py
```

The server will:
- Use production configuration
- Listen on all interfaces (0.0.0.0)
- Use PostgreSQL instead of SQLite
- Require API key on all endpoints
- Log at WARNING level (not DEBUG)

---

## 📝 Next Steps

1. ✅ Run local server with test script
2. ✅ Validate license generation and validation work
3. ✅ Generate sample licenses for testing MacR-PyQt integration
4. ⏭️ Integrate with MacR-PyQt to use MacR API
5. ✅ PQTI endpoints ready for MacR-PyQt/PQTI integration
6. ⏭️ Integrate Stripe payment callback to mark purchases as paid
7. ⏭️ Deploy to production server when ready
8. ⏭️ Set up monitoring and audit log analysis

### PQTI Integration Checklist

- [ ] MacR-PyQt client loads license from local storage
- [ ] Client calls `/api/v1/licenses/generate` to get initial license
- [ ] Client verifies signature locally using `LicenseSigner`
- [ ] Client extracts features using `FeatureBitmap.decode()`
- [ ] Client enforces feature access based on bitmap
- [ ] Client calls `/api/v1/licenses/refresh` when trial about to expire
- [ ] Client calls `/api/v1/licenses/purchase` to request new features
- [ ] Stripe webhook calls `/api/v1/licenses/purchase/{token}` to apply paid features
- [ ] Client detects feature revocation and disables access

---

**Server ready for local development and production deployment!**
