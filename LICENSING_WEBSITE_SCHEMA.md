# Licensing Website Database Schema

**Status:** Design Phase (Pre-staging for PQTI integration)
**Database:** PostgreSQL (or SQLite for testing in Locker container)
**Purpose:** License generation, validation, rental management, feature access control

---

## Overview

The licensing system manages:
1. **Users** - Who buys licenses
2. **Products** - Apps/tools being licensed (MacR-PyQt, etc.)
3. **Licenses** - Individual license keys, types, expiration
4. **Features** - What features each product has
5. **License Features** - Which features unlock for each license type
6. **Rentals** - Time-limited access sessions
7. **Payments** - Transaction history with Stripe

---

## Core Tables

### 1. `users`
Customers who purchase licenses.

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  display_name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  -- Stripe integration
  stripe_customer_id VARCHAR(255) UNIQUE,

  -- Contact
  phone VARCHAR(20),
  address_line1 VARCHAR(255),
  address_line2 VARCHAR(255),
  city VARCHAR(100),
  state VARCHAR(50),
  zip_code VARCHAR(20),
  country VARCHAR(100),

  -- Account status
  status ENUM('active', 'inactive', 'suspended') DEFAULT 'active',

  -- Preferences
  newsletter_opt_in BOOLEAN DEFAULT FALSE,

  INDEX idx_email (email),
  INDEX idx_stripe_customer_id (stripe_customer_id)
);
```

---

### 2. `products`
Apps/tools available for licensing.

```sql
CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug VARCHAR(100) UNIQUE NOT NULL, -- 'macr-pyqt', 'forbidden-spice', etc.
  name VARCHAR(255) NOT NULL,
  description TEXT,
  version VARCHAR(50),

  -- Pricing
  base_price_cents INTEGER, -- in cents ($99.99 = 9999)
  currency VARCHAR(3) DEFAULT 'USD',

  -- Status
  is_active BOOLEAN DEFAULT TRUE,
  is_testable BOOLEAN DEFAULT TRUE, -- allow free/trial licenses

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  INDEX idx_slug (slug),
  INDEX idx_active (is_active)
);
```

**Example Data:**
```sql
INSERT INTO products (slug, name, base_price_cents) VALUES
('macr-pyqt', 'Mac Retriever', 4999),  -- $49.99
('forbidden-spice-book', 'Forbidden Spice eBook', 1999), -- $19.99
('sw-tools-bundle', 'Silver Wizard Tools Bundle', 12999); -- $129.99
```

---

### 3. `features`
Individual features within products.

```sql
CREATE TABLE features (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES products(id),
  slug VARCHAR(100) NOT NULL, -- 'export', 'ai_features', 'cloud_sync', etc.
  name VARCHAR(255) NOT NULL,
  description TEXT,

  -- Feature type
  feature_type ENUM('core', 'premium', 'beta', 'experimental') DEFAULT 'core',

  -- Availability
  available_since_version VARCHAR(50),
  deprecated_in_version VARCHAR(50),

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  UNIQUE (product_id, slug),
  INDEX idx_product_features (product_id),
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);
```

**Example Data:**
```sql
INSERT INTO features (product_id, slug, name, feature_type) VALUES
(product_id, 'search', 'Email Search', 'core'),
(product_id, 'export', 'Export Emails', 'premium'),
(product_id, 'ai_classify', 'AI Categorization', 'premium'),
(product_id, 'cloud_sync', 'Cloud Backup', 'premium'),
(product_id, 'api_access', 'API Access', 'premium');
```

---

### 4. `license_types`
Different ways to license a product (purchase, subscription, rental).

```sql
CREATE TABLE license_types (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID NOT NULL REFERENCES products(id),
  slug VARCHAR(100) NOT NULL, -- 'perpetual', '30day_rental', 'yearly_subscription', etc.
  name VARCHAR(255) NOT NULL,
  description TEXT,

  -- License behavior
  duration_days INTEGER, -- NULL = perpetual, 30 = 30 days, 365 = yearly, etc.
  is_renewable BOOLEAN DEFAULT TRUE,
  is_transferable BOOLEAN DEFAULT FALSE,
  max_macs INTEGER DEFAULT 1, -- 1 = single Mac, 0 = unlimited

  -- Pricing
  price_cents INTEGER,
  renewal_price_cents INTEGER, -- for subscriptions

  -- Status
  is_active BOOLEAN DEFAULT TRUE,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  UNIQUE (product_id, slug),
  INDEX idx_product_types (product_id),
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);
```

**Example Data:**
```sql
INSERT INTO license_types (product_id, slug, name, duration_days, max_macs, price_cents) VALUES
(product_id, 'perpetual', 'Perpetual (1 Mac)', NULL, 1, 4999),      -- $49.99
(product_id, 'perpetual_family', 'Perpetual (5 Macs)', NULL, 5, 9999),  -- $99.99
(product_id, '7day_trial', '7-Day Trial', 7, 1, 0),                -- Free
(product_id, '30day_rental', '30-Day Rental', 30, 1, 999),         -- $9.99
(product_id, 'yearly_sub', 'Yearly Subscription', 365, 1, 6999),   -- $69.99/year
(product_id, 'monthly_sub', 'Monthly Subscription', 30, 1, 799);   -- $7.99/month
```

---

### 5. `license_type_features`
Which features are included in each license type.

```sql
CREATE TABLE license_type_features (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  license_type_id UUID NOT NULL REFERENCES license_types(id),
  feature_id UUID NOT NULL REFERENCES features(id),

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  UNIQUE (license_type_id, feature_id),
  INDEX idx_license_features (license_type_id),
  INDEX idx_feature_types (feature_id),
  FOREIGN KEY (license_type_id) REFERENCES license_types(id) ON DELETE CASCADE,
  FOREIGN KEY (feature_id) REFERENCES features(id) ON DELETE CASCADE
);
```

**Example:**
```sql
-- Perpetual license includes: search, export, ai_classify, cloud_sync
INSERT INTO license_type_features (license_type_id, feature_id) VALUES
(perpetual_type_id, search_feature_id),
(perpetual_type_id, export_feature_id),
(perpetual_type_id, ai_classify_feature_id),
(perpetual_type_id, cloud_sync_feature_id);

