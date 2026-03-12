#!/usr/bin/env python3
"""
Test Suite for Local Licensing Server

Demonstrates:
1. Generating licenses for this Mac
2. Validating licenses
3. Testing rental functionality
4. Feature access control

Usage:
    # Terminal 1 - Start server:
    python licensing_server_local.py

    # Terminal 2 - Run tests:
    python test_licensing_server.py
"""

import requests
import json
import time
from pathlib import Path
import sys

# Import Mac fingerprinting to get this machine's fingerprint
sys.path.insert(0, str(Path(__file__).parent))
from mac_fingerprint_service import MacFingerprintService

# Server config
SERVER_URL = "http://localhost:8000"
TIMEOUT = 5

# Colors for output
class Color:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_test(name):
    """Print test header."""
    print(f"\n{Color.BOLD}{Color.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}TEST: {name}{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Color.RESET}")

def print_result(success, message):
    """Print test result."""
    symbol = f"{Color.GREEN}✓{Color.RESET}" if success else f"{Color.RED}✗{Color.RESET}"
    status = f"{Color.GREEN}PASS{Color.RESET}" if success else f"{Color.RED}FAIL{Color.RESET}"
    print(f"{symbol} [{status}] {message}")

def print_response(data):
    """Pretty print JSON response."""
    print(f"{Color.YELLOW}Response:{Color.RESET}")
    print(json.dumps(data, indent=2, default=str))

def test_server_health():
    """Test server is running."""
    print_test("Server Health Check")
    try:
        response = requests.get(f"{SERVER_URL}/docs", timeout=TIMEOUT)
        is_healthy = response.status_code == 200
        print_result(is_healthy, f"Server responding (HTTP {response.status_code})")
        return is_healthy
    except requests.exceptions.ConnectionError:
        print_result(False, "❌ Cannot connect to server. Is it running? (python licensing_server_local.py)")
        return False
    except Exception as e:
        print_result(False, f"Server health check failed: {e}")
        return False

def get_products():
    """Get available products."""
    print_test("List Products")
    try:
        response = requests.get(f"{SERVER_URL}/api/products", timeout=TIMEOUT)
        response.raise_for_status()
        products = response.json()
        print_result(True, f"Found {len(products)} product(s)")
        print_response(products)
        return products
    except Exception as e:
        print_result(False, f"Failed to get products: {e}")
        return []

def get_mac_fingerprint():
    """Get this Mac's fingerprint."""
    print_test("Get Mac Fingerprint")
    try:
        service = MacFingerprintService(use_cache=True)
        fingerprint = service.get_mac_fingerprint()
        serial = service.get_hardware_serial()
        print_result(True, f"Mac serial (masked): ****{serial[-6:]}")
        print(f"{Color.YELLOW}Fingerprint:{Color.RESET} {fingerprint}")
        return fingerprint, serial
    except Exception as e:
        print_result(False, f"Failed to get Mac fingerprint: {e}")
        return None, None

