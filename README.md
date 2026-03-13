# Silver Wizard Licensing System

**Complete IP protection licensing infrastructure for MacR-PyQt and other Silver Wizard products.**

---

## 📚 Documentation Guide

Start here based on what you need:

### **🎯 I want to get started in 30 seconds**
→ Read: [`QUICK_START.md`](QUICK_START.md)
- Start the server
- Generate test licenses
- Validate licenses
- Basic examples

### **🔧 I want to understand the API**
→ Read: [`LICENSING_SERVER_GUIDE.md`](LICENSING_SERVER_GUIDE.md)
- All endpoints documented
- Request/response examples
- curl commands
- Integration examples

### **📊 I want to see what's been built**
→ Read: [`DELIVERY_SUMMARY.md`](DELIVERY_SUMMARY.md)
- What was delivered
- Files and their purpose
- Testing checklist
- Next steps

### **🏗️ I want to understand the architecture**
→ Read: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- System overview diagrams
- Data flow visualization
- Database schema
- Production deployment architecture

### **📈 I want to check current status**
→ Read: [`LICENSING_STATUS.md`](LICENSING_STATUS.md)
- What works ✅
- What needs work ⏳
- Root causes and workarounds
- Immediate vs medium-term priorities

### **💾 I want to see the database design**
→ Read: [`LICENSING_WEBSITE_SCHEMA.md`](LICENSING_WEBSITE_SCHEMA.md)
- Complete 9-table schema
- Relationships and indexes
- Example data
- Migration path

---

## 🚀 Quick Start (5 minutes)

### 1. Start the Server
```bash
cd /Users/stevedeighton/Library/CloudStorage/Dropbox/A_Coding/SA
python3 licensing_server_local.py
```

### 2. Test It (in another terminal)
```bash
python3 test_licensing_server.py
```

### 3. Try the API
```bash
# Get products
curl http://localhost:8000/api/products

# View API docs
open http://localhost:8000/docs
```

---

## 📁 Files Overview

### **Code Files**
| File | Purpose | Size |
|------|---------|------|
| `mac_fingerprint_service.py` | Mac hardware identification & license key generation | 12KB |
| `licensing_server_local.py` | Local FastAPI licensing server | 21KB |
| `test_licensing_server.py` | Comprehensive test suite | 10KB |

### **Documentation Files**
| File | Purpose | Best For |
|------|---------|----------|
| `DELIVERY_SUMMARY.md` | What was delivered | Overview & status |
| `QUICK_START.md` | 30-second guide | Getting started |
| `LICENSING_SERVER_GUIDE.md` | Complete API reference | API integration |
| `ARCHITECTURE.md` | System design & diagrams | Understanding design |
| `LICENSING_STATUS.md` | Current status & next steps | Tracking progress |
| `LICENSING_WEBSITE_SCHEMA.md` | Database design | DB understanding |
| `README.md` | This file | Navigation |

---

## 🎯 Key Features

### ✅ **What Works**
- Mac fingerprinting via `ioreg` command
- License key generation & validation (MD5-based)
- Hardware-locked licensing (tied to Mac serial)
- License validation API (`/api/validate-license`)
- Rental checking API (`/api/check-rental`)
- SQLite database with 9-table schema
- Test suite with examples
- CORS enabled for cross-origin requests

### ⏳ **Pending**
- License generation endpoints (async subprocess fix needed)
- PQTI feature framework integration
- Stripe payment processing
- Production deployment

---

## 💡 How It Works

```
1. App gets Mac serial via ioreg
2. Hashes it to create fingerprint
3. Calls /api/validate-license with:
   - mac_fingerprint
   - license_key
   - product_id

4. Server returns:
   - valid: true/false
   - features: [list of enabled features]
   - license_type: perpetual/trial/rental/subscription
   - expires_at: date or null

5. App enables/disables features based on response
```

---

## 🔐 License Types Available

| Type | Duration | Features | Price | Use Case |
|------|----------|----------|-------|----------|
| **Perpetual** | Forever | All (4) | $49.99 | Permanent purchase |
| **Trial** | 7 days | Search only | Free | Freemium tier |
| **Rental** | 30 days | Search+Export | $9.99 | Short-term access |
| **Subscription** | 365 days | All (4) | $69.99/yr | Recurring revenue |

---

## 🎓 Features Included

