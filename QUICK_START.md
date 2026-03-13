# Licensing System - Quick Start

## 30-Second Setup

```bash
# Terminal 1: Start server
cd /Users/stevedeighton/Library/CloudStorage/Dropbox/A_Coding/SA
python3 licensing_server_local.py

# Terminal 2: Test it
curl "http://localhost:8000/api/products"
```

---

## Generate a Test License

```bash
# Get your Mac's fingerprint
FP=$(python3 << 'EOF'
from mac_fingerprint_service import MacFingerprintService
s = MacFingerprintService()
print(s.get_mac_fingerprint())
EOF
)

# Generate license key
KEY=$(python3 << 'EOF'
from mac_fingerprint_service import MacFingerprintService
s = MacFingerprintService()
print(s.generate_license_key('macr-pyqt', '0.9.0', 'perpetual'))
EOF
)

echo "Fingerprint: $FP"
echo "License Key: $KEY"
```

---

## Validate a License

```bash
curl "http://localhost:8000/api/validate-license?mac_fingerprint=YOUR_FP&license_key=YOUR_KEY&product_id=macr-pyqt"
```

**Response (valid):**
```json
{
  "valid": true,
  "license_type": "perpetual",
  "expires_at": null,
  "features": ["search", "export", "ai_classify", "cloud_sync"]
}
```

---

## Check Rental Status

```bash
curl "http://localhost:8000/api/check-rental?mac_fingerprint=YOUR_FP&product_id=macr-pyqt"
```

---

## In MacR-PyQt Code

```python
import requests
from mac_fingerprint_service import MacFingerprintService

def validate_app_license():
    """Check if app is licensed on this Mac."""
    service = MacFingerprintService()
    fingerprint = service.get_mac_fingerprint()

    # Get stored license key (from preferences/keychain)
    license_key = get_stored_license_key()

    # Validate
    response = requests.post(
        "http://localhost:8000/api/validate-license",
        params={
            "mac_fingerprint": fingerprint,
            "license_key": license_key,
            "product_id": "macr-pyqt"
        },
        timeout=5
    )

    if response.status_code == 200:
        data = response.json()
        if data["valid"]:
            # Licensed - enable all features
            ENABLED_FEATURES = data["features"]
            show_license_badge("Licensed")
            return True

    # Not licensed or error - show trial mode
    ENABLED_FEATURES = ["search"]  # Trial features only
    show_license_badge("Trial Mode")
    return False

def is_feature_enabled(feature_name):
    """Check if feature is enabled for this license."""
    return feature_name in ENABLED_FEATURES
```

---

## Trial vs Perpetual vs Rental

**4 License Types Available:**

| Type | Duration | Features | Price |
|------|----------|----------|-------|
| `perpetual` | Never expires | All 4 | $49.99 |
| `7day_trial` | 7 days | Search only | Free |
| `30day_rental` | 30 days | Search, Export | $9.99 |
| `yearly_sub` | 365 days | All 4 | $69.99 |

---

## Database Check

```bash
# Show database stats
curl "http://localhost:8000/api/debug/database"

# Direct SQLite
sqlite3 ~/.silver_wizard/licensing_test.db "SELECT license_key, license_type, status FROM licenses;"
```

---

## API Reference

| Endpoint | Method | Params | Status |
|----------|--------|--------|--------|
| `/api/validate-license` | POST | `mac_fingerprint`, `license_key`, `product_id` | ✅ Works |
| `/api/check-rental` | POST | `mac_fingerprint`, `product_id` | ✅ Works |
| `/api/products` | GET | - | ✅ Works |
| `/api/products/{id}/features` | GET | - | ✅ Works |
| `/api/generate-license` | POST | `product_id`, `license_type` | ❌ Hangs |
| `/api/generate-rental` | POST | `product_id`, `duration_days` | ❌ Hangs |
| `/api/debug/database` | GET | - | ✅ Works |

---

## Troubleshooting

**Server won't start?**
```bash
lsof -i :8000  # Check if port is in use
kill -9 <PID>  # Kill existing process
```

**Can't import MacFingerprintService?**
```bash
# Make sure both files are in SA folder
ls -la /Users/stevedeighton/Library/CloudStorage/Dropbox/A_Coding/SA/
# Should have:
#   - mac_fingerprint_service.py
#   - licensing_server_local.py
```

**Validation returns "not_found"?**
- License key doesn't exist in database
- Product doesn't exist (only `macr-pyqt` created by default)
- Database hasn't been initialized yet

---

## Docs & Files

- **Full Schema:** `LICENSING_WEBSITE_SCHEMA.md`
- **API Guide:** `LICENSING_SERVER_GUIDE.md`
- **Status Report:** `LICENSING_STATUS.md`
- **Test Suite:** `test_licensing_server.py`

---

**Ready to integrate! Start with `/api/validate-license`**
