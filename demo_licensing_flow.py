#!/usr/bin/env python3
"""
PQTI Licensing System - Demo Flow

This script demonstrates the complete user journey for the PQTI licensing system:
1. Generate a new license
2. Refresh with updated features
3. Initiate a feature purchase
4. Confirm payment (admin)
5. Check purchase status and get updated license
6. Revoke a license

Run this after starting the licensing server:
    python licensing_server_local.py  # Terminal 1
    python demo_licensing_flow.py      # Terminal 2
"""

import requests
import json
import time
from typing import Dict, Any

# ============================================================================
# CONFIG
# ============================================================================

SERVER_URL = "http://localhost:8000"
API_KEY = "test-api-key-12345"

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def print_section(title: str):
    """Print a section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def print_response(response: requests.Response, label: str = "Response"):
    """Pretty print API response."""
    print(f"\n{label}:")
    print(f"  Status: {response.status_code}")
    try:
        data = response.json()
        print(f"  Data: {json.dumps(data, indent=2)}")
        return data
    except:
        print(f"  Body: {response.text}")
        return None


def make_request(method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Make API request and return JSON response."""
    url = f"{SERVER_URL}{endpoint}"

    print(f"\n>>> {method} {endpoint}")
    if data:
        print(f"    Payload: {json.dumps(data, indent=2)}")

    try:
        if method == "GET":
            response = requests.get(url, headers=HEADERS)
        elif method == "POST":
            response = requests.post(url, headers=HEADERS, json=data)
        elif method == "PUT":
            response = requests.put(url, headers=HEADERS, json=data)
        else:
            raise ValueError(f"Unknown method: {method}")

        return print_response(response)
    except requests.exceptions.ConnectionError:
        print(f"\n❌ ERROR: Cannot connect to server at {SERVER_URL}")
        print(f"   Make sure the licensing server is running:")
        print(f"   python licensing_server_local.py")
        return None


# ============================================================================
# DEMO FLOW
# ============================================================================

def demo_complete_flow():
    """Demonstrate complete licensing flow."""

    print("\n" + "=" * 70)
    print("  🔐 PQTI Licensing System - Complete Demo Flow")
    print("=" * 70)
    print("\nThis demo shows the complete user journey:")
    print("  1️⃣  Generate a new license")
    print("  2️⃣  Refresh with updated features")
    print("  3️⃣  Initiate a feature purchase")
    print("  4️⃣  Confirm payment (admin)")
    print("  5️⃣  Check purchase status")
    print("  6️⃣  Verify features were applied")
    print("  7️⃣  Revoke the license")
    print("\n" + "=" * 70)

    # ========================================================================
    # Step 1: Generate License
    # ========================================================================
    print_section("Step 1️⃣  Generate a New License")

    license_data = {
        "app": "pqti",
        "features_to_enable": [0, 1, 2]  # Enable features 0, 1, 2
    }

    result = make_request("POST", "/api/v1/licenses/generate", license_data)
    if not result:
        return

    key_id = result.get("key_id")
    initial_signature = result.get("signature")
    initial_features = result.get("features_hex")

    print(f"\n✓ License generated successfully!")
    print(f"  Key ID: {key_id}")
    print(f"  Features: {initial_features}")
    print(f"  Signature: {initial_signature[:32]}...")

    # ========================================================================
    # Step 2: Refresh License (update features)
    # ========================================================================
    print_section("Step 2️⃣  Refresh License with New Features")

    refresh_data = {
        "key_id": key_id,
        "app": "pqti",
        "features_hex": initial_features  # Could add more features here
    }

    result = make_request("POST", "/api/v1/licenses/refresh", refresh_data)
    if not result:
        return

    print(f"\n✓ License refreshed successfully!")

    # ========================================================================
    # Step 3: Initiate Purchase
    # ========================================================================
    print_section("Step 3️⃣  Initiate Feature Purchase")

    purchase_data = {
        "key_id": key_id,
        "app": "pqti",
        "features_to_add": [3, 4],  # Add features 3 and 4
        "duration": "1year"
    }

    result = make_request("POST", "/api/v1/licenses/purchase", purchase_data)
    if not result:
        return

    purchase_token = result.get("token")
    amount_cents = result.get("amount_cents")

    print(f"\n✓ Purchase initiated!")
    print(f"  Purchase Token: {purchase_token}")
    print(f"  Amount: ${amount_cents / 100:.2f}")
    print(f"  Status: {result.get('status')}")
    print(f"  Payment URL (mock): {result.get('payment_url')}")

    # ========================================================================
    # Step 4: Check Payment Status (before confirmation)
    # ========================================================================
    print_section("Step 4️⃣  Check Purchase Status (Before Confirmation)")

    result = make_request("GET", f"/api/v1/licenses/purchase/{purchase_token}")
    if not result:
        return

    print(f"\n✓ Purchase status checked")
    print(f"  Status: {result.get('status')}")

    # ========================================================================
    # Step 5: Confirm Payment (Admin)
    # ========================================================================
    print_section("Step 5️⃣  Confirm Payment (Admin Endpoint)")

    print("\n🔐 Simulating Stripe webhook: Payment confirmed...")
    time.sleep(1)

    result = make_request("POST", f"/api/v1/test/confirm-payment/{purchase_token}")
    if not result:
        return

    print(f"\n✓ Payment confirmed!")
    print(f"  Status: {result.get('status')}")
    print(f"  Paid At: {result.get('paid_at')}")

    # ========================================================================
    # Step 6: Check Payment Status (after confirmation)
    # ========================================================================
    print_section("Step 6️⃣  Check Purchase Status (After Confirmation)")

    result = make_request("GET", f"/api/v1/licenses/purchase/{purchase_token}")
    if not result:
        return

    print(f"\n✓ Purchase completed!")
    print(f"  Status: {result.get('status')}")

    if result.get("license"):
        updated_license = result.get("license")
        print(f"\n  Updated License:")
        print(f"    Key ID: {updated_license.get('key_id')}")
        print(f"    Features: {updated_license.get('features_hex')}")
        print(f"    Signature: {updated_license.get('signature')[:32]}...")
        print(f"\n  ✓ Features 3 and 4 are now added to the license!")

    # ========================================================================
    # Step 7: Revoke License
    # ========================================================================
    print_section("Step 7️⃣  Revoke License")

    revoke_data = {
        "key_id": key_id,
        "reason": "demo_complete"
    }

    result = make_request("POST", "/api/v1/licenses/revoke", revoke_data)
    if not result:
        return

    print(f"\n✓ License revoked successfully!")
    print(f"  Status: {result.get('status')}")

    # ========================================================================
    # Summary
    # ========================================================================
    print_section("Demo Complete! ✓")

    print("Summary of the complete flow:")
    print(f"  ✓ Generated license: {key_id}")
    print(f"  ✓ Refreshed license with features")
    print(f"  ✓ Initiated purchase for ${ amount_cents / 100:.2f}")
    print(f"  ✓ Confirmed payment")
    print(f"  ✓ Applied new features to license")
    print(f"  ✓ Revoked license")

    print("\nKey Points:")
    print("  • Licenses use HMAC-SHA256 signatures for offline validation")
    print("  • Features are encoded in 128-bit hex strings")
    print("  • Purchases track payment state independently")
    print("  • Payment confirmation updates both DB and license signature")
    print("  • Licenses can be revoked at any time")

    print("\n" + "=" * 70)
    print("  Next: Integrate with MacR-PyQt for client-side validation")
    print("=" * 70 + "\n")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    demo_complete_flow()
