-- Run this once in MySQL before starting the server.
-- Creates the database and the single table used by the demo.

CREATE DATABASE IF NOT EXISTS railway_demo;
USE railway_demo;

-- The only table in the demo: one row per train.
CREATE TABLE IF NOT EXISTS trains (
  id              INT PRIMARY KEY,
  name            VARCHAR(100) NOT NULL,
  available_seats INT NOT NULL
);

-- One train with exactly one seat. Re-running this file does not reset the seat count.
INSERT INTO trains (id, name, available_seats)
VALUES (1, 'Express 101', 1)
ON DUPLICATE KEY UPDATE available_seats = available_seats;
