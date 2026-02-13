def adapt_prime_to_v11(race_card):
    """
    Adapts the Pydantic RaceCard model (Prime) to the dictionary format 
    expected by the legacy V11 Brain (Playbook E).
    """
    v11_data = {}
    
    for time, race in race_card.races.items():
        v11_runners = []
        for r in race.runners:
            v11_runners.append({
                "name": r.horse_name,
                "jockey": r.jockey,
                "trainer": r.trainer,
                "OR": r.official_rating,
                "TS": r.topspeed,
                "RPR": r.rpr,
                "draw": r.draw,
                "form": r.form_string,
                "odds": r.odds,
                "age": r.age,
                "sire": r.sire,
                "dam": r.dam,
                "weight": r.weight_lbs
            })
            
        v11_data[time] = {
            "venue": race.venue,
            "time": time,
            "runners": v11_runners,
            "meta": {
                "distance": race.distance,
                "going": race.going,
                "class": race.race_class
            }
        }
        
    return v11_data
