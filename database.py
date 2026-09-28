import sqlite3
import hashlib
from datetime import datetime, timedelta

def get_connection():
    return sqlite3.connect("tl_dkp.db")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'player',
            class TEXT NOT NULL,
            current_dkp INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Миграция: если таблица уже существует, но без новых столбцов
    cursor.execute("PRAGMA table_info(players)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'password' not in columns:
        cursor.execute("ALTER TABLE players ADD COLUMN password TEXT DEFAULT ''")
        # Устанавливаем пароль "1234" всем старым игрокам
        cursor.execute("UPDATE players SET password = ?", (hash_password("1234"),))
    if 'role' not in columns:
        cursor.execute("ALTER TABLE players ADD COLUMN role TEXT DEFAULT 'player'")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES players (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auctions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            start_price INTEGER NOT NULL,
            current_max_bid INTEGER DEFAULT 0,
            current_winner_id INTEGER,
            status TEXT DEFAULT 'active',
            end_time TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (current_winner_id) REFERENCES players (id)
        )
    """)

    cursor.execute("PRAGMA table_info(auctions)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'current_max_bid' not in columns:
        cursor.execute("ALTER TABLE auctions ADD COLUMN current_max_bid INTEGER DEFAULT 0")
    if 'current_winner_id' not in columns:
        cursor.execute("ALTER TABLE auctions ADD COLUMN current_winner_id INTEGER")
    if 'end_time' not in columns:
        cursor.execute("ALTER TABLE auctions ADD COLUMN end_time TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auction_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (auction_id) REFERENCES auctions (id),
            FOREIGN KEY (player_id) REFERENCES players (id)
        )
    """)

    conn.commit()
    conn.close()

# ========== АВТОРИЗАЦИЯ ==========

def login(nickname, password):
    conn = get_connection()
    cursor = conn.cursor()
    hashed = hash_password(password)
    cursor.execute(
        "SELECT id, nickname, role, class, current_dkp FROM players WHERE nickname = ? AND password = ? AND is_active = 1",
        (nickname, hashed)
    )
    player = cursor.fetchone()
    conn.close()
    return player

def register_player(nickname, password, player_class, role='player', starting_dkp=0):
    if nickname.strip().lower() == "stolp":
        role = "admin"
        starting_dkp = 0
    conn = get_connection()
    cursor = conn.cursor()
    try:
        hashed = hash_password(password)
        cursor.execute(
            "INSERT INTO players (nickname, password, role, class, current_dkp) VALUES (?, ?, ?, ?, ?)",
            (nickname, hashed, role, player_class, starting_dkp)
        )
        conn.commit()
        player_id = cursor.lastrowid
        if starting_dkp > 0:
            cursor.execute(
                "INSERT INTO transactions (player_id, amount, type, description) VALUES (?, ?, ?, ?)",
                (player_id, starting_dkp, "earn", "Стартовый баланс")
            )
            conn.commit()
        return True, "Игрок зарегистрирован"
    except sqlite3.IntegrityError:
        return False, "Игрок с таким ником уже существует"
    finally:
        conn.close()

# ========== ИГРОКИ ==========

def get_all_players():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nickname, class, current_dkp, is_active FROM players WHERE is_active = 1 ORDER BY current_dkp DESC")
    players = cursor.fetchall()
    conn.close()
    return players

def get_player_dkp(nickname):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT current_dkp FROM players WHERE nickname = ?", (nickname,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def change_dkp(nickname, amount, description=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, current_dkp FROM players WHERE nickname = ?", (nickname,))
    player = cursor.fetchone()
    if not player:
        conn.close()
        return False, "Игрок не найден"
    player_id, current_dkp = player
    new_dkp = current_dkp + amount
    cursor.execute("UPDATE players SET current_dkp = ? WHERE id = ?", (new_dkp, player_id))
    trans_type = "earn" if amount > 0 else "spend"
    cursor.execute("INSERT INTO transactions (player_id, amount, type, description) VALUES (?, ?, ?, ?)",
                   (player_id, amount, trans_type, description))
    conn.commit()
    conn.close()
    return True, f"DKP изменен. Новый баланс: {new_dkp}"

