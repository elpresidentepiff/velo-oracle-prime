class DarkArtsDetector:
    def __init__(self):
        self.elite_jockeys = [
            "Oisin Murphy", "William Buick", "Tom Marquand", "Ryan Moore", 
            "James Doyle", "Hollie Doyle", "Billy Loughnane", "Rossa Ryan"
        ]
        self.plot_trainers = [
            "Sir Mark Prescott", "Tony Carroll", "Michael Appleby", 
            "David Evans", "Gay Kelleway"
        ]

    def detect_plot(self, runner, history):
        """
        Scans a runner for signs of a 'Release Race' or 'Handicap Plot'.
        Returns a 'Dark Arts Score' (0-100) and a list of flags.
        """
        score = 0
        flags = []

        # 1. The "Rating Plunge" (Dropped significantly in weights)
        # Assuming we have access to past OR (needs history parsing)
        # For now, we check if current OR is significantly below last winning OR (if available)
        # This requires deeper data, but we can check the "OR" trend if we had it.
        
        # 2. The "Jockey Upgrade"
        # If the jockey is Elite and the horse has been losing with non-elite jockeys
        if any(j in runner.jockey for j in self.elite_jockeys):
            # We'd need to check previous jockeys to confirm it's an *upgrade*
            # For now, we flag "Elite Jockey" on a low-rated horse as suspicious
            if runner.official_rating and runner.official_rating < 70:
                score += 15
                flags.append(f"Elite Jockey ({runner.jockey}) in Low Grade")

        # 3. The "Headgear Switch" (First time Blinkers/Visor)
        # We need to parse headgear from the runner string (e.g., "b1", "v1")
        # This is usually in the name or a separate column.
        if "b1" in runner.horse_name.lower() or "v1" in runner.horse_name.lower():
             score += 20
             flags.append("First Time Headgear (The Sharpener)")

        # 4. The "Trainer Plot"
        if any(t in runner.trainer for t in self.plot_trainers):
            score += 10
            flags.append(f"Plot Trainer ({runner.trainer})")

        # 5. The "Distance Switch" (Genetics Check)
        # If we know the Sire's optimal distance (e.g., Kodiac = 6f) and the horse is now running 6f
        # after running 1m. (Requires Genetics Layer integration)
        
        return score, flags