-- 7-day trial includes only: search
INSERT INTO license_type_features (license_type_id, feature_id) VALUES
(trial_type_id, search_feature_id);
```

---

### 6. `licenses`
Individual license keys issued to users.

```sql
CREATE TABLE licenses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  product_id UUID NOT NULL REFERENCES products(id),
  license_type_id UUID NOT NULL REFERENCES license_types(id),

  -- License key (encrypted)
  license_key_hash VARCHAR(255) UNIQUE NOT NULL, -- SHA256 hash for lookup
  license_key_encrypted TEXT NOT NULL, -- Encrypted with user's mac fingerprint

  -- Mac binding
  mac_fingerprint_hash VARCHAR(255) NOT NULL, -- MD5(mac_serial + product_id + version)
  mac_serial_suffix VARCHAR(20), -- Last 6 chars of serial for user recognition

  -- Status
  status ENUM('active', 'expired', 'revoked', 'suspended') DEFAULT 'active',

  -- Dates
  purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  activated_date TIMESTAMP,
  expires_at TIMESTAMP, -- NULL = never expires (perpetual)
  last_validation TIMESTAMP,

  -- Renewal
  next_renewal_date TIMESTAMP, -- for subscriptions
  auto_renew BOOLEAN DEFAULT TRUE,

  -- Metadata
  user_agent VARCHAR(500), -- What app/version requested the license
  ip_address INET,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  INDEX idx_user (user_id),
  INDEX idx_product (product_id),
  INDEX idx_license_key_hash (license_key_hash),
  INDEX idx_mac_fingerprint (mac_fingerprint_hash),
  INDEX idx_status (status),
  INDEX idx_expires (expires_at),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id),
  FOREIGN KEY (license_type_id) REFERENCES license_types(id)
);
```

---

### 7. `license_validations`
Audit log of when licenses are validated (for analytics and fraud detection).

```sql
CREATE TABLE license_validations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  license_id UUID NOT NULL REFERENCES licenses(id),

  -- What was checked
  mac_fingerprint_hash VARCHAR(255),
  app_version VARCHAR(50),
  os_version VARCHAR(100),

  -- Result
  validation_result ENUM('valid', 'invalid_mac', 'expired', 'revoked', 'error') DEFAULT 'valid',
  error_message VARCHAR(500),

  -- When
  validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  INDEX idx_license (license_id),
  INDEX idx_validation_time (validated_at),
  FOREIGN KEY (license_id) REFERENCES licenses(id) ON DELETE CASCADE
);
```

---

### 8. `rentals`
Time-limited rental sessions for licenses.

```sql
CREATE TABLE rentals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  product_id UUID NOT NULL REFERENCES products(id),
  license_type_id UUID NOT NULL REFERENCES license_types(id),

  -- Mac binding
  mac_fingerprint_hash VARCHAR(255) NOT NULL,

  -- Rental period
  rental_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  rental_end TIMESTAMP NOT NULL, -- Calculated from duration_days

  -- Status
  status ENUM('active', 'expired', 'cancelled') DEFAULT 'active',

  -- Renewal
  auto_renew BOOLEAN DEFAULT FALSE,
  renewal_attempts INTEGER DEFAULT 0,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  INDEX idx_user (user_id),
  INDEX idx_product (product_id),
  INDEX idx_mac (mac_fingerprint_hash),
  INDEX idx_status (status),
  INDEX idx_rental_end (rental_end),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id),
  FOREIGN KEY (license_type_id) REFERENCES license_types(id)
);
```

---

### 9. `payments`
Transaction history with Stripe.

```sql
CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  license_id UUID REFERENCES licenses(id),
  rental_id UUID REFERENCES rentals(id),

  -- What was purchased
  product_id UUID NOT NULL REFERENCES products(id),
  license_type_id UUID NOT NULL REFERENCES license_types(id),

  -- Payment details
  amount_cents INTEGER NOT NULL,
  currency VARCHAR(3) DEFAULT 'USD',

  -- Stripe integration
  stripe_payment_intent_id VARCHAR(255) UNIQUE,
  stripe_charge_id VARCHAR(255) UNIQUE,

  -- Status
  status ENUM('pending', 'succeeded', 'failed', 'refunded') DEFAULT 'pending',

  -- Dates
  payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_date TIMESTAMP,

  -- Metadata
  ip_address INET,
  user_agent VARCHAR(500),

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  INDEX idx_user (user_id),
  INDEX idx_license (license_id),
  INDEX idx_rental (rental_id),
  INDEX idx_stripe_intent (stripe_payment_intent_id),
  INDEX idx_status (status),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id),
  FOREIGN KEY (license_type_id) REFERENCES license_types(id)
);
```

---

## API Endpoints Schema

### POST `/api/validate-license`

**Request:**
```json
{
  "mac_fingerprint": "a1b2c3d4e5f6...", // MD5(mac_serial + product + version)
  "license_key": "SW-XXXX-XXXX-XXXX",
  "product_id": "macr-pyqt",
  "app_version": "0.9.0"
}
```

**Response (Valid):**
```json
{
  "valid": true,
  "license_type": "perpetual",
  "expires_at": null,
  "features": [
    "search", "export", "ai_classify", "cloud_sync"
  ],
  "mac_serial_suffix": "ABC123",
  "last_check": "2026-03-11T10:30:00Z",
  "days_remaining": null
}
```

**Response (Invalid):**
```json
{
  "valid": false,
  "reason": "expired", // or "invalid_mac", "revoked", "not_found"
  "days_remaining": -5,
  "can_renew": true,
  "renewal_url": "https://licensing.silverwizard.io/renew?license_id=..."
}
```

---

### POST `/api/check-rental`

**Request:**
```json
{
  "mac_fingerprint": "a1b2c3d4e5f6...",
  "product_id": "macr-pyqt"
}
```

**Response (Active Rental):**
```json
{
  "is_rental": true,
  "days_remaining": 15,
  "expires_at": "2026-03-26T10:30:00Z",
  "can_renew": true,
  "renewal_price_cents": 999
}
```

---

## Relationships Diagram

```
users (1) ──→ (many) licenses
        └──→ (many) payments
        └──→ (many) rentals

