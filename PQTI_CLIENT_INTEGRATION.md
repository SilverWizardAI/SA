# PQTI Client Integration Guide

For MacR-PyQt and other applications using PQTI licensing.

---

## Overview

PQTI provides three components for your client:

1. **feature_bitmap.py** - Encode/decode feature access
2. **license_signing.py** - Verify license signatures
3. **licensing_server** - Get and refresh licenses

Your app needs to:
- Fetch license from server
- Store locally
- Validate offline
- Refresh when needed

---

## Integration Steps

### Step 1: Copy PQTI Modules to Your Project

```bash
# Copy these two files to your MacR-PyQt project
cp feature_bitmap.py ~/path/to/macr-pyqt/
cp license_signing.py ~/path/to/macr-pyqt/
```

No additional dependencies - both are pure Python!

### Step 2: Request License from Server

```python
import requests
from pathlib import Path

# Request initial license
def get_initial_license(app_id="pqti"):
    response = requests.post(
        "http://localhost:8000/api/v1/licenses/generate",
        headers={"X-API-Key": "your-api-key"},
        json={
            "app": app_id,
            "access_levels": {
                "0": 15,  # VIDEO_RECORDING: perpetual
                "2": 4,   # MUTATION_TESTING: 30-day trial
                "4": 6    # SESSION_RECORDING: paid
            },
            "mac_fingerprint": None,  # Optional: for single-user
            "trial_durations": {
                "2": 30,
                "4": 14
            }
        }
    )

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.json()}")
        return None
```

### Step 3: Store License Locally

```python
import json
from pathlib import Path

def save_license(license_data):
    license_dir = Path.home() / ".app_licenses"
    license_dir.mkdir(exist_ok=True)

    license_file = license_dir / f"{license_data['key_id']}.json"

    with open(license_file, 'w') as f:
        json.dump(license_data, f)

    print(f"✓ License saved: {license_file}")
    return license_file


def load_license(key_id):
    license_file = Path.home() / ".app_licenses" / f"{key_id}.json"

    if not license_file.exists():
        return None

    with open(license_file, 'r') as f:
        return json.load(f)
```

### Step 4: Validate License Signature (Offline)

```python
from license_signing import LicenseSigner

def validate_license_signature(license_data, secret_key):
    """
    Verify license signature without calling server.
    This confirms the license hasn't been tampered with.
    """
    signer = LicenseSigner(secret_key)

    # Extract fields needed for signature verification
    verify_dict = {
        "key_id": license_data["key_id"],
        "app": license_data["app"],
        "issued_at": license_data["issued_at"],
        "features_hex": license_data["features_hex"],
        "mac_fingerprint": license_data.get("mac_fingerprint")
    }

    signature = license_data["signature"]
    is_valid = signer.verify(verify_dict, signature)

    if is_valid:
        print("✓ License signature verified!")
        return True
    else:
        print("✗ License signature INVALID - revoked or tampered")
        return False
```

### Step 5: Check Feature Access

```python
from feature_bitmap import FeatureBitmap
from datetime import datetime, timedelta

class FeatureManager:
    def __init__(self, license_data):
        self.license_data = license_data
        self.features = FeatureBitmap.decode(license_data["features_hex"])
        self.issued_at = datetime.fromisoformat(license_data["issued_at"])

    def has_feature(self, feature_idx):
        """Check if feature is enabled."""
        return FeatureBitmap.has_feature(self.license_data["features_hex"], feature_idx)

    def get_trial_days_remaining(self, feature_idx, trial_duration_days):
        """Calculate remaining trial days."""
        if feature_idx not in self.features:
            return 0  # No access

        access_level = self.features[feature_idx]

        # Access level 1-4 = trial (configuration-dependent)
        if 1 <= access_level <= 4:
            trial_end = self.issued_at + timedelta(days=trial_duration_days)
            days_left = (trial_end - datetime.now()).days
            return max(0, days_left)

        return None  # Not a trial (perpetual or paid)

    def is_trial_expiring_soon(self, feature_idx, trial_days, warning_days=3):
        """Check if trial expires within N days."""
        days_left = self.get_trial_days_remaining(feature_idx, trial_days)
        if days_left is None:
            return False  # Not a trial
        return 0 <= days_left <= warning_days
```