def mass_award_dkp(player_nicknames, amount, description=""):
    conn = get_connection()
    cursor = conn.cursor()
    success_list = []
    error_list = []
    for nickname in player_nicknames:
        cursor.execute("SELECT id, current_dkp FROM players WHERE nickname = ?", (nickname,))
        player = cursor.fetchone()
        if not player:
            error_list.append(f"{nickname}: не найден")
            continue
        player_id, current_dkp = player
        new_dkp = current_dkp + amount
        cursor.execute("UPDATE players SET current_dkp = ? WHERE id = ?", (new_dkp, player_id))
        cursor.execute("INSERT INTO transactions (player_id, amount, type, description) VALUES (?, ?, ?, ?)",
                       (player_id, amount, "earn", description))
        success_list.append(f"{nickname}: +{amount} DKP (баланс: {new_dkp})")
    conn.commit()
    conn.close()
    return success_list, error_list

# ========== ИСТОРИЯ ==========

def get_player_history(nickname):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM players WHERE nickname = ?", (nickname,))
    player = cursor.fetchone()
    if not player:
        conn.close()
        return None
    cursor.execute("SELECT amount, type, description, created_at FROM transactions WHERE player_id = ? ORDER BY created_at DESC",
                   (player[0],))
    transactions = cursor.fetchall()
    conn.close()
    return transactions

# ========== АУКЦИОН ==========

def create_auction(item_name, start_price, duration_minutes=5):
    conn = get_connection()
    cursor = conn.cursor()
    end_time = (datetime.now() + timedelta(minutes=duration_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO auctions (item_name, start_price, current_max_bid, status, end_time) VALUES (?, ?, ?, 'active', ?)",
        (item_name, start_price, start_price, end_time)
    )
    conn.commit()
    conn.close()
    return True, f"Лот создан! Торги до {end_time}"

def check_expired_auctions():
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("SELECT id, current_winner_id, current_max_bid, item_name FROM auctions WHERE status = 'active' AND end_time <= ?", (now,))
    expired = cursor.fetchall()
    for auc_id, winner_id, final_price, item_name in expired:
        if winner_id:
            cursor.execute("SELECT current_dkp FROM players WHERE id = ?", (winner_id,))
            player = cursor.fetchone()
            if player:
                new_dkp = player[0] - final_price
                cursor.execute("UPDATE players SET current_dkp = ? WHERE id = ?", (new_dkp, winner_id))
                cursor.execute("INSERT INTO transactions (player_id, amount, type, description) VALUES (?, ?, ?, ?)",
                               (winner_id, -final_price, "spend", f"Покупка: {item_name}"))
        cursor.execute("UPDATE auctions SET status = 'sold' WHERE id = ?", (auc_id,))
    conn.commit()
    conn.close()

def get_active_auctions():
    check_expired_auctions()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.item_name, a.start_price, a.current_max_bid, a.end_time, p.nickname
        FROM auctions a
        LEFT JOIN players p ON a.current_winner_id = p.id
        WHERE a.status = 'active'
        ORDER BY a.id DESC
    """)
    auctions = cursor.fetchall()
    conn.close()
    return auctions

def place_bid(auction_id, player_id, bid_amount):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT current_max_bid, end_time, status FROM auctions WHERE id = ?", (auction_id,))
    auction = cursor.fetchone()
    if not auction:
        conn.close()
        return False, "Аукцион не найден"
    current_max, end_time, status = auction
    if status != 'active':
        conn.close()
        return False, "Аукцион уже закрыт"
    if datetime.now().strftime("%Y-%m-%d %H:%M:%S") > end_time:
        conn.close()
        return False, "Время аукциона истекло"
    if bid_amount <= current_max:
        conn.close()
        return False, f"Ставка должна быть выше {current_max} DKP"
    cursor.execute("SELECT current_dkp FROM players WHERE id = ?", (player_id,))
    player = cursor.fetchone()
    if not player or player[0] < bid_amount:
        conn.close()
        return False, f"Недостаточно DKP! У тебя {player[0] if player else 0}, нужно {bid_amount}"
    cursor.execute("INSERT INTO bids (auction_id, player_id, amount) VALUES (?, ?, ?)",
                   (auction_id, player_id, bid_amount))
    cursor.execute("UPDATE auctions SET current_max_bid = ?, current_winner_id = ? WHERE id = ?",
                   (bid_amount, player_id, auction_id))
    # Анти-снайп: если до конца меньше 1 минуты, продлеваем на 1 минуту
    end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    if (end_dt - datetime.now()).total_seconds() < 60:
        new_end = (end_dt + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE auctions SET end_time = ? WHERE id = ?", (new_end, auction_id))
    conn.commit()
    conn.close()
    return True, f"Ставка {bid_amount} DKP принята!"

def get_auction_bids(auction_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.nickname, b.amount, b.created_at
        FROM bids b JOIN players p ON b.player_id = p.id
        WHERE b.auction_id = ? ORDER BY b.amount DESC
    """, (auction_id,))
    bids = cursor.fetchall()
    conn.close()
    return bids