products (1) ──→ (many) features
          ├──→ (many) license_types
          └──→ (many) licenses

license_types (1) ──→ (many) license_type_features
             ├──→ (many) licenses
             └──→ (many) rentals

features (1) ──→ (many) license_type_features

licenses (1) ──→ (many) license_validations

rentals (1) ──→ (many) payments (optional)
```

---

## Indexes for Performance

**Critical Indexes:**
- `licenses(mac_fingerprint_hash)` - License validation query
- `licenses(license_key_hash)` - License key lookup
- `licenses(user_id, status)` - User's active licenses
- `rentals(mac_fingerprint_hash, status)` - Check for active rental
- `payments(user_id, status)` - User's payment history
- `license_validations(validated_at)` - Analytics/fraud detection

---

## Security Considerations

1. **License Key Encryption:**
   - Store only hash in `license_key_hash`
   - Encrypt full key with mac_fingerprint (so key is tied to Mac)
   - Never log actual keys

2. **Mac Fingerprint:**
   - Store hash of fingerprint
   - Never log actual hardware serial numbers
   - Verification: `MD5(received_fingerprint + product_id) == stored_hash`

3. **Payment Data:**
   - Never store full credit card numbers (use Stripe)
   - Store only Stripe charge/intent IDs
   - Log IP addresses for fraud detection

4. **Audit Trail:**
   - `license_validations` tracks every check
   - Can detect unusual patterns (validating from multiple IPs, etc.)

---

## Testing Data

```sql
-- Test user
INSERT INTO users (email, display_name) VALUES
('test@example.com', 'Test User');

