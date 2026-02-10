from core.schema import RaceCard

def adapt_prime_to_v11(race_card: RaceCard):
    """
    Converts the Prime Pydantic RaceCard into the dictionary format 
    expected by the V11 Playbooks.
    """
    v11_data = {}
    
    for time, race in race_card.races.items():
        # V11 expects a list of runners with specific keys
        runners_list = []
        for r in race.runners:
            runner_dict = {
                "name": r.horse_name,
                "saddle": r.saddle_cloth,
                "form": r.form_string,
                "jockey": r.jockey,
                "trainer": r.trainer,
                "OR": r.official_rating,
                "RPR": r.rpr,
                "TS": r.topspeed,
                # Add derived fields that V11 might need (default to None if missing)
                "days_off": None, # Parser needs to extract this if V11 uses it
                "weight": None    # Parser needs to extract this if V11 uses it
            }
            runners_list.append(runner_dict)
            
        v11_data[time] = {
            "time": time,
            "venue": race_card.venue,
            "date": race_card.date,
            "runners": runners_list
        }
        
    return v11_data
