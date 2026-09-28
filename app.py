import streamlit as st
import pandas as pd
import io
import database as db
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="TL DKP System", page_icon="⚔️", layout="wide")

# ===================== АВТОРИЗАЦИЯ =====================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("⚔️ Система DKP Гильдии HEID")
    st.markdown("### Войди в свой аккаунт или зарегистрируйся")

    tab_login, tab_register = st.tabs(["🔑 Вход", "📝 Регистрация"])

    with tab_login:
        with st.form("login_form"):
            nickname = st.text_input("Никнейм")
            password = st.text_input("Пароль", type="password")
            submitted = st.form_submit_button("Войти", use_container_width=True)
            if submitted:
                player = db.login(nickname.strip(), password)
                if player:
                    st.session_state.logged_in = True
                    st.session_state.player_id = player[0]
                    st.session_state.nickname = player[1]
                    st.session_state.role = player[2]
                    st.session_state.player_class = player[3]
                    st.session_state.current_dkp = player[4]
                    st.rerun()
                else:
                    st.error("❌ Неверный никнейм или пароль")

    with tab_register:
        with st.form("register_form"):
            new_nick = st.text_input("Никнейм")
            new_pass = st.text_input("Придумай пароль", type="password")
            new_class = st.selectbox("Класс", ["Воин", "Рыцарь", "Ассасин", "Лучник", "Маг", "Жрец", "Другое"])
            reg_submitted = st.form_submit_button("Зарегистрироваться", use_container_width=True)
            if reg_submitted:
                if new_nick.strip() and new_pass:
                    success, message = db.register_player(new_nick.strip(), new_pass, new_class, starting_dkp=10)
                    if success:
                        st.success(f"✅ {message}! Стартовый баланс: 10 DKP. Теперь войди на вкладке «Вход».")
                    else:
                        st.error(f"❌ {message}")
                else:
                    st.warning("Заполни все поля!")

    st.stop()

# ===================== ОСНОВНОЙ ИНТЕРФЕЙС =====================

# Автообновление каждые 10 секунд
st_autorefresh(interval=1000, key="auction_refresh")

# Обновляем баланс из БД
fresh_dkp = db.get_player_dkp(st.session_state.nickname)
if fresh_dkp is not None:
    st.session_state.current_dkp = fresh_dkp

is_admin = st.session_state.role == "admin"

# Шапка
st.title(f"⚔️ TL DKP System")
st.markdown(f"**👤 {st.session_state.nickname}** ({st.session_state.player_class}) | "
            f"{'👑 Офицер' if is_admin else '⚔️ Игрок'} | "
            f"💰 Баланс: **{st.session_state.current_dkp} DKP**")

