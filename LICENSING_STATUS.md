# Licensing System Status

**Date:** 2026-03-11
**Status:** ✅ **Core functionality working, local testing ready**

---

## ✅ What Works

### 1. **Mac Fingerprinting Service** (`mac_fingerprint_service.py`)
- ✅ Extracts Mac hardware serial via `ioreg -l`
- ✅ Generates hardware-locked license keys (MD5 format: SW-XXXX-XXXX-XXXX-XXXX)
- ✅ Validates license keys on this Mac
- ✅ Implements caching for performance
- ✅ CLI interface for testing

**Test:**
```bash
python3 -c "from mac_fingerprint_service import MacFingerprintService; s = MacFingerprintService(); print('Serial:', s.get_hardware_serial()); print('Fingerprint:', s.get_mac_fingerprint())"
```

### 2. **Local Licensing Server** (`licensing_server_local.py`)
- ✅ FastAPI server running on `http://localhost:8000`
- ✅ SQLite database auto-initialized with schema
- ✅ CORS enabled for MacR-PyQt integration
- ✅ Auto-creates test data (MacR-PyQt product with 4 features, 4 license types)

**Core Endpoints Working:**
- `POST /api/validate-license` - Validate license key ✅
- `POST /api/check-rental` - Check rental status ✅
- `GET /api/products` - List products ✅
- `GET /api/debug/database` - Database stats ✅

**Example:**
```bash
# Start server
python3 licensing_server_local.py

# In another terminal, validate a license
curl -s "http://localhost:8000/api/validate-license?mac_fingerprint=ABC123&license_key=SW-1234-5678&product_id=macr-pyqt" | python3 -m json.tool
```

### 3. **Database Schema** (`LICENSING_WEBSITE_SCHEMA.md`)
- ✅ 9 tables designed and documented
- ✅ Supports multiple license types (perpetual, trial, rental, subscription)
- ✅ Feature-level access control
- ✅ Audit trail for validations
- ✅ Payment integration structure (ready for Stripe)

---

## ⏳ What Needs Work

### 1. **License Generation Endpoints** (Subprocess Hang)
- ❌ `POST /api/generate-license` - Times out
- ❌ `POST /api/generate-rental` - Times out

**Root Cause:** MacFingerprintService.get_mac_fingerprint() calls subprocess.run(ioreg) which hangs in async context.

**Fix Options:**
1. Run subprocess in thread pool executor
2. Cache fingerprint before async operations
3. Use sync endpoint instead of async

### 2. **Integration with PQTI Feature Framework**
- ⏳ Awaiting PQTI's feature-locking + licensing framework
- ⏳ Need to integrate with MacR-PyQt once delivered

### 3. **Production Deployment**
- ⏳ Deploy to web server (currently local-only)
- ⏳ Configure database (currently SQLite, can upgrade to PostgreSQL)
- ⏳ Add Stripe integration for payments
- ⏳ SSL/TLS certificate setup

---

## 📊 Current Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MacR-PyQt App                         │
│                                                           │
│  Calls /api/validate-license on startup                 │
│  Passes: mac_fingerprint, license_key, product_id       │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS
                     ▼
┌─────────────────────────────────────────────────────────┐
│         Licensing Server (FastAPI)                       │
│                                                           │
│  - validate-license ✅ (returns: valid, features, ...)   │
│  - check-rental ✅ (returns: days_remaining, ...)        │
│  - generate-license ❌ (hangs on subprocess)            │
│  - generate-rental ❌ (hangs on subprocess)             │
│  - debug/database ✅ (stats endpoint)                   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│         SQLite Database                                  │
│      ~/.silver_wizard/licensing_test.db                 │
│                                                           │
│  - products                                              │
│  - features                                              │
│  - license_types                                         │
│  - licenses                                              │
│  - license_validations                                   │
│  - rentals                                               │
│  - payments (ready for Stripe)                          │
└─────────────────────────────────────────────────────────┘
```

---

## 🔄 How It Works (Current Flow)

### License Validation Flow

```
1. MacR-PyQt gets stored license key and this Mac's fingerprint
   - Uses MacFingerprintService to get hardware serial
   - Hashes it with product_id to create fingerprint

2. Calls POST /api/validate-license with:
   {
     "mac_fingerprint": "fef623de1d23...",
     "license_key": "SW-12A6-9D8D-C421-D24B",
     "product_id": "macr-pyqt"
   }

3. Server:
   - Looks up license in database
   - Checks mac_fingerprint matches
   - Checks expiration (if applicable)
   - Returns features enabled for this license type

4. MacR-PyQt:
   - Shows "Licensed" badge
   - Enables features based on response
   - Prevents expired licenses
   - Logs validation for analytics
```

### Database Record Example

```
products:
  id: "macr-pyqt"
  name: "Mac Retriever"
  version: "0.9.0"

