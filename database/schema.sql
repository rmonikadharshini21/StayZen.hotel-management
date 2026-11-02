-- StayZen database schema (MySQL 8)
-- Team BYTEBUILDER - JJCET AI-PDLC Hackathon 2026
-- Run through backend/seed.py, which also loads the sample data.

DROP DATABASE IF EXISTS stayzen;
CREATE DATABASE stayzen CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE stayzen;

-- Hotels: real ones come from OpenStreetMap (source = 'osm'), new ones are registered by owners.
-- status: listed = shown from OSM but owner not verified (no pre-booking)
--         pending = waiting for admin, approved = verified badge + pre-booking allowed
CREATE TABLE hotels (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(160) NOT NULL,
  district      VARCHAR(60)  NOT NULL,
  area          VARCHAR(200),
  latitude      DECIMAL(9,6) NOT NULL,
  longitude     DECIMAL(9,6) NOT NULL,
  rating        DECIMAL(2,1) NULL,
  stars         TINYINT      NOT NULL DEFAULT 0,
  review_count  INT          NOT NULL DEFAULT 0,
  phone         VARCHAR(60),
  website       VARCHAR(255),
  photo         MEDIUMTEXT   NULL,
  source        ENUM('osm','owner','demo') NOT NULL DEFAULT 'osm',
  status        ENUM('listed','pending','approved','rejected','suspended') NOT NULL DEFAULT 'listed',
  data_score    INT          NOT NULL DEFAULT 0,
  parking_watchman BOOLEAN   NULL,    -- security guard at the parking
  parking_cars  INT          NULL,    -- car slots
  parking_bikes INT          NULL,    -- two-wheeler slots
  wifi_info     VARCHAR(200) NULL,    -- e.g. free, speed, where it works
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_hotels_district (district),
  INDEX idx_hotels_status (status)
);

CREATE TABLE users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(120) NOT NULL,
  email         VARCHAR(160) NOT NULL UNIQUE,
  password_hash VARCHAR(200) NOT NULL,
  role          ENUM('guest','staff','admin') NOT NULL,
  hotel_id      INT NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE SET NULL
);

-- Login sessions. Only a SHA-256 hash of the token is stored.
CREATE TABLE sessions (
  token_hash CHAR(64) PRIMARY KEY,
  user_id    INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE hotel_amenities (
  hotel_id INT NOT NULL,
  amenity  VARCHAR(40) NOT NULL,
  PRIMARY KEY (hotel_id, amenity),
  FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE
);

CREATE TABLE rooms (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  hotel_id        INT NOT NULL,
  room_type       VARCHAR(60) NOT NULL,
  ac              ENUM('AC','Non-AC') NOT NULL,
  price_per_night INT NOT NULL,
  rooms_available INT NOT NULL DEFAULT 0,
  FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE
);

-- The same floor-plan layout is used for every hotel in the prototype.
CREATE TABLE facility_types (
  code          VARCHAR(20) PRIMARY KEY,
  name          VARCHAR(60) NOT NULL,
  name_ta       VARCHAR(60) NOT NULL,
  amenity       VARCHAR(40) NULL,
  grid_col      TINYINT NOT NULL,
  grid_row      TINYINT NOT NULL,
  duration_min  INT NOT NULL,
  directions    VARCHAR(300) NOT NULL,
  directions_ta VARCHAR(300) NOT NULL
);

-- Crowd counts are typed in by hotel staff (no cameras or sensors).
CREATE TABLE facilities (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  hotel_id      INT NOT NULL,
  code          VARCHAR(20) NOT NULL,
  capacity      INT NOT NULL,
  current_count INT NOT NULL DEFAULT 0,
  last_updated  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  open_hours    VARCHAR(60)  NULL,
  staff_help    VARCHAR(200) NULL,   -- e.g. trainer, lifeguard, therapists
  equipment     VARCHAR(400) NULL,   -- e.g. gym machines, pool size, menu
  notes         VARCHAR(300) NULL,
  UNIQUE KEY uq_facility (hotel_id, code),
  FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE,
  FOREIGN KEY (code) REFERENCES facility_types(code)
);

CREATE TABLE restaurants (
  id        INT AUTO_INCREMENT PRIMARY KEY,
  name      VARCHAR(160) NOT NULL,
  district  VARCHAR(60) NOT NULL,
  latitude  DECIMAL(9,6) NOT NULL,
  longitude DECIMAL(9,6) NOT NULL,
  cuisine   VARCHAR(255),
  INDEX idx_rest_district (district)
);

CREATE TABLE bookings (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  booking_code VARCHAR(12) NOT NULL UNIQUE,
  guest_id     INT NOT NULL,
  hotel_id     INT NOT NULL,
  room_id      INT NULL,
  room_type    VARCHAR(80) NOT NULL,
  rooms_count  INT NOT NULL,
  check_in     DATE NOT NULL,
  check_out    DATE NOT NULL,
  nights       INT NOT NULL,
  guests       INT NOT NULL,
  total_cost   INT NOT NULL,
  status       ENUM('pending','confirmed','rejected','checked_in','completed') NOT NULL DEFAULT 'pending',
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (guest_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE,
  FOREIGN KEY (room_id)  REFERENCES rooms(id)  ON DELETE SET NULL
);

CREATE TABLE queue_tokens (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  token_code  VARCHAR(12) NOT NULL,
  facility_id INT NOT NULL,
  guest_id    INT NULL,
  status      ENUM('waiting','called','cancelled') NOT NULL DEFAULT 'waiting',
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (facility_id) REFERENCES facilities(id) ON DELETE CASCADE,
  FOREIGN KEY (guest_id)    REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE notifications (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT NOT NULL,
  message    VARCHAR(300) NOT NULL,
  kind       VARCHAR(10) NOT NULL DEFAULT 'info',
  seen       BOOLEAN NOT NULL DEFAULT FALSE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Every change a hotel makes is logged here for the Stays Admin to review.
CREATE TABLE hotel_updates (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  hotel_id    INT NOT NULL,
  change_text VARCHAR(500) NOT NULL,
  reviewed    BOOLEAN NOT NULL DEFAULT FALSE,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE
);

CREATE TABLE feedback (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  booking_id  INT NOT NULL UNIQUE,
  hotel_id    INT NOT NULL,
  overall     TINYINT NOT NULL,
  clean       TINYINT NOT NULL,
  facilities  TINYINT NOT NULL,
  staff       TINYINT NOT NULL,
  accuracy    TINYINT NOT NULL,
  nav         TINYINT NOT NULL,
  crowd       TINYINT NOT NULL,
  queue       TINYINT NOT NULL,
  comments    VARCHAR(1000),
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
  FOREIGN KEY (hotel_id)   REFERENCES hotels(id)   ON DELETE CASCADE
);