# PQTI Licensing - Quick Start Guide

Get the PQTI licensing system running in 5 minutes!

---

## Step 1: Start the Server (Terminal 1)

```bash
cd /Users/stevedeighton/Library/CloudStorage/Dropbox/A_Coding/SA
python licensing_server_local.py
```

**Expected output:**
```
═══════════════════════════════════════════════════════
🔐 Silver Wizard Licensing Server (Local Development)
═══════════════════════════════════════════════════════
✓ Database initialized: /Users/.../licensing_test.db
✓ PQTI schema created
...
✓ Starting server on http://127.0.0.1:8000
✓ Fingerprint cache initialized: abc123...
```

---

## Step 2: Test the System (Terminal 2)

```bash
python test_licensing_server.py
```

This runs ~20 tests including:
- ✓ PQTI license generation
- ✓ Offline signature validation
- ✓ License refresh
- ✓ Feature purchase initiation
- ✓ License revocation

---

## Step 3: Try Manual API Calls

### 1. Generate a License

```bash
curl -X POST http://localhost:8000/api/v1/licenses/generate \
  -H "X-API-Key: dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "app": "pqti",
    "access_levels": {
      "0": 15,  # VIDEO_RECORDING: perpetual
      "2": 4,   # MUTATION_TESTING: trial
      "4": 6    # SESSION_RECORDING: paid
    },
    "mac_fingerprint": "test-device-abc123"
  }'
```

**Response:**
```json
{
  "key_id": "LIC-2026-XYZ789",
  "app": "pqti",
  "issued_at": "2026-03-12",
  "features_hex": "F0123456789ABCDEF0123456789ABCD",
  "signature": "abc123def456...",
  "mac_fingerprint": "test-device-abc123"
}
```

### 2. Verify the Signature (Offline Validation)

```python
from license_signing import LicenseSigner
import licensing_config as config

license_data = {
    "key_id": "LIC-2026-XYZ789",
    "app": "pqti",
    "issued_at": "2026-03-12",
    "features_hex": "F0123456789ABCDEF0123456789ABCD",
    "mac_fingerprint": "test-device-abc123"
}

signature = "abc123def456..."  # From response above

signer = LicenseSigner(config.PQTI_SECRET_KEY)
is_valid = signer.verify(license_data, signature)
print(f"✓ License signature valid: {is_valid}")
```

### 3. Decode Features from Bitmap

```python
from feature_bitmap import FeatureBitmap

features_hex = "F0123456789ABCDEF0123456789ABCD"
features = FeatureBitmap.decode(features_hex)

print(features)
# Output: {0: 15, 2: 4, 4: 6, ...}

# Check individual feature
has_video = FeatureBitmap.has_feature(features_hex, feature_idx=0)
print(f"✓ Has VIDEO_RECORDING: {has_video}")

# Get access level
level = FeatureBitmap.get_access_level(features_hex, 2)
print(f"✓ MUTATION_TESTING access level: {level}")
```

### 4. Refresh License

```bash
curl -X POST http://localhost:8000/api/v1/licenses/refresh \
  -H "X-API-Key: dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "key_id": "LIC-2026-XYZ789",
    "app": "pqti",
    "features_hex": "F0123456789ABCDEF0123456789ABCD"
  }'
```

### 5. Purchase New Features

```bash
curl -X POST http://localhost:8000/api/v1/licenses/purchase \
  -H "X-API-Key: dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "key_id": "LIC-2026-XYZ789",
    "app": "pqti",
    "features_to_add": [1, 3],
    "duration": "1year"
  }'
```

**Response:**
```json
{
  "token": "purch-12345678",
  "status": "pending",
  "payment_url": "http://localhost:8000/stripe/mock?token=purch-12345678",
  "amount_cents": 4999
}
```

### 6. Check Purchase Status

```bash
curl http://localhost:8000/api/v1/licenses/purchase/purch-12345678 \
  -H "X-API-Key: dev-key-12345"
```

**Response (while pending):**
```json
{
  "status": "pending",
  "token": "purch-12345678"
}
```

### 7. Revoke License

