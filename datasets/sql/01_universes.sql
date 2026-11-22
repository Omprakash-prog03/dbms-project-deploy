-- 1. universes — 2 rows
-- target table: uni_universe
DELETE FROM uni_universe;
INSERT INTO uni_universe (universe_id, universe_name, publisher, description, continuity_type) VALUES (1, 'Marvel', 'Marvel Comics', 'The Marvel universe as published by Marvel Comics and adapted by Marvel Studios: Earth-616, the Ultimate and Spider-Gwen branches, and the Marvel Cinematic Universe of Earth-199999.', 'Comic book continuity plus film and television continuities');
INSERT INTO uni_universe (universe_id, universe_name, publisher, description, continuity_type) VALUES (2, 'DC', 'DC Comics', 'The DC universe as published by DC Comics and adapted by Warner Bros.: the post-Crisis and Prime Earth continuity, the DCEU of Earth-1, and the Arrowverse, Smallville, DCAU and Dark Knight screen continuities.', 'Comic book continuity plus film and television continuities');
