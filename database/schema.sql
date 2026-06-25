DROP TABLE IF EXISTS aftersale_tickets CASCADE;
DROP TABLE IF EXISTS logistics_records CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS aftersale_policies CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    customer_id VARCHAR(32) PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    phone_masked VARCHAR(32),
    level VARCHAR(32) DEFAULT 'normal',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    product_id VARCHAR(32) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    brand VARCHAR(100),
    price NUMERIC(10, 2) NOT NULL,
    stock INT DEFAULT 0,
    specs JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(32) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
    order_id VARCHAR(32) PRIMARY KEY,
    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id),
    order_status VARCHAR(32) NOT NULL,
    payment_amount NUMERIC(10, 2) NOT NULL,
    pay_time TIMESTAMP,
    ship_time TIMESTAMP,
    receive_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_items (
    item_id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    product_id VARCHAR(32) NOT NULL REFERENCES products(product_id),
    quantity INT NOT NULL DEFAULT 1,
    unit_price NUMERIC(10, 2) NOT NULL
);

CREATE TABLE logistics_records (
    logistics_id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    carrier VARCHAR(100),
    tracking_no VARCHAR(100),
    logistics_status VARCHAR(64) NOT NULL,
    location VARCHAR(255),
    description TEXT,
    event_time TIMESTAMP NOT NULL
);

CREATE TABLE aftersale_policies (
    policy_id BIGSERIAL PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    policy_type VARCHAR(32) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    allow_days INT,
    conditions JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aftersale_tickets (
    ticket_id VARCHAR(32) PRIMARY KEY,
    order_id VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id),
    product_id VARCHAR(32) NOT NULL REFERENCES products(product_id),
    ticket_type VARCHAR(32) NOT NULL,
    reason TEXT,
    ticket_status VARCHAR(32) DEFAULT 'created',
    rule_result JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(order_status);
CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_logistics_order_id ON logistics_records(order_id);
CREATE INDEX idx_aftersale_tickets_order_id ON aftersale_tickets(order_id);
CREATE INDEX idx_aftersale_policies_category ON aftersale_policies(category);