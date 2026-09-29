from supabase import create_client, Client
from datetime import datetime, timedelta
import hashlib
import os

# Подключение к Supabase (ключи нужно будет добавить в Secrets на Streamlit)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://hdfcmicyckybkwmlejxb.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhkZmNtaWN5Y2t5Ymt3bWxlanhiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA2NDE3NzEsImV4cCI6MjEwNjIxNzc3MX0.C9xLEqVYXRyrxCYkYQEKZlhlrsCCOB1brgcjacGtIBs")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ========== АВТОРИЗАЦИЯ ==========

def login(nickname, password):
    hashed = hash_password(password)
    response = supabase.table("players").select("id, nickname, role, class, current_dkp").eq("nickname", nickname).eq("password", hashed).eq("is_active", 1).execute()
    if response.data:
        player = response.data[0]
        return (player["id"], player["nickname"], player["role"], player["class"], player["current_dkp"])
    return None

def register_player(nickname, password, player_class, role='player', starting_dkp=0):
    if nickname.strip().lower() == "admin":
        role = "admin"
        starting_dkp = 0
    
    hashed = hash_password(password)
    try:
        response = supabase.table("players").insert({
            "nickname": nickname.strip(),
            "password": hashed,
            "role": role,
            "class": player_class,
            "current_dkp": starting_dkp
        }).execute()
        
        player_id = response.data[0]["id"]
        
        if starting_dkp > 0:
            supabase.table("transactions").insert({
                "player_id": player_id,
                "amount": starting_dkp,
                "type": "earn",
                "description": "Стартовый баланс"
            }).execute()
        
        return True, "Игрок зарегистрирован"
    except Exception as e:
        if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
            return False, "Игрок с таким ником уже существует"
        return False, f"Ошибка: {str(e)}"

# ========== ИГРОКИ ==========

def get_all_players():
    response = supabase.table("players").select("nickname, class, current_dkp, is_active").eq("is_active", 1).order("current_dkp", desc=True).execute()
    return [(p["nickname"], p["class"], p["current_dkp"], p["is_active"]) for p in response.data]

def get_player_dkp(nickname):
    response = supabase.table("players").select("current_dkp").eq("nickname", nickname).execute()
    return response.data[0]["current_dkp"] if response.data else None

def change_dkp(nickname, amount, description=""):
    response = supabase.table("players").select("id, current_dkp").eq("nickname", nickname).execute()
    if not response.data:
        return False, "Игрок не найден"
    
    player = response.data[0]
    player_id = player["id"]
    current_dkp = player["current_dkp"]
    new_dkp = current_dkp + amount
    
    supabase.table("players").update({"current_dkp": new_dkp}).eq("id", player_id).execute()
    
    trans_type = "earn" if amount > 0 else "spend"
    supabase.table("transactions").insert({
        "player_id": player_id,
        "amount": amount,
        "type": trans_type,
        "description": description
    }).execute()
    
    return True, f"DKP изменен. Новый баланс: {new_dkp}"

def mass_award_dkp(player_nicknames, amount, description=""):
    success_list = []
    error_list = []
    
    for nickname in player_nicknames:
        response = supabase.table("players").select("id, current_dkp").eq("nickname", nickname).execute()
        if not response.data:
            error_list.append(f"{nickname}: не найден")
            continue
        
        player = response.data[0]
        player_id = player["id"]
        current_dkp = player["current_dkp"]
        new_dkp = current_dkp + amount
        
        supabase.table("players").update({"current_dkp": new_dkp}).eq("id", player_id).execute()
        supabase.table("transactions").insert({
            "player_id": player_id,
            "amount": amount,
            "type": "earn",
            "description": description
        }).execute()
        
        success_list.append(f"{nickname}: +{amount} DKP (баланс: {new_dkp})")
    
    return success_list, error_list

# ========== ИСТОРИЯ ==========

def get_player_history(nickname):
    response = supabase.table("players").select("id").eq("nickname", nickname).execute()
    if not response.data:
        return None
    
    player_id = response.data[0]["id"]
    response = supabase.table("transactions").select("amount, type, description, created_at").eq("player_id", player_id).order("created_at", desc=True).execute()
    
    return [(t["amount"], t["type"], t["description"], t["created_at"]) for t in response.data]

# ========== АУКЦИОН ==========

