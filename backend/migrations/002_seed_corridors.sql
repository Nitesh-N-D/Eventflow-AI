-- Migration 002: Seed real ASTRAM corridor data
-- 22 real Bengaluru corridors from the official dataset

INSERT INTO corridors (corridor_name, centroid_location, historical_incident_count, zone) VALUES
  ('Airport New South Road', ST_SetSRID(ST_MakePoint(77.6340222427, 13.0284768524), 4326)::geography, 63, 'North Zone 1'),
  ('Bannerghata Road', ST_SetSRID(ST_MakePoint(77.5979230249, 12.8965670455), 4326)::geography, 208, 'South Zone 2'),
  ('Bellary Road 1', ST_SetSRID(ST_MakePoint(77.586415195, 13.0168900763), 4326)::geography, 607, 'North Zone 2'),
  ('Bellary Road 2', ST_SetSRID(ST_MakePoint(77.6032707079, 13.1059559846), 4326)::geography, 379, 'North Zone 2'),
  ('CBD 1', ST_SetSRID(ST_MakePoint(77.606662228, 12.980940852), 4326)::geography, 25, 'Central Zone 2'),
  ('CBD 2', ST_SetSRID(ST_MakePoint(77.5947652799, 12.9835692071), 4326)::geography, 97, 'Central Zone 2'),
  ('Hennur Main Road', ST_SetSRID(ST_MakePoint(77.6262318687, 13.0513857138), 4326)::geography, 94, 'North Zone 1'),
  ('Hosur Road', ST_SetSRID(ST_MakePoint(77.6247291001, 12.9153484239), 4326)::geography, 297, 'South Zone 2'),
  ('IRR(Thanisandra road)', ST_SetSRID(ST_MakePoint(77.6269448713, 12.9375064237), 4326)::geography, 95, 'South Zone 2'),
  ('Magadi Road', ST_SetSRID(ST_MakePoint(77.5231572989, 12.9850949907), 4326)::geography, 243, 'West Zone 1'),
  ('Mysore Road', ST_SetSRID(ST_MakePoint(77.5641858289, 12.9580883933), 4326)::geography, 728, 'Central Zone 2'),
  ('Non-corridor', ST_SetSRID(ST_MakePoint(77.5992236072, 12.9830196379), 4326)::geography, 3082, 'Central Zone 2'),
  ('ORR East 1', ST_SetSRID(ST_MakePoint(77.6689833989, 12.9282478354), 4326)::geography, 242, 'East Zone 1'),
  ('ORR East 2', ST_SetSRID(ST_MakePoint(77.6959229676, 12.975979769), 4326)::geography, 183, 'East Zone 1'),
  ('ORR North 1', ST_SetSRID(ST_MakePoint(77.6373432126, 13.0246440101), 4326)::geography, 274, 'North Zone 1'),
  ('ORR North 2', ST_SetSRID(ST_MakePoint(77.5588224813, 13.0419277115), 4326)::geography, 235, 'North Zone 2'),
  ('ORR West 1', ST_SetSRID(ST_MakePoint(77.55895797310001, 12.9210118666), 4326)::geography, 166, 'South Zone 1'),
  ('Old Airport Road', ST_SetSRID(ST_MakePoint(77.6619064524, 12.9588635773), 4326)::geography, 74, 'Central Zone 1'),
  ('Old Madras Road', ST_SetSRID(ST_MakePoint(77.6295817784, 12.9810095901), 4326)::geography, 257, 'Central Zone 1'),
  ('Tumkur Road', ST_SetSRID(ST_MakePoint(77.53366289, 13.0314585564), 4326)::geography, 458, 'West Zone 1'),
  ('Varthur Road', ST_SetSRID(ST_MakePoint(77.7160916161, 12.9565573436), 4326)::geography, 75, 'East Zone 1'),
  ('West of Chord Road', ST_SetSRID(ST_MakePoint(77.5462767445, 12.982936885400001), 4326)::geography, 172, 'West Zone 2');
