#!/usr/bin/env python3
"""
Feature Bitmap Encoding for PQTI Licenses

Encodes features as a 128-bit bitmap (32 hex characters).
Each feature gets 4 bits (one nibble), supporting access levels 0-15.

Access Level Meanings:
    0     = No access
    1-4   = Trial (1=7day, 2=14day, 3=30day, 4=custom)
    5     = Free tier
    6-9   = Paid tier (6=basic, 7=pro, 8=enterprise, 9=custom)
    10-14 = Reserved for future use
    15    = Perpetual/Unlimited

Feature Indices (0-31):
    0  = VIDEO_RECORDING
    1  = OFFLINE_STORAGE
    2  = MUTATION_TESTING
    3  = REMOTE_EXECUTION
    4  = SESSION_RECORDING
    5-31 = Reserved for future features
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class FeatureBitmap:
    """Feature bitmap encoding/decoding for PQTI licenses."""

    # Feature index definitions
    FEATURES = {
        0: "VIDEO_RECORDING",
        1: "OFFLINE_STORAGE",
        2: "MUTATION_TESTING",
        3: "REMOTE_EXECUTION",
        4: "SESSION_RECORDING",
    }

    # Reverse mapping
    FEATURE_NAMES = {v: k for k, v in FEATURES.items()}

    # Access level meanings (for documentation)
    ACCESS_LEVELS = {
        0: "No access",
        1: "7-day trial",
        2: "14-day trial",
        3: "30-day trial",
        4: "Custom trial",
        5: "Free tier",
        6: "Basic paid",
        7: "Pro paid",
        8: "Enterprise paid",
        9: "Custom paid",
        15: "Perpetual/Unlimited",
    }

    @staticmethod
    def encode(access_levels: Dict[int, int]) -> str:
        """
        Encode feature access levels to 32-character hex string.

        Args:
            access_levels: Dict mapping feature_idx (0-31) to access_level (0-15)
                          Example: {0: 15, 2: 4, 4: 6}

        Returns:
            str: 32-character hex string representing 128-bit bitmap

        Raises:
            ValueError: If feature_idx or access_level out of range
        """
        # Start with zeros (all features disabled)
        bits = [0] * 32

        for feature_idx, access_level in access_levels.items():
            if not isinstance(feature_idx, int) or feature_idx < 0 or feature_idx > 31:
                raise ValueError(f"Invalid feature_idx: {feature_idx} (must be 0-31)")

            if not isinstance(access_level, int) or access_level < 0 or access_level > 15:
                raise ValueError(f"Invalid access_level: {access_level} (must be 0-15)")

            bits[feature_idx] = access_level

        # Convert to hex string: bits[0] is high nibble, bits[1] is low nibble, etc.
        # Result is 32 hex chars (each char = 4 bits = 1 feature)
        hex_str = ""
        for i in range(0, 32, 2):
            high = bits[i]
            low = bits[i + 1] if i + 1 < 32 else 0
            # Each pair of nibbles becomes one byte, formatted as two hex chars
            byte_val = (high << 4) | low
            hex_str += f"{byte_val:02x}"

        return hex_str.upper()

    @staticmethod
    def decode(features_hex: str) -> Dict[int, int]:
        """
        Decode 32-character hex string to feature access levels.

        Args:
            features_hex: 32-character hex string from encode()

        Returns:
            Dict mapping feature_idx to access_level

        Raises:
            ValueError: If hex string is invalid format
        """
        if not isinstance(features_hex, str):
            raise ValueError("features_hex must be a string")

        features_hex = features_hex.upper()

        if len(features_hex) != 32:
            raise ValueError(f"features_hex must be exactly 32 characters, got {len(features_hex)}")

        try:
            # Convert hex to bytes
            bytes_val = bytes.fromhex(features_hex)
        except ValueError as e:
            raise ValueError(f"Invalid hex string: {e}")

        # Extract nibbles back to feature indices
        access_levels = {}
        for i, byte_val in enumerate(bytes_val):
            high = (byte_val >> 4) & 0xF
            low = byte_val & 0xF

            feature_idx = i * 2
            if high > 0:
                access_levels[feature_idx] = high

            feature_idx = i * 2 + 1
            if low > 0:
                access_levels[feature_idx] = low

        return access_levels

    @staticmethod
    def has_feature(features_hex: str, feature_idx: int) -> bool:
        """
        Quick check: does license have a feature enabled?

        Args:
            features_hex: Feature bitmap hex string
            feature_idx: Feature index to check (0-31)

        Returns:
            bool: True if feature is enabled (access_level > 0)
        """
        decoded = FeatureBitmap.decode(features_hex)
        return feature_idx in decoded and decoded[feature_idx] > 0

    @staticmethod
    def get_access_level(features_hex: str, feature_idx: int) -> int:
        """
        Get access level for a specific feature.

        Args:
            features_hex: Feature bitmap hex string
            feature_idx: Feature index (0-31)

        Returns:
            int: Access level (0-15), where 0 = no access
        """
        decoded = FeatureBitmap.decode(features_hex)
        return decoded.get(feature_idx, 0)

    @staticmethod
    def merge(features_hex1: str, features_hex2: str) -> str:
        """
        Merge two feature bitmaps (union of features, max access level).

        Args:
            features_hex1: First bitmap
            features_hex2: Second bitmap

        Returns:
            str: Merged bitmap (features_hex1 OR features_hex2)
        """
        decoded1 = FeatureBitmap.decode(features_hex1)
        decoded2 = FeatureBitmap.decode(features_hex2)

        # Merge: take maximum access level for each feature
        merged = {}
        for feature_idx in set(list(decoded1.keys()) + list(decoded2.keys())):
            merged[feature_idx] = max(
                decoded1.get(feature_idx, 0),
                decoded2.get(feature_idx, 0)
            )

        # Remove zero entries
        merged = {k: v for k, v in merged.items() if v > 0}

        return FeatureBitmap.encode(merged)

    @staticmethod
    def describe(features_hex: str) -> str:
        """
        Human-readable description of feature bitmap.

        Args:
            features_hex: Feature bitmap hex string

        Returns:
            str: Formatted description
        """
        decoded = FeatureBitmap.decode(features_hex)

        if not decoded:
            return "No features enabled"

        lines = []
        for feature_idx in sorted(decoded.keys()):
            access_level = decoded[feature_idx]
            feature_name = FeatureBitmap.FEATURES.get(feature_idx, f"UNKNOWN({feature_idx})")
            access_desc = FeatureBitmap.ACCESS_LEVELS.get(access_level, f"Level {access_level}")
            lines.append(f"  [{feature_idx}] {feature_name:20} = {access_desc}")

        return "Features:\n" + "\n".join(lines)


if __name__ == "__main__":
    import json

    # Test encoding/decoding
    print("Feature Bitmap Test")
    print("=" * 60)

    # Encode some features
    test_features = {
        0: 15,  # VIDEO_RECORDING: perpetual
        2: 4,   # MUTATION_TESTING: custom trial
        4: 6,   # SESSION_RECORDING: basic paid
    }

    print("\nInput features:")
    for feature_idx, access_level in sorted(test_features.items()):
        feature_name = FeatureBitmap.FEATURES.get(feature_idx, f"UNKNOWN({feature_idx})")
        access_desc = FeatureBitmap.ACCESS_LEVELS.get(access_level, f"Level {access_level}")
        print(f"  {feature_name:20} = {access_desc}")

    hex_str = FeatureBitmap.encode(test_features)
    print(f"\nEncoded: {hex_str}")
    print(f"Hex length: {len(hex_str)} chars (128 bits)")

    decoded = FeatureBitmap.decode(hex_str)
    print(f"\nDecoded: {json.dumps(decoded)}")

    print(f"\nHuman-readable:\n{FeatureBitmap.describe(hex_str)}")

    # Test feature check
    print("\nFeature checks:")
    for idx in range(5):
        has_it = FeatureBitmap.has_feature(hex_str, idx)
        level = FeatureBitmap.get_access_level(hex_str, idx)
        print(f"  Feature {idx}: has={has_it}, level={level}")

    # Test merge
    print("\n\nMerge test:")
    hex2 = FeatureBitmap.encode({1: 5, 2: 8, 3: 2})
    print(f"License 1: {hex_str}")
    print(f"License 2: {hex2}")
    merged = FeatureBitmap.merge(hex_str, hex2)
    print(f"Merged:    {merged}")
    print(f"\nMerged features:\n{FeatureBitmap.describe(merged)}")
