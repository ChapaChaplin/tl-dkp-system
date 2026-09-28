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
    st.title("⚔️ Система DKP для Throne and Liberty")
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
st_autorefresh(interval=5000, key="auction_refresh")

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
        st.info("Сейчас нет активных аукционов. Аукцион обновляется каждые 5 секунд.")
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
    with t3:
        st.subheader("➕ Добавить игрока")
        with st.form("add_player_form"):
            nickname = st.text_input("Никнейм")
            password = st.text_input("Пароль для игрока", type="password")
            player_class = st.selectbox("Класс", ["Воин", "Рыцарь", "Ассасин", "Лучник", "Маг", "Жрец", "Другое"])
            starting_dkp = st.number_input("Стартовый DKP", min_value=0, value=100, step=10)
            submitted = st.form_submit_button("Добавить")
            if submitted:
                if nickname.strip() and password:
                    success, message = db.register_player(nickname.strip(), password, player_class, 'player', starting_dkp)
                    if success:
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
                else:
                    st.warning("Заполни все поля!")

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
