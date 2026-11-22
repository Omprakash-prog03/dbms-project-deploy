"""Missions and storylines for the Marvel & DC Universe Database.

60 storylines: 30 Marvel, 30 DC. Each is a story unit — a comic event, a comic arc,
a film saga, a television saga or a crossover — with a start and end year, an outcome
and a participation list.

Columns:
    (key, name, universe, category, start_year, end_year, description, outcome,
     continuity, [(character_key, role, outcome, survival_status), ...])
"""

MISSIONS = [
    # -------------------------------- MARVEL --------------------------------
    ('infinity_saga', 'The Infinity Saga', 'Marvel', 'Film saga', 2008, 2019,
     'The twenty-three film MCU arc from Tony Stark cave to the Snap and its reversal, '
     'told as one story about six stones and the people who would not leave them alone.',
     'Thanos defeated; the Snap reversed; Stark and Romanoff dead',
     'Marvel Cinematic Universe (Earth-199999)', [
        ('mcu_iron_man', 'Founding Avenger', 'Sacrificed himself to reverse the Snap', 'Killed'),
        ('mcu_captain_america', 'Field leader', 'Passed the shield on and retired', 'Survived'),
        ('mcu_thor', 'Front-line commander', 'Left Earth with the Guardians', 'Survived'),
        ('mcu_hulk', 'Science lead', 'Performed the reversal snap', 'Survived'),
        ('mcu_thanos', 'Antagonist', 'Defeated on two timelines', 'Killed'),
        ('mcu_black_widow', 'Infiltration', 'Died acquiring the Soul Stone', 'Killed'),
        ('mcu_spider_man', 'Recruit', 'Returned and lost his mentor', 'Survived')]),

    ('secret_wars_1984', 'Secret Wars', 'Marvel', 'Comic event', 1984, 1985,
     'The Beyonder pulls a selection of heroes and villains to Battleworld and offers the '
     'winner anything they want; the heroes win by not playing.',
     'Battleworld destroyed; heroes returned to Earth',
     'Marvel Comics (Earth-616)', [
        ('doctor_strange', 'Team leader', 'Led the hero faction to victory', 'Survived'),
        ('captain_america', 'Field commander', 'Destroyed the Beyonder construct', 'Survived'),
        ('iron_man', 'Technology', 'Rebuilt the team armour on Battleworld', 'Survived'),
        ('hulk', 'Heavy assault', 'Held the line at Doomstadt', 'Survived'),
        ('galactus', 'Cosmic observer', 'Fed on Battleworld and withdrew', 'Survived')]),

    ('civil_war', 'Civil War', 'Marvel', 'Comic event', 2006, 2007,
     'A school explosion forces the Superhuman Registration Act; the hero community splits '
     'between Captain America refusal and Iron Man enforcement.',
     'Registration enforced; Captain America surrendered and was assassinated later',
     'Marvel Comics (Earth-616)', [
        ('captain_america', 'Anti-registration leader', 'Surrendered to end the fighting', 'Killed'),
        ('iron_man', 'Pro-registration leader', 'Won the political argument', 'Survived'),
        ('spider_man', 'Defector', 'Revealed his identity and changed sides', 'Survived'),
        ('black_widow', 'Pro-registration operative', 'Enforced the Act, then defected', 'Survived'),
        ('punisher', 'Unaffiliated', 'Joined the resistance and was expelled from it', 'Survived')]),

    ('infinity_gauntlet', 'The Infinity Gauntlet', 'Marvel', 'Comic event', 1991, 1991,
     'Thanos assembles all six Infinity Gems and erases half the universe to court Death; '
     'the surviving heroes and cosmic entities counter-attack.',
     'Gauntlet taken by Nebula, then by Adam Warlock; the Snap reversed',
     'Marvel Comics (Earth-616)', [
        ('thanos', 'Antagonist', 'Erased half of all life, then lost the gauntlet', 'Survived'),
        ('silver_surfer', 'Cosmic counter-attack', 'Led the assault on Thanos', 'Survived'),
        ('doctor_strange', 'Magic support', 'Coordinated the mystic front', 'Survived'),
        ('spider_man', 'Field support', 'Survived the initial Snap by chance', 'Survived'),
        ('nebula', 'Opportunist', 'Claimed the gauntlet briefly', 'Survived')]),

    ('dark_phoenix_saga', 'The Dark Phoenix Saga', 'Marvel', 'Comic arc', 1980, 1980,
     'Jean Grey is corrupted by the Hellfire Club and the Phoenix Force, consumes a star '
     'and a planet, and the X-Men must decide whether to save or execute her.',
     'Jean Grey sacrificed herself on the moon',
     'Marvel Comics (Earth-616)', [
        ('jean_grey', 'Phoenix host', 'Died on the moon by her own choice', 'Killed'),
        ('cyclops', 'Team leader', 'Refused to let the team kill her', 'Survived'),
        ('wolverine', 'Field operative', 'Argued for execution and was overruled', 'Survived'),
        ('emma_frost', 'Antagonist', 'Hellfire Club manipulation of the Phoenix', 'Survived')]),

    ('days_of_future_past', 'Days of Future Past', 'Marvel', 'Comic arc', 1981, 1981,
     'A Sentinel-ruled future sends Kate Pryde mind back into her younger self to stop the '
     'assassination that started the war.',
     'Assassination prevented; future timeline averted',
     'Marvel Comics (Earth-616)', [
        ('kitty_pryde', 'Time traveller', 'Prevented the assassination', 'Survived'),
        ('wolverine', 'Future resistance', 'Held the camp line', 'Killed'),
        ('storm', 'Future resistance', 'Covered the escape', 'Killed'),
        ('professor_x', 'Strategy', 'Planned the mind transfer', 'Killed')]),

    ('age_of_apocalypse', 'Age of Apocalypse', 'Marvel', 'Comic event', 1995, 1996,
     'Legion kills Xavier in the past, and the world he returns to is one where Apocalypse '
     'has ruled for twenty years and the X-Men were founded by Magneto.',
     'Timeline restored; Apocalypse defeated in the altered present',
     'Marvel Comics (Earth-616)', [
        ('apocalypse', 'Antagonist', 'Ruled the altered world for twenty years', 'Killed'),
        ('magneto', 'Founder of the altered X-Men', 'Drove the resistance', 'Survived'),
        ('wolverine', 'Field operative', 'One-handed, still the best there is', 'Survived'),
        ('cyclops', 'Field leader', 'Led the raid on Apocalypse', 'Killed'),
        ('sabretooth', 'Altered X-Men member', 'Fought alongside the team', 'Survived')]),

    ('house_of_m', 'House of M', 'Marvel', 'Comic event', 2005, 2005,
     'Wanda Maximoff rewrites reality into a mutant-ruled world where her family is whole; '
     'the heroes who remember it have to ask her to stop.',
     'Reality restored; mutants reduced to a few hundred',
     'Marvel Comics (Earth-616)', [
        ('scarlet_witch', 'Reality warper', 'Restored reality and decimated mutantkind', 'Survived'),
        ('magneto', 'Putative ruler', 'Lost his children and his world', 'Survived'),
        ('professor_x', 'Opposition', 'Led the attempt to stop her', 'Killed'),
        ('quicksilver', 'Instigator', 'Pushed Wanda into the rewrite', 'Survived'),
        ('doctor_strange', 'Opposition', 'Broke the illusion from within', 'Survived')]),

    ('secret_invasion_2008', 'Secret Invasion', 'Marvel', 'Comic event', 2008, 2008,
     'The Skrull Empire has been replacing heroes and officials for years; the invasion '
     'begins with a SHIELD helicarrier crashing into Central Park.',
     'Skrull invasion defeated; Norman Osborn put in charge of national security',
     'Marvel Comics (Earth-616)', [
        ('nick_fury', 'Underground coordinator', 'Ran the resistance from a hidden base', 'Survived'),
        ('iron_man', 'Technology', 'Built the detection system that ended it', 'Survived'),
        ('black_widow', 'Infiltration', 'Rooted out the replaced agents', 'Survived'),
        ('veranke', 'Antagonist', 'Skrull queen, defeated in Central Park', 'Killed')]),

    ('planet_hulk', 'Planet Hulk', 'Marvel', 'Comic arc', 2006, 2007,
     'The Illuminati exile the Hulk to an uninhabited world; he lands on Sakaar instead and '
     'fights his way from gladiator to king.',
     'Hulk crowned king of Sakaar, then returned to Earth for revenge',
     'Marvel Comics (Earth-616)', [
        ('hulk', 'Protagonist', 'Became king of Sakaar', 'Survived'),
        ('silver_surfer', 'Cosmic observer', 'Warned Earth of the return', 'Survived'),
        ('iron_man', 'Responsible party', 'Voted for the exile', 'Survived'),
        ('doctor_strange', 'Responsible party', 'Voted for the exile', 'Survived')]),

    ('kree_skrull_war', 'The Kree-Skrull War', 'Marvel', 'Comic event', 1971, 1972,
     'The Kree and Skrull empires bring their war to Earth, with the Avengers caught '
     'between SHIELD, the Inhumans and a pacifist Kree captain.',
     'War averted on Earth by the Avengers and the Inhuman royal family',
     'Marvel Comics (Earth-616)', [
        ('captain_marvel', 'Kree defector', 'Turned against his own empire', 'Survived'),
        ('black_bolt', 'Inhuman king', 'Refused to give up his people', 'Survived'),
        ('vision', 'Avengers operative', 'Kept the team coordinated', 'Survived'),
        ('nick_fury', 'SHIELD director', 'Ran the intelligence side', 'Survived'),
        ('medusa', 'Inhuman queen', 'Brokered the final deal', 'Survived')]),

    ('weapon_x', 'Weapon X', 'Marvel', 'Comic arc', 1991, 1991,
     'The Weapon X programme binds Wolverine to an operating table and coats his skeleton in '
     'Adamantium, erasing his memory and producing their perfect weapon.',
     'Wolverine escaped; the programme continued',
     'Marvel Comics (Earth-616)', [
        ('wolverine', 'Test subject', 'Escaped and lost his memory', 'Survived'),
        ('sabretooth', 'Programme operative', 'Hunted the escapee', 'Survived'),
        ('professor_x', 'Post-rescue', 'Rebuilt his mind', 'Survived')]),

    ('dark_reign', 'Dark Reign', 'Marvel', 'Comic event', 2008, 2009,
     'Norman Osborn is given control of national security after the Skrull invasion and '
     'rebuilds SHIELD as HAMMER with villains in every uniform.',
     'Osborn regime collapsed at the Siege of Asgard',
     'Marvel Comics (Earth-616)', [
        ('green_goblin', 'Antagonist', 'Ran HAMMER, then lost it', 'Survived'),
        ('iron_man', 'Opposition', 'Lost his technology and his company', 'Survived'),
        ('nick_fury', 'Opposition', 'Ran a resistance from hiding', 'Survived'),
        ('bullseye', 'HAMMER enforcer', 'Killed in the Siege', 'Killed')]),

    ('siege_asgard', 'Siege of Asgard', 'Marvel', 'Comic event', 2010, 2010,
     'Osborn invades the floating Asgard over Oklahoma with HAMMER and a stolen Sentry, and '
     'the Avengers must defend a city that is also a god.',
     'Osborn defeated; Asgard rebuilt; the Heroic Age began',
     'Marvel Comics (Earth-616)', [
        ('thor', 'City defender', 'Rebuilt Asgard after the siege', 'Survived'),
        ('iron_man', 'City defender', 'Led the aerial counter-attack', 'Survived'),
        ('captain_america', 'City defender', 'Rallied the defence', 'Survived'),
        ('green_goblin', 'Antagonist', 'Arrested at the end of the siege', 'Survived'),
        ('bullseye', 'HAMMER enforcer', 'Killed during the assault', 'Killed')]),

    ('demon_in_a_bottle', 'Demon in a Bottle', 'Marvel', 'Comic arc', 1979, 1979,
     'An armour malfunction and a takeover of Stark International push Tony Stark into '
     'alcoholism, and the arc is about the armoured hero admitting he cannot fix himself.',
     'Stark accepted he was an alcoholic and sought help',
     'Marvel Comics (Earth-616)', [
        ('iron_man', 'Protagonist', 'Admitted the addiction', 'Survived'),
        ('war_machine', 'Friend and support', 'Took over the suit while Stark recovered', 'Survived'),
        ('black_widow', 'Ally', 'Covered the corporate front', 'Survived')]),

    ('born_again', 'Born Again', 'Marvel', 'Comic arc', 1986, 1986,
     'The Kingpin learns Daredevil identity and dismantles his life piece by piece — licence, '
     'home, mind — and Matt Murdock rebuilds from nothing.',
     'Murdock rebuilt and defeated the Kingpin scheme',
     'Marvel Comics (Earth-616)', [
        ('daredevil', 'Protagonist', 'Rebuilt his life and his law practice', 'Survived'),
        ('kingpin', 'Antagonist', 'Lost the war he started', 'Survived'),
        ('bullseye', 'Antagonist enforcer', 'Assassinated Karen Page', 'Survived')]),

    ('mcu_infinity_war', 'Avengers: Infinity War', 'Marvel', 'Film saga', 2018, 2018,
     'Thanos takes the stones across four fronts, and the Avengers lose every one of them. '
     'The film ends with the Snap.',
     'Thanos won; half of all life erased',
     'Marvel Cinematic Universe (Earth-199999)', [
        ('mcu_thanos', 'Antagonist', 'Completed the gauntlet', 'Survived'),
        ('mcu_iron_man', 'Front leader', 'Lost the fight on Titan', 'Survived'),
        ('mcu_thor', 'Front leader', 'Struck the chest instead of the head', 'Survived'),
        ('mcu_loki', 'Antagonist turned ally', 'Killed by Thanos at the start', 'Killed'),
        ('mcu_gamora', 'Guardian', 'Died on Vormir for the Soul Stone', 'Killed'),
        ('mcu_wanda_title', 'Front leader', 'Held the line in Wakanda', 'Survived')]),

    ('mcu_endgame', 'Avengers: Endgame', 'Marvel', 'Film saga', 2019, 2019,
     'The surviving Avengers use the Quantum Realm to borrow the stones from the past, and '
     'the final battle is fought by everyone they brought back.',
     'Snap reversed; Thanos killed; Stark and Romanoff dead',
     'Marvel Cinematic Universe (Earth-199999)', [
        ('mcu_iron_man', 'Founding Avenger', 'Snapped Thanos army away and died of it', 'Killed'),
        ('mcu_captain_america', 'Field leader', 'Returned the stones and stayed in the past', 'Survived'),
        ('mcu_hulk', 'Science lead', 'Performed the reversal snap', 'Survived'),
        ('mcu_black_widow', 'Infiltration', 'Died on Vormir', 'Killed'),
        ('mcu_hawkeye', 'Infiltration', 'Watched Romanoff die for the stone', 'Survived'),
        ('mcu_thanos', 'Antagonist', 'Killed twice across two timelines', 'Killed')]),

    ('mcu_civil_war', 'Captain America: Civil War', 'Marvel', 'Film saga', 2016, 2016,
     'The Sokovia Accords split the Avengers, and Zemo uses a HYDRA file to make the split '
     'about Bucky Barnes and Howard Stark instead of policy.',
     'Avengers fractured; the Accords enforced; Zemo imprisoned',
     'Marvel Cinematic Universe (Earth-199999)', [
        ('mcu_captain_america', 'Anti-Accords leader', 'Abandoned the shield', 'Survived'),
        ('mcu_iron_man', 'Pro-Accords leader', 'Won the vote and lost the friend', 'Survived'),
        ('mcu_winter_soldier', 'Fugitive', 'Frozen in Wakanda at his own request', 'Survived'),
        ('mcu_black_panther', 'Neutral crown', 'Chose justice over revenge', 'Survived'),
        ('mcu_spider_man', 'Recruit', 'Recruited to the Berlin airport fight', 'Survived'),
        ('mcu_black_widow', 'Defector', 'Let the fugitives go', 'Survived')]),

    ('mcu_ragnarok', 'Thor: Ragnarok', 'Marvel', 'Film saga', 2017, 2017,
     'Hela takes Asgard, Thor is stranded on Sakaar, and the only way to stop her is to '
     'destroy the place he is trying to save.',
     'Asgard destroyed; Hela dead; the Asgardians fled to Earth',
     'Marvel Cinematic Universe (Earth-199999)', [
        ('mcu_thor', 'Protagonist', 'Destroyed Asgard to save its people', 'Survived'),
        ('mcu_loki', 'Ally', 'Held Surtur line briefly, then stole an escape', 'Survived'),
        ('mcu_hela', 'Antagonist', 'Killed by Surtur', 'Killed'),
        ('mcu_hulk', 'Gladiator', 'Two years on Sakaar', 'Survived')]),

    ('mcu_wanda_hex', 'The Westview Anomaly', 'Marvel', 'Television saga', 2021, 2021,
     'Wanda Maximoff creates a sitcom reality around her grief in Westview, and SWORD, '
     'Agatha Harkness and the townspeople all try to end it.',
     'The Hex collapsed; Wanda left as the Scarlet Witch',
     'Marvel Cinematic Universe (Earth-199999)', [
        ('mcu_wanda_title', 'Protagonist', 'Accepted her grief and released the town', 'Survived'),
        ('mcu_scarlet_witch', 'Protagonist', 'Same person, earlier name', 'Survived'),
        ('mcu_vision', 'Supporting', 'Recreated, then released by Wanda', 'Killed'),
        ('darcy_lewis', 'Supporting', 'Broke into the Hex to help', 'Survived')]),

    ('mcu_tva', 'The Time Variance Authority', 'Marvel', 'Television saga', 2021, 2021,
     'A Loki variant is arrested by the TVA and discovers the organisation maintaining a '
     'single sacred timeline, and the man who is actually running it.',
     'The sacred timeline branched; Loki took a throne at the end of time',
     'Marvel Cinematic Universe (Earth-199999)', [
        ('mcu_loki', 'Protagonist', 'Chose the branches over the throne', 'Survived'),
        ('mcu_loki_variant_sylvie', 'Variant', 'Killed He Who Remains', 'Survived'),
        ('phil_coulson', 'Supporting', 'Not present; TVA files only', 'Unknown')]),

    ('mcu_multiverse', 'The Multiverse Saga', 'Marvel', 'Film saga', 2021, 2025,
     'The MCU arc from the Hex to the Kang dynasty: every spell, portal and variant that '
     'opened the multiverse and the councils trying to police it.',
     'Ongoing; the multiverse is unstable',
     'Marvel Cinematic Universe (Earth-199999)', [
        ('mcu_doctor_strange', 'Architect of the breach', 'Opened and stabilised portals', 'Survived'),
        ('mcu_spider_man', 'Affected', 'Brought three villains through and fixed them', 'Survived'),
        ('mcu_scarlet_witch', 'Antagonist', 'Buried under Mount Wundagore', 'Presumed dead'),
        ('mcu_wanda_title', 'Antagonist', 'Destroyed the Darkhold and herself', 'Presumed dead')]),

    ('mcu_black_order_assault', 'The Black Order Assault', 'Marvel', 'Film saga', 2018, 2018,
     'The children of Thanos hit New York, Edinburgh and Wakanda in sequence to take the '
     'Time and Mind Stones.',
     'Stones taken; the Order destroyed',
     'Marvel Cinematic Universe (Earth-199999)', [
        ('mcu_ebony_maw', 'Field commander', 'Killed in space by Tony Stark', 'Killed'),
        ('mcu_cull_obsidian', 'Heavy assault', 'Killed in Wakanda by the Avengers', 'Killed'),
        ('mcu_proxima_midnight', 'Assassin', 'Killed by Scarlet Witch in Wakanda', 'Killed'),
        ('mcu_corvus_glaive', 'Assassin', 'Killed by Vision in Wakanda', 'Killed'),
        ('mcu_wanda_title', 'Defender', 'Held the Wakandan field', 'Survived')]),

    ('xmen_phoenix_end', 'X-Men: The Dark Phoenix', 'Marvel', 'Film saga', 2006, 2006,
     'The X-Men film continuity retells the Phoenix story as Jean Grey losing control of a '
     'cosmic force, with the team splitting over whether to save her.',
     'Jean Grey killed and the school reopened',
     'Marvel Comics (X-Men Film Series)', [
        ('jean_grey', 'Phoenix host', 'Died stopping the Phoenix', 'Killed'),
        ('cyclops', 'Team leader', 'Killed at Alkali Lake', 'Killed'),
        ('wolverine', 'Field operative', 'Ended the Phoenix threat', 'Survived'),
        ('storm', 'Field operative', 'Held the mansion defence', 'Survived'),
        ('professor_x', 'Leadership', 'Killed by the Phoenix', 'Killed')]),

    ('defenders_hand', 'The Hand War', 'Marvel', 'Television saga', 2017, 2017,
     'Four street-level heroes discover the Hand is digging under New York for a substance '
     'that will raise the dead, and that Elektra is leading it.',
     'The Hand defeated; Midland Circle collapsed',
     'Marvel Cinematic Universe (Earth-199999)', [
        ('mcu_daredevil', 'Field leader', 'Buried under Midland Circle and survived', 'Presumed dead'),
        ('elektra', 'Antagonist', 'Died with the building', 'Killed'),
        ('mcu_jessica_jones', 'Investigator', 'Found the dig sites', 'Survived'),
        ('mcu_luke_cage', 'Community protection', 'Evacuated Harlem', 'Survived'),
        ('mcu_iron_fist', 'Field operative', 'Sealed the gate', 'Survived')]),

    ('secret_wars_2015', 'Secret Wars (2015)', 'Marvel', 'Comic event', 2015, 2015,
     'The final incursion destroys the Marvel multiverse and Doctor Doom rebuilds what is '
     'left as Battleworld, ruling it as God-Emperor.',
     'Multiverse restored; Reed Richards rebuilt reality',
     'Marvel Comics (Earth-616)', [
        ('doctor_strange', 'Opposition', 'Worked against Doom inside Battleworld', 'Survived'),
        ('mr_fantastic', 'Reality rebuilder', 'Restored the multiverse', 'Survived'),
        ('black_panther', 'Opposition', 'Held Wakanda as the last nation', 'Survived'),
        ('thanos', 'Opposition', 'Killed early and resurrected by Doom', 'Killed')]),

    ('orig_accord_crisis', 'The Accord Crisis', 'Marvel', 'Crossover', 2020, 2021,
     'Original addition — a registration-style dispute between unaffiliated heroes and a '
     'metahuman authority, written for this demonstration as a small-scale civil-war analogue.',
     'Negotiated settlement; the Vigil Accord formed',
     'Marvel Comics (Earth-616)', [
        ('orig_antares', 'Negotiator', 'Brokered the settlement', 'Survived'),
        ('orig_ferro', 'Field operative', 'Refused the authority writ', 'Survived'),
        ('orig_cassandra', 'Advisor', 'Predicted the settlement branch', 'Survived'),
        ('doctor_strange', 'Neutral authority', 'Witnessed and refused to enforce the writ', 'Survived')]),
]