**MacR-PyQt includes 4 features:**
1. **Search** - Email search (included in all licenses)
2. **Export** - Export emails to files (perpetual+rental+subscription)
3. **AI Classify** - AI email categorization (perpetual+subscription)
4. **Cloud Sync** - Cloud backup & sync (perpetual+subscription)

---

## 🔄 Integration Checklist

- [ ] Start licensing server (`python3 licensing_server_local.py`)
- [ ] Import `MacFingerprintService` in MacR-PyQt
- [ ] Call `/api/validate-license` on app startup
- [ ] Store license key (encrypted with fingerprint)
- [ ] Enable/disable features per response
- [ ] Show "Licensed" or "Trial" badge
- [ ] Await PQTI feature framework
- [ ] Integrate feature locking per license type

---

## 📞 Common Questions

**Q: How do I generate a license for testing?**
A: Use `MacFingerprintService` directly:
```python
from mac_fingerprint_service import MacFingerprintService
s = MacFingerprintService()
key = s.generate_license_key('macr-pyqt', '0.9.0', 'perpetual')
print(key)  # SW-XXXX-XXXX-XXXX-XXXX
```

**Q: How do I validate a license?**
A: Call the API endpoint:
```bash
curl "http://localhost:8000/api/validate-license?mac_fingerprint=ABC&license_key=SW-XXXX&product_id=macr-pyqt"
```

**Q: Can licenses be transferred to another Mac?**
A: No - they're hardware-locked to the Mac serial number. This prevents piracy.

**Q: How do I check database contents?**
A: Use the debug endpoint or SQLite directly:
```bash
curl http://localhost:8000/api/debug/database
# or
sqlite3 ~/.silver_wizard/licensing_test.db "SELECT * FROM licenses;"
```

**Q: What's the async subprocess issue?**
A: The `/api/generate-license` endpoint calls `ioreg` via subprocess in an async context, which hangs. Fix: use ThreadPoolExecutor or move to sync endpoint. Workaround: generate licenses directly in Python script.

---

## 🎯 Next Milestones

### This Week
- [ ] Verify licensing server works in your environment
- [ ] Test license validation endpoint
- [ ] Fix async subprocess issue (optional)

### Next 1-2 Weeks
- [ ] Await PQTI feature framework
- [ ] Begin MacR-PyQt integration
- [ ] Create feature-locking UI

### Following 2-4 Weeks
- [ ] Integrate Stripe payments
- [ ] Deploy to production
- [ ] Launch monetization

---

## 📊 Architecture Overview

```
MacR-PyQt App
    ↓ (calls /api/validate-license)
Licensing Server (FastAPI)
    ↓ (validates fingerprint + key)
SQLite Database
    ↓ (returns features array)
App enables/disables features
    ↓ (PQTI framework when ready)
Feature-level access control
```

---

## 💾 Database Location

All data stored in:
```
~/.silver_wizard/licensing_test.db
```

SQLite database with 9 tables:
- `products` - Apps being licensed
- `features` - Individual features
- `licenses` - Issued keys
- `rentals` - Time-limited access
- `payments` - Transaction history
- + 4 more tables (see LICENSING_WEBSITE_SCHEMA.md)

---

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| Server won't start | Check port 8000 not in use: `lsof -i :8000` |
| "Cannot import MacFingerprintService" | Ensure both .py files in same directory |
| API returns 422 (validation error) | Use query params, not JSON body |
| License validation times out | Server needs restart (check logs) |
| Generate-license endpoint hangs | Known issue - use direct Python generation |

---

## 📚 Additional Resources

- **[QUICK_START.md](QUICK_START.md)** - Get running in 30 seconds
- **[LICENSING_SERVER_GUIDE.md](LICENSING_SERVER_GUIDE.md)** - Complete API reference
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design & diagrams
- **[LICENSING_STATUS.md](LICENSING_STATUS.md)** - What works, what needs work
- **[LICENSING_WEBSITE_SCHEMA.md](LICENSING_WEBSITE_SCHEMA.md)** - Database design

---

## 🚀 Ready to Use!

The licensing system is **ready for local testing and integration**.

**Start here:** [`QUICK_START.md`](QUICK_START.md)

**Questions?** Check the relevant documentation file above.

---

**Last Updated:** March 11, 2026
**Status:** ✅ Core System Complete & Tested
**Next Milestone:** PQTI Feature Framework Integration