### Step 6: Use Features in Your App

```python
# Feature indices (from PQTI spec)
FEATURE_VIDEO_RECORDING = 0
FEATURE_OFFLINE_STORAGE = 1
FEATURE_MUTATION_TESTING = 2
FEATURE_REMOTE_EXECUTION = 3
FEATURE_SESSION_RECORDING = 4

def startup_check():
    """Check licenses and enable/disable features."""
    # Load stored license
    license_data = load_license("LIC-2026-ABC123")

    if not license_data:
        print("No license found - trial mode")
        return enable_trial_features()

    # Verify signature
    if not validate_license_signature(license_data, SECRET_KEY):
        print("License invalid - disabling features")
        return disable_all_features()

    # Check features
    fm = FeatureManager(license_data)

    # VIDEO_RECORDING: perpetual or paid
    if fm.has_feature(FEATURE_VIDEO_RECORDING):
        enable_video_recording()

    # MUTATION_TESTING: trial-based
    if fm.has_feature(FEATURE_MUTATION_TESTING):
        days_left = fm.get_trial_days_remaining(FEATURE_MUTATION_TESTING, 30)

        if days_left is None:
            # Perpetual/paid
            enable_mutation_testing()
        elif days_left > 0:
            # Trial active
            enable_mutation_testing()

            if fm.is_trial_expiring_soon(FEATURE_MUTATION_TESTING, 30):
                show_upgrade_dialog(f"Trial expires in {days_left} days")
        else:
            # Trial expired
            disable_mutation_testing()
            show_upgrade_dialog("Trial expired - purchase to continue")

    # SESSION_RECORDING: premium feature
    if fm.has_feature(FEATURE_SESSION_RECORDING):
        enable_session_recording()
    else:
        disable_session_recording()

def enable_trial_features():
    """No license yet - enable basic features for trial."""
    enable_video_recording()
    disable_mutation_testing()
    disable_session_recording()
    show_trial_banner()

def disable_all_features():
    """License invalid - lockdown."""
    disable_video_recording()
    disable_mutation_testing()
    disable_session_recording()
    show_error("License invalid")
```

### Step 7: Refresh License When Needed

```python
def refresh_license(license_data):
    """
    Call server to refresh/extend license.
    Needed when:
    - Trial about to expire
    - User purchased new features
    - Update from cloud
    """
    response = requests.post(
        "http://localhost:8000/api/v1/licenses/refresh",
        headers={"X-API-Key": "your-api-key"},
        json={
            "key_id": license_data["key_id"],
            "app": license_data["app"],
            "features_hex": license_data["features_hex"]
        }
    )

    if response.status_code == 200:
        updated_license = response.json()
        save_license(updated_license)
        print("✓ License refreshed")
        return updated_license
    else:
        print("✗ Failed to refresh license")
        return None

def refresh_on_interval():
    """Periodically refresh license (e.g., weekly)."""
    import threading

    def refresh_worker():
        while True:
            try:
                license_data = load_license("LIC-2026-ABC123")
                if license_data:
                    refresh_license(license_data)
            except Exception as e:
                print(f"Refresh error: {e}")

            # Check weekly
            time.sleep(7 * 24 * 60 * 60)

    thread = threading.Thread(target=refresh_worker, daemon=True)
    thread.start()
```

### Step 8: Handle Feature Purchase

```python
def initiate_purchase(license_data, feature_indices_to_add):
    """
    User wants to purchase new features.
    Open browser to payment URL, then check status later.
    """
    response = requests.post(
        "http://localhost:8000/api/v1/licenses/purchase",
        headers={"X-API-Key": "your-api-key"},
        json={
            "key_id": license_data["key_id"],
            "app": license_data["app"],
            "features_to_add": feature_indices_to_add,
            "duration": "1year"
        }
    )

    if response.status_code == 200:
        purchase = response.json()

        # Open payment URL
        import webbrowser
        webbrowser.open(purchase["payment_url"])

        # Store purchase token for later
        save_purchase_token(purchase["token"])

        return purchase
    else:
        show_error("Failed to initiate purchase")
        return None

def check_purchase_status(token):
    """
    Poll server to check if payment completed.
    Run this periodically after user initiates purchase.
    """
    response = requests.get(
        f"http://localhost:8000/api/v1/licenses/purchase/{token}",
        headers={"X-API-Key": "your-api-key"}
    )

    if response.status_code == 200:
        status = response.json()

        if status["status"] == "paid":
            # Payment completed - load updated license
            updated_license = status["license"]
            save_license(updated_license)

            # Re-check features
            startup_check()
            show_success("Purchase complete! New features enabled.")

            return updated_license

        elif status["status"] == "pending":
            print("Payment still pending...")
            return None

    return None
```