def get_auction_history():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.item_name, a.current_max_bid, p.nickname, a.created_at
        FROM auctions a LEFT JOIN players p ON a.current_winner_id = p.id
        WHERE a.status = 'sold' ORDER BY a.id DESC LIMIT 20
    """)
    history = cursor.fetchall()
    conn.close()
    return history

# ========== ЭКСПОРТ ==========

def get_full_report():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nickname, class, current_dkp, is_active, created_at FROM players ORDER BY current_dkp DESC")
    players = cursor.fetchall()
    conn.close()
    return players

def get_all_transactions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.nickname, t.amount, t.type, t.description, t.created_at
        FROM transactions t JOIN players p ON t.player_id = p.id
        ORDER BY t.created_at DESC
    """)
    transactions = cursor.fetchall()
    conn.close()
    return transactions
# ========== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ УПРАВЛЕНИЯ ==========

def update_player_class(nickname, new_class):
    """Изменяет класс игрока"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE players SET class = ? WHERE nickname = ?", (new_class, nickname))
    conn.commit()
    conn.close()
    return True, f"Класс изменен на '{new_class}'"

def delete_player(nickname):
    """
    Полностью удаляет игрока и все связанные данные:
    - транзакции
    - ставки на аукционах
    - саму запись игрока
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Получаем ID игрока
    cursor.execute("SELECT id FROM players WHERE nickname = ?", (nickname,))
    player = cursor.fetchone()
    if not player:
        conn.close()
        return False, "Игрок не найден"
    
    player_id = player[0]
    
    # Удаляем связанные данные (каскадно)
    cursor.execute("DELETE FROM transactions WHERE player_id = ?", (player_id,))
    cursor.execute("DELETE FROM bids WHERE player_id = ?", (player_id,))
    
    # Сбрасываем ссылки на игрока в аукционах (если он был победителем)
    cursor.execute("UPDATE auctions SET current_winner_id = NULL WHERE current_winner_id = ?", (player_id,))
    
    # Удаляем самого игрока
    cursor.execute("DELETE FROM players WHERE id = ?", (player_id,))
    
    conn.commit()
    conn.close()
    return True, f"Игрок '{nickname}' и все его данные удалены"
def update_player_nickname(old_nickname, new_nickname):
    """Изменяет никнейм игрока"""
    if not new_nickname.strip():
        return True, "Никнейм не изменен"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE players SET nickname = ? WHERE nickname = ?", (new_nickname.strip(), old_nickname))
        conn.commit()
        return True, "Никнейм успешно изменен"
    except sqlite3.IntegrityError:
        return False, "Игрок с таким никнеймом уже существует"
    finally:
        conn.close()
def update_player_password(nickname, new_password):
    """Изменяет пароль игрока"""
    if not new_password.strip():
        return True, "Пароль не изменен"
    conn = get_connection()
    cursor = conn.cursor()
    hashed = hash_password(new_password)
    cursor.execute("UPDATE players SET password = ? WHERE nickname = ?", (hashed, nickname))
    conn.commit()
    conn.close()
    return True, "Пароль успешно изменен"
init_db()
