from core.dark_arts import DarkArtsDetector

def execute_attack_doctrine(race_card):
    print("--- V11 BRAIN: ENGAGING DARK ARTS PROTOCOL ---")
    
    detector = DarkArtsDetector()
    
    for race in race_card.races:
        print(f"Scanning {race.time} for Plots...")
        for runner in race.runners:
            score, flags = detector.detect_plot(runner, [])
            
            if score > 0:
                print(f"  [!] PLOT DETECTED: {runner.horse_name} (Score: {score})")
                for flag in flags:
                    print(f"      - {flag}")
                
                # Inject the Dark Arts Score into the runner's metadata for the final tally
                # (This would normally merge with the main score)