---

## Best Practices

### License Storage
```python
# ✓ DO: Store in user's home directory with restrictive permissions
license_file = Path.home() / ".app_licenses" / f"{key_id}.json"
license_file.chmod(0o600)  # Only user can read

# ✗ DON'T: Store in project directory (user can easily edit)
# ✗ DON'T: Store in plaintext without validation
```

### Signature Validation
```python
# ✓ DO: Always validate signature before using license
if not validate_license_signature(license_data, SECRET_KEY):
    disable_features()  # Assume tampered

# ✗ DON'T: Skip validation
# ✗ DON'T: Trust license without verifying signature
```

### Trial Expiry
```python
# ✓ DO: Check trial expiry on every startup
days_left = fm.get_trial_days_remaining(feature_idx, trial_days)

# ✓ DO: Warn user before trial expires (3+ days warning)
if days_left < 3:
    show_upgrade_dialog()

# ✗ DON'T: Just check if feature exists (ignore expiry)
# ✗ DON'T: Trust issued_at without server confirmation
```

### Error Handling
```python
# ✓ DO: Graceful fallback if server unavailable
try:
    updated = refresh_license(license_data)
except requests.ConnectionError:
    print("Server unavailable - using cached license")
    # Continue with cached license

# ✗ DON'T: Lock user out if server is down
# ✗ DON'T: Assume offline = no license
```

---

## Testing Locally

### 1. Start the licensing server
```bash
python licensing_server_local.py
```

### 2. Get a test license
```bash
curl -X POST http://localhost:8000/api/v1/licenses/generate \
  -H "X-API-Key: dev-key-12345" \
  -H "Content-Type: application/json" \
  -d '{"app": "pqti", "access_levels": {"0": 15, "2": 4}}'
```

### 3. Use in your app
```python
license_data = {
    "key_id": "LIC-2026-ABC123",
    "app": "pqti",
    "issued_at": "2026-03-12",
    "features_hex": "F0123456789ABCDEF0123456789ABCD",
    "signature": "abc123...",
    "mac_fingerprint": None
}

# Validate offline
from license_signing import LicenseSigner
import licensing_config as config

signer = LicenseSigner(config.PQTI_SECRET_KEY)
assert signer.verify({...}, license_data["signature"])

# Check features
from feature_bitmap import FeatureBitmap
features = FeatureBitmap.decode(license_data["features_hex"])
print(features)
```

---

## Common Issues

### "No module named 'license_signing'"
Make sure both files are in the same directory as your code:
```bash
ls -la | grep feature_bitmap.py
ls -la | grep license_signing.py
```

### "License signature INVALID"
Check that:
1. You're using the correct SECRET_KEY
2. License data fields match exactly (key_id, app, issued_at, features_hex, mac_fingerprint)
3. Signature from server wasn't modified

### Trial doesn't expire
Check that:
1. You're using `get_trial_days_remaining()` with correct trial duration
2. Current datetime is correct on the machine
3. Signature validates (tampered licenses fail validation)

---

## Reference

**Feature Indices:**
- 0: VIDEO_RECORDING
- 1: OFFLINE_STORAGE
- 2: MUTATION_TESTING
- 3: REMOTE_EXECUTION
- 4: SESSION_RECORDING

**Access Levels:**
- 0: No access
- 1-4: Trial
- 5: Free
- 6-9: Paid
- 15: Perpetual

**Server Endpoints:**
- `POST /api/v1/licenses/generate` - Get new license
- `POST /api/v1/licenses/refresh` - Extend/update license
- `POST /api/v1/licenses/purchase` - Start payment flow
- `GET /api/v1/licenses/purchase/{token}` - Check payment status

---

**Happy licensing! 🚀**
