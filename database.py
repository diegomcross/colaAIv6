# database.py
import sqlite3
import datetime
import pytz
import json
from constants import DB_NAME
from typing import List, Dict, Set, Optional, Tuple

def init_db():
    print("DEBUG: init_db - Iniciando")
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # --- Tabela server_configs ---
    cursor.execute("PRAGMA table_info(server_configs)")
    server_configs_columns = [column['name'] for column in cursor.fetchall()]

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS server_configs (
            guild_id INTEGER PRIMARY KEY,
            digest_channel_id INTEGER,
            ranking_channel_id INTEGER,
            mod_notification_channel_id INTEGER,
            penalty_role_id INTEGER,
            clan_admin_discord_id INTEGER,
            clan_role_id INTEGER
        )
    ''')
    if 'ranking_channel_id' not in server_configs_columns:
        try: cursor.execute("ALTER TABLE server_configs ADD COLUMN ranking_channel_id INTEGER")
        except sqlite3.OperationalError: pass
    if 'mod_notification_channel_id' not in server_configs_columns:
        try: cursor.execute("ALTER TABLE server_configs ADD COLUMN mod_notification_channel_id INTEGER")
        except sqlite3.OperationalError: pass
    if 'penalty_role_id' not in server_configs_columns:
        try: cursor.execute("ALTER TABLE server_configs ADD COLUMN penalty_role_id INTEGER")
        except sqlite3.OperationalError: pass
    if 'clan_admin_discord_id' not in server_configs_columns:
        try: cursor.execute("ALTER TABLE server_configs ADD COLUMN clan_admin_discord_id INTEGER")
        except sqlite3.OperationalError: pass
    if 'clan_role_id' not in server_configs_columns:
        try: cursor.execute("ALTER TABLE server_configs ADD COLUMN clan_role_id INTEGER")
        except sqlite3.OperationalError: pass


    # --- Tabela bungie_profiles ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bungie_profiles (
            discord_id INTEGER PRIMARY KEY,
            bungie_membership_id TEXT NOT NULL,
            bungie_membership_type INTEGER NOT NULL,
            bungie_name TEXT,
            access_token TEXT,
            refresh_token TEXT,
            token_expires_at TEXT
        )
    ''')

    # --- Tabela pending_clan_invites ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_clan_invites (
            bungie_membership_id TEXT PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL
        )
    ''')


    # --- Tabela event_permissions ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_permissions (
            guild_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            PRIMARY KEY (guild_id, role_id, permission)
        )
    ''')

    # --- Tabela events ---
    cursor.execute("PRAGMA table_info(events)")
    events_columns = [column['name'] for column in cursor.fetchall()]

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, 
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL, 
            creator_id INTEGER NOT NULL,
            title TEXT NOT NULL, 
            description TEXT, 
            event_time_utc TEXT NOT NULL, 
            activity_type TEXT NOT NULL, 
            max_attendees INTEGER NOT NULL,
            created_at_utc TEXT NOT NULL,
            message_id INTEGER UNIQUE,
            status TEXT DEFAULT 'ativo', 
            delete_message_after_utc TEXT, 
            reminder_sent INTEGER DEFAULT 0, 
            temp_role_id INTEGER,
            confirmation_reminder_sent INTEGER DEFAULT 0,
            thread_id INTEGER,
            voice_channel_id INTEGER,
            attendance_checked INTEGER DEFAULT 0
        )
    ''')
    if 'attendance_checked' not in events_columns:
        try: cursor.execute("ALTER TABLE events ADD COLUMN attendance_checked INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass

    # --- Tabela rsvps ---
    cursor.execute("PRAGMA table_info(rsvps)")
    rsvps_columns = [column['name'] for column in cursor.fetchall()]

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rsvps (
            rsvp_id INTEGER PRIMARY KEY AUTOINCREMENT, 
            event_id INTEGER NOT NULL, 
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL, 
            rsvp_timestamp TEXT NOT NULL,
            attendance_status TEXT DEFAULT 'pendente',
            UNIQUE(event_id, user_id), 
            FOREIGN KEY (event_id) REFERENCES events (event_id) ON DELETE CASCADE
        )''')

    if 'attendance_status' not in rsvps_columns:
        try: cursor.execute("ALTER TABLE rsvps ADD COLUMN attendance_status TEXT DEFAULT 'pendente'")
        except sqlite3.OperationalError: pass

    # --- Tabela voice_sessions ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voice_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            session_start_utc TEXT NOT NULL,
            session_end_utc TEXT,
            duration_seconds INTEGER
        )
    ''')

    # --- Tabela ranking_roles ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ranking_roles (
            guild_id INTEGER PRIMARY KEY,
            role_tier_1_id INTEGER,
            role_tier_2_id INTEGER,
            role_tier_3_id INTEGER,
            role_tier_4_id INTEGER
        )
    ''')

    # --- Tabela designated_event_channels ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS designated_event_channels (
            guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, PRIMARY KEY (guild_id, channel_id)
        )''')

    conn.commit()
    if conn: conn.close()
    print("DEBUG: init_db - Concluído, schema verificado/atualizado.")

def db_track_pending_invite(bungie_membership_id: str, guild_id: int, message_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    expires_at = (datetime.datetime.now(pytz.utc) + datetime.timedelta(days=7)).isoformat()
    try:
        cursor.execute(
            "INSERT INTO pending_clan_invites (bungie_membership_id, guild_id, message_id, expires_at) VALUES (?, ?, ?, ?)",
            (bungie_membership_id, guild_id, message_id, expires_at)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"Erro DB ao rastrear convite pendente para {bungie_membership_id}: {e}")
    finally:
        if conn: conn.close()

def db_untrack_pending_invite(bungie_membership_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM pending_clan_invites WHERE bungie_membership_id = ?", (bungie_membership_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Erro DB ao remover rastreamento de convite para {bungie_membership_id}: {e}")
    finally:
        if conn: conn.close()

def db_is_invite_tracked(bungie_membership_id: str) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM pending_clan_invites WHERE bungie_membership_id = ?", (bungie_membership_id,))
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(f"Erro DB ao verificar se convite é rastreado para {bungie_membership_id}: {e}")
        return False
    finally:
        if conn: conn.close()

def db_prune_expired_invites():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now_utc_iso = datetime.datetime.now(pytz.utc).isoformat()
    try:
        cursor.execute("DELETE FROM pending_clan_invites WHERE expires_at <= ?", (now_utc_iso,))
        conn.commit()
        print(f"DB Cleanup: {cursor.rowcount} convites pendentes expirados foram removidos.")
    except sqlite3.Error as e:
        print(f"Erro DB ao podar convites expirados: {e}")
    finally:
        if conn: conn.close()

def db_set_server_config(guild_id: int, **kwargs):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO server_configs (guild_id) VALUES (?)", (guild_id,))
    updates = [f"{key} = ?" for key in kwargs]
    params = list(kwargs.values())
    params.append(guild_id)
    query = f"UPDATE server_configs SET {', '.join(updates)} WHERE guild_id = ?"
    try:
        cursor.execute(query, tuple(params))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Erro DB ao atualizar server_configs: {e}")
    finally:
        if conn: conn.close()

def db_get_server_configs(guild_id: int) -> Optional[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM server_configs WHERE guild_id = ?", (guild_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"Erro DB ao buscar server_configs: {e}")
        return None
    finally:
        if conn: conn.close()

def db_get_bungie_profile_by_bnet_id(bungie_membership_id: str) -> Optional[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM bungie_profiles WHERE bungie_membership_id = ?", (bungie_membership_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"Erro DB ao buscar perfil Bungie pelo bnet_id {bungie_membership_id}: {e}")
        return None
    finally:
        if conn: conn.close()

def db_set_ranking_roles(guild_id: int, role_ids: Dict[int, int]):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO ranking_roles (guild_id, role_tier_1_id, role_tier_2_id, role_tier_3_id, role_tier_4_id) 
            VALUES (?, ?, ?, ?, ?) 
            ON CONFLICT(guild_id) DO UPDATE SET 
            role_tier_1_id = excluded.role_tier_1_id, role_tier_2_id = excluded.role_tier_2_id,
            role_tier_3_id = excluded.role_tier_3_id, role_tier_4_id = excluded.role_tier_4_id
        ''', (guild_id, role_ids.get(1), role_ids.get(2), role_ids.get(3), role_ids.get(4)))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Erro DB ao definir cargos de ranking: {e}")
    finally:
        if conn: conn.close()

