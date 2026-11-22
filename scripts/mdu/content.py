"""Films and series for the Marvel & DC Universe Database.

95 titles across the MCU, the Infinity Saga and Multiverse Saga, the DCEU, the Dark
Knight trilogy, the Arrowverse, pre-MCU superhero cinema and animation.

Columns:
    (title, universe, release_year, content_type, director, studio,
     duration_minutes, rating, synopsis, continuity)

`director` is the credited director of a film, or the credited pilot director of a
series. Where the pilot director is not established here, the value is None rather
than guessed — the data dictionary states that None means "not established", and the
validation report counts it. `duration_minutes` is the theatrical runtime for a film
and the typical episode length for a series; the synopsis states the episode count.
"""

CONTENT = [
    # ------------------------- MCU — Infinity Saga --------------------------
    ('Iron Man', 'Marvel', 2008, 'Film', 'Jon Favreau', 'Marvel Studios', 126, 'PG-13',
     'Weapons engineer Tony Stark is captured in Afghanistan, builds an armoured suit in a cave '
     'and returns home to shut down the business that armed his captors.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('The Incredible Hulk', 'Marvel', 2008, 'Film', 'Louis Leterrier', 'Marvel Studios', 112, 'PG-13',
     'Bruce Banner hides from the US Army while hunting a cure for the gamma accident that turns '
     'him into the Hulk, until Emil Blonsky forces the fight he was avoiding.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Iron Man 2', 'Marvel', 2010, 'Film', 'Jon Favreau', 'Marvel Studios', 124, 'PG-13',
     'Tony Stark faces a Senate subpoena over the suit, a dying reactor and Ivan Vanko, a '
     'physicist with a grudge and a weaponised whip.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Thor', 'Marvel', 2011, 'Film', 'Kenneth Branagh', 'Marvel Studios', 115, 'PG-13',
     'Odin exiles a reckless Thor to Earth, where he learns humility while Loki takes the throne '
     'of Asgard and lets the Frost Giants in.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Captain America: The First Avenger', 'Marvel', 2011, 'Film', 'Joe Johnston', 'Marvel Studios', 124, 'PG-13',
     'Scrawny volunteer Steve Rogers becomes the Super-Soldier Captain America, leads the Howling '
     'Commandos against HYDRA and loses seventy years to the ice.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('The Avengers', 'Marvel', 2012, 'Film', 'Joss Whedon', 'Marvel Studios', 143, 'PG-13',
     'Nick Fury assembles six heroes to stop Loki and the Chitauri army over New York, proving '
     'the Avengers Initiative only on the third attempt.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Iron Man 3', 'Marvel', 2013, 'Film', 'Shane Black', 'Marvel Studios', 130, 'PG-13',
     'Stripped of his suits by a terrorist called the Mandarin, Tony Stark rebuilds himself from '
     'a hardware-store haul and a bad night in Tennessee.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Thor: The Dark World', 'Marvel', 2013, 'Film', 'Alan Taylor', 'Marvel Studios', 112, 'PG-13',
     'The Dark Elf Malekith hunts the Aether, forcing Thor into an alliance with the imprisoned '
     'Loki and a final fight across the Nine Realms.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Captain America: The Winter Soldier', 'Marvel', 2014, 'Film', 'Anthony and Joe Russo', 'Marvel Studios', 136, 'PG-13',
     'Steve Rogers discovers HYDRA has grown inside SHIELD, and that the assassin sent to stop '
     'him is his oldest friend.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Guardians of the Galaxy', 'Marvel', 2014, 'Film', 'James Gunn', 'Marvel Studios', 121, 'PG-13',
     'Peter Quill steals an orb that half the galaxy wants, and accidentally forms a team with a '
     'tree, a raccoon, an assassin and a literalist.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Avengers: Age of Ultron', 'Marvel', 2015, 'Film', 'Joss Whedon', 'Marvel Studios', 141, 'PG-13',
     'Tony Stark peacekeeping AI decides humanity is the threat, and the Avengers have to undo '
     'their own best idea in a floating Sokovian city.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Ant-Man', 'Marvel', 2015, 'Film', 'Peyton Reed', 'Marvel Studios', 117, 'PG-13',
     'Ex-convict Scott Lang inherits Hank Pym shrinking suit and a heist that has to be pulled '
     'off inside a corporate headquarters.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Captain America: Civil War', 'Marvel', 2016, 'Film', 'Anthony and Joe Russo', 'Marvel Studios', 147, 'PG-13',
     'The Sokovia Accords split the Avengers into two camps, and a HYDRA file turns the argument '
     'personal for both Steve Rogers and Tony Stark.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Doctor Strange', 'Marvel', 2016, 'Film', 'Scott Derrickson', 'Marvel Studios', 115, 'PG-13',
     'A surgeon who loses his hands finds Kamar-Taj, the Time Stone and a bargain with Dormammu '
     'that he wins by refusing to stop losing.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Guardians of the Galaxy Vol. 2', 'Marvel', 2017, 'Film', 'James Gunn', 'Marvel Studios', 136, 'PG-13',
     'Peter Quill meets his father Ego, discovers what Ego actually does to planets, and learns '
     'that the family he chose was the point all along.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Spider-Man: Homecoming', 'Marvel', 2017, 'Film', 'Jon Watts', 'Marvel Studios', 133, 'PG-13',
     'Peter Parker returns to Queens after Berlin and wants a bigger role, while Adrian Toomes '
     'sells alien salvage under everyone notice.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Thor: Ragnarok', 'Marvel', 2017, 'Film', 'Taika Waititi', 'Marvel Studios', 130, 'PG-13',
     'Thor loses his hammer, his hair and his home in one week, and has to win a gladiator fight '
     'on Sakaar to stop Hela and save the Asgardians instead of Asgard.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Black Panther', 'Marvel', 2018, 'Film', 'Ryan Coogler', 'Marvel Studios', 134, 'PG-13',
     'T Challa takes the Wakandan throne and loses it to Erik Killmonger, whose argument about '
     'the world outside is harder to answer than his challenge.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Avengers: Infinity War', 'Marvel', 2018, 'Film', 'Anthony and Joe Russo', 'Marvel Studios', 149, 'PG-13',
     'Thanos collects six Infinity Stones while the Avengers split across three fronts, and wins '
     'anyway; half of all life is erased with a snap.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Ant-Man and the Wasp', 'Marvel', 2018, 'Film', 'Peyton Reed', 'Marvel Studios', 118, 'PG-13',
     'Scott Lang serves house arrest and joins Hope van Dyne on a rescue from the Quantum Realm, '
     'which is where the film leaves him when the Snap lands.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Captain Marvel', 'Marvel', 2019, 'Film', 'Anna Boden and Ryan Fleck', 'Marvel Studios', 123, 'PG-13',
     'Kree soldier Vers discovers she is Carol Danvers, an Air Force pilot betrayed by the empire '
     'that trained her, and stops a war she started.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Avengers: Endgame', 'Marvel', 2019, 'Film', 'Anthony and Joe Russo', 'Marvel Studios', 181, 'PG-13',
     'Five years after the Snap, the surviving Avengers borrow time itself to undo it, and lose '
     'Natasha Romanoff and Tony Stark to get everyone else back.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Spider-Man: Far From Home', 'Marvel', 2019, 'Film', 'Jon Watts', 'Marvel Studios', 129, 'PG-13',
     'A grieving Peter Parker takes a school trip to Europe, is handed Tony Stark posthumous '
     'responsibility and is lied to by Quentin Beck for two acts.',
     'Marvel Cinematic Universe (Earth-199999)'),
    # ------------------------- MCU — Multiverse Saga ------------------------
    ('Black Widow', 'Marvel', 2021, 'Film', 'Cate Shortland', 'Marvel Studios', 134, 'PG-13',
     'Between Civil War and Infinity War, Natasha Romanoff confronts the Red Room, the family she '
     'was assigned and the ledger she has been trying to clear.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Shang-Chi and the Legend of the Ten Rings', 'Marvel', 2021, 'Film', 'Destin Daniel Cretton', 'Marvel Studios', 132, 'PG-13',
     'Valet Shang-Chi is dragged back into the Ten Rings and the family business by a father who '
     'will open a gate to reach a voice he should not trust.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Eternals', 'Marvel', 2021, 'Film', 'Chloe Zhao', 'Marvel Studios', 156, 'PG-13',
     'Immortals who were told not to interfere watch human history from the sidelines, then '
     'discover what they were actually sent to prepare, and split over it.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Spider-Man: No Way Home', 'Marvel', 2021, 'Film', 'Jon Watts', 'Marvel Studios', 148, 'PG-13',
     'A botched spell brings villains from other universes into Peter Parker\'s world, and the only '
     'way out costs him every memory anyone has of him.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Doctor Strange in the Multiverse of Madness', 'Marvel', 2022, 'Film', 'Sam Raimi', 'Marvel Studios', 126, 'PG-13',
     'Stephen Strange protects America Chavez from a Scarlet Witch who will burn every universe '
     'to reach a version of her children that exists.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Thor: Love and Thunder', 'Marvel', 2022, 'Film', 'Taika Waititi', 'Marvel Studios', 119, 'PG-13',
     'Gorr hunts gods and Thor has to reassemble a team, including Jane Foster wielding a rebuilt '
     'Mjolnir and a terminal diagnosis.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Black Panther: Wakanda Forever', 'Marvel', 2022, 'Film', 'Ryan Coogler', 'Marvel Studios', 161, 'PG-13',
     'Wakanda grieves its king while a newly revealed underwater nation demands an alliance, and '
     'Shuri has to decide what the Black Panther is for.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Ant-Man and the Wasp: Quantumania', 'Marvel', 2023, 'Film', 'Peyton Reed', 'Marvel Studios', 124, 'PG-13',
     'The Lang family is pulled into the Quantum Realm, where Kang the Conqueror has been '
     'exiled and is building a way out at any universe cost.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Guardians of the Galaxy Vol. 3', 'Marvel', 2023, 'Film', 'James Gunn', 'Marvel Studios', 150, 'PG-13',
     'Rocket backstory is the plot: the High Evolutionary wants his experiment back and the '
     'Guardians have to survive the answer to what Rocket is.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('WandaVision', 'Marvel', 2021, 'Television series', 'Matt Shakman', 'Marvel Studios', 40, 'TV-14',
     'Nine episodes. Wanda Maximoff builds a sitcom reality in Westview around her grief, and the '
     'town underneath it is screaming.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('The Falcon and the Winter Soldier', 'Marvel', 2021, 'Television series', 'Kari Skogland', 'Marvel Studios', 50, 'TV-14',
     'Six episodes. Sam Wilson and Bucky Barnes argue over the shield, the Flag Smashers and what '
     'a Black Captain America is actually being asked to represent.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Loki', 'Marvel', 2021, 'Television series', 'Kate Herron', 'Marvel Studios', 48, 'TV-14',
     'Six episodes. A variant of Loki is arrested by the Time Variance Authority and ends up '
     'helping decide whether the timeline should have one branch or many.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Hawkeye', 'Marvel', 2021, 'Television series', 'Rhys Thomas', 'Marvel Studios', 45, 'TV-14',
     'Six episodes. Clint Barton tries to get home for Christmas and instead deals with the Ronin '
     'suit, the Tracksuit Mafia and Kate Bishop.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Moon Knight', 'Marvel', 2022, 'Television series', 'Mohamed Diab', 'Marvel Studios', 47, 'TV-14',
     'Six episodes. Marc Spector and Steven Grant share a body, a job for Khonshu and an '
     'obligation to stop Arthur Harrow from judging the world.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('She-Hulk: Attorney at Law', 'Marvel', 2022, 'Television series', 'Kat Coiro', 'Marvel Studios', 35, 'TV-14',
     'Nine episodes. Jennifer Walters inherits her cousin gamma condition and a legal practice '
     'specialising in superhuman clients.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Ms. Marvel', 'Marvel', 2022, 'Television series', 'Adil El Arbi and Bilall Fallah', 'Marvel Studios', 45, 'TV-14',
     'Six episodes. Jersey City teenager Kamala Khan finds a family bangle that gives her hard '
     'light and a very complicated origin.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Secret Invasion', 'Marvel', 2023, 'Television series', 'Ali Selim', 'Marvel Studios', 50, 'TV-14',
     'Six episodes. Nick Fury returns to Earth to stop a Skrull faction that has spent thirty '
     'years inside every government worth infiltrating.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Daredevil', 'Marvel', 2015, 'Television series', 'Phil Abraham', 'Marvel Television', 54, 'TV-MA',
     'Three seasons. Blind lawyer Matt Murdock works Hell Kitchen by day and by night against '
     'Wilson Fisk, the Hand and his own conscience.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Jessica Jones', 'Marvel', 2015, 'Television series', 'S. J. Clarkson', 'Marvel Television', 50, 'TV-MA',
     'Three seasons. A private investigator with super strength and no patience takes the case '
     'that put Kilgrave in her head in the first place.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Luke Cage', 'Marvel', 2016, 'Television series', 'Paul McGuigan', 'Marvel Television', 52, 'TV-MA',
     'Two seasons. A bulletproof ex-convict becomes the reluctant hero of Harlem and then has to '
     'decide whether to take the neighbourhood institution instead.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Iron Fist', 'Marvel', 2017, 'Television series', 'John Dahl', 'Marvel Television', 55, 'TV-MA',
     'Two seasons. Danny Rand returns to New York with a glowing fist, a claim on a company and '
     'no idea how either of them works.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('The Defenders', 'Marvel', 2017, 'Television series', 'S. J. Clarkson', 'Marvel Television', 50, 'TV-MA',
     'Eight episodes. Four street-level heroes are dragged into the same fight with the Hand and '
     'spend most of it arguing about jurisdiction.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Agents of SHIELD', 'Marvel', 2013, 'Television series', 'Joss Whedon', 'Marvel Television', 45, 'TV-14',
     'Seven seasons. Phil Coulson runs a small SHIELD team through the fall of the agency, the '
     'Inhumans and eventually the end of the world.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Agent Carter', 'Marvel', 2015, 'Television series', 'Louis D Esposito', 'Marvel Television', 43, 'TV-14',
     'Two seasons. Peggy Carter fights for a job at the Strategic Scientific Reserve while '
     'clearing Howard Stark\'s name in 1946 New York.',
     'Marvel Cinematic Universe (Earth-199999)'),
    # ------------------------------ DCEU ------------------------------------
    ('Man of Steel', 'DC', 2013, 'Film', 'Zack Snyder', 'Warner Bros. Pictures', 143, 'PG-13',
     'Kal-El grows up hiding his powers in Kansas, reveals himself to stop Zod, and levels '
     'Metropolis in the process.',
     'DCEU (Earth-1)'),
    ('Batman v Superman: Dawn of Justice', 'DC', 2016, 'Film', 'Zack Snyder', 'Warner Bros. Pictures', 151, 'PG-13',
     'Bruce Wayne decides Superman is too dangerous to leave alive, Lex Luthor arranges the fight, '
     'and Doomsday ends it.',
     'DCEU (Earth-1)'),
    ('Suicide Squad', 'DC', 2016, 'Film', 'David Ayer', 'Warner Bros. Pictures', 123, 'PG-13',
     'Amanda Waller sends a squad of collared convicts into Midway City to clean up an '
     'enchantress problem the government created.',
     'DCEU (Earth-1)'),
    ('Wonder Woman', 'DC', 2017, 'Film', 'Patty Jenkins', 'Warner Bros. Pictures', 141, 'PG-13',
     'Diana leaves Themyscira with Steve Trevor to end the First World War, and learns what Ares '
     'was actually selling.',
     'DCEU (Earth-1)'),
    ('Justice League', 'DC', 2017, 'Film', 'Zack Snyder', 'Warner Bros. Pictures', 120, 'PG-13',
     'Bruce Wayne assembles a team to stop Steppenwolf collecting the Mother Boxes, and the '
     'resurrection of Superman is the only plan that works.',
     'DCEU (Earth-1)'),
    ('Aquaman', 'DC', 2018, 'Film', 'James Wan', 'Warner Bros. Pictures', 143, 'PG-13',
     'Arthur Curry has to take the Atlantean throne to stop his half-brother from starting a war '
     'with the surface, which requires a trident and a lot of water.',
     'DCEU (Earth-1)'),
    ('Shazam!', 'DC', 2019, 'Film', 'David F. Sandberg', 'Warner Bros. Pictures', 132, 'PG-13',
     'Foster kid Billy Batson says a word and becomes a superhero, then has to learn what the '
     'job costs before Thaddeus Sivana takes the powers back.',
     'DCEU (Earth-1)'),
    ('Birds of Prey (and the Fantabulous Emancipation of One Harley Quinn)', 'DC', 2020, 'Film', 'Cathy Yan', 'Warner Bros. Pictures', 109, 'R',
     'Harley Quinn breaks up with the Joker and every bounty hunter in Gotham realises she is no '
     'longer protected, which is how the Birds of Prey happen.',
     'DCEU (Earth-1)'),
    ('Wonder Woman 1984', 'DC', 2020, 'Film', 'Patty Jenkins', 'Warner Bros. Pictures', 151, 'PG-13',
     'A wish-granting stone gives Diana back Steve Trevor and gives everyone else exactly what '
     'they asked for, which is the problem.',
     'DCEU (Earth-1)'),
    ('The Suicide Squad', 'DC', 2021, 'Film', 'James Gunn', 'Warner Bros. Pictures', 132, 'R',
     'Two squads go to Corto Maltese; the decoy one dies immediately, and the real mission turns '
     'out to be about covering up an American experiment.',
     'DCEU (Earth-1)'),
    ('Black Adam', 'DC', 2022, 'Film', 'Jaume Collet-Serra', 'Warner Bros. Pictures', 125, 'PG-13',
     'An ancient champion wakes in Kahndaq with the power of the gods and none of the restraint, '
     'and the Justice Society is sent to explain restraint to him.',
     'DCEU (Earth-1)'),
    ('Shazam! Fury of the Gods', 'DC', 2023, 'Film', 'David F. Sandberg', 'Warner Bros. Pictures', 130, 'PG-13',
     'The Daughters of Atlas come to reclaim their father power, and Billy Batson discovers that '
     'being one of six superheroes does not make him an adult.',
     'DCEU (Earth-1)'),
    ('The Flash', 'DC', 2023, 'Film', 'Andy Muschietti', 'Warner Bros. Pictures', 144, 'PG-13',
     'Barry Allen runs back to save his mother and finds that a single change has rewritten the '
     'world into one where Michael Keaton Batman is still working.',
     'DCEU (Earth-1)'),
    ('Blue Beetle', 'DC', 2023, 'Film', 'Angel Manuel Soto', 'Warner Bros. Pictures', 127, 'PG-13',
     'Jaime Reyes is chosen by an alien scarab and has to keep it away from Kord Industries while '
     'his whole family insists on helping.',
     'DCEU (Earth-1)'),
    ('Aquaman and the Lost Kingdom', 'DC', 2023, 'Film', 'James Wan', 'Warner Bros. Pictures', 124, 'PG-13',
     'Arthur Curry has to break his half-brother out of prison to stop Black Manta using ancient '
     'Atlantean weapons on the surface.',
     'DCEU (Earth-1)'),
    # --------------- Other DC film continuities (clearly separated) ---------
    ('Batman Begins', 'DC', 2005, 'Film', 'Christopher Nolan', 'Warner Bros. Pictures', 140, 'PG-13',
     'Bruce Wayne trains with the League of Shadows, returns to Gotham and builds a symbol that '
     'criminals can be afraid of.',
     'DC Comics (Dark Knight Trilogy)'),
    ('The Dark Knight', 'DC', 2008, 'Film', 'Christopher Nolan', 'Warner Bros. Pictures', 152, 'PG-13',
     'The Joker proves that every institution in Gotham can be turned, and Batman takes the blame '
     'for the crimes that keep the city believing in Harvey Dent.',
     'DC Comics (Dark Knight Trilogy)'),
    ('The Dark Knight Rises', 'DC', 2012, 'Film', 'Christopher Nolan', 'Warner Bros. Pictures', 165, 'PG-13',
     'Bane takes Gotham hostage with a nuclear bomb and a class war, and a broken Batman has to '
     'climb out of the only prison that ever held him.',
     'DC Comics (Dark Knight Trilogy)'),
    ('Superman', 'DC', 1978, 'Film', 'Richard Donner', 'Warner Bros. Pictures', 143, 'PG',
     'Jor-El sends his son to Earth, where Clark Kent grows into Superman and Lex Luthor plans a '
     'real-estate scheme with a nuclear missile.',
     'DC Comics (1978 Film Series)'),
    ('Batman', 'DC', 1989, 'Film', 'Tim Burton', 'Warner Bros. Pictures', 126, 'PG-13',
     'A new kind of criminal called the Joker takes over Gotham\'s crime, and Batman has a personal '
     'reason to end him.',
     'DC Comics (Burton Film Series)'),
    ('Spider-Man', 'Marvel', 2002, 'Film', 'Sam Raimi', 'Columbia Pictures', 121, 'PG-13',
     'Peter Parker is bitten, loses his uncle, and learns the lesson too late against the Green '
     'Goblin.',
     'Marvel Comics (Raimi Film Series)'),
    ('Spider-Man 2', 'Marvel', 2004, 'Film', 'Sam Raimi', 'Columbia Pictures', 127, 'PG-13',
     'Peter Parker quits the costume, and Otto Octavius becomes a four-armed problem that only '
     'Spider-Man can talk down.',
     'Marvel Comics (Raimi Film Series)'),
    ('X-Men', 'Marvel', 2000, 'Film', 'Bryan Singer', '20th Century Fox', 104, 'PG-13',
     'A mutant registration bill, a wary Wolverine and Magneto plan to turn every world leader '
     'into a mutant at the Statue of Liberty.',
     'Marvel Comics (X-Men Film Series)'),
    ('X2: X-Men United', 'Marvel', 2003, 'Film', 'Bryan Singer', '20th Century Fox', 134, 'PG-13',
     'Colonel Stryker attacks the school and the X-Men have to work with Magneto to stop a plan '
     'that uses Cerebro to kill every mutant on Earth.',
     'Marvel Comics (X-Men Film Series)'),
    ('Blade', 'Marvel', 1998, 'Film', 'Stephen Norrington', 'New Line Cinema', 120, 'R',
     'The Daywalker hunts vampires through a blood-rave opening and stops Deacon Frost from '
     'summoning the blood god La Magra.',
     'Marvel Comics (Blade Film Series)'),
    ('Fantastic Four', 'Marvel', 2005, 'Film', 'Tim Story', '20th Century Fox', 106, 'PG-13',
     'A cosmic storm gives four astronauts powers and turns Victor Von Doom into the problem they '
     'cannot solve as a family.',
     'Marvel Comics (Fantastic Four Film Series)'),
    ('Deadpool', 'Marvel', 2016, 'Film', 'Tim Miller', '20th Century Fox', 108, 'R',
     'Mercenary Wade Wilson is cured of cancer by an experiment that leaves him scarred, and '
     'spends the film breaking the fourth wall and hunting the man responsible.',
     'Marvel Comics (X-Men Film Series)'),
    ('Logan', 'Marvel', 2017, 'Film', 'James Mangold', '20th Century Fox', 137, 'R',
     'An ageing Wolverine drives a limousine in 2029, cares for a failing Professor X and has to '
     'escort a child who was made the same way he was.',
     'Marvel Comics (X-Men Film Series)'),
    ('Venom', 'Marvel', 2018, 'Film', 'Ruben Fleischer', 'Sony Pictures', 112, 'PG-13',
     'Reporter Eddie Brock bonds with a symbiote that would rather eat people, and the pair stop '
     'the Life Foundation from evacuating Earth for its own good.',
     'Marvel Comics (Spider-Man Universe)'),
    ('Spider-Man: Into the Spider-Verse', 'Marvel', 2018, 'Animated film', 'Bob Persichetti, Peter Ramsey and Rodney Rothman', 'Sony Pictures Animation', 117, 'PG',
     'Miles Morales is bitten in a world already losing Spider-Man, and a collider brings five '
     'other Spiders through to teach him the leap of faith.',
     'Marvel Comics (Spider-Verse)'),
    ('X-Men: The Animated Series', 'Marvel', 1992, 'Animated series', 'Larry Houston', 'Fox Kids', 22, 'TV-Y7',
     'Five seasons. The X-Men of the animated era run the Savage Land, Genosha and Days of Future '
     'Past in twenty-two minutes each.',
     'Marvel Comics (X-Men Animation)'),
    ('Spider-Man: The Animated Series', 'Marvel', 1994, 'Animated series', None, 'Fox Kids', 21, 'TV-Y7',
     'Five seasons. Peter Parker balances graduate school, a Daily Bugle job and a rogues '
     'gallery that keeps getting larger.',
     'Marvel Comics (Spider-Man Animation)'),
    # --------------------------- Arrowverse --------------------------------
    ('Arrow', 'DC', 2012, 'Television series', 'David Nutter', 'Warner Bros. Television', 42, 'TV-14',
     'Eight seasons. Oliver Queen returns from Lian Yu with a list of names, a bow and a plan, '
     'then spends eight years becoming something other than a killer.',
     'DC Comics (Arrowverse)'),
    ('The Flash', 'DC', 2014, 'Television series', 'David Nutter', 'Warner Bros. Television', 43, 'TV-14',
     'Nine seasons. Barry Allen wakes from a lightning coma in a world that now has metahumans, '
     'and speedsters who want his life.',
     'DC Comics (Arrowverse)'),
    ('Supergirl', 'DC', 2015, 'Television series', 'Glen Winter', 'Warner Bros. Television', 43, 'TV-14',
     'Six seasons. Kara Danvers works at CatCo and saves National City, and keeps being told she '
     'is not her cousin.',
     'DC Comics (Arrowverse)'),
    ('Legends of Tomorrow', 'DC', 2016, 'Television series', 'Glen Winter', 'Warner Bros. Television', 43, 'TV-14',
     'Seven seasons. Rip Hunter assembles a thief, a historian, two firestorm halves and a '
     'reincarnated guard, and the plan collapses within the first episode.',
     'DC Comics (Arrowverse)'),
    ('Smallville', 'DC', 2001, 'Television series', 'David Nutter', 'Warner Bros. Television', 43, 'TV-PG',
     'Ten seasons. Clark Kent grows up in Kansas before the cape, and the show is about what a '
     'secret does to a family.',
     'DC Comics (Smallville continuity)'),
    ('Titans', 'DC', 2018, 'Television series', 'Brad Anderson', 'DC Universe', 45, 'TV-MA',
     'Four seasons. Dick Grayson walks away from Batman and finds a group of young heroes who '
     'need an adult, which is the job he is least prepared for.',
     'DC Comics (Titans Series)'),
    ('Doom Patrol', 'DC', 2019, 'Television series', None, 'DC Universe', 50, 'TV-MA',
     'Four seasons. The Chief collects people the world cannot use and gives them a mansion, a '
     'mission and a very strange support group.',
     'DC Comics (Titans Series)'),
    ('Batman: The Animated Series', 'DC', 1992, 'Animated series', 'Kevin Altieri', 'Warner Bros. Animation', 22, 'TV-PG',
     'Four seasons. The definitive animated Batman: noir staging, a full rogues gallery and the '
     'best Mr Freeze episode anyone has written.',
     'DC Comics (DCAU)'),
    ('Justice League', 'DC', 2001, 'Animated series', None, 'Warner Bros. Animation', 22, 'TV-PG',
     'Two seasons. Seven heroes form a team after an alien invasion reveals how badly Earth needs '
     'one.',
     'DC Comics (DCAU)'),
    # ------------------ Other Marvel screen continuities --------------------
    ('Spider-Man (1967 Series)', 'Marvel', 1967, 'Animated series', None, 'Grantray-Lawrence Animation', 15, 'TV-G',
     'Three seasons. The first animated Spider-Man, with a theme song that outlived the show.',
     'Marvel Comics (Spider-Man Animation)'),
    ('The Avengers: Earth Mightiest Heroes', 'Marvel', 2010, 'Animated series', None, 'Film Roman', 22, 'TV-Y7',
     'Two seasons. The animated Avengers form out of four separate breakout shorts and fight '
     'Kang in the first two minutes.',
     'Marvel Comics (Avengers Animation)'),
]

