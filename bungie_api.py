# bungie_api.py
import aiohttp
import asyncio
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv
from typing import Any, Dict, List, Set, Optional, Tuple

import database as db
from config import BUNGIE_API_KEY, BUNGIE_CLIENT_ID, BUNGIE_CLIENT_SECRET, BUNGIE_CLAN_ID

load_dotenv()

CLAN_ID = BUNGIE_CLAN_ID 

BUNGIE_API_ROOT = "https://www.bungie.net/Platform"
TOKEN_URL = "https://www.bungie.net/Platform/App/OAuth/Token/"

async def exchange_code_for_token(code: str) -> Optional[Dict[str, Any]]:
    """Troca um código de autorização por tokens de acesso e de atualização."""
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': BUNGIE_CLIENT_ID,
        'client_secret': BUNGIE_CLIENT_SECRET
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    async with aiohttp.ClientSession() as session:
        async with session.post(TOKEN_URL, data=data, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                print(f"BUNGIE_API_ERROR: Falha ao trocar código por token. Status: {resp.status}, Resposta: {await resp.text()}")
                return None

async def get_bungie_memberships_for_current_user(access_token: str) -> Optional[Dict[str, Any]]:
    """Busca as informações de perfil do usuário autenticado."""
    url = f"{BUNGIE_API_ROOT}/User/GetMembershipsForCurrentUser/"
    headers = {
        "X-API-Key": BUNGIE_API_KEY,
        "Authorization": f"Bearer {access_token}"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                print(f"BUNGIE_API_ERROR: Falha ao buscar perfil do usuário. Status: {resp.status}")
                return None

async def _get_access_token_from_db(discord_id: int):
    profile = db.db_get_bungie_profile(discord_id)
    if not profile:
        return None

    expires_at = datetime.fromisoformat(profile['token_expires_at'])
    if datetime.now(pytz.utc) >= expires_at:
        return await _refresh_access_token(discord_id, profile['refresh_token'])
    else:
        return profile['access_token']

async def _refresh_access_token(discord_id: int, refresh_token: str) -> str | None:
    print(f"BUNGIE_API: Refreshing token for user {discord_id}")
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        'client_id': BUNGIE_CLIENT_ID,
        'client_secret': BUNGIE_CLIENT_SECRET
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with aiohttp.ClientSession() as session:
        async with session.post(TOKEN_URL, data=data, headers=headers) as response:
            if response.status == 200:
                token_data = await response.json()
                new_access_token = token_data['access_token']
                new_refresh_token = token_data['refresh_token']
                expires_in = token_data['expires_in']
                new_expires_at = (datetime.now(pytz.utc) + timedelta(seconds=expires_in)).isoformat()

                profile = db.db_get_bungie_profile(discord_id)
                if profile:
                    db.db_save_bungie_profile(
                        discord_id=discord_id,
                        bungie_membership_id=profile['bungie_membership_id'],
                        bungie_membership_type=profile['bungie_membership_type'],
                        bungie_name=profile['bungie_name'],
                        access_token=new_access_token,
                        refresh_token=new_refresh_token,
                        token_expires_at=new_expires_at
                    )
                return new_access_token
            else:
                print(f"BUNGIE_API_ERROR: Failed to refresh token for user {discord_id}. Status: {response.status}")
                return None

async def _approve_or_deny_pending_members(admin_discord_id: int, approve: bool, membership_id: str, membership_type: int, message: str) -> bool:
    action_word = "Approving" if approve else "Denying"
    admin_token = await _get_access_token_from_db(admin_discord_id)
    if not admin_token: return False

    url = f"{BUNGIE_API_ROOT}/GroupV2/{CLAN_ID}/Members/{'Approve' if approve else 'Deny'}/{membership_type}/{membership_id}/"
    headers = {"X-API-Key": BUNGIE_API_KEY, "Authorization": f"Bearer {admin_token}"}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json={"message": message}) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("ErrorStatus") == "Success" and data.get("Response")
            return False

async def approve_pending_invitation(admin_discord_id: int, membership_id: str, membership_type: int) -> bool:
    return await _approve_or_deny_pending_members(admin_discord_id, True, membership_id, membership_type, "Bem-vindo ao clã!")

async def deny_pending_invitation(admin_discord_id: int, membership_id: str, membership_type: int) -> bool:
    return await _approve_or_deny_pending_members(admin_discord_id, False, membership_id, membership_type, "Seu pedido de entrada no clã foi recusado.")

async def get_pending_invitations(admin_discord_id: int) -> List[Dict[str, Any]]:
    admin_token = await _get_access_token_from_db(admin_discord_id)
    if not admin_token: return []
    url = f"{BUNGIE_API_ROOT}/GroupV2/{CLAN_ID}/Members/Pending/"
    headers = {"X-API-Key": BUNGIE_API_KEY, "Authorization": f"Bearer {admin_token}"}
    invites = []
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                if data.get('ErrorStatus') == 'Success':
                    for invite in data.get('Response', {}).get('results', []):
                        user_info = invite.get('destinyUserInfo', {})
                        if user_info.get('membershipId'):
                            invites.append({
                                'bungie_name': f"{user_info.get('bungieGlobalDisplayName', 'N/A')}#{user_info.get('bungieGlobalDisplayNameCode', '0000')}",
                                'membership_id': user_info.get('membershipId'),
                                'membership_type': user_info.get('membershipType'),
                                'date_applied': invite.get('dateApplied')
                            })
        except Exception as e:
            print(f"BUNGIE_API_ERROR: An unexpected error occurred while fetching pending invites: {e}")
    return invites

async def kick_clan_member(admin_discord_id: int, member_to_kick_bnet_id: str, member_to_kick_membership_type: int) -> bool:
    admin_token = await _get_access_token_from_db(admin_discord_id)
    if not admin_token: return False
    url = f"{BUNGIE_API_ROOT}/GroupV2/{CLAN_ID}/Members/{member_to_kick_membership_type}/{member_to_kick_bnet_id}/Kick/"
    headers = {"X-API-Key": BUNGIE_API_KEY, "Authorization": f"Bearer {admin_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers) as response:
            if response.status == 200:
                return (await response.json()).get("ErrorStatus") == "Success"
            return False

async def get_clan_members(admin_discord_id: int) -> set[str]:
    admin_token = await _get_access_token_from_db(admin_discord_id)
    if not admin_token: return set()
    url = f"{BUNGIE_API_ROOT}/GroupV2/{CLAN_ID}/Members/"
    headers = {"X-API-Key": BUNGIE_API_KEY, "Authorization": f"Bearer {admin_token}"}
    member_ids = set()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                if data.get('ErrorStatus') == 'Success':
                    for member in data.get('Response', {}).get('results', []):
                        if membership_id := member.get('destinyUserInfo', {}).get('membershipId'):
                            member_ids.add(membership_id)
        except Exception as e:
            print(f"BUNGIE_API_ERROR: An unexpected error occurred while fetching clan members: {e}")
    return member_ids