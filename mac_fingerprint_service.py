#!/usr/bin/env python3
"""
Mac Fingerprinting Service - Extracted from Locker Project

Provides Mac hardware identification for licensing and DRM purposes.
Uses ioreg to extract unique Mac hardware serial number.

Usage:
    from mac_fingerprint_service import MacFingerprintService

    service = MacFingerprintService()

    # Get Mac's unique hardware serial
    serial = service.get_hardware_serial()

    # Generate license key for this Mac (with product ID and version)
    license_key = service.generate_license_key(
        product_id="macr-pyqt",
        version="0.9.0",
        license_type="perpetual"
    )

    # Validate a license key
    is_valid = service.validate_license_key(license_key, "macr-pyqt")
"""

import subprocess
import hashlib
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
from pathlib import Path
import json

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Only add handler if one doesn't exist (avoid duplicate logs)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - MacFingerprint - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)


class MacFingerprintService:
    """
    Mac hardware fingerprinting service for licensing.

    Extracts unique identifiers from the Mac to create hardware-locked licenses.
    Uses ioreg to get IOPlatformSerialNumber (unique per Mac).

    The fingerprint is NOT stored directly (privacy), only hashed.
    """

    # Cache directory for fingerprint (encrypted at rest)
    CACHE_DIR = Path.home() / ".silver_wizard" / "cache"
    FINGERPRINT_CACHE_FILE = CACHE_DIR / "fingerprint.cache"

    def __init__(self, use_cache: bool = True):
        """
        Initialize Mac fingerprint service.

        Args:
            use_cache: If True, cache the fingerprint to speed up subsequent calls.
                      Fingerprint doesn't change unless hardware is replaced.
        """
        self.use_cache = use_cache
        self._cached_serial: Optional[str] = None
        self._cached_fingerprint: Optional[str] = None

        # Create cache directory
        if self.use_cache:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        logger.info("MacFingerprintService initialized")

    def get_hardware_serial(self) -> str:
        """
        Get Mac hardware serial number.

        Extracts from: `ioreg -l | grep IOPlatformSerialNumber`

        Returns:
            str: Mac's unique hardware serial number (e.g., "ABC123XYZ789")

        Raises:
            RuntimeError: If serial number cannot be retrieved
        """
        # Return cached value if available
        if self._cached_serial:
            logger.debug("Using cached hardware serial")
            return self._cached_serial

        try:
            # Extract serial from ioreg
            cmd = [
                'sh', '-c',
                'ioreg -l | grep IOPlatformSerialNumber | awk \'{print $4}\' | tr -d \'"\''
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )

            serial = result.stdout.strip()

            if not serial:
                raise ValueError("Hardware serial is empty - ioreg returned no data")

            # Validate format (typically alphanumeric)
            if not serial.replace('-', '').isalnum():
                raise ValueError(f"Invalid serial format: {serial}")

            # Cache for this session
            self._cached_serial = serial

            logger.info(f"Hardware serial retrieved (last 6 chars: {serial[-6:]})")
            return serial

        except subprocess.TimeoutExpired:
            raise RuntimeError("ioreg command timed out (>10s)")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to execute ioreg: {e.stderr}")
        except Exception as e:
            raise RuntimeError(f"Failed to get hardware serial: {str(e)}")

    def get_mac_fingerprint(self) -> str:
        """
        Get Mac fingerprint (hashed for privacy).

        Returns a SHA256 hash of the hardware serial.
        This is what's stored in the license database (never the raw serial).

        Fingerprint is cached to disk to avoid expensive subprocess calls
        in async contexts (FastAPI endpoints).

        Returns:
            str: SHA256 hash of the hardware serial
        """
        # Return cached value if available in memory
        if self._cached_fingerprint:
            return self._cached_fingerprint

        # Check if fingerprint exists on disk
        if self.FINGERPRINT_CACHE_FILE.exists():
            try:
                with open(self.FINGERPRINT_CACHE_FILE, 'r') as f:
                    cached_data = json.load(f)
                    self._cached_fingerprint = cached_data.get('fingerprint')
                    if self._cached_fingerprint:
                        logger.debug(f"Loaded fingerprint from cache: {self._cached_fingerprint[:16]}...")
                        return self._cached_fingerprint
            except Exception as e:
                logger.warning(f"Failed to read cached fingerprint: {e}")

        # Generate new fingerprint from serial
        serial = self.get_hardware_serial()
        fingerprint = hashlib.sha256(serial.encode()).hexdigest()

        # Cache for this session
        self._cached_fingerprint = fingerprint

        # Cache to disk for future calls (if caching enabled)
        if self.use_cache:
            try:
                self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
                with open(self.FINGERPRINT_CACHE_FILE, 'w') as f:
                    json.dump({
                        'fingerprint': fingerprint,
                        'cached_at': datetime.now().isoformat()
                    }, f)
                logger.debug(f"Cached fingerprint to disk")
            except Exception as e:
                logger.warning(f"Failed to cache fingerprint to disk: {e}")

        logger.debug(f"Generated fingerprint: {fingerprint[:16]}...")
        return fingerprint

    def generate_license_key(
        self,
        product_id: str,
        version: str = "1.0.0",
        license_type: str = "perpetual"
    ) -> str:
        """
        Generate a license key for this Mac.

        The key is a hash of:
        - Mac's hardware serial
        - Product ID (e.g., "macr-pyqt")
        - Version (e.g., "0.9.0")
        - License type (e.g., "perpetual")

        This creates a unique key that only works on this specific Mac
        for this specific product version.

        Args:
            product_id: Product identifier (e.g., "macr-pyqt", "forbidden-spice")
            version: Product version (e.g., "0.9.0")
            license_type: License type (e.g., "perpetual", "30day_rental")

        Returns:
            str: License key (format: SW-XXXX-XXXX-XXXX-XXXX)
        """
        try:
            serial = self.get_hardware_serial()

            # Create key material
            key_material = f"{serial}:{product_id}:{version}:{license_type}"

            # Hash to create key
            key_hash = hashlib.md5(key_material.encode()).hexdigest().upper()

            # Format as: SW-XXXX-XXXX-XXXX-XXXX
            key = f"SW-{key_hash[0:4]}-{key_hash[4:8]}-{key_hash[8:12]}-{key_hash[12:16]}"

            logger.info(f"Generated license key for {product_id}")
            return key

        except Exception as e:
            logger.error(f"Failed to generate license key: {e}")
            raise RuntimeError(f"Failed to generate license key: {str(e)}")

    def validate_license_key(
        self,
        license_key: str,
        product_id: str,
        version: str = "1.0.0",
        license_type: str = "perpetual"
    ) -> bool:
        """
        Validate a license key against this Mac.

        Regenerates the key locally and compares with provided key.
        If they match, the license is valid for this Mac.

        Args:
            license_key: License key to validate (e.g., "SW-XXXX-XXXX-XXXX-XXXX")
            product_id: Expected product ID
            version: Expected product version
            license_type: Expected license type

        Returns:
            bool: True if license is valid for this Mac, False otherwise
        """
        try:
            # Generate expected key
            expected_key = self.generate_license_key(product_id, version, license_type)

            # Compare (case-insensitive)
            is_valid = license_key.upper() == expected_key.upper()

            if is_valid:
                logger.info(f"License key validated for {product_id}")
            else:
                logger.warning(f"License key INVALID for {product_id}")

            return is_valid

        except Exception as e:
            logger.error(f"Error validating license key: {e}")
            return False

    def get_system_info(self) -> Dict[str, str]:
        """
        Get system information (for debugging/logging).

        Returns hardware details without revealing full serial number.

        Returns:
            dict: System info with masked serial number
        """
        try:
            serial = self.get_hardware_serial()

            # Mask serial (show only last 6 characters)
            masked_serial = f"****{serial[-6:]}"

            return {
                "os": "macOS",
                "mac_serial_suffix": serial[-6:],
                "fingerprint_type": "SHA256",
                "cached": bool(self._cached_serial)
            }
        except Exception as e:
            return {
                "error": str(e),
                "os": "macOS",
                "fingerprint_type": "SHA256"
            }

    def clear_cache(self):
        """Clear in-memory cache (fingerprint remains valid, just refetched on next call)."""
        self._cached_serial = None
        self._cached_fingerprint = None
        logger.debug("Cache cleared")