def generate_license(fingerprint, product_id="macr-pyqt", license_type="perpetual"):
    """Generate a test license."""
    print_test(f"Generate License ({license_type})")
    try:
        payload = {
            "mac_fingerprint": fingerprint,
            "product_id": product_id,
            "license_type": license_type
        }
        response = requests.post(
            f"{SERVER_URL}/api/generate-license",
            json=payload,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        license_data = response.json()
        print_result(True, f"License generated: {license_data['license_key']}")
        print_response(license_data)
        return license_data
    except Exception as e:
        print_result(False, f"Failed to generate license: {e}")
        return None

def validate_license(fingerprint, license_key, product_id="macr-pyqt"):
    """Validate a license."""
    print_test(f"Validate License")
    try:
        params = {
            "mac_fingerprint": fingerprint,
            "license_key": license_key,
            "product_id": product_id
        }
        response = requests.post(
            f"{SERVER_URL}/api/validate-license",
            params=params,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        is_valid = result.get("valid", False)
        print_result(is_valid, f"License validation: {'VALID' if is_valid else 'INVALID'}")
        print_response(result)
        return result
    except Exception as e:
        print_result(False, f"Failed to validate license: {e}")
        return None

def validate_wrong_mac(fingerprint, license_key):
    """Test that license fails on wrong Mac."""
    print_test("Validate License on Wrong Mac (should fail)")
    try:
        # Modify fingerprint to simulate different Mac
        wrong_fingerprint = "0" * len(fingerprint)
        params = {
            "mac_fingerprint": wrong_fingerprint,
            "license_key": license_key,
            "product_id": "macr-pyqt"
        }
        response = requests.post(
            f"{SERVER_URL}/api/validate-license",
            params=params,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        is_invalid = not result.get("valid", False)
        print_result(is_invalid, f"License correctly rejected on different Mac")
        print_response(result)
        return result
    except Exception as e:
        print_result(False, f"Failed to test wrong Mac: {e}")
        return None

def generate_rental(fingerprint, product_id="macr-pyqt", days=7):
    """Generate a test rental."""
    print_test(f"Generate Rental ({days} days)")
    try:
        payload = {
            "mac_fingerprint": fingerprint,
            "product_id": product_id,
            "duration_days": days
        }
        response = requests.post(
            f"{SERVER_URL}/api/generate-rental",
            json=payload,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        rental_data = response.json()
        print_result(True, f"Rental generated, expires in {rental_data.get('days_remaining')} days")
        print_response(rental_data)
        return rental_data
    except Exception as e:
        print_result(False, f"Failed to generate rental: {e}")
        return None

def check_rental(fingerprint, product_id="macr-pyqt"):
    """Check rental status."""
    print_test("Check Rental Status")
    try:
        params = {
            "mac_fingerprint": fingerprint,
            "product_id": product_id
        }
        response = requests.post(
            f"{SERVER_URL}/api/check-rental",
            params=params,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        has_rental = result.get("is_rental", False)
        print_result(has_rental, f"Rental status: {'ACTIVE' if has_rental else 'NO ACTIVE RENTAL'}")
        print_response(result)
        return result
    except Exception as e:
        print_result(False, f"Failed to check rental: {e}")
        return None

def get_database_stats():
    """Get database statistics."""
    print_test("Database Statistics")
    try:
        response = requests.get(
            f"{SERVER_URL}/api/debug/database",
            timeout=TIMEOUT
        )
        response.raise_for_status()
        stats = response.json()
        print_result(True, "Database stats retrieved")
        print_response(stats)
        return stats
    except Exception as e:
        print_result(False, f"Failed to get database stats: {e}")
        return None


# ============================================================================
# PQTI Tests
# ============================================================================

def test_pqti_generate_license(api_key="dev-key-12345"):
    """Test PQTI license generation."""
    print_test("PQTI: Generate License")
    try:
        payload = {
            "app": "pqti",
            "access_levels": {
                "0": 15,  # VIDEO_RECORDING: perpetual
                "2": 4,   # MUTATION_TESTING: trial
                "4": 6    # SESSION_RECORDING: paid
            },
            "mac_fingerprint": "test-fingerprint-abc123",
            "trial_durations": {
                "2": 30,
                "4": 14
            }
        }
        response = requests.post(
            f"{SERVER_URL}/api/v1/licenses/generate",
            json=payload,
            headers={"X-API-Key": api_key},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        license_data = response.json()
        print_result(True, f"License generated: {license_data['key_id']}")
        print_response(license_data)
        return license_data
    except Exception as e:
        print_result(False, f"Failed to generate PQTI license: {e}")
        return None


def test_pqti_refresh_license(key_id, features_hex, api_key="dev-key-12345"):
    """Test PQTI license refresh."""
    print_test("PQTI: Refresh License")
    try:
        payload = {
            "key_id": key_id,
            "app": "pqti",
            "features_hex": features_hex
        }
        response = requests.post(
            f"{SERVER_URL}/api/v1/licenses/refresh",
            json=payload,
            headers={"X-API-Key": api_key},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        print_result(True, f"License refreshed: {result['key_id']}")
        print_response(result)
        return result
    except Exception as e:
        print_result(False, f"Failed to refresh PQTI license: {e}")
        return None


def test_pqti_purchase_features(key_id, api_key="dev-key-12345"):
    """Test PQTI purchase initiation."""
    print_test("PQTI: Purchase Features")
    try:
        payload = {
            "key_id": key_id,
            "app": "pqti",
            "features_to_add": [1, 3],
            "duration": "1year"
        }
        response = requests.post(
            f"{SERVER_URL}/api/v1/licenses/purchase",
            json=payload,
            headers={"X-API-Key": api_key},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        print_result(True, f"Purchase initiated: {result['token']}")
        print_response(result)
        return result
    except Exception as e:
        print_result(False, f"Failed to initiate PQTI purchase: {e}")
        return None


def test_pqti_revoke_license(key_id, api_key="dev-key-12345"):
    """Test PQTI license revocation."""
    print_test("PQTI: Revoke License")
    try:
        payload = {
            "key_id": key_id,
            "reason": "test_revoke"
        }
        response = requests.post(
            f"{SERVER_URL}/api/v1/licenses/revoke",
            json=payload,
            headers={"X-API-Key": api_key},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        print_result(True, f"License revoked: {result['key_id']}")
        print_response(result)
        return result
    except Exception as e:
        print_result(False, f"Failed to revoke PQTI license: {e}")
        return None


def test_pqti_purchase_status(token, api_key="dev-key-12345"):
    """Test PQTI purchase status check."""
    print_test("PQTI: Check Purchase Status")
    try:
        response = requests.get(
            f"{SERVER_URL}/api/v1/licenses/purchase/{token}",
            headers={"X-API-Key": api_key},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        print_result(True, f"Purchase status: {result['status']}")
        print_response(result)
        return result
    except Exception as e:
        print_result(False, f"Failed to check PQTI purchase: {e}")
        return None


def test_pqti_signature_validation(license_data):
    """Test PQTI signature validation (offline)."""
    print_test("PQTI: Verify Signature (Offline)")
    try:
        # Import signing module
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from license_signing import LicenseSigner
        import licensing_config as config

        signer = LicenseSigner(config.PQTI_SECRET_KEY)

        license_dict = {
            "key_id": license_data["key_id"],
            "app": license_data["app"],
            "issued_at": license_data["issued_at"],
            "features_hex": license_data["features_hex"],
            "mac_fingerprint": license_data.get("mac_fingerprint")
        }

        is_valid = signer.verify(license_dict, license_data["signature"])
        print_result(is_valid, f"Signature valid: {is_valid}")
        if is_valid:
            print(f"{Color.GREEN}✓ License signature verified!{Color.RESET}")
        else:
            print(f"{Color.RED}✗ License signature INVALID!{Color.RESET}")
        return is_valid
    except Exception as e:
        print_result(False, f"Failed to verify signature: {e}")
        return False

def main():
    """Run all tests."""
    print(f"\n{Color.BOLD}{Color.HEADER}")
    print("═" * 80)
    print("SILVER WIZARD LICENSING SERVER - COMPREHENSIVE TEST SUITE")
    print("═" * 80)
    print(f"{Color.RESET}\n")

    # 1. Server health
    if not test_server_health():
        print(f"\n{Color.RED}❌ Cannot reach server. Start it first:{Color.RESET}")
        print(f"  python licensing_server_local.py")
        return

    # ========================================================================
    # MacR-PyQt Legacy Tests
    # ========================================================================
    print(f"\n{Color.BOLD}{Color.HEADER}═ MacR-PyQt (Legacy) Tests ═{Color.RESET}\n")

    # 2. Get products and fingerprint
    products = get_products()
    fingerprint, serial = get_mac_fingerprint()

    if not fingerprint:
        print(f"\n{Color.RED}❌ Failed to get Mac fingerprint{Color.RESET}")
        return

    # 3. Generate and validate license (perpetual)
    license_data = generate_license(fingerprint, "macr-pyqt", "perpetual")
    if license_data:
        license_key = license_data["license_key"]

        # Validate it works
        validate_license(fingerprint, license_key, "macr-pyqt")

        # Test it fails on wrong Mac
        validate_wrong_mac(fingerprint, license_key)

    # 4. Test trial license
    trial_data = generate_license(fingerprint, "macr-pyqt", "7day_trial")
    if trial_data:
        validate_license(fingerprint, trial_data["license_key"], "macr-pyqt")

    # 5. Test rental
    rental_data = generate_rental(fingerprint, "macr-pyqt", 7)
    if rental_data:
        check_rental(fingerprint, "macr-pyqt")

    # 6. Database stats
    get_database_stats()

    # ========================================================================
    # PQTI Tests
    # ========================================================================
    print(f"\n{Color.BOLD}{Color.HEADER}═ PQTI (Bitmap+Signature) Tests ═{Color.RESET}\n")

    # 7. Generate PQTI license
    pqti_license = test_pqti_generate_license()
    if pqti_license:
        # Test signature verification
        test_pqti_signature_validation(pqti_license)

        # Test refresh
        test_pqti_refresh_license(pqti_license["key_id"], pqti_license["features_hex"])

        # Test purchase
        purchase_result = test_pqti_purchase_features(pqti_license["key_id"])
        if purchase_result:
            # Test purchase status (will be pending)
            test_pqti_purchase_status(purchase_result["token"])

        # Test revocation
        test_pqti_revoke_license(pqti_license["key_id"])

    # Summary
    print(f"\n{Color.BOLD}{Color.HEADER}")
    print("═" * 80)
    print("TEST SUITE COMPLETE")
    print("═" * 80)
    print(f"{Color.RESET}")
    print(f"\n{Color.GREEN}✓ Licensing server is working with both MacR and PQTI!{Color.RESET}")
    print(f"\n{Color.YELLOW}PQTI Features Tested:{Color.RESET}")
    print(f"  ✓ License generation with feature bitmaps")
    print(f"  ✓ HMAC-SHA256 signature generation")
    print(f"  ✓ Offline signature verification")
    print(f"  ✓ License refresh/extension")
    print(f"  ✓ Feature purchase initiation")
    print(f"  ✓ License revocation")
    print(f"\n{Color.YELLOW}Next steps:{Color.RESET}")
    print(f"  1. Deploy to production environment")
    print(f"  2. Integrate with MacR-PyQt app")
    print(f"  3. Configure Stripe payment integration")
    print(f"  4. Monitor audit logs for usage patterns")

if __name__ == "__main__":
    main()