```bash
curl -X POST http://localhost:8000/api/v1/licenses/revoke \
  -H "X-API-Key: dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "key_id": "LIC-2026-XYZ789",
    "reason": "payment_failed"
  }'
```

---

## Understanding the Output

### Feature Bitmap (32 hex characters)

Each character = 4 bits = 1 feature's access level

Example: `F0123456789ABCDEF0123456789ABCD`

| Hex Char | Binary | Feature | Access Level |
|----------|--------|---------|--------------|
| F | 1111 | 0 (VIDEO_RECORDING) | 15 (perpetual) |
| 0 | 0000 | 1 (OFFLINE_STORAGE) | 0 (no access) |
| 1 | 0001 | 2 (MUTATION_TESTING) | 1 (7-day trial) |
| 2 | 0010 | 3 (REMOTE_EXECUTION) | 2 (14-day trial) |
| ... | ... | ... | ... |

### Access Levels

- **0** = No access
- **1-4** = Trial (1=7day, 2=14day, 3=30day, 4=custom)
- **5** = Free tier
- **6-9** = Paid variants (6=basic, 7=pro, 8=enterprise, 9=custom)
- **15** = Perpetual/Unlimited

### Feature Indices

- **0** = VIDEO_RECORDING
- **1** = OFFLINE_STORAGE
- **2** = MUTATION_TESTING
- **3** = REMOTE_EXECUTION
- **4** = SESSION_RECORDING
- **5-31** = Reserved for future use

---

## Key Concepts

### Offline Validation
✨ **No server call needed to check if feature is available!**

```python
# Client-side code (no network required)
signer = LicenseSigner(shared_secret)
is_valid = signer.verify(license, signature)

if is_valid:
    features = FeatureBitmap.decode(features_hex)
    if 2 in features:  # MUTATION_TESTING available
        enable_mutation_testing()
```

### Per-Feature Trials
Each feature can have its own trial duration:
- MUTATION_TESTING: 30-day trial
- SESSION_RECORDING: 14-day trial
- VIDEO_RECORDING: no trial (perpetual or paid)

Client tracks trial expiry locally and calls refresh when needed.

### Cloud Sync (Optional)
Client can call server to:
- Extend trial before expiry
- Unlock new features (after payment)
- Check if license is revoked

But if server unavailable, cached license still works!

---

## Troubleshooting

### "Cannot connect to server"
Make sure server is running in Terminal 1:
```bash
python licensing_server_local.py
```

### "X-API-Key missing" error
Add header to curl:
```bash
-H "X-API-Key: dev-key-12345"
```

### "Import error: license_signing not found"
Make sure all files are in same directory:
```bash
ls -la /Users/stevedeighton/Library/CloudStorage/Dropbox/A_Coding/SA/
```

Should see:
- `licensing_server_local.py`
- `feature_bitmap.py`
- `license_signing.py`
- `licensing_config.py`
- `mac_fingerprint_service.py`
- `test_licensing_server.py`

### Test script shows failures
Check server logs for errors. Common issues:
- Database locked (other process accessing it)
- Port 8000 already in use
- Import paths incorrect

---

## Production Deployment

To run in production with real security:

```bash
export LICENSING_ENV=production
export LICENSING_SECRET_KEY="your-32-char-random-secret-here"
export LICENSING_API_KEY="your-strong-api-key-here"
export LICENSING_DATABASE_URL="postgresql://user:pass@localhost/licensing"

python licensing_server_local.py
```

---

## Next Steps

1. **Run the test suite** to understand all features
2. **Try manual API calls** to get familiar with endpoints
3. **Integrate with MacR-PyQt** using the PQTI endpoints
4. **Deploy to production** when ready

---

## Full Documentation

See `LICENSING_SERVER_GUIDE.md` for:
- Complete API endpoint documentation
- Database schema details
- Integration examples
- Monitoring and maintenance

See `PQTI_IMPLEMENTATION_SUMMARY.md` for:
- Architecture overview
- Security features
- Deployment checklist
- Phase completion status

---

**Happy licensing! 🚀**