MISSIONS += [
    # ---------------------------------- DC ----------------------------------
    ('crisis_infinite_earths', 'Crisis on Infinite Earths', 'DC', 'Comic event', 1985, 1986,
     'The Anti-Monitor destroys the multiverse one Earth at a time, and the surviving heroes '
     'fight a war across collapsing realities.',
     'Multiverse collapsed into one Earth; the Flash and Supergirl died',
     'DC Comics (New Earth/Prime Earth)', [
        ('flash', 'Field leader', 'Died destroying the Anti-Monitor cannon', 'Killed'),
        ('supergirl', 'Field commander', 'Died fighting the Anti-Monitor directly', 'Killed'),
        ('superman', 'Front line', 'Led the final assault', 'Survived'),
        ('batman', 'Strategy', 'Coordinated the Earth defences', 'Survived'),
        ('wonder_woman', 'Front line', 'Held the Amazon front', 'Survived'),
        ('darkseid', 'Reluctant ally', 'Fought the Anti-Monitor, not for the heroes', 'Survived')]),

    ('flashpoint_event', 'Flashpoint', 'DC', 'Comic event', 2011, 2011,
     'Barry Allen saves his mother and creates a timeline where Atlantis and Themyscira are '
     'at war, Superman was never raised free and Bruce Wayne died instead of his father.',
     'Timeline restored; the New 52 began',
     'DC Comics (New Earth/Prime Earth)', [
        ('flash', 'Protagonist', 'Restored the timeline at the cost of his mother', 'Survived'),
        ('reverse_flash', 'Antagonist', 'Caused the original break', 'Killed'),
        ('batman', 'Altered timeline ally', 'Thomas Wayne Batman in the altered world', 'Killed'),
        ('aquaman', 'Altered timeline antagonist', 'Waged war on the surface', 'Killed'),
        ('wonder_woman', 'Altered timeline antagonist', 'Ruled the Amazons at war', 'Killed')]),

    ('knightfall_saga', 'Knightfall', 'DC', 'Comic arc', 1993, 1994,
     'Bane wears Batman down over months and breaks his back, and Gotham is handed to '
     'Azrael until Bruce Wayne takes it back.',
     'Batman recovered; Bane defeated; Azrael removed',
     'DC Comics (New Earth/Prime Earth)', [
        ('bane', 'Antagonist', 'Broke Batman back', 'Survived'),
        ('batman', 'Protagonist', 'Recovered and reclaimed the mantle', 'Survived'),
        ('robin_tim', 'Supporting', 'Held the city while Bruce healed', 'Survived'),
        ('nightwing', 'Supporting', 'Took over the cowl briefly', 'Survived')]),

    ('death_of_superman', 'The Death of Superman', 'DC', 'Comic arc', 1992, 1993,
     'Doomsday fights its way across America to Metropolis, and Superman dies stopping it. '
     'The funeral issues are the point of the story.',
     'Doomsday killed; Superman resurrected months later',
     'DC Comics (New Earth/Prime Earth)', [
        ('doomsday', 'Antagonist', 'Killed by Superman in Metropolis', 'Killed'),
        ('superman', 'Protagonist', 'Died in Metropolis and returned', 'Killed'),
        ('lex_luthor', 'Supporting antagonist', 'Claimed the body for study', 'Survived'),
        ('supergirl', 'Supporting', 'Held the city during the fight', 'Survived')]),

    ('dark_knight_returns', 'The Dark Knight Returns', 'DC', 'Comic arc', 1986, 1986,
     'A retired Bruce Wayne puts the cowl back on at fifty-five, and the story is about '
     'whether Batman was ever anything but a necessary monster.',
     'Batman faked his death and trained a new generation',
     'DC Comics (New Earth/Prime Earth)', [
        ('batman', 'Protagonist', 'Returned, then faked his death', 'Survived'),
        ('joker', 'Antagonist', 'Killed himself to frame Batman', 'Killed'),
        ('superman', 'Antagonist ally', 'Sent to stop him by the government', 'Survived'),
        ('robin_tim', 'Successor', 'Became the new Robin', 'Survived')]),

    ('killing_joke', 'Batman: The Killing Joke', 'DC', 'Comic arc', 1988, 1988,
     'The Joker shoots Barbara Gordon, kidnaps Jim Gordon and tries to prove that one bad '
     'day is all it takes to make anyone into him.',
     'Barbara paralysed; the argument left unresolved',
     'DC Comics (New Earth/Prime Earth)', [
        ('joker', 'Antagonist', 'Failed to break Jim Gordon', 'Survived'),
        ('batgirl', 'Victim', 'Paralysed and became Oracle', 'Survived'),
        ('batman', 'Protagonist', 'Refused the joke', 'Survived')]),

    ('death_in_the_family', 'A Death in the Family', 'DC', 'Comic arc', 1988, 1989,
     'Jason Todd goes looking for his mother and finds the Joker instead; the readers voted '
     'for the ending.',
     'Jason Todd killed; the Joker escaped',
     'DC Comics (New Earth/Prime Earth)', [
        ('red_hood', 'Victim', 'Killed by the Joker in Ethiopia', 'Killed'),
        ('joker', 'Antagonist', 'Escaped with the crowbar', 'Survived'),
        ('batman', 'Protagonist', 'Arrived too late', 'Survived')]),

    ('long_halloween', 'The Long Halloween', 'DC', 'Comic arc', 1996, 1997,
     'A year-long murder mystery in which a Holiday killer takes one victim a month and the '
     'answer turns out to be the district attorney.',
     'Two-Face created; the Falcone family broken',
     'DC Comics (New Earth/Prime Earth)', [
        ('two_face', 'Antagonist', 'Turned by the year and the acid', 'Survived'),
        ('batman', 'Investigator', 'Solved it too late', 'Survived'),
        ('catwoman', 'Ally', 'Worked the case with him', 'Survived'),
        ('joker', 'Antagonist', 'Interfered with the investigation', 'Survived')]),

    ('hush_arc', 'Hush', 'DC', 'Comic arc', 2002, 2003,
     'An old friend orchestrates a year of attacks on Batman using every villain in Gotham, '
     'and the case ends with Catwoman and Batman closer than ever.',
     'Hush defeated; the Riddler revealed as the architect',
     'DC Comics (New Earth/Prime Earth)', [
        ('batman', 'Protagonist', 'Survived the campaign', 'Survived'),
        ('catwoman', 'Ally', 'Saved his life and learned his identity', 'Survived'),
        ('riddler', 'Antagonist', 'Architect of the plot', 'Survived'),
        ('poison_ivy', 'Antagonist', 'Controlled Catwoman against him', 'Survived')]),

    ('jla_tower_of_babel', 'Tower of Babel', 'DC', 'Comic arc', 2000, 2000,
     'Ra al Ghul steals Batman contingency plans for every Justice League member and uses '
     'them one by one, which is worse than beating them.',
     'League freed; Batman expelled from the team',
     'DC Comics (New Earth/Prime Earth)', [
        ('batman', 'Protagonist', 'Built the plans and then had to fix them', 'Survived'),
        ('ra_as_ghul', 'Antagonist', 'Used the plans against the League', 'Presumed dead'),
        ('superman', 'Victim', 'Taken down by a Kryptonite contingency', 'Survived'),
        ('wonder_woman', 'Victim', 'Drugged into a fight she could not win', 'Survived'),
        ('flash', 'Victim', 'Shot in the leg to force a seizure', 'Survived')]),

    ('blackest_night_event', 'Blackest Night', 'DC', 'Comic event', 2009, 2010,
     'The Black Lantern rings raise the dead across the universe and every Corps has to '
     'fight its own casualties.',
     'Black Lanterns defeated; the White Lantern entity appeared',
     'DC Comics (New Earth/Prime Earth)', [
        ('green_lantern', 'Corps commander', 'Led the Lantern alliance', 'Survived'),
        ('sinestro', 'Reluctant ally', 'Became a White Lantern briefly', 'Survived'),
        ('atrocitus', 'Reluctant ally', 'Fought alongside the Greens', 'Survived'),
        ('flash', 'Field support', 'Turned his own ring into a weapon', 'Survived')]),

    ('sinestro_corps_war', 'The Sinestro Corps War', 'DC', 'Comic event', 2007, 2007,
     'Sinestro builds a fear-powered Corps on Qward and attacks Oa, and the Guardians '
     'respond by rewriting their own laws.',
     'Sinestro captured; the Guardians authorised lethal force',
     'DC Comics (New Earth/Prime Earth)', [
        ('sinestro', 'Antagonist', 'Captured after the battle of Oa', 'Survived'),
        ('green_lantern', 'Corps defender', 'Held Oa', 'Survived'),
        ('green_lantern_john', 'Corps defender', 'Held the Mogo line', 'Survived'),
        ('atrocitus', 'Third party', 'Escaped with his own Corps', 'Survived')]),

    ('infinite_crisis_event', 'Infinite Crisis', 'DC', 'Comic event', 2005, 2006,
     'Alexander Luthor and Superboy-Prime pull Earth-Two back into existence and try to '
     'rebuild a single perfect Earth out of the survivors.',
     'Multiverse restored; Superboy-Prime imprisoned',
     'DC Comics (New Earth/Prime Earth)', [
        ('superman', 'Protagonist', 'Stopped the Superboy-Prime plan', 'Survived'),
        ('batman', 'Protagonist', 'Refused the rebuilt world', 'Survived'),
        ('wonder_woman', 'Protagonist', 'Killed Maxwell Lord and became a fugitive', 'Survived'),
        ('darkseid', 'Instigator', 'Manipulated the crisis from the shadows', 'Survived')]),

    ('dc_darkseid_war', 'The Darkseid War', 'DC', 'Comic event', 2015, 2016,
     'Darkseid and the Anti-Monitor fight a war across the multiverse with the Justice League '
     'as instruments, and Batman ends up sitting in a Mobius Chair.',
     'Anti-Monitor defeated; Darkseid killed; Batman briefly omniscient',
     'DC Comics (New Earth/Prime Earth)', [
        ('darkseid', 'Antagonist', 'Killed in the final confrontation', 'Killed'),
        ('batman', 'Protagonist', 'Took the Mobius Chair', 'Survived'),
        ('wonder_woman', 'Protagonist', 'Became the God of War', 'Survived'),
        ('flash', 'Protagonist', 'Ran the war fronts', 'Survived'),
        ('green_lantern', 'Protagonist', 'Held the air war', 'Survived')]),

    ('kingdom_come', 'Kingdom Come', 'DC', 'Comic arc', 1996, 1996,
     'A future in which the Justice League has retired and a new generation of heroes has '
     'started killing; the old guard returns to stop the war.',
     'Nuclear detonation; the League rebuilt the world afterwards',
     'DC Comics (New Earth/Prime Earth)', [
        ('superman', 'Protagonist', 'Returned from retirement', 'Survived'),
        ('wonder_woman', 'Protagonist', 'Led the intervention', 'Survived'),
        ('batman', 'Protagonist', 'Ran the resistance', 'Survived'),
        ('green_lantern', 'Supporting', 'Held the orbital front', 'Survived')]),

    ('no_mans_land', 'Batman: No Mans Land', 'DC', 'Comic arc', 1999, 2000,
     'An earthquake levels Gotham, the government abandons it and the city becomes a '
     'year-long territory war run by its own villains.',
     'Gotham rebuilt; Batman returned to the city',
     'DC Comics (New Earth/Prime Earth)', [
        ('batman', 'Protagonist', 'Took the city back block by block', 'Survived'),
        ('joker', 'Antagonist', 'Held territory and killed the mayor', 'Survived'),
        ('batgirl', 'Protagonist', 'Became Oracle during the crisis', 'Survived'),
        ('robin_tim', 'Supporting', 'Ran courier routes across no man land', 'Survived'),
        ('nightwing', 'Supporting', 'Held the south side', 'Survived')]),

    ('judas_contract', 'The Judas Contract', 'DC', 'Comic arc', 1984, 1984,
     'Terra is a mole inside the Teen Titans working for Deathstroke, and the team is picked '
     'apart from the inside.',
     'Terra killed; Deathstroke defeated; the team rebuilt',
     'DC Comics (New Earth/Prime Earth)', [
        ('deathstroke', 'Antagonist', 'Ran the contract against the Titans', 'Survived'),
        ('starfire', 'Protagonist', 'Took command after the betrayal', 'Survived'),
        ('nightwing', 'Protagonist', 'Captured and rescued', 'Survived'),
        ('raven', 'Protagonist', 'Held the team together', 'Survived'),
        ('beast_boy', 'Protagonist', 'Lost Terra', 'Survived')]),

    ('suicide_squad_missions', 'Task Force X: Belle Reve', 'DC', 'Comic arc', 1987, 1988,
     'Amanda Waller builds a squad of convicts with explosive collars and sends them on the '
     'missions the Justice League would refuse to authorise.',
     'Programme continued despite the body count',
     'DC Comics (New Earth/Prime Earth)', [
        ('amanda_waller', 'Director', 'Ran the programme', 'Survived'),
        ('deadshot', 'Marksman', 'Completed the mission and returned to prison', 'Survived'),
        ('harley_squad', 'Wildcard', 'Survived the collar', 'Survived'),
        ('killer_croc', 'Heavy assault', 'Left behind, then recovered', 'Survived'),
        ('black_manta', 'Aquatic operations', 'Turned on the squad, survived', 'Survived')]),

    ('legion_doom_plot', 'The Legion of Doom', 'DC', 'Comic event', 1978, 1979,
     'A villain coalition organised against the Justice League itself, and the first time '
     'the League had to fight an enemy that planned like they did.',
     'League broke the coalition; several members imprisoned',
     'DC Comics (New Earth/Prime Earth)', [
        ('lex_luthor', 'Founder', 'Organised the coalition', 'Survived'),
        ('joker', 'Member', 'Undermined the plan for fun', 'Survived'),
        ('cheetah', 'Member', 'Held the Wonder Woman front', 'Survived'),
        ('sinestro', 'Member', 'Lost the Lantern engagement', 'Survived'),
        ('reverse_flash', 'Member', 'Countered the Flash', 'Survived'),
        ('batman', 'Opposition', 'Broke the coalition planning', 'Survived')]),

    ('dceu_steppenwolf', 'The Steppenwolf Invasion', 'DC', 'Film saga', 2017, 2017,
     'Steppenwolf collects the three Mother Boxes on Earth, and the newly formed League has '
     'to stop him before Apokolips has a bridge.',
     'Steppenwolf killed; the Mother Boxes separated',
     'DCEU (Earth-1)', [
        ('dceu_batman', 'Founder', 'Assembled the team', 'Survived'),
        ('dceu_wonder_woman', 'Front-line commander', 'Killed Steppenwolf with Aquaman', 'Survived'),
        ('dceu_superman', 'Resurrected', 'Turned the battle', 'Survived'),
        ('dceu_flash', 'Speed support', 'Fed the League energy', 'Survived'),
        ('dceu_cyborg', 'Technology', 'Separated the boxes', 'Survived'),
        ('dceu_aquaman', 'Front line', 'Held the tunnel', 'Survived'),
        ('dceu_steppenwolf', 'Antagonist', 'Killed by the League', 'Killed')]),

    ('dceu_black_zero', 'The Battle of Metropolis', 'DC', 'Film saga', 2013, 2013,
     'Zod terraforms Earth into Krypton above Metropolis, and Superman has to destroy his '
     'own species to stop it.',
     'Zod killed; Metropolis levelled; Superman revealed',
     'DCEU (Earth-1)', [
        ('dceu_superman', 'Protagonist', 'Killed Zod', 'Survived'),
        ('dceu_zod', 'Antagonist', 'Killed by Superman', 'Killed'),
        ('dceu_batman', 'Witness', 'Watched Wayne Tower fall', 'Survived')]),

    ('dceu_task_force_x', 'The Midway City Mission', 'DC', 'Film saga', 2016, 2016,
     'Amanda Waller sends Task Force X into a city taken over by Enchantress to recover a '
     'high-value asset, and loses two members doing it.',
     'Enchantress defeated; the Squad honoured unofficially',
     'DCEU (Earth-1)', [
        ('dceu_amanda_waller', 'Director', 'Ran the mission from an office', 'Survived'),
        ('dceu_deadshot', 'Marksman', 'Killed Enchantress brother', 'Survived'),
        ('dceu_harley', 'Wildcard', 'Held the rooftop', 'Survived'),
        ('dceu_killer_croc', 'Heavy assault', 'Blew the tunnel', 'Survived'),
        ('dceu_captain_boomerang', 'Thief', 'Tried to desert and failed', 'Survived')]),

    ('dceu_atlantis_war', 'The War for the Throne of Atlantis', 'DC', 'Film saga', 2018, 2018,
     'Orm declares war on the surface and Arthur Curry has to win a trident and a duel to '
     'stop him.',
     'Orm deposed; Arthur crowned; the war called off',
     'DCEU (Earth-1)', [
        ('dceu_aquaman', 'Protagonist', 'Won the throne and the war', 'Survived'),
        ('dceu_orin', 'Antagonist', 'Deposed and imprisoned', 'Survived'),
        ('dceu_mera', 'Ally', 'Fought at Arthur side', 'Survived'),
        ('dceu_atlanna', 'Ally', 'Returned from the Trench', 'Survived'),
        ('dceu_black_manta', 'Antagonist', 'Lost the duel and survived', 'Survived')]),

    ('arrow_undertaking', 'The Undertaking', 'DC', 'Television saga', 2013, 2013,
     'Malcolm Merlyn plans to level the Glades with a seismic device, and Oliver Queen has '
     'to stop it with a bow and a small team.',
     'Device partially detonated; the Glades destroyed',
     'DC Comics (Arrowverse)', [
        ('green_arrow_tv', 'Protagonist', 'Stopped the second device', 'Survived'),
        ('john_diggle', 'Field support', 'Evacuated the Glades', 'Survived'),
        ('felicity_smoak', 'Technical lead', 'Disarmed the trigger', 'Survived'),
        ('black_canary_tv', 'Field support', 'Held the courthouse', 'Survived')]),

    ('arrow_savi_saga', 'The Savitar Saga', 'DC', 'Television saga', 2016, 2017,
     'Team Flash fights a speedster god who turns out to be a future version of Barry Allen, '
     'and the only way to win is to let him erase himself.',
     'Savitar erased; Iris survived',
     'DC Comics (Arrowverse)', [
        ('flash', 'Protagonist', 'Erased his own future self', 'Survived'),
        ('reverse_flash', 'Antagonist ally', 'Helped, for his own reasons', 'Unknown'),
        ('kara_danvers_cw', 'Crossover ally', 'Held the speedster fight', 'Survived')]),

    ('legends_savage', 'Vandal Savage and the Time Masters', 'DC', 'Television saga', 2016, 2016,
     'Rip Hunter assembles the Legends to stop Vandal Savage from rewriting history, and '
     'discovers the Time Masters were never on their side.',
     'Savage defeated; the Time Masters dissolved',
     'DC Comics (Arrowverse)', [
        ('rip_hunter', 'Convenor', 'Assembled and led the Legends', 'Survived'),
        ('green_arrow_tv', 'Crossover ally', 'Held 2016 Star City', 'Survived'),
        ('kara_danvers_cw', 'Crossover ally', 'Fought Savage in 1958', 'Survived')]),

    ('smallville_meteor', 'The Meteor Shower Years', 'DC', 'Television saga', 2001, 2011,
     'Clark Kent grows up in Smallville hiding what he is while kryptonite-powered threats '
     'and Lex Luthor friendship collapse around him.',
     'Clark accepted the cape; Lex became the enemy',
     'DC Comics (Smallville continuity)', [
        ('chloe_sullivan', 'Ally', 'Built Watchtower and kept every secret', 'Survived'),
        ('superman', 'Protagonist', 'Became Superman', 'Survived'),
        ('lex_luthor', 'Antagonist', 'Became the enemy', 'Survived')]),

    ('orig_lantern_circle', 'The Lantern Relief Accord', 'DC', 'Crossover', 2021, 2022,
     'Original addition — a disaster-relief pact between unaffiliated heroes and two Lantern '
     'sectors, written for this demonstration as a small-scale coordination exercise.',
     'Accord signed; the Blue Lantern Circle formed',
     'DC Comics (New Earth/Prime Earth)', [
        ('orig_lumen', 'Coordinator', 'Drafted and signed the accord', 'Survived'),
        ('orig_silica', 'Technical support', 'Built the relay network', 'Survived'),
        ('green_lantern_john', 'Corps liaison', 'Signed for Sector 2814', 'Survived'),
        ('orig_quiet_hour', 'Saboteur', 'Attempted to void the accord', 'Survived')]),
]