# Кнопка выхода в сайдбаре
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state.nickname}")
    st.caption(f"{'👑 Офицер' if is_admin else '⚔️ Игрок'}")
    if st.button("🚪 Выйти из аккаунта", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Вкладки зависят от роли
if is_admin:
    t1, t2, t3, t4, t5, t6, t7 = st.tabs([
        "🔨 Аукцион", "📊 Лидеры", "➕ Игроки", "💰 DKP", "🎯 Рейд", "👤 Кабинет", "📤 Отчеты"
    ])
else:
    t1, t2, t3 = st.tabs([
        "🔨 Аукцион", "📊 Лидеры", "👤 Мой кабинет"
    ])

# ===================== 🔨 АУКЦИОН (для всех) =====================
with t1:
    st.subheader("🔨 Аукцион")

    active_auctions = db.get_active_auctions()

    if not active_auctions:
        st.info("Сейчас нет активных аукционов.")
    else:
        for auc in active_auctions:
            auc_id, item_name, start_price, current_max, end_time, winner_name = auc

            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    st.markdown(f"### 🏆 {item_name}")
                    st.caption(f"Стартовая цена: {start_price} DKP")

                with col2:
                    st.markdown(f"💰 Текущая ставка: **{current_max} DKP**")
                    if winner_name:
                        st.markdown(f"👤 Лидер: **{winner_name}**")
                    else:
                        st.markdown("👤 Пока нет ставок")

                with col3:
                    try:
                        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                        remaining = (end_dt - datetime.now()).total_seconds()
                        if remaining > 0:
                            mins = int(remaining // 60)
                            secs = int(remaining % 60)
                            color = "🟢" if remaining > 60 else "🔴"
                            st.markdown(f"⏰ {color} **{mins}:{secs:02d}**")
                        else:
                            st.markdown("⏰ **Завершён**")
                    except:
                        pass

                # Форма ставки
                with st.form(key=f"bid_form_{auc_id}"):
                    bc1, bc2 = st.columns([3, 1])
                    with bc1:
                        bid_amount = st.number_input(
                            "Твоя ставка",
                            min_value=current_max + 10,
                            value=current_max + 10,
                            step=10,
                            key=f"bid_input_{auc_id}"
                        )
                    with bc2:
                        bid_btn = st.form_submit_button("⚡ Поставить", use_container_width=True)

                    if bid_btn:
                        success, message = db.place_bid(auc_id, st.session_state.player_id, bid_amount)
                        if success:
                            st.success(f"✅ {message}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")

                # История ставок
                bids = db.get_auction_bids(auc_id)
                if bids:
                    with st.expander(f"📜 Все ставки ({len(bids)})"):
                        for bidder, amount, btime in bids[:10]:
                            st.caption(f"**{bidder}**: {amount} DKP — {btime}")

    # История завершённых аукционов
    st.markdown("---")
    st.markdown("#### 📜 Завершённые аукционы")
    history = db.get_auction_history()
    if history:
        hist_df = pd.DataFrame(history, columns=["Предмет", "Цена", "Победитель", "Дата"])
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
    else:
        st.caption("Пока нет завершённых аукционов")

# ===================== ВКЛАДКИ АДМИНА =====================
if is_admin:
    # --- 📊 Лидеры ---
    with t2:
        st.subheader("📊 Таблица лидеров")
        players = db.get_all_players()
        if players:
            df = pd.DataFrame(players, columns=["Никнейм", "Класс", "DKP", "Статус"])
            df["Статус"] = df["Статус"].apply(lambda x: "✅" if x == 1 else "❌")
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Нет игроков")

    # --- ➕ Игроки ---
        # --- ⚙️ Управление игроками ---
    with t3:
        st.subheader("⚙️ Управление учетными записями")
        st.caption("Выбери игрока и измени любые данные его аккаунта.")
        
        players = db.get_all_players()
        
        if players:
            player_names = [p[0] for p in players]
            
            # === БЛОК 1: РЕДАКТИРОВАНИЕ ===
            st.markdown("#### ✏️ Редактирование аккаунта")
            
            with st.form("edit_player_form"):
                target_player = st.selectbox("🎯 Выбери игрока", player_names)
                
                # Показываем текущие данные
                
                st.markdown("---")
                st.markdown("**Что изменить?** *(оставь пустым, если не хочешь менять)*")
                
                col1, col2 = st.columns(2)
                with col1:
                    new_nickname = st.text_input("🆕 Новый никнейм")
                    new_password = st.text_input("🔑 Новый пароль", type="password")
                with col2:
                    current_class = st.session_state.player_class if target_player == st.session_state.nickname else "Воин"
                    new_class = st.selectbox(
                        "⚔️ Класс", 
                        ["Воин", "Рыцарь", "Ассасин", "Лучник", "Маг", "Жрец", "Другое"])
  
                
                edit_submitted = st.form_submit_button("💾 Сохранить изменения", use_container_width=True, type="primary")
                
                if edit_submitted:
                    changes_made = []
                    
                    # 1. Меняем никнейм
                    if new_nickname.strip() and new_nickname.strip() != target_player:
                        success, message = db.update_player_nickname(target_player, new_nickname)
                        if success:
                            changes_made.append(f"✅ Никнейм: {target_player} → {new_nickname.strip()}")
                            target_player = new_nickname.strip()
                        else:
                            st.error(f"❌ Никнейм: {message}")
                    
                    # 2. Меняем пароль
                    if new_password.strip():
                        success, message = db.update_player_password(target_player, new_password)
                        if success:
                            changes_made.append(f"✅ Пароль изменен")
                        else:
                            st.error(f"❌ Пароль: {message}")
                    
                    # 3. Меняем класс
                    success, message = db.update_player_class(target_player, new_class)
                    if success:
                        changes_made.append(f"✅ Класс: {new_class}")
                    
                    # 4. Меняем роль
                    success, message = db.update_player_role(target_player, new_role)
                    if success:
                        changes_made.append(f"✅ Роль: {new_role}")
                    
                    if changes_made:
                        st.success("Изменения сохранены:")
                        for change in changes_made:
                            st.caption(change)
                        
                        # Если админ изменил свои собственные данные — выходим, чтобы применить
                        if target_player == st.session_state.nickname:
                            if new_nickname.strip() and new_nickname.strip() != st.session_state.nickname:
                                st.warning("⚠️ Ты изменил свой никнейм. Выйди и войди заново.")
                            if new_role != st.session_state.role:
                                st.warning("⚠️ Ты изменил свою роль. Выйди и войди заново.")
                        
                        st.balloons()
                        st.rerun()
            
            st.markdown("---")
            
            # === БЛОК 2: УДАЛЕНИЕ ===
            st.markdown("#### 🗑️ Удаление аккаунта")
            st.warning("⚠️ **Внимание!** Это действие необратимо. Будут удалены:")
            st.caption("• Все транзакции (история DKP)\n• Все ставки на аукционах\n• Сам аккаунт игрока")
            
            with st.form("delete_player_form"):
                player_to_delete = st.selectbox("🎯 Выбери игрока для удаления", player_names, key="delete_select")
                
                # Защита от удаления самого себя
                if player_to_delete == st.session_state.nickname:
                    st.error("🚫 Ты не можешь удалить сам себя!")
                    confirm_delete = False
                else:
                    confirm_delete = st.checkbox(f"☑️ Я подтверждаю удаление игрока **{player_to_delete}**")
                
                delete_submitted = st.form_submit_button(
                    "🗑️ Удалить аккаунт", 
                    use_container_width=True,
                    disabled=(player_to_delete == st.session_state.nickname),
                    type="secondary"
                )
                
                if delete_submitted:
                    if confirm_delete:
                        success, message = db.delete_player(player_to_delete)
                        if success:
                            st.success(f"✅ {message}")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                    else:
                        st.warning("Поставь галочку подтверждения!")
        else:
            st.info("В базе пока нет игроков.")
    # --- 💰 DKP ---
    with t4:
        st.subheader("💰 Изменить DKP")
        players = db.get_all_players()
        if players:
            player_names = [p[0] for p in players]
            with st.form("change_dkp_form"):
                selected = st.selectbox("Игрок", player_names)
                amount = st.number_input("Сумма (+ начислить, - списать)", value=10)
                desc = st.text_input("Причина")
                submitted = st.form_submit_button("Применить")
                if submitted:
                    success, message = db.change_dkp(selected, amount, desc)
                    if success:
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")

        st.markdown("---")
        st.subheader("🔨 Создать аукцион")
        with st.form("create_auction_form"):
            item_name = st.text_input("Название предмета")
            start_price = st.number_input("Стартовая цена", min_value=1, value=50, step=10)
            duration = st.selectbox("Длительность", [3, 5, 10, 15], index=1, format_func=lambda x: f"{x} минут")
            submitted = st.form_submit_button("🔨 Выставить на аукцион")
            if submitted:
                if item_name.strip():
                    success, message = db.create_auction(item_name.strip(), start_price, duration)
                    st.success(f"✅ {message}")
                    st.rerun()
                else:
                    st.warning("Введи название предмета!")

    # --- 🎯 Рейд ---
    with t5:
        st.subheader("🎯 Массовое начисление DKP за рейд")
        players = db.get_all_players()
        if players:
            player_names = [p[0] for p in players]
            with st.form("raid_form"):
                selected = st.multiselect("Участники рейда", player_names)
                amount = st.number_input("DKP за явку", min_value=1, value=50, step=10)
                desc = st.text_input("Описание рейда", value="Рейд")
                submitted = st.form_submit_button("💰 Начислить всем")
                if submitted:
                    if selected:
                        ok, err = db.mass_award_dkp(selected, amount, desc)
                        if ok:
                            st.success(f"✅ Начислено {len(ok)} игрокам")
                            for m in ok:
                                st.caption(m)
                            st.balloons()
                            st.rerun()
                        if err:
                            for m in err:
                                st.error(m)
                    else:
                        st.warning("Выбери хотя бы одного игрока!")

    # --- 👤 Кабинет ---
    with t6:
        st.subheader(f"👤 Кабинет: {st.session_state.nickname}")
        st.success(f"💰 Баланс: **{st.session_state.current_dkp} DKP**")
        history = db.get_player_history(st.session_state.nickname)
        if history:
            data = []
            for amount, t_type, desc, created in history:
                icon = "🟢" if t_type == "earn" else "🔴"
                action = "Начисление" if t_type == "earn" else "Списание"
                data.append({"Дата": created, "Тип": f"{icon} {action}", "Сумма": f"+{amount}" if amount > 0 else str(amount), "Описание": desc or "—"})
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    # --- 📤 Отчеты ---
    with t7:
        st.subheader("📤 Экспорт отчетов")
        col1, col2 = st.columns(2)
        with col1:
            players_data = db.get_full_report()
            if players_data:
                df = pd.DataFrame(players_data, columns=["Никнейм", "Класс", "DKP", "Статус", "Дата"])
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Лидеры')
                output.seek(0)
                st.download_button("📥 Скачать таблицу лидеров", output, "tl_dkp_leaders.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with col2:
            trans_data = db.get_all_transactions()
            if trans_data:
                data = []
                for nick, amount, t_type, desc, created in trans_data:
                    data.append({"Игрок": nick, "Тип": "Начисление" if t_type == "earn" else "Списание", "Сумма": amount, "Описание": desc or "—", "Дата": created})
                df = pd.DataFrame(data)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Транзакции')
                output.seek(0)
                st.download_button("📥 Скачать транзакции", output, "tl_dkp_transactions.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

# ===================== ВКЛАДКИ ИГРОКА =====================
if not is_admin:
    # --- 📊 Лидеры ---
    with t2:
        st.subheader("📊 Таблица лидеров")
        players = db.get_all_players()
        if players:
            df = pd.DataFrame(players, columns=["Никнейм", "Класс", "DKP", "Статус"])
            df["Статус"] = df["Статус"].apply(lambda x: "✅" if x == 1 else "❌")
            st.dataframe(df, use_container_width=True, hide_index=True)

    # --- 👤 Мой кабинет ---
    with t3:
        st.subheader(f"👤 Мой кабинет")
        st.success(f"💰 Твой баланс: **{st.session_state.current_dkp} DKP**")
        history = db.get_player_history(st.session_state.nickname)
        if history:
            data = []
            total_earned = 0
            total_spent = 0
            for amount, t_type, desc, created in history:
                icon = "🟢" if t_type == "earn" else "🔴"
                action = "Начисление" if t_type == "earn" else "Списание"
                data.append({"Дата": created, "Тип": f"{icon} {action}", "Сумма": f"+{amount}" if amount > 0 else str(amount), "Описание": desc or "—"})
                if t_type == "earn":
                    total_earned += amount
                else:
                    total_spent += abs(amount)
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            c1.metric("Заработано", f"{total_earned} DKP")
            c2.metric("Потрачено", f"{total_spent} DKP")
            c3.metric("Баланс", f"{st.session_state.current_dkp} DKP")