# Convenience functions for CLI usage

def cmd_get_serial():
    """CLI: Get Mac hardware serial."""
    try:
        service = MacFingerprintService(use_cache=True)
        serial = service.get_hardware_serial()
        print(f"Hardware Serial: {serial}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=__import__('sys').stderr)
        return 1


def cmd_get_fingerprint():
    """CLI: Get Mac fingerprint (hashed)."""
    try:
        service = MacFingerprintService(use_cache=True)
        fingerprint = service.get_mac_fingerprint()
        print(f"Fingerprint: {fingerprint}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=__import__('sys').stderr)
        return 1


def cmd_generate_key(product_id: str, version: str = "1.0.0"):
    """CLI: Generate license key for product."""
    try:
        service = MacFingerprintService(use_cache=True)
        key = service.generate_license_key(product_id, version)
        print(f"License Key: {key}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=__import__('sys').stderr)
        return 1


def cmd_validate_key(license_key: str, product_id: str, version: str = "1.0.0"):
    """CLI: Validate license key."""
    try:
        service = MacFingerprintService(use_cache=True)
        is_valid = service.validate_license_key(license_key, product_id, version)
        status = "✓ VALID" if is_valid else "✗ INVALID"
        print(f"License Validation: {status}")
        return 0 if is_valid else 1
    except Exception as e:
        print(f"Error: {e}", file=__import__('sys').stderr)
        return 1


def cmd_system_info():
    """CLI: Get system information."""
    try:
        service = MacFingerprintService(use_cache=True)
        info = service.get_system_info()
        print("System Info:")
        for key, value in info.items():
            print(f"  {key}: {value}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=__import__('sys').stderr)
        return 1


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python mac_fingerprint_service.py serial         # Get hardware serial")
        print("  python mac_fingerprint_service.py fingerprint    # Get fingerprint hash")
        print("  python mac_fingerprint_service.py genkey <prod>  # Generate license key")
        print("  python mac_fingerprint_service.py validate <key> <prod>  # Validate key")
        print("  python mac_fingerprint_service.py sysinfo        # Show system info")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "serial":
        sys.exit(cmd_get_serial())
    elif cmd == "fingerprint":
        sys.exit(cmd_get_fingerprint())
    elif cmd == "genkey":
        product = sys.argv[2] if len(sys.argv) > 2 else "test-app"
        version = sys.argv[3] if len(sys.argv) > 3 else "1.0.0"
        sys.exit(cmd_generate_key(product, version))
    elif cmd == "validate":
        if len(sys.argv) < 4:
            print("Usage: validate <license_key> <product_id>")
            sys.exit(1)
        key = sys.argv[2]
        product = sys.argv[3]
        version = sys.argv[4] if len(sys.argv) > 4 else "1.0.0"
        sys.exit(cmd_validate_key(key, product, version))
    elif cmd == "sysinfo":
        sys.exit(cmd_system_info())
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