# ---------------------------------------------------------------------------
# Ten further titles: the current MCU slate and the standalone DC films and
# series, each labelled with its own continuity.
# ---------------------------------------------------------------------------
CONTENT += [
    ('Deadpool & Wolverine', 'Marvel', 2024, 'Film', 'Shawn Levy', 'Marvel Studios', 128, 'R',
     'Wade Wilson is recruited by the Time Variance Authority to matter again, and drags a '
     'reluctant Wolverine variant across the multiverse to keep his own timeline alive.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('The Marvels', 'Marvel', 2023, 'Film', 'Nia DaCosta', 'Marvel Studios', 105, 'PG-13',
     'Carol Danvers, Kamala Khan and Monica Rambeau swap places every time they use their '
     'powers, which makes stopping a Kree civil war considerably harder.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Werewolf by Night', 'Marvel', 2022, 'Television special', 'Michael Giacchino', 'Marvel Studios', 53, 'TV-14',
     'A black-and-white monster-hunter gathering turns into a hunt for the hunters when the '
     'Bloodstone is claimed by something that is not a monster at all.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('Captain America: Brave New World', 'Marvel', 2025, 'Film', 'Julius Onah', 'Marvel Studios', 118, 'PG-13',
     'Sam Wilson is the new Captain America and has to stop a plot built on the same serum that '
     'made the last one, with a president turning red on live television.',
     'Marvel Cinematic Universe (Earth-199999)'),
    ('The Batman', 'DC', 2022, 'Film', 'Matt Reeves', 'Warner Bros. Pictures', 176, 'PG-13',
     'In year two, Batman follows the Riddler through a corruption map of Gotham and discovers '
     'that the renewal fund and his own family name are on it.',
     'DC Comics (Reeves Film Series)'),
    ('Joker', 'DC', 2019, 'Film', 'Todd Phillips', 'Warner Bros. Pictures', 122, 'R',
     'Failed comedian Arthur Fleck is ground down by Gotham until the city riots for him, and '
     'the film is about the crowd rather than the clown.',
     'DC Comics (Joker Film Series)'),
    ('Peacemaker', 'DC', 2022, 'Television series', 'James Gunn', 'Warner Bros. Television', 44, 'TV-MA',
     'Eight episodes. Christopher Smith kills a lot of people for peace, and the show is mostly '
     'about a grown man learning to be a decent one.',
     'DC Comics (DCEU)'),
    ('Watchmen', 'DC', 2009, 'Film', 'Zack Snyder', 'Warner Bros. Pictures', 162, 'R',
     'Retired masked heroes investigate the murder of a government asset and uncover a plot to '
     'unite humanity by sacrificing a city.',
     'DC Comics (Vertigo)'),
    ('Constantine', 'DC', 2005, 'Film', 'Francis Lawrence', 'Warner Bros. Pictures', 121, 'R',
     'John Constantine smoke-hunts a demonic incursion while dying of lung cancer and looking '
     'for a way to buy his soul back with a favour.',
     'DC Comics (Vertigo)'),
    ('Superman & Lois', 'DC', 2021, 'Television series', 'Lee Toland Krieger', 'Warner Bros. Television', 43, 'TV-14',
     'Four seasons. Clark and Lois raise two sons in Smallville while Superman fights a world '
     'that is running out of patience with him.',
     'DC Comics (Arrowverse)'),
]
