#!/usr/bin/env python3
"""
License Signing and Verification (HMAC-SHA256)

Handles generation and verification of HMAC signatures for PQTI licenses.
Enables offline license validation on the client side.

Signature is computed over a canonical JSON representation of the license data,
ensuring deterministic results regardless of key ordering.
"""

import hmac
import hashlib
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class LicenseSigner:
    """Generate and verify HMAC-SHA256 signatures for licenses."""

    def __init__(self, secret_key: str):
        """
        Initialize signer with shared secret key.

        Args:
            secret_key: Shared secret for HMAC (must be 32+ chars in production)
        """
        if not secret_key:
            raise ValueError("secret_key cannot be empty")

        if len(secret_key) < 16:
            logger.warning(
                f"⚠️ Secret key is short ({len(secret_key)} chars). "
                "Minimum 32 characters recommended for production."
            )

        self.secret_key = secret_key
        logger.info(f"LicenseSigner initialized (key: {secret_key[:10]}...)")

    def _canonicalize(self, license_data: Dict[str, Any]) -> str:
        """
        Create canonical JSON representation of license data.

        This ensures deterministic signatures regardless of key order or formatting.
        Only includes specific fields that form the license contract:
            - key_id
            - app
            - issued_at
            - mac_fingerprint (if present)
            - features_hex

        Args:
            license_data: License dictionary

        Returns:
            str: Canonical JSON string
        """
        # Extract only signature-relevant fields, in consistent order
        canonical_dict = {
            "app": license_data.get("app"),
            "issued_at": license_data.get("issued_at"),
            "key_id": license_data.get("key_id"),
            "features_hex": license_data.get("features_hex"),
        }

        # Only include mac_fingerprint if present (for single-user licenses)
        if "mac_fingerprint" in license_data and license_data["mac_fingerprint"]:
            canonical_dict["mac_fingerprint"] = license_data["mac_fingerprint"]

        # Serialize to JSON with sorted keys (deterministic)
        return json.dumps(canonical_dict, sort_keys=True, separators=(',', ':'))

    def sign(self, license_data: Dict[str, Any]) -> str:
        """
        Generate HMAC-SHA256 signature for license.

        Args:
            license_data: License dictionary with:
                - key_id: License identifier
                - app: Application identifier
                - issued_at: Issue date (ISO format)
                - features_hex: Feature bitmap (32 hex chars)
                - mac_fingerprint: (optional) Hardware fingerprint

        Returns:
            str: Hex-encoded HMAC-SHA256 signature

        Raises:
            ValueError: If required fields missing
        """
        # Validate required fields
        required_fields = ["key_id", "app", "issued_at", "features_hex"]
        for field in required_fields:
            if field not in license_data or not license_data[field]:
                raise ValueError(f"Missing required field: {field}")

        # Create canonical form and sign
        canonical = self._canonicalize(license_data)

        signature = hmac.new(
            self.secret_key.encode(),
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()

        logger.debug(f"Signed license: {license_data['key_id']}")
        return signature

    def verify(self, license_data: Dict[str, Any], signature: str) -> bool:
        """
        Verify HMAC signature matches license data.

        Args:
            license_data: License dictionary (same format as sign())
            signature: Hex-encoded signature to verify

        Returns:
            bool: True if signature is valid, False otherwise
        """
        try:
            # Regenerate signature
            expected_signature = self.sign(license_data)

            # Constant-time comparison to prevent timing attacks
            is_valid = hmac.compare_digest(expected_signature, signature)

            if is_valid:
                logger.debug(f"Verified license: {license_data['key_id']}")
            else:
                logger.warning(f"Invalid signature for: {license_data['key_id']}")

            return is_valid

        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    @staticmethod
    def create_license_dict(
        key_id: str,
        app: str,
        issued_at: str,
        features_hex: str,
        mac_fingerprint: str = None
    ) -> Dict[str, Any]:
        """
        Create a license data dictionary for signing.

        Args:
            key_id: Unique license identifier (e.g., "LIC-2026-ABC123")
            app: Application identifier (e.g., "pqti", "macr")
            issued_at: Issue date in ISO format (e.g., "2026-03-12")
            features_hex: Feature bitmap (32 hex chars)
            mac_fingerprint: Optional hardware fingerprint for single-user license

        Returns:
            Dict: License data ready for signing
        """
        license_dict = {
            "key_id": key_id,
            "app": app,
            "issued_at": issued_at,
            "features_hex": features_hex,
        }

        if mac_fingerprint:
            license_dict["mac_fingerprint"] = mac_fingerprint

        return license_dict


if __name__ == "__main__":
    import json

    # Test signing and verification
    print("License Signing Test")
    print("=" * 60)

    signer = LicenseSigner("test-secret-key-32-characters-long")

    # Create test license
    license_data = {
        "key_id": "LIC-2026-ABC123",
        "app": "pqti",
        "issued_at": "2026-03-12",
        "features_hex": "F0123456789ABCDEF0123456789ABCD",
        "mac_fingerprint": "abc123def456...",
    }

    print("\nLicense data:")
    print(json.dumps(license_data, indent=2))

    # Sign
    signature = signer.sign(license_data)
    print(f"\nGenerated signature:")
    print(f"  {signature}")
    print(f"  Length: {len(signature)} hex chars")

    # Verify (should succeed)
    is_valid = signer.verify(license_data, signature)
    print(f"\nVerification (correct signature): {is_valid}")

    # Verify with corrupted data (should fail)
    corrupted = license_data.copy()
    corrupted["features_hex"] = "F0123456789ABCDEF0123456789ABCE"  # Changed last char
    is_valid = signer.verify(corrupted, signature)
    print(f"Verification (corrupted data): {is_valid}")

    # Verify with wrong signature (should fail)
    wrong_sig = "0" * 64
    is_valid = signer.verify(license_data, wrong_sig)
    print(f"Verification (wrong signature): {is_valid}")

    # Test different key ordering (should produce same signature)
    print("\n\nKey order independence test:")
    license_data_reordered = {
        "features_hex": license_data["features_hex"],
        "key_id": license_data["key_id"],
        "mac_fingerprint": license_data["mac_fingerprint"],
        "app": license_data["app"],
        "issued_at": license_data["issued_at"],
    }
    signature2 = signer.sign(license_data_reordered)
    print(f"  Signature 1: {signature}")
    print(f"  Signature 2: {signature2}")
    print(f"  Match: {signature == signature2}")
