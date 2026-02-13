# VÉLØ Research: The Dark Arts of UK Handicap Manipulation

## 1. The Core Concept: "Running for a Mark"
In UK racing, a horse's weight is determined by its Official Rating (OR). To win a handicap, a horse often needs to be "well-in" (rated lower than its true ability).
Trainers achieve this by running the horse over the wrong distance, on the wrong ground, or with "tender" handling in 3+ qualifying runs to get a low opening mark, or to drop an existing mark.

## 2. The "Quiet Run" Indicators (The Setup)
*   **"Held Up, Never Nearest"**: The horse is dropped to the back, makes "late headway" but never threatens. Comment: "Not knocked about."
*   **Wrong Distance**: A sprinter (6f pedigree) running over 1m (stamina test) to fade late. Or a stayer running over 6f (outpaced).
*   **Wrong Ground**: A "mudlark" (soft ground horse) running on Firm ground.
*   **Jockey Choice**: Using an inexperienced apprentice (claiming 7lbs) who "can't get the horse going" vs a strong pro.
*   **Drift in Market**: Odds drift from 8.0 to 20.0. The "smart money" knows it's not today.

## 3. The "Release" Signals (The Coup)
When the handicap mark is low enough, the connections "pull the trigger".
*   **The "Plot" Jockey**: Switching from an apprentice to a top "strong" jockey (e.g., Oisin Murphy, William Buick, Tom Marquand) or a "go-to" handicap specialist (e.g., Jamie Spencer for hold-up plots).
*   **Gear Change**: First-time **Blinkers** or **Visor** (Headgear) to sharpen the horse up. "Wakes them up."
*   **Distance Switch**: Moving back to the horse's *optimal* distance (verified by pedigree/past wins) after running over the wrong trip.
*   **Market Move**: A sudden "Gamma Squeeze" in the betting. 12.0 -> 6.0 in the morning.
*   **Trainer Pattern**: Some trainers (e.g., Sir Mark Prescott, Barney Curley historically) are masters of the "3 runs for a mark, 1 run for the money" strategy.

## 4. Detection Logic for VÉLØ
We need to build a `DarkArtsDetector` module that scans for:
1.  **Rating Drop**: Has the OR dropped >5lbs in the last 3 runs?
2.  **Jockey Upgrade**: Is the current jockey significantly better (by strike rate/experience) than the last 3?
3.  **Headgear**: Is "1st Time Blinkers" (b1) or "Visor" (v1) applied?
4.  **Pedigree/Distance Match**: Is the horse finally running over its *genetic* optimal distance after failing at others?
5.  **The "Sleeper" Flag**: If (OR Drop) AND (Jockey Upgrade) AND (Market Support) -> **MAX BET**.