-- Test products
INSERT INTO products (slug, name, base_price_cents) VALUES
('macr-test', 'Mac Retriever (Test)', 4999);

-- Test features
INSERT INTO features (product_id, slug, name) VALUES
(product_id, 'search', 'Search'),
(product_id, 'export', 'Export');

-- Test license types
INSERT INTO license_types (product_id, slug, name, duration_days, price_cents) VALUES
(product_id, 'perpetual', 'Perpetual', NULL, 4999),
(product_id, '7day_trial', '7-Day Trial', 7, 0);

-- Link features to license types
INSERT INTO license_type_features (license_type_id, feature_id) VALUES
(perpetual_id, search_id),
(perpetual_id, export_id),
(trial_id, search_id);
```

---

## Migration Path (When Schema Evolves)

```sql
-- Schema versioning
CREATE TABLE schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  description VARCHAR(500)
);

INSERT INTO schema_version (version, description) VALUES
(1, 'Initial schema with users, products, licenses');
```

Then future migrations:
```sql
-- Migration 2: Add usage tracking
ALTER TABLE licenses ADD COLUMN usage_units INTEGER DEFAULT 0;

INSERT INTO schema_version (version, description) VALUES
(2, 'Add usage tracking to licenses');
```

---

**Status:** Schema designed, ready for implementation when agents take over.
**Dependencies:** Stripe API integration, Locker fingerprinting extraction
**Estimated Implementation:** 1-2 weeks for MVP (just license validation)
