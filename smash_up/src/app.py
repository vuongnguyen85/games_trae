from flask import Flask, render_template, jsonify, request
import random
import sqlite3
from datetime import datetime

app = Flask(__name__)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('factions.db')
    c = conn.cursor()
    
    # Drop existing tables if they exist
    c.execute('DROP TABLE IF EXISTS score_history')
    c.execute('DROP TABLE IF EXISTS player_factions')
    c.execute('DROP TABLE IF EXISTS players')
    c.execute('DROP TABLE IF EXISTS game_settings')
    c.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            current_score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS player_factions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            faction TEXT NOT NULL,
            selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES players (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS game_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            max_players INTEGER DEFAULT 4,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS score_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES players (id)
        )
    ''')
    conn.commit()
    conn.close()

# Initialize the database when the app starts
init_db()

# List of Smash Up factions
FACTIONS = [
    "Aliens",
    "Astroknights",
    "Bear Cavalry",
    "Changerbots",
    "Cyborg Apes",
    "Dinosaurs",
    "Disco Dancers",
    "Dragons",
    "Elder Things",
    "Explorers",
    "Geeks",
    "Ghosts",
    "Giant Ants",
    "Grannies",
    "Ignobles",
    "Innsmouth",
    "Killer Plants",
    "Kung Fu Fighters",
    "Luchadors",
    "Mad Scientists",
    "Minions of Gthulhu",
    "Miskatonic University",
    "Mounties",
    "Musketeers",
    "Mythic Greeks",
    "Ninjas",
    "Pirates",
    "Robots",
    "Sharks",
    "Shapeshifters",
    "Star Roamers",
    "Steampunks",
    "Sumo Wrestlers",
    "Super Heroes",
    "Super Spies",
    "Teddy Bears",
    "Time Travellers",
    "Tornados",
    "Tricksters",
    "Truckers",
    "Vampires",
    "Vigilantes",
    "Werewolves",
    "Wizards",
    "Zombies"
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_player', methods=['POST'])
def add_player():
    name = request.json.get('name')
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    
    conn = sqlite3.connect('factions.db')
    c = conn.cursor()
    c.execute('INSERT INTO players (name, current_score) VALUES (?, 0)', (name,))
    player_id = c.lastrowid
    # Initialize score history with 0
    c.execute('INSERT INTO score_history (player_id, score) VALUES (?, 0)', (player_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'id': player_id, 'name': name})

@app.route('/get_players')
def get_players():
    conn = sqlite3.connect('factions.db')
    c = conn.cursor()
    c.execute('''
        SELECT p.id, p.name, GROUP_CONCAT(pf.faction) as factions
        FROM players p
        LEFT JOIN player_factions pf ON p.id = pf.player_id
        GROUP BY p.id
    ''')
    players = [{
        'id': row[0],
        'name': row[1],
        'factions': row[2].split(',') if row[2] else []
    } for row in c.fetchall()]
    conn.close()
    return jsonify(players)

@app.route('/add_faction', methods=['POST'])
def add_faction():
    player_id = request.json.get('player_id')
    if not player_id:
        return jsonify({'error': 'Player ID is required'}), 400
        
    conn = sqlite3.connect('factions.db')
    c = conn.cursor()
    
    # Check if player exists and has less than 2 factions
    c.execute('SELECT COUNT(*) FROM player_factions WHERE player_id = ?', (player_id,))
    count = c.fetchone()[0]
    if count >= 2:
        conn.close()
        return jsonify({'error': 'Player already has maximum number of factions'}), 400
    
    # Get all currently used factions
    c.execute('SELECT faction FROM player_factions')
    used_factions = {row[0] for row in c.fetchall()}
    
    # Get available factions
    available_factions = [f for f in FACTIONS if f not in used_factions]
    
    if not available_factions:
        conn.close()
        return jsonify({'error': 'No more factions available'}), 400
    
    faction = random.choice(available_factions)
    try:
        c.execute('INSERT INTO player_factions (player_id, faction) VALUES (?, ?)', 
                  (player_id, faction))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Invalid player ID'}), 400
        
    conn.close()
    return jsonify({'faction': faction})

@app.route('/get_settings')
def get_settings():
    conn = sqlite3.connect('factions.db')
    c = conn.cursor()
    c.execute('SELECT max_players FROM game_settings ORDER BY id DESC LIMIT 1')
    result = c.fetchone()
    max_players = result[0] if result else 4
    conn.close()
    return jsonify({'max_players': max_players})

@app.route('/update_settings', methods=['POST'])
def update_settings():
    max_players = request.json.get('max_players')
    if not max_players or not isinstance(max_players, int) or max_players < 1:
        return jsonify({'error': 'Invalid max players value'}), 400
    
    conn = sqlite3.connect('factions.db')
    c = conn.cursor()
    c.execute('INSERT INTO game_settings (max_players) VALUES (?)', (max_players,))
    conn.commit()
    conn.close()
    return jsonify({'max_players': max_players})

@app.route('/update_score', methods=['POST'])
def update_score():
    player_id = request.json.get('player_id')
    score = request.json.get('score')
    conn = None
    
    if not player_id:
        return jsonify({'error': 'Player ID is required'}), 400
    
    if score is None:
        return jsonify({'error': 'Score is required'}), 400
        
    try:
        # Convert score to integer if it's a string
        score = int(score) if isinstance(score, str) else score
        if not isinstance(score, int):
            return jsonify({'error': 'Score must be a number'}), 400
            
        conn = sqlite3.connect('factions.db')
        c = conn.cursor()
        
        # Check if player exists and get current score
        c.execute('SELECT id, current_score FROM players WHERE id = ?', (player_id,))
        player = c.fetchone()
        if not player:
            return jsonify({'error': 'Player not found'}), 404
            
        current_score = player[1]
        
        # Only update history if the score is different
        if current_score != score:
            c.execute('UPDATE players SET current_score = ? WHERE id = ?', (score, player_id))
            c.execute('INSERT INTO score_history (player_id, score) VALUES (?, ?)', (player_id, score))
            conn.commit()
        return jsonify({'message': 'Score updated successfully'})
    
    except ValueError as e:
        return jsonify({'error': 'Invalid score format'}), 400
    except sqlite3.Error as e:
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/get_score_history/<int:player_id>')
def get_score_history(player_id):
    conn = sqlite3.connect('factions.db')
    c = conn.cursor()
    
    # Get score history excluding the current score
    c.execute('''
        SELECT sh.score, sh.recorded_at 
        FROM score_history sh
        JOIN (
            SELECT player_id, MAX(recorded_at) as max_recorded_at
            FROM score_history
            GROUP BY player_id
        ) latest ON sh.player_id = latest.player_id
        WHERE sh.player_id = ? AND sh.recorded_at < latest.max_recorded_at
        ORDER BY sh.recorded_at DESC
    ''', (player_id,))
    
    history = [{'score': row[0], 'recorded_at': row[1]} for row in c.fetchall()]
    conn.close()
    return jsonify(history)

@app.route('/clear_all', methods=['POST'])
def clear_all():
    conn = sqlite3.connect('factions.db')
    c = conn.cursor()
    try:
        c.execute('DELETE FROM player_factions')
        c.execute('DELETE FROM players')
        c.execute('DELETE FROM score_history')
        conn.commit()
        return jsonify({'message': 'All data cleared successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)