def create_auction(item_name, start_price, duration_minutes=5):
    end_time = (datetime.now() + timedelta(minutes=duration_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    supabase.table("auctions").insert({
        "item_name": item_name,
        "start_price": start_price,
        "current_max_bid": start_price,
        "status": "active",
        "end_time": end_time
    }).execute()
    return True, f"Лот создан! Торги до {end_time}"

def check_expired_auctions():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response = supabase.table("auctions").select("id, current_winner_id, current_max_bid, item_name").eq("status", "active").lte("end_time", now).execute()
    
    for auction in response.data:
        auc_id = auction["id"]
        winner_id = auction["current_winner_id"]
        final_price = auction["current_max_bid"]
        item_name = auction["item_name"]
        
        if winner_id:
            player_resp = supabase.table("players").select("current_dkp").eq("id", winner_id).execute()
            if player_resp.data:
                new_dkp = player_resp.data[0]["current_dkp"] - final_price
                supabase.table("players").update({"current_dkp": new_dkp}).eq("id", winner_id).execute()
                supabase.table("transactions").insert({
                    "player_id": winner_id,
                    "amount": -final_price,
                    "type": "spend",
                    "description": f"Покупка: {item_name}"
                }).execute()
        
        supabase.table("auctions").update({"status": "sold"}).eq("id", auc_id).execute()

def get_active_auctions():
    check_expired_auctions()
    response = supabase.table("auctions").select("id, item_name, start_price, current_max_bid, end_time, current_winner_id").eq("status", "active").order("id", desc=True).execute()
    
    auctions = []
    for auc in response.data:
        winner_name = None
        if auc["current_winner_id"]:
            winner_resp = supabase.table("players").select("nickname").eq("id", auc["current_winner_id"]).execute()
            if winner_resp.data:
                winner_name = winner_resp.data[0]["nickname"]
        auctions.append((auc["id"], auc["item_name"], auc["start_price"], auc["current_max_bid"], auc["end_time"], winner_name))
    
    return auctions

def place_bid(auction_id, player_id, bid_amount):
    auction_resp = supabase.table("auctions").select("current_max_bid, end_time, status").eq("id", auction_id).execute()
    if not auction_resp.data:
        return False, "Аукцион не найден"
    
    auction = auction_resp.data[0]
    current_max = auction["current_max_bid"]
    end_time = auction["end_time"]
    status = auction["status"]
    
    if status != 'active':
        return False, "Аукцион уже закрыт"
    
    if datetime.now().strftime("%Y-%m-%d %H:%M:%S") > end_time:
        return False, "Время аукциона истекло"
    
    if bid_amount <= current_max:
        return False, f"Ставка должна быть выше {current_max} DKP"
    
    player_resp = supabase.table("players").select("current_dkp").eq("id", player_id).execute()
    if not player_resp.data or player_resp.data[0]["current_dkp"] < bid_amount:
        current_dkp = player_resp.data[0]["current_dkp"] if player_resp.data else 0
        return False, f"Недостаточно DKP! У тебя {current_dkp}, нужно {bid_amount}"
    
    supabase.table("bids").insert({
        "auction_id": auction_id,
        "player_id": player_id,
        "amount": bid_amount
    }).execute()
    
    supabase.table("auctions").update({
        "current_max_bid": bid_amount,
        "current_winner_id": player_id
    }).eq("id", auction_id).execute()
    
    end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    if (end_dt - datetime.now()).total_seconds() < 60:
        new_end = (end_dt + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
        supabase.table("auctions").update({"end_time": new_end}).eq("id", auction_id).execute()
    
    return True, f"Ставка {bid_amount} DKP принята!"

def get_auction_bids(auction_id):
    response = supabase.table("bids").select("player_id, amount, created_at").eq("auction_id", auction_id).order("amount", desc=True).execute()
    
    bids = []
    for bid in response.data:
        player_resp = supabase.table("players").select("nickname").eq("id", bid["player_id"]).execute()
        if player_resp.data:
            bids.append((player_resp.data[0]["nickname"], bid["amount"], bid["created_at"]))
    
    return bids

def get_auction_history():
    response = supabase.table("auctions").select("item_name, current_max_bid, current_winner_id, created_at").eq("status", "sold").order("id", desc=True).limit(20).execute()
    
    history = []
    for auc in response.data:
        winner_name = None
        if auc["current_winner_id"]:
            winner_resp = supabase.table("players").select("nickname").eq("id", auc["current_winner_id"]).execute()
            if winner_resp.data:
                winner_name = winner_resp.data[0]["nickname"]
        history.append((auc["item_name"], auc["current_max_bid"], winner_name, auc["created_at"]))
    
    return history

# ========== УПРАВЛЕНИЕ АККАУНТАМИ ==========

def get_player_role(nickname):
    response = supabase.table("players").select("role").eq("nickname", nickname).execute()
    return response.data[0]["role"] if response.data else 'player'

def update_player_nickname(old_nickname, new_nickname):
    if not new_nickname.strip():
        return True, "Никнейм не изменен"
    try:
        supabase.table("players").update({"nickname": new_nickname.strip()}).eq("nickname", old_nickname).execute()
        return True, "Никнейм успешно изменен"
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            return False, "Игрок с таким никнеймом уже существует"
        return False, str(e)

def update_player_password(nickname, new_password):
    if not new_password.strip():
        return True, "Пароль не изменен"
    hashed = hash_password(new_password)
    supabase.table("players").update({"password": hashed}).eq("nickname", nickname).execute()
    return True, "Пароль успешно изменен"

def update_player_role(nickname, new_role):
    supabase.table("players").update({"role": new_role}).eq("nickname", nickname).execute()
    return True, f"Роль изменена на '{new_role}'"

def update_player_class(nickname, new_class):
    supabase.table("players").update({"class": new_class}).eq("nickname", nickname).execute()
    return True, f"Класс изменен на '{new_class}'"

def delete_player(nickname):
    response = supabase.table("players").select("id").eq("nickname", nickname).execute()
    if not response.data:
        return False, "Игрок не найден"
    
    player_id = response.data[0]["id"]
    
    supabase.table("transactions").delete().eq("player_id", player_id).execute()
    supabase.table("bids").delete().eq("player_id", player_id).execute()
    supabase.table("auctions").update({"current_winner_id": None}).eq("current_winner_id", player_id).execute()
    supabase.table("players").delete().eq("id", player_id).execute()
    
    return True, f"Игрок '{nickname}' и все его данные удалены"

# ========== ЭКСПОРТ ==========

def get_full_report():
    response = supabase.table("players").select("nickname, class, current_dkp, is_active, created_at").order("current_dkp", desc=True).execute()
    return [(p["nickname"], p["class"], p["current_dkp"], p["is_active"], p["created_at"]) for p in response.data]

def get_all_transactions():
    response = supabase.table("transactions").select("player_id, amount, type, description, created_at").order("created_at", desc=True).execute()
    
    transactions = []
    for t in response.data:
        player_resp = supabase.table("players").select("nickname").eq("id", t["player_id"]).execute()
        if player_resp.data:
            transactions.append((player_resp.data[0]["nickname"], t["amount"], t["type"], t["description"], t["created_at"]))
    
    return transactions