MISSIONS += [
    ('mcu_kang_dynasty', 'The Kang Dynasty', 'Marvel', 'Film saga', 2023, 2025,
     'The MCU council of Kangs begins moving between branches after the sacred timeline '
     'ends, and the Avengers franchise is rebuilt around stopping them.',
     'Ongoing; the multiverse is unmanaged',
     'Marvel Cinematic Universe (Earth-199999)', [
        ('mcu_he_who_remains', 'Antagonist origin', 'Killed at the end of time', 'Killed'),
        ('mcu_doctor_strange', 'Field lead', 'Held the incursion line', 'Survived'),
        ('mcu_spider_man', 'Field support', 'Unknown to the councils by choice', 'Survived'),
        ('mcu_loki', 'Anomaly', 'Holding the branches together', 'Survived')]),

    ('avengers_standoff', 'The Avengers: Standoff', 'Marvel', 'Comic event', 2016, 2016,
     'SHIELD replaces the town of Pleasant Hill with a prison for supervillains whose minds '
     'have been rewritten, and the heroes find out from the inside.',
     'Pleasant Hill exposed; trust in SHIELD broken again',
     'Marvel Comics (Earth-616)', [
        ('captain_america', 'Opposition', 'Led the breakout', 'Survived'),
        ('winter_soldier', 'Opposition', 'Held the perimeter', 'Survived'),
        ('nick_fury', 'Responsible party', 'Ran the programme as SHIELD', 'Survived'),
        ('taskmaster', 'Prisoner', 'Escaped during the breakout', 'Survived')]),

    ('dc_trinity_war', 'Trinity War', 'DC', 'Comic event', 2013, 2013,
     'A murder with a Justice League weapon turns the League, Justice League Dark and the '
     'Justice League of America against each other.',
     'The factions fractured; the Crime Syndicate followed',
     'DC Comics (New Earth/Prime Earth)', [
        ('batman', 'Investigator', 'Refused the official version', 'Survived'),
        ('superman', 'Suspect', 'Cleared only after the war', 'Survived'),
        ('wonder_woman', 'Suspect', 'Held the Amazon position', 'Survived'),
        ('constantine', 'Justice League Dark', 'Supplied the occult evidence', 'Survived')]),

    ('dc_forever_evil', 'Forever Evil', 'DC', 'Comic event', 2013, 2014,
     'The Crime Syndicate of Earth-3 replaces the Justice League and the villains of Earth '
     'have to save it, which is the joke and the point.',
     'Crime Syndicate defeated; the League restored',
     'DC Comics (New Earth/Prime Earth)', [
        ('lex_luthor', 'Reluctant protagonist', 'Led the villain resistance', 'Survived'),
        ('black_manta', 'Reluctant ally', 'Fought the Syndicate at sea', 'Survived'),
        ('captain_cold', 'Reluctant ally', 'Froze the Syndicate line', 'Survived'),
        ('batman', 'Captured', 'Held prisoner by the Syndicate', 'Survived')]),
]
