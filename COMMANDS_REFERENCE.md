# Licensing System - Commands Reference

Quick copy-paste reference for all common operations.

---

## 🚀 Server Operations

### Start Server
```bash
cd /Users/stevedeighton/Library/CloudStorage/Dropbox/A_Coding/SA
python3 licensing_server_local.py
```

### Stop Server
```bash
pkill -f "python3 licensing_server_local.py"
```

### Check If Running
```bash
lsof -i :8000
```

### View Server Logs
```bash
# If running in background:
tail -f /tmp/licensing_server.log

# Or check system logs:
curl http://localhost:8000/api/debug/database
```

---

## 🧪 Testing

### Run Full Test Suite
```bash
python3 test_licensing_server.py
```

### Test Individual Endpoint
```bash
# List products
curl http://localhost:8000/api/products

# Check API docs
open http://localhost:8000/docs
```

---

## 🔑 License Management

### Generate License (Python Script)
```python
from mac_fingerprint_service import MacFingerprintService

service = MacFingerprintService()

# Get serial
serial = service.get_hardware_serial()
print(f"Serial: {serial}")

# Get fingerprint
fp = service.get_mac_fingerprint()
print(f"Fingerprint: {fp}")

# Generate license key
key = service.generate_license_key('macr-pyqt', '0.9.0', 'perpetual')
print(f"License: {key}")
```

### Generate License (One-Liner)
```bash
python3 -c "from mac_fingerprint_service import MacFingerprintService; s = MacFingerprintService(); print(s.generate_license_key('macr-pyqt', '0.9.0', 'perpetual'))"
```

### Validate License
```bash
# Set variables
FP="your_fingerprint_here"
KEY="SW-XXXX-XXXX-XXXX-XXXX"

# Validate
curl "http://localhost:8000/api/validate-license?mac_fingerprint=$FP&license_key=$KEY&product_id=macr-pyqt"
```

### Check Rental
```bash
FP="your_fingerprint_here"

curl "http://localhost:8000/api/check-rental?mac_fingerprint=$FP&product_id=macr-pyqt"
```

---

## 💾 Database Operations

### View Database Stats
```bash
curl http://localhost:8000/api/debug/database
```

### List All Licenses
```bash
sqlite3 ~/.silver_wizard/licensing_test.db "SELECT license_key, license_type, status, created_at FROM licenses ORDER BY created_at DESC;"
```

### List All Rentals
```bash
sqlite3 ~/.silver_wizard/licensing_test.db "SELECT * FROM rentals ORDER BY created_at DESC LIMIT 10;"
```

### Count Validations
```bash
sqlite3 ~/.silver_wizard/licensing_test.db "SELECT COUNT(*) as validations FROM license_validations;"
```

### View Specific License
```bash
sqlite3 ~/.silver_wizard/licensing_test.db "SELECT * FROM licenses WHERE license_key_hash LIKE '%ABC%';"
```

### Delete Test Database (Reset)
```bash
rm ~/.silver_wizard/licensing_test.db
# Server will auto-recreate on next start
```

### Backup Database
```bash
cp ~/.silver_wizard/licensing_test.db ~/.silver_wizard/licensing_test.db.backup
```

---

## 🔍 Troubleshooting Commands

### Check Port Usage
```bash
lsof -i :8000
```

### Kill Process on Port
```bash
kill -9 $(lsof -t -i :8000)
```

### Reset Everything
```bash
# Kill server
pkill -f "python3 licensing_server_local.py"

# Delete database
rm ~/.silver_wizard/licensing_test.db

# Delete cache (if any)
rm -rf ~/.silver_wizard/cache/

# Restart server
python3 licensing_server_local.py
```

### View Mac Info
```bash
# Get Mac serial
ioreg -l | grep IOPlatformSerialNumber | awk '{print $4}' | tr -d '"'

# Get Mac model
system_profiler SPHardwareDataType | grep "Model Name"

# Full system info
system_profiler SPHardwareDataType
```

---

## 📝 API Quick Reference

### Validate License
```bash
POST /api/validate-license
?mac_fingerprint=<fingerprint>
&license_key=<key>
&product_id=macr-pyqt
&app_version=0.9.0
```

**Response:**
```json
{
  "valid": true,
  "license_type": "perpetual",
  "expires_at": null,
  "features": ["search", "export", "ai_classify", "cloud_sync"],
  "days_remaining": null
}
```