features:
  - slug: "search" (type: core)
  - slug: "export" (type: premium)
  - slug: "ai_classify" (type: premium)
  - slug: "cloud_sync" (type: premium)

license_types:
  - perpetual (NULL expiry, all 4 features)
  - 7day_trial (7 days, only "search")
  - 30day_rental (30 days, "search" + "export")
  - yearly_sub (365 days, all 4 features)

licenses:
  - license_key: "SW-12A6-9D8D-C421-D24B"
  - mac_fingerprint_hash: "fef623de1d23..."
  - license_type: "perpetual"
  - status: "active"
```

---

## 🎯 Quick Start

### 1. Run Server

```bash
cd /Users/stevedeighton/Library/CloudStorage/Dropbox/A_Coding/SA
python3 licensing_server_local.py
```

Expected output:
```
🔐 Silver Wizard Licensing Server (Local Development)
✓ Database initialized
✓ Starting server on http://127.0.0.1:8000
📖 Docs: http://localhost:8000/docs
```

### 2. Test Validation (Works ✅)

```bash
# Terminal 2
curl -s "http://localhost:8000/api/validate-license?mac_fingerprint=ABC123&license_key=SW-1234-5678&product_id=macr-pyqt"
```

### 3. Check Database

```bash
curl -s "http://localhost:8000/api/debug/database" | python3 -m json.tool
```

### 4. API Documentation

Visit http://localhost:8000/docs for interactive API docs (Swagger UI)

---

## 📝 Files Provided

| File | Purpose | Status |
|------|---------|--------|
| `mac_fingerprint_service.py` | Mac hardware fingerprinting | ✅ Complete & Tested |
| `licensing_server_local.py` | FastAPI server | ✅ Core endpoints work |
| `test_licensing_server.py` | Test suite | ✅ Tests core functionality |
| `LICENSING_WEBSITE_SCHEMA.md` | Database design | ✅ Complete design |
| `LICENSING_SERVER_GUIDE.md` | API documentation | ✅ Complete guide |
| `LICENSING_STATUS.md` | This file | ℹ️ Current status |

---

## 🚀 Next Steps

### Immediate (This Week)
1. **Fix async subprocess hang**
   - Option A: Use ThreadPoolExecutor for ioreg calls
   - Option B: Cache fingerprint before async operations
   - Priority: Medium (workaround: manually generate licenses for testing)

2. **Manual License Generation for Testing**
   ```bash
   python3 -c "
   from mac_fingerprint_service import MacFingerprintService
   s = MacFingerprintService()
   fp = s.get_mac_fingerprint()
   key = s.generate_license_key('macr-pyqt', '0.9.0', 'perpetual')
   print(f'Fingerprint: {fp}')
   print(f'License Key: {key}')
   "
   ```

3. **Test with MacR-PyQt**
   - Integrate validation endpoint into app startup
   - Store license key (encrypted with fingerprint)
   - Call server on app launch

### Short Term (1-2 weeks)
1. **Await PQTI Feature Framework**
   - PQTI implementing feature-locking + licensing
   - Will provide interface for unlocking features per license type

2. **Database Schema Production**
   - Migrate from SQLite to PostgreSQL (if needed)
   - Set up proper indexes and backups
   - Configure audit trail retention

3. **Stripe Integration**
   - Implement POST /api/payments endpoint
   - Process real credit cards
   - Track renewals and subscriptions

### Medium Term (2-4 weeks)
1. **Production Deployment**
   - Host on web server (Heroku, DigitalOcean, AWS)
   - SSL/TLS certificates (Let's Encrypt)
   - Monitoring and analytics

2. **MacR-PyQt Integration**
   - Full feature-locking per license type
   - Renewal reminders and notifications
   - License transfer/management UI

3. **Monetization Launch**
   - Pricing strategy finalized
   - Payment processing live
   - License keys distributed

---

## 💾 Database Location

```
~/.silver_wizard/licensing_test.db
```

To inspect:
```bash
sqlite3 ~/.silver_wizard/licensing_test.db "SELECT * FROM licenses LIMIT 5;"
```

---

## 🔐 Security Notes

- ✅ License keys are hashed before storage (SHA256)
- ✅ Mac fingerprints are hashed (SHA256)
- ✅ Passwords/sensitive data not stored (use Stripe for payments)
- ✅ SQLite not encrypted (for local development - use database encryption in production)
- ⏳ API authentication not yet implemented (add JWT/API keys for production)

---

## 📞 Contact Points

For integration:
- **MacR-PyQt:** Import `MacFingerprintService` and call `/api/validate-license`
- **PQTI:** Feature framework will integrate feature-locking
- **Brand Manager:** Can trigger license generation/renewal notifications

---

**Licensing system ready for local testing and integration!**

Next milestone: PQTI feature framework delivery → Full MacR-PyQt + licensing integration
