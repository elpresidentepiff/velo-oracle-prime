"""
Kempton 4:40 Race Data
Date: October 15, 2025
Track: Kempton (All-Weather)
"""

race_info = {
    "track": "Kempton",
    "time": "16:40",
    "date": "2025-10-15",
    "surface": "All-Weather",
    "race_type": "Flat"
}

# Complete field with all available data
runners = [
    {
        "position": 1,
        "name": "Hierarchy",
        "draw": 3,
        "jockey": "Toby Moore",
        "jockey_claim": 7,
        "trainer": "J A Osborne",
        "form_id": "921531",
        "weight": "9-9",
        "age": 6,
        "current_odds": 4.00,
        "odds_movement": [3.75, 4.00, 3.75],
        "official_rating": 75,
        "speed_figures": [71, 70, 70, 75, 72, 71, 71],
        # Statistics from images
        "going_record": {"wins": 0, "runs": 9, "win_rate": 0},
        "distance_record": {"wins": 5, "runs": 40, "win_rate": 13},
        "course_record": {"wins": 0, "runs": 9, "win_rate": 0},
        "jockey_stats": {
            "last_14_days": {"wins": 0, "runs": 1, "win_rate": 0, "profit": -1.00},
            "overall": {"wins": 0, "runs": 1, "win_rate": 0, "profit": -1.00}
        },
        "trainer_stats": {
            "last_14_days": {"wins": 2, "runs": 21, "win_rate": 10, "profit": -12.67},
            "overall": {"wins": 21, "runs": 211, "win_rate": 10, "profit": -17.97}
        }
    },
    {
        "position": 8,
        "name": "Tyger Bay",
        "draw": 4,
        "jockey": "Ryan Kavanagh",
        "trainer": "C Allen",
        "form_id": "435110",
        "weight": "9-6",
        "age": 8,
        "current_odds": 5.00,
        "odds_movement": [5.50, 5.00, 5.50],
        "official_rating": 72,
        "speed_figures": [70, 68, 67, 66, 68, 72, 79],
        "market_favorite": True,  # Star indicator
        "going_record": {"wins": 6, "runs": 29, "win_rate": 21},
        "distance_record": {"wins": 12, "runs": 66, "win_rate": 18},
        "course_record": {"wins": 5, "runs": 25, "win_rate": 20},
        "jockey_stats": {
            "last_14_days": {"wins": 0, "runs": 8, "win_rate": 0, "profit": -8.00},
            "overall": {"wins": 1, "runs": 26, "win_rate": 4, "profit": -23.75}
        },
        "trainer_stats": {
            "last_14_days": {"wins": 0, "runs": 4, "win_rate": 0, "profit": -4.00},
            "overall": {"wins": 8, "runs": 75, "win_rate": 11, "profit": -12.42}
        }
    },
    {
        "position": 11,
        "name": "Danger Alert",
        "draw": 2,
        "jockey": "Liam Wright",
        "trainer": "George Baker",
        "form_id": "762420",
        "weight": "9-2",
        "age": 5,
        "current_odds": 7.00,
        "odds_movement": [7.50, 7.00, 7.50],
        "official_rating": 68,
        "speed_figures": [69, 69, 69, 69, 69, 69, 85],
        "going_record": {"wins": 1, "runs": 4, "win_rate": 25},
        "distance_record": {"wins": 1, "runs": 23, "win_rate": 4},
        "course_record": {"wins": 1, "runs": 4, "win_rate": 25},
        "jockey_stats": {
            "last_14_days": {"wins": 0, "runs": 5, "win_rate": 0, "profit": -5.00},
            "overall": {"wins": 5, "runs": 44, "win_rate": 11, "profit": -13.94}
        },
        "trainer_stats": {
            "last_14_days": {"wins": 0, "runs": 10, "win_rate": 0, "profit": -10.00},
            "overall": {"wins": 17, "runs": 182, "win_rate": 9, "profit": -28.03}
        }
    },
    {
        "position": 10,
        "name": "Treacherous",
        "draw": 10,
        "jockey": "Elizabeth Gale",
        "jockey_claim": 3,
        "trainer": "E De Giles",
        "form_id": "086769",
        "weight": "9-2",
        "age": 11,
        "current_odds": 8.50,
        "odds_movement": [9.00, 8.50, 9.00],
        "official_rating": 68,
        "speed_figures": [79, 77, 75, 73, 73, 70, 86],
        "going_record": {"wins": 1, "runs": 12, "win_rate": 8},
        "distance_record": {"wins": 3, "runs": 50, "win_rate": 6},
        "course_record": {"wins": 1, "runs": 10, "win_rate": 10},
        "jockey_stats": {
            "last_14_days": {"wins": 0, "runs": 6, "win_rate": 0, "profit": -6.00},
            "overall": {"wins": 0, "runs": 7, "win_rate": 0, "profit": -7.00}
        },
        "trainer_stats": {
            "last_14_days": {"wins": 0, "runs": 4, "win_rate": 0, "profit": -4.00},
            "overall": {"wins": 8, "runs": 71, "win_rate": 11, "profit": -2.05}
        }
    },
    {
        "position": 3,
        "name": "Mc Loven",
        "draw": 11,
        "jockey": "Ashley Lewis",
        "jockey_claim": 3,
        "trainer": "S Dow",
        "form_id": "440337",
        "weight": "9-8",
        "age": 4,
        "current_odds": 9.00,
        "odds_movement": [10.00, 9.00, 10.00],
        "official_rating": 74,
        "speed_figures": [81, 80, 79, 76, 75, 75, 77],
        "going_record": {"wins": 0, "runs": 0, "win_rate": 0},
        "distance_record": {"wins": 0, "runs": 3, "win_rate": 0},
        "course_record": {"wins": 0, "runs": 0, "win_rate": 0},
        "jockey_stats": {
            "last_14_days": {"wins": 1, "runs": 17, "win_rate": 6, "profit": -10.50},
            "overall": {"wins": 0, "runs": 12, "win_rate": 0, "profit": -12.00}
        },
        "trainer_stats": {
            "last_14_days": {"wins": 2, "runs": 7, "win_rate": 29, "profit": +0.75},
            "overall": {"wins": 13, "runs": 200, "win_rate": 7, "profit": -55.67}
        }
    },
    {
        "position": 2,
        "name": "Invincible Speed",
        "draw": 1,
        "jockey": "Tom Kiely-Marshall",
        "trainer": "D M Loughnane",
        "form_id": "138656",
        "weight": "9-9",
        "age": 4,
        "current_odds": 10.00,
        "odds_movement": [8.00, 10.00, 11.00],
        "official_rating": 75,
        "speed_figures": [75, 80, 80, 79, 77, 76, 78],
        "going_record": {"wins": 0, "runs": 4, "win_rate": 0},
        "distance_record": {"wins": 2, "runs": 14, "win_rate": 14},
        "course_record": {"wins": 0, "runs": 2, "win_rate": 0},
        "jockey_stats": {
            "last_14_days": {"wins": 0, "runs": 7, "win_rate": 0, "profit": -7.00},
            "overall": {"wins": 0, "runs": 2, "win_rate": 0, "profit": -2.00}
        },
        "trainer_stats": {
            "last_14_days": {"wins": 0, "runs": 12, "win_rate": 0, "profit": -12.00},
            "overall": {"wins": 26, "runs": 229, "win_rate": 11, "profit": -29.81}
        }
    },
    {
        "position": 5,
        "name": "Lerwick",
        "draw": 6,
        "jockey": "Warren Fentiman",
        "trainer": "D M Loughnane",
        "form_id": "585797",
        "weight": "9-7",
        "age": 5,
        "current_odds": 10.00,
        "odds_movement": [11.00, 10.00, 11.00],
        "official_rating": 73,
        "speed_figures": [82, 81, 79, 79, 78, 76],
        "going_record": {"wins": 0, "runs": 2, "win_rate": 0},
        "distance_record": {"wins": 0, "runs": 1, "win_rate": 0},
        "course_record": {"wins": 0, "runs": 2, "win_rate": 0},
        "jockey_stats": {
            "last_14_days": {"wins": 2, "runs": 24, "win_rate": 8, "profit": -1.00},
            "overall": {"wins": 2, "runs": 17, "win_rate": 12, "profit": -9.00}
        },
        "trainer_stats": {
            "last_14_days": {"wins": 0, "runs": 12, "win_rate": 0, "profit": -12.00},
            "overall": {"wins": 26, "runs": 229, "win_rate": 11, "profit": -29.81}
        }
    },
    {
        "position": 9,
        "name": "One More Dream",
        "draw": 8,
        "jockey": "Sam Feilden",
        "jockey_claim": 3,
        "trainer": "J & S Quinn",
        "form_id": "586210",
        "weight": "9-5",
        "age": 6,
        "current_odds": 15.00,
        "odds_movement": [17.00, 15.00, 13.00],
        "official_rating": 71,
        "speed_figures": [69, 67, 65, 64, 65, 71, 79],
        "going_record": {"wins": 2, "runs": 5, "win_rate": 40},
        "distance_record": {"wins": 8, "runs": 35, "win_rate": 23},
        "course_record": {"wins": 0, "runs": 0, "win_rate": 0},
        "jockey_stats": {
            "last_14_days": {"wins": 0, "runs": 2, "win_rate": 0, "profit": -2.00},
            "overall": {"wins": 1, "runs": 12, "win_rate": 8, "profit": -7.00}
        },
        "trainer_stats": {
            "last_14_days": {"wins": 2, "runs": 14, "win_rate": 14, "profit": -4.67},
            "overall": {"wins": 0, "runs": 1, "win_rate": 0, "profit": -1.00}
        }
    },
    {
        "position": 4,
        "name": "Harry's Halo",
        "draw": 5,
        "jockey": "Alfie Gee",
        "jockey_claim": 5,
        "trainer": "K Frost",
        "form_id": "312-64",
        "weight": "9-8",
        "age": 5,
        "current_odds": 19.00,
        "odds_movement": [13.00, 15.00, 17.00],
        "official_rating": 74,
        "speed_figures": [71, 71, 71, 75, 75, 75],
        "going_record": {"wins": 0, "runs": 1, "win_rate": 0},
        "distance_record": {"wins": 4, "runs": 23, "win_rate": 17},
        "course_record": {"wins": 0, "runs": 1, "win_rate": 0},
        "jockey_stats": {
            "last_14_days": {"wins": 0, "runs": 1, "win_rate": 0, "profit": -1.00},
            "overall": {"wins": 0, "runs": 0, "win_rate": 0, "profit": 0.00}
        },
        "trainer_stats": {
            "last_14_days": {"wins": 0, "runs": 16, "win_rate": 0, "profit": -16.00},
            "overall": {"wins": 0, "runs": 27, "win_rate": 0, "profit": -27.00}
        }
    },
    {
        "position": 7,
        "name": "Lipsink",
        "draw": 9,
        "jockey": "Mason Paetel",
        "trainer": "M Appleby",
        "form_id": "742175",
        "weight": "9-6",
        "age": 8,
        "current_odds": 19.00,
        "odds_movement": [17.00, 15.00, 17.00],
        "official_rating": 72,
        "speed_figures": [70, 69, 67, 68, 72, 73, 85],
        "going_record": {"wins": 0, "runs": 3, "win_rate": 0},
        "distance_record": {"wins": 1, "runs": 7, "win_rate": 14},
        "course_record": {"wins": 0, "runs": 0, "win_rate": 0},
        "jockey_stats": {
            "last_14_days": {"wins": 0, "runs": 12, "win_rate": 0, "profit": -12.00},
            "overall": {"wins": 1, "runs": 14, "win_rate": 7, "profit": -8.50}
        },
        "trainer_stats": {
            "last_14_days": {"wins": 2, "runs": 27, "win_rate": 7, "profit": -18.50},
            "overall": {"wins": 30, "runs": 285, "win_rate": 11, "profit": -130.41}
        }
    },
    {
        "position": 6,
        "name": "El Bufalo",
        "draw": 7,
        "jockey": "Zoe Lewis",
        "jockey_claim": 5,
        "trainer": "T Faulkner",
        "form_id": "614507",
        "weight": "9-7",
        "age": 4,
        "current_odds": 34.00,
        "odds_movement": [29.00, 26.00, 29.00],
        "official_rating": 73,
        "speed_figures": [75, 73, 77, 77, 76, 75, 73],
        "going_record": {"wins": 1, "runs": 3, "win_rate": 33},
        "distance_record": {"wins": 0, "runs": 3, "win_rate": 0},
        "course_record": {"wins": 0, "runs": 0, "win_rate": 0},
        "jockey_stats": {
            "last_14_days": {"wins": 0, "runs": 1, "win_rate": 0, "profit": -1.00},
            "overall": {"wins": 0, "runs": 0, "win_rate": 0, "profit": 0.00}
        },
        "trainer_stats": {
            "last_14_days": {"wins": 1, "runs": 8, "win_rate": 13, "profit": -2.00},
            "overall": {"wins": 0, "runs": 17, "win_rate": 0, "profit": -17.00}
        }
    }
]

# Additional race context
race_context = {
    "field_size": 11,
    "track_condition": "All-Weather",
    "distance": "Unknown - need to determine from form",
    "class": "Unknown",
    "prize_money": "Unknown"
}