### Check Rental
```bash
POST /api/check-rental
?mac_fingerprint=<fingerprint>
&product_id=macr-pyqt
```

**Response:**
```json
{
  "is_rental": true,
  "days_remaining": 15,
  "expires_at": "2026-03-26T10:30:00"
}
```

### List Products
```bash
GET /api/products
```

### Get Features
```bash
GET /api/products/macr-pyqt/features
```

### Database Stats
```bash
GET /api/debug/database
```

---

## 🛠️ Development Commands

### Install Dependencies (if needed)
```bash
pip3 install fastapi uvicorn requests
```

### View All Requirements
```bash
python3 -c "
import fastapi, uvicorn, requests
print('FastAPI:', fastapi.__version__)
print('Uvicorn:', uvicorn.__version__)
print('Requests:', requests.__version__)
"
```

### Run Individual Module
```bash
# Test Mac fingerprinting
python3 mac_fingerprint_service.py serial
python3 mac_fingerprint_service.py fingerprint
python3 mac_fingerprint_service.py genkey macr-pyqt
```

### Run Server with Output
```bash
# Show all logs (don't use &)
python3 licensing_server_local.py
```

### Run Server in Background (macOS)
```bash
# Start
python3 licensing_server_local.py > /tmp/licensing.log 2>&1 &

# View logs
tail -f /tmp/licensing.log

# Stop
pkill -f "python3 licensing_server_local.py"
```

---

## 🎯 Integration Commands

### For MacR-PyQt - Get Fingerprint
```python
from mac_fingerprint_service import MacFingerprintService
service = MacFingerprintService()
fingerprint = service.get_mac_fingerprint()
print(fingerprint)
```

### For MacR-PyQt - Validate License
```python
import requests
response = requests.post(
    "http://localhost:8000/api/validate-license",
    params={
        "mac_fingerprint": fingerprint,
        "license_key": license_key,
        "product_id": "macr-pyqt"
    }
)
print(response.json())
```

### Generate Multiple Test Licenses
```bash
# Generate perpetual, trial, and rental licenses
python3 << 'EOF'
from mac_fingerprint_service import MacFingerprintService
s = MacFingerprintService()

for license_type in ['perpetual', '7day_trial', '30day_rental', 'yearly_sub']:
    key = s.generate_license_key('macr-pyqt', '0.9.0', license_type)
    print(f"{license_type:20} {key}")
EOF
```

---

## 📊 Monitoring Commands

### Monitor Validations in Real-Time
```bash
# Count validations every 5 seconds
while true; do
  COUNT=$(sqlite3 ~/.silver_wizard/licensing_test.db "SELECT COUNT(*) FROM license_validations;")
  echo "Validations: $COUNT"
  sleep 5
done
```

### Watch Database Size
```bash
while true; do
  SIZE=$(ls -lh ~/.silver_wizard/licensing_test.db | awk '{print $5}')
  LINES=$(sqlite3 ~/.silver_wizard/licensing_test.db "SELECT COUNT(*) FROM licenses;")
  echo "$(date): Size=$SIZE Licenses=$LINES"
  sleep 10
done
```

### Monitor Active Rentals
```bash
sqlite3 ~/.silver_wizard/licensing_test.db \
  "SELECT COUNT(*) as active_rentals FROM rentals WHERE status='active' AND rental_end > datetime('now');"
```

---

## 🔐 Security Commands

### Export Licenses (Backup)
```bash
sqlite3 ~/.silver_wizard/licensing_test.db \
  "SELECT license_key_hash, mac_fingerprint_hash, license_type FROM licenses;" \
  > licenses_backup.csv
```

### Check for Suspicious Activity
```bash
# Multiple validations from different IPs
sqlite3 ~/.silver_wizard/licensing_test.db \
  "SELECT license_id, COUNT(*) as attempts FROM license_validations GROUP BY license_id HAVING COUNT(*) > 10;"
```

### Revoke License
```bash
# Update database directly
sqlite3 ~/.silver_wizard/licensing_test.db \
  "UPDATE licenses SET status='revoked' WHERE license_key_hash='ABC123';"
```

---

## 📞 Quick Help

### Full API Documentation
```bash
open http://localhost:8000/docs
```

### Check Implementation Status
```bash
python3 test_licensing_server.py
```

### View System Status
```bash
curl http://localhost:8000/api/debug/database
```

---

**Bookmark this file for quick reference! Most common operations listed above.**