def db_get_ranking_roles(guild_id: int) -> Optional[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM ranking_roles WHERE guild_id = ?", (guild_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"Erro DB ao buscar cargos de ranking: {e}")
        return None
    finally:
        if conn: conn.close()

def db_save_bungie_profile(discord_id: int, bungie_membership_id: str, bungie_membership_type: int, bungie_name: str, access_token: str, refresh_token: str, token_expires_at: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO bungie_profiles (discord_id, bungie_membership_id, bungie_membership_type, bungie_name, access_token, refresh_token, token_expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                bungie_membership_id = excluded.bungie_membership_id,
                bungie_membership_type = excluded.bungie_membership_type,
                bungie_name = excluded.bungie_name,
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                token_expires_at = excluded.token_expires_at
        ''', (discord_id, bungie_membership_id, bungie_membership_type, bungie_name, access_token, refresh_token, token_expires_at))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Erro DB ao salvar perfil Bungie para user {discord_id}: {e}")
    finally:
        if conn: conn.close()

def db_get_bungie_profile(discord_id: int) -> Optional[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM bungie_profiles WHERE discord_id = ?", (discord_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"Erro DB ao buscar perfil Bungie para user {discord_id}: {e}")
        return None
    finally:
        if conn: conn.close()

def db_get_all_linked_profiles() -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT discord_id, bungie_membership_id FROM bungie_profiles")
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Erro DB ao buscar todos os perfis vinculados: {e}")
        return []
    finally:
        if conn: conn.close()

def db_get_user_weekly_voice_time(guild_id: int, user_id: int) -> int:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    total_seconds = 0
    seven_days_ago = (datetime.datetime.now(pytz.utc) - datetime.timedelta(days=7)).isoformat()
    try:
        cursor.execute(
            "SELECT SUM(duration_seconds) FROM voice_sessions WHERE guild_id = ? AND user_id = ? AND session_start_utc >= ?",
            (guild_id, user_id, seven_days_ago)
        )
        result = cursor.fetchone()
        if result and result[0] is not None:
            total_seconds = int(result[0])
    except sqlite3.Error as e:
        print(f"Erro DB ao calcular tempo de voz semanal para user {user_id}: {e}")
    finally:
        if conn: conn.close()
    return total_seconds

def db_get_all_users_weekly_voice_time(guild_id: int) -> List[Tuple[int, int]]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    results = []
    seven_days_ago = (datetime.datetime.now(pytz.utc) - datetime.timedelta(days=7)).isoformat()
    try:
        cursor.execute(
            "SELECT user_id, SUM(duration_seconds) as total_time FROM voice_sessions WHERE guild_id = ? AND session_start_utc >= ? GROUP BY user_id ORDER BY total_time DESC",
            (guild_id, seven_days_ago)
        )
        results = [tuple(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Erro DB ao buscar tempo de voz semanal de todos os users: {e}")
    finally:
        if conn: conn.close()
    return results

def db_get_inactive_members(guild_id: int, weeks_inactive: int) -> List[int]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    inactive_users = []
    cutoff_date = (datetime.datetime.now(pytz.utc) - datetime.timedelta(weeks=weeks_inactive)).isoformat()
    try:
        cursor.execute("SELECT DISTINCT user_id FROM rsvps INNER JOIN events ON rsvps.event_id = events.event_id WHERE events.guild_id = ?", (guild_id,))
        all_rsvpd_users = [row[0] for row in cursor.fetchall()]

        for user_id in all_rsvpd_users:
            cursor.execute('''
                SELECT MAX(events.event_time_utc) 
                FROM rsvps 
                INNER JOIN events ON rsvps.event_id = events.event_id 
                WHERE rsvps.user_id = ? AND events.guild_id = ? AND rsvps.attendance_status = 'compareceu'
            ''', (user_id, guild_id))
            last_attended_row = cursor.fetchone()

            if last_attended_row is None or last_attended_row[0] is None or last_attended_row[0] < cutoff_date:
                inactive_users.append(user_id)
    except sqlite3.Error as e:
        print(f"Erro DB ao buscar membros inativos: {e}")
    finally:
        if conn: conn.close()
    return inactive_users

def db_log_voice_session(user_id: int, guild_id: int, session_start_utc: str, session_end_utc: str, duration_seconds: int):
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO voice_sessions (user_id, guild_id, session_start_utc, session_end_utc, duration_seconds) VALUES (?, ?, ?, ?, ?)",
            (user_id, guild_id, session_start_utc, session_end_utc, duration_seconds)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"Erro DB ao registar sessão de voz para user {user_id}: {e}")
    finally:
        if conn:
            conn.close()

def db_add_event_permission(guild_id: int, role_id: int, permission: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO event_permissions (guild_id, role_id, permission) VALUES (?, ?, ?)", (guild_id, role_id, permission))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Erro DB ao adicionar permissão de evento: {e}")
    finally:
        if conn: conn.close()

def db_remove_event_permission(guild_id: int, role_id: int, permission: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM event_permissions WHERE guild_id = ? AND role_id = ? AND permission = ?", (guild_id, role_id, permission))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Erro DB ao remover permissão de evento: {e}")
    finally:
        if conn: conn.close()

def db_get_roles_with_permission(guild_id: int, permission: str) -> List[int]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT role_id FROM event_permissions WHERE guild_id = ? AND permission = ?", (guild_id, permission))
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Erro DB ao buscar cargos com permissão '{permission}': {e}")
        return []
    finally:
        if conn: conn.close()

def db_get_all_event_permissions(guild_id: int) -> Dict[int, List[str]]:
    permissions_by_role: Dict[int, List[str]] = {}
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT role_id, permission FROM event_permissions WHERE guild_id = ?", (guild_id,))
        for role_id, permission in cursor.fetchall():
            if role_id not in permissions_by_role:
                permissions_by_role[role_id] = []
            permissions_by_role[role_id].append(permission)
    except sqlite3.Error as e:
        print(f"Erro DB ao buscar todas as permissões de evento: {e}")
    finally:
        if conn: conn.close()
    return permissions_by_role

def db_check_user_permission(guild_id: int, user_roles_ids: Set[int], permission: str) -> bool:
    roles_with_perm = db_get_roles_with_permission(guild_id, permission)
    if not roles_with_perm:
        return False
    return not user_roles_ids.isdisjoint(roles_with_perm)

def db_add_designated_event_channel(guild_id: int, channel_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO designated_event_channels (guild_id, channel_id) VALUES (?, ?)", (guild_id, channel_id))
        conn.commit()
    except sqlite3.Error as e: print(f"Erro DB ao adicionar canal designado: {e}")
    finally:
        if conn: conn.close()

def db_remove_designated_event_channel(guild_id: int, channel_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM designated_event_channels WHERE guild_id = ? AND channel_id = ?", (guild_id, channel_id))
        conn.commit()
    except sqlite3.Error as e: print(f"Erro DB ao remover canal designado: {e}")
    finally:
        if conn: conn.close()

def db_get_designated_event_channels(guild_id: int) -> list[int]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT channel_id FROM designated_event_channels WHERE guild_id = ?", (guild_id,))
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e: print(f"Erro DB ao buscar canais designados: {e}"); return []
    finally:
        if conn: conn.close()

def db_add_or_update_rsvp(event_id: int, user_id: int, status: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp_utc = datetime.datetime.now(pytz.utc).isoformat()
    try:
        cursor.execute('''
            INSERT INTO rsvps (event_id, user_id, status, rsvp_timestamp, attendance_status) 
            VALUES (?, ?, ?, ?, 'pendente')
            ON CONFLICT(event_id, user_id) DO UPDATE SET 
            status = excluded.status, 
            rsvp_timestamp = excluded.rsvp_timestamp
        ''', (event_id, user_id, status, timestamp_utc))
        conn.commit()
    except sqlite3.Error as e: print(f"Erro DB ao adicionar/atualizar RSVP: {e}")
    finally:
        if conn: conn.close()

def db_remove_rsvp(event_id: int, user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM rsvps WHERE event_id = ? AND user_id = ?", (event_id, user_id))
        conn.commit()
    except sqlite3.Error as e: print(f"Erro DB ao remover RSVP: {e}")
    finally:
        if conn: conn.close()

def db_get_rsvps_for_event(event_id: int) -> dict:
    rsvps = {'vou': [], 'nao_vou': [], 'talvez': [], 'lista_espera': []}
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id, status FROM rsvps WHERE event_id = ? ORDER BY rsvp_timestamp ASC", (event_id,))
        for row in cursor.fetchall():
            if row['status'] in rsvps: rsvps[row['status']].append(row['user_id'])
    except sqlite3.Error as e: print(f"Erro DB ao buscar RSVPs: {e}")
    finally:
        if conn: conn.close()
    return rsvps

def db_get_user_active_rsvps_in_guild(user_id: int, guild_id: int) -> list[int]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT event_id FROM rsvps 
            WHERE user_id = ? AND event_id IN 
            (SELECT event_id FROM events WHERE guild_id = ? AND status = 'ativo')
        ''', (user_id, guild_id))
        return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Erro DB ao buscar RSVPs ativos do usuário na guild: {e}")
        return []
    finally:
        if conn: conn.close()

def db_get_event_details(event_id: int) -> Optional[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
        return cursor.fetchone()
    except sqlite3.Error as e: print(f"Erro DB ao buscar detalhes do evento {event_id}: {e}"); return None
    finally:
        if conn: conn.close()

def db_update_event_status(event_id: int, status: str, delete_after_utc: Optional[str] = None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        if delete_after_utc:
            cursor.execute("UPDATE events SET status = ?, delete_message_after_utc = ? WHERE event_id = ?", (status, delete_after_utc, event_id))
        else:
            cursor.execute("UPDATE events SET status = ?, delete_message_after_utc = NULL WHERE event_id = ?", (status, event_id))
        conn.commit()
    except sqlite3.Error as e: print(f"Erro DB ao atualizar status do evento {event_id}: {e}")
    finally:
        if conn: conn.close()

def db_update_event_details(event_id: int, **kwargs):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    updates = [f"{key} = ?" for key in kwargs]
    params = list(kwargs.values())
    if not updates:
        return
    params.append(event_id)
    query = f"UPDATE events SET {', '.join(updates)} WHERE event_id = ?"
    try:
        cursor.execute(query, tuple(params))
        conn.commit()
    except sqlite3.Error as e: print(f"Erro no DB ao atualizar detalhes do evento {event_id}: {e}")
    finally:
        if conn: conn.close()

def db_get_events_for_cleanup() -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    two_hours_ago = datetime.datetime.now(pytz.utc) - datetime.timedelta(hours=2)
    try:
        cursor.execute("SELECT * FROM events WHERE status = 'ativo' AND event_time_utc < ?", (two_hours_ago.isoformat(),))
        return cursor.fetchall()
    except sqlite3.Error as e: print(f"Erro DB ao buscar eventos para cleanup: {e}"); return []
    finally:
        if conn: conn.close()

def db_get_events_to_delete_message() -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    now_utc = datetime.datetime.now(pytz.utc).isoformat()
    try:
        cursor.execute("SELECT event_id, guild_id, channel_id, message_id, status FROM events WHERE (status = 'cancelado' OR status = 'concluido') AND delete_message_after_utc IS NOT NULL AND delete_message_after_utc <= ?", (now_utc,))
        return cursor.fetchall()
    except sqlite3.Error as e: print(f"Erro DB ao buscar eventos para deletar msg: {e}"); return []
    finally:
        if conn: conn.close()

def db_clear_message_id_and_update_status_after_delete(event_id: int, original_status: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    new_status = f"msg_{original_status}_deletada"
    try:
        cursor.execute("UPDATE events SET message_id = NULL, status = ?, delete_message_after_utc = NULL WHERE event_id = ?", (new_status, event_id))
        conn.commit()
    except sqlite3.Error as e: print(f"Erro DB ao limpar message_id e status do evento {event_id}: {e}")
    finally:
        if conn: conn.close()

def db_get_upcoming_events_for_reminder() -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    now_utc = datetime.datetime.now(pytz.utc)
    start_window = (now_utc + datetime.timedelta(minutes=14)).isoformat()
    end_window = (now_utc + datetime.timedelta(minutes=16)).isoformat()
    try:
        cursor.execute("SELECT * FROM events WHERE status = 'ativo' AND reminder_sent = 0 AND event_time_utc > ? AND event_time_utc <= ?", (start_window, end_window ))
        return cursor.fetchall()
    except sqlite3.Error as e: print(f"Erro DB ao buscar eventos para lembrete: {e}"); return []
    finally:
        if conn: conn.close()

def db_mark_reminder_sent(event_id: int, reminder_type: str = "standard"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    column_to_update = "reminder_sent"
    if reminder_type == "confirmation":
        column_to_update = "confirmation_reminder_sent"
    try:
        cursor.execute(f"UPDATE events SET {column_to_update} = 1 WHERE event_id = ?", (event_id,))
        conn.commit()
    except sqlite3.Error as e: print(f"Erro DB ao marcar {reminder_type} lembrete como enviado para evento {event_id}: {e}")
    finally:
        if conn: conn.close()

def db_get_events_for_confirmation_reminder() -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    now_utc = datetime.datetime.now(pytz.utc)
    start_window = (now_utc + datetime.timedelta(minutes=59)).isoformat()
    end_window = (now_utc + datetime.timedelta(minutes=61)).isoformat()
    try:
        cursor.execute("SELECT * FROM events WHERE status = 'ativo' AND confirmation_reminder_sent = 0 AND event_time_utc > ? AND event_time_utc <= ?", (start_window, end_window ))
        return cursor.fetchall()
    except sqlite3.Error as e: print(f"Erro DB ao buscar eventos para lembrete de confirmação: {e}"); return []
    finally:
        if conn: conn.close()

def db_create_event(**kwargs) -> Optional[int]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    event_id = None
    columns = [
        "guild_id", "channel_id", "creator_id", "title", "description", "event_time_utc", 
        "activity_type", "max_attendees", "created_at_utc", "temp_role_id", "thread_id", "voice_channel_id"
    ]
    values = tuple(kwargs.get(col) for col in columns)
    columns_str = ", ".join(columns)
    placeholders = ", ".join(["?"] * len(columns))
    try:
        cursor.execute(f"INSERT INTO events ({columns_str}) VALUES ({placeholders})", values)
        event_id = cursor.lastrowid
        conn.commit()
    except sqlite3.Error as e: print(f"Erro DB ao criar evento: {e}")
    finally:
        if conn: conn.close()
    return event_id

def db_update_event_message_id(event_id: int, message_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE events SET message_id = ? WHERE event_id = ?", (message_id, event_id))
        conn.commit()
    except sqlite3.Error as e: print(f"Erro DB ao atualizar message_id do evento {event_id}: {e}")
    finally:
        if conn: conn.close()

def db_get_event_temp_role_id(event_id: int) -> Optional[int]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT temp_role_id FROM events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()
        return row['temp_role_id'] if row else None
    except sqlite3.Error as e: print(f"Erro DB ao buscar temp_role_id para evento {event_id}: {e}"); return None
    finally:
        if conn: conn.close()

def db_get_digest_channel(guild_id: int) -> Optional[int]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        configs = db_get_server_configs(guild_id)
        return configs['digest_channel_id'] if configs and configs.get('digest_channel_id') else None
    finally:
        if conn: conn.close()

def db_get_events_for_digest_list(guild_id: int, start_utc: datetime.datetime, end_utc: datetime.datetime) -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM events WHERE guild_id = ? AND status = 'ativo' AND event_time_utc BETWEEN ? AND ? ORDER BY event_time_utc ASC", (guild_id, start_utc.isoformat(), end_utc.isoformat()))
        return cursor.fetchall()
    except sqlite3.Error as e: print(f"Erro DB ao buscar eventos para digest: {e}"); return []
    finally:
        if conn: conn.close()

def db_get_far_future_events(guild_id: int, after_utc: datetime.datetime) -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM events WHERE guild_id = ? AND status = 'ativo' AND event_time_utc > ? ORDER BY event_time_utc ASC", (guild_id, after_utc.isoformat()))
        return cursor.fetchall()
    except sqlite3.Error as e: print(f"Erro DB ao buscar eventos futuros (distantes): {e}"); return []
    finally:
        if conn: conn.close()

def db_get_events_for_attendance_check() -> List[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    now_utc = datetime.datetime.now(pytz.utc)
    start_window = (now_utc - datetime.timedelta(minutes=40)).isoformat()
    end_window = (now_utc - datetime.timedelta(minutes=30)).isoformat()
    try:
        cursor.execute("SELECT * FROM events WHERE status = 'ativo' AND attendance_checked = 0 AND event_time_utc BETWEEN ? AND ?", (start_window, end_window))
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Erro DB ao buscar eventos para verificação de presença: {e}")
        return []
    finally:
        if conn: conn.close()

def db_update_rsvp_attendance(event_id: int, user_id: int, attendance_status: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE rsvps SET attendance_status = ? WHERE event_id = ? AND user_id = ?", (attendance_status, event_id, user_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Erro DB ao atualizar presença para evento {event_id}, user {user_id}: {e}")
    finally:
        if conn: conn.close()

def db_mark_attendance_checked(event_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE events SET attendance_checked = 1 WHERE event_id = ?", (event_id,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Erro DB ao marcar verificação de presença para evento {event_id}: {e}")
    finally:
        if conn: conn.close()

def db_get_events_for_vc_creation() -> List[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    now_utc = datetime.datetime.now(pytz.utc)
    start_window = (now_utc + datetime.timedelta(minutes=59)).isoformat()
    end_window = (now_utc + datetime.timedelta(minutes=61)).isoformat()
    try:
        cursor.execute("SELECT * FROM events WHERE status = 'ativo' AND voice_channel_id IS NULL AND event_time_utc BETWEEN ? AND ?", (start_window, end_window))
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Erro DB ao buscar eventos para criação de VC: {e}")
        return []
    finally:
        if conn: conn.close()

def db_get_events_for_vc_deletion() -> List[sqlite3.Row]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    three_hours_ago = (datetime.datetime.now(pytz.utc) - datetime.timedelta(hours=3)).isoformat()
    try:
        cursor.execute("SELECT event_id, guild_id, voice_channel_id FROM events WHERE status = 'ativo' AND voice_channel_id IS NOT NULL AND event_time_utc <= ?", (three_hours_ago,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Erro DB ao buscar eventos para deleção de VC: {e}")
        return []
    finally:
        if conn: conn.close()