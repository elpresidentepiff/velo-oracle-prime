import sqlite3
import json

DB_PATH = "velo_memory.db"

# Official Results for Punchestown 15 Feb 2026
# Based on search results:
# 13:40 - Winner: Soldier In Milan (13/8)
# 14:10 - Winner: Kiss Will (13/8)
# 14:40 - Winner: My Immortal (25/1) | Built By Ballymore was 3rd
# 15:10 - Winner: Spillane's Tower (3.5)
# 15:40 - Winner: Maskada (6.0)
# 16:10 - Winner: Senior Chief (5.5)
# 16:40 - Winner: Jalon D'oudairies (2.2)
# 17:10 - Winner: Cantico (4.0)

RESULTS = {
    "D B Cooper": {"pos": 0, "win": False},
    "Fleur In The Park": {"pos": 0, "win": False},
    "Kinturk Kalanisi": {"pos": 0, "win": False},
    "Slade Steel": {"pos": 0, "win": False},
    "Built By Ballymore": {"pos": 3, "win": False}, # 3rd
    "Answer To Kayf": {"pos": 0, "win": False},
    "Spillane's Tower": {"pos": 1, "win": True, "sp": 3.5}, # WINNER
    "Blood Destiny": {"pos": 0, "win": False},
    "Maskada": {"pos": 1, "win": True, "sp": 6.0}, # WINNER
    "Solness": {"pos": 0, "win": False},
    "Senior Chief": {"pos": 1, "win": True, "sp": 5.5}, # WINNER
    "The Goffer": {"pos": 0, "win": False},
    "Jalon D'oudairies": {"pos": 1, "win": True, "sp": 2.2}, # WINNER
    "Romeo Coolio": {"pos": 0, "win": False},
    "Cantico": {"pos": 1, "win": True, "sp": 4.0}, # WINNER
    "The Enabler": {"pos": 0, "win": False},
    "Sounds Victorius": {"pos": 0, "win": False}
}

def resolve():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Resolving Punchestown Results...")
    
    total_profit = 0
    stake_per_bet = 10  # Standard unit stake
    
    for horse, result in RESULTS.items():
        # Update the database
        cursor.execute('''
        UPDATE runners 
        SET position = ?, odds_sp = ?
        WHERE horse_name = ?
        ''', (result['pos'], result.get('sp', 0), horse))
        
        if result['win']:
            profit = (stake_per_bet * result['sp']) - stake_per_bet
            total_profit += profit
            print(f"🏆 WINNER: {horse} @ {result['sp']} (+{profit:.2f})")
        else:
            total_profit -= stake_per_bet
            # print(f"❌ LOST: {horse} (-{stake_per_bet})")
            
    conn.commit()
    conn.close()
    
    print("-" * 30)
    print(f"💰 TOTAL P&L: {total_profit:.2f} units")
    print("-" * 30)
    print("✅ Results committed to Memory Vault.")

if __name__ == "__main__":
    resolve()
