"""
Rank synchronization system - monitors Discord activity and syncs ranks with roles
"""
import re
import asyncio
import discord
from typing import Optional, Dict, List, Tuple
from utils.config_manager import load_config
from utils.google_sheets import sheets_manager


class RankSyncManager:
    """Manager for synchronizing ranks from game activity to Discord roles"""
    
    def __init__(self, bot):
        self.bot = bot
        self.server_patterns = [
            "RMRP.ru - Арбат",
            "RMRP.ru - Арбат",  # Possible variations
            "rmrp.ru - арбат",
            "RMRP - Арбат"
        ]
        
        # Rank variations mapping - handles different formats and abbreviations
        self.rank_variations = {
            # Рядовые
            "рядовой": ["рядовой", "рдв", "р"],
            "ефрейтор": ["ефрейтор", "еф", "ефр"],
            
            # Сержанты
            "мл. сержант": ["мл. сержант", "младший сержант", "мл сержант", "мл.сержант", "мл сер", "мс"],
            "сержант": ["сержант", "сер", "с", "сер."],
            "ст. сержант": ["ст. сержант", "старший сержант", "ст сержант", "ст.сержант", "ст сер", "сс"],
            "старшина": ["старшина", "ст", "стар"],
            
            # Прапорщики
            "прапорщик": ["прапорщик", "пр", "прап"],
            "ст. прапорщик": ["ст. прапорщик", "старший прапорщик", "ст прапорщик", "ст.прапорщик", "ст пр", "сп"],
            
            # Лейтенанты
            "мл. лейтенант": ["мл. лейтенант", "младший лейтенант", "мл лейтенант", "мл.лейтенант", "мл лт", "мл"],
            "лейтенант": ["лейтенант", "лт", "л", "лт.", "лейт.", "лейт"],
            "ст. лейтенант": ["ст. лейтенант", "старший лейтенант", "ст лейтенант", "ст.лейтенант", "ст лт", "сл", "ст лт.", "ст.лт."],
            
            # Капитан и выше
            "капитан": ["капитан", "кап", "к", "кап.", "капит.", "капит"],
            "майор": ["майор", "май", "м"],
            "подполковник": ["подполковник", "пп", "ппк"],
            "полковник": ["полковник", "п", "плк"],
            "генерал-майор": ["генерал-майор", "генерал майор", "ген-май", "ген май", "гм"],
            "генерал-лейтенант": ["генерал-лейтенант", "генерал лейтенант", "ген-лт", "ген лт", "гл"],
            "генерал-полковник": ["генерал-полковник", "генерал полковник", "ген-плк", "ген плк", "гп"],
            "генерал армии": ["генерал армии", "ген армии", "га"],
            "маршал": ["маршал", "мар", "мш"]
        }
        
        # Reverse mapping for quick lookup
        self.variation_to_rank = {}
        for rank, variations in self.rank_variations.items():
            for variation in variations:
                self.variation_to_rank[variation.lower()] = rank
    
    def extract_rank_from_activity(self, activity_text: str) -> Optional[str]:
        """Extract rank from Discord activity text"""
        if not activity_text:
            return None
        
        # Check if playing on correct server first
        if not self.is_rmrp_arbat_server(activity_text):
            return None
        
        # Convert to lowercase for matching
        activity_lower = activity_text.lower()
        
        # Enhanced patterns to find rank in activity text
        # Common patterns: "1553-326 | Капитан (1153 из 5000)" or "Капитан | 1553-326"
        patterns = [
            # Pattern 1: "| Капитан (число из число)"
            r'\|\s*([а-яё\.\s]+?)\s*\([0-9]+\s*из\s*[0-9]+\)',
            # Pattern 2: "| Капитан | число"  
            r'\|\s*([а-яё\.\s]+?)\s*\|',
            # Pattern 3: "| Капитан" at end of string
            r'\|\s*([а-яё\.\s]+?)(?:\s*$|\s*\()',
            # Pattern 4: "Капитан (число"
            r'([а-яё\.\s]+?)\s*\([0-9]+',
            # Pattern 5: Just rank name between pipes
            r'\|\s*([а-яё\.\s]{3,20})\s*\|',
            # Pattern 6: Rank at the end after pipe
            r'\|\s*([а-яё\.\s]{3,20})\s*$',
            # Pattern 7: "Арбат (Капитан)" - rank in parentheses after server name
            r'арбат\s*\(([а-яё\.\s]+)\)',
            # Pattern 8: Generic "(Капитан)" - rank in parentheses
            r'\(([а-яё\.\s]{3,20})\)(?:\s*$)',
            # Pattern 9: "- Арбат (Капитан)" - with dash
            r'-\s*арбат\s*\(([а-яё\.\s]+)\)',
            # Pattern 10: "(Капитан Имя)" - rank with name in parentheses
            r'\(([а-яё\.\s]{3,20})\s+[А-ЯЁ][а-яё]+\)',
            # Pattern 11: "(лт. Имя)" - abbreviation with name in parentheses 
            r'\(([а-яё\.]{2,10})\s+[А-ЯЁ][а-яё]+\)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, activity_text, re.IGNORECASE | re.UNICODE)
            for match in matches:
                potential_rank = match.group(1).strip().lower()
                
                # Skip if it's obviously not a rank (contains numbers, too long, etc.)
                if (len(potential_rank) < 3 or len(potential_rank) > 20 or 
                    any(char.isdigit() for char in potential_rank) or
                    any(char in '🔹🎮⚡️💎' for char in potential_rank)):
                    continue
                
                # Try to normalize the rank
                normalized_rank = self.normalize_rank(potential_rank)
                if normalized_rank:
                    return normalized_rank
        
        return None
    
    def normalize_rank(self, rank_text: str) -> Optional[str]:
        """Normalize rank text to standard format"""
        rank_lower = rank_text.lower().strip()
        
        # Clean up the rank text
        rank_lower = re.sub(r'\s+', ' ', rank_lower)  # Normalize spaces
        rank_lower = rank_lower.replace('ё', 'е')      # Replace ё with е
        
        # Direct lookup
        if rank_lower in self.variation_to_rank:
            return self.variation_to_rank[rank_lower]
        
        # Try partial matching for complex cases
        for standard_rank, variations in self.rank_variations.items():
            if rank_lower in variations:
                return standard_rank
        
        # Try fuzzy matching for abbreviations and partial matches
        for standard_rank in self.rank_variations.keys():
            if self.is_rank_match(rank_lower, standard_rank):
                return standard_rank
        
        # Try matching individual words for compound ranks
        rank_words = rank_lower.split()
        if len(rank_words) >= 2:
            # For ranks like "мл. лейтенант" try matching "мл лейтенант", "младший лейтенант" etc
            for standard_rank, variations in self.rank_variations.items():
                for variation in variations:
                    if all(word in variation for word in rank_words):
                        return standard_rank
        
        return None
    
    def is_rank_match(self, test_rank: str, standard_rank: str) -> bool:
        """Enhanced matching for ranks including abbreviations"""
        # Exact match
        if test_rank == standard_rank:
            return True
            
        # Check if test_rank is in variations
        variations = self.rank_variations.get(standard_rank, [])
        if test_rank in variations:
            return True
        
        # For ranks with dots (like "мл. сержант")
        if "." in standard_rank or "." in test_rank:
            return self.is_rank_abbreviation_match(test_rank, standard_rank)
        
        # Check partial matching for compound ranks
        standard_words = standard_rank.split()
        test_words = test_rank.split()
        
        if len(standard_words) == 2 and len(test_words) >= 1:
            # Check if test contains key parts of the rank
            if (test_words[0].startswith(standard_words[0][:2]) or 
                any(word.startswith(standard_words[1][:3]) for word in test_words)):
                return True
        
        return False
    
    def is_rank_abbreviation_match(self, abbrev: str, full_rank: str) -> bool:
        """Check if abbreviation matches full rank"""
        abbrev_clean = abbrev.replace(".", "").replace(" ", "")
        
        # For ranks with dots (like "мл. сержант")
        if "." in full_rank:
            parts = full_rank.split()
            if len(parts) == 2:
                first_abbrev = parts[0].replace(".", "")[:2]  # "мл"
                second_abbrev = parts[1][:3]  # "сер"
                possible_abbrevs = [
                    first_abbrev + second_abbrev,  # "млсер"
                    first_abbrev + parts[1][:2],   # "млсе"
                    first_abbrev,                  # "мл"
                ]
                return abbrev_clean in possible_abbrevs
        
        return False
    
    def is_rmrp_arbat_server(self, activity_text: str) -> bool:
        """Check if the activity is from RMRP Arbat server"""
        activity_lower = activity_text.lower()
        
        for pattern in self.server_patterns:
            if pattern.lower() in activity_lower:
                return True
        
        return False
    
    async def sync_user_rank(self, member: discord.Member, activity_rank: str, force: bool = False) -> bool:
        """Sync user's Discord roles based on detected rank"""
        try:
            config = load_config()
            rank_roles = config.get('rank_roles', {})
            
            print(f"🔧 Starting sync for {member.display_name}, detected rank: '{activity_rank}'")
            print(f"📋 Available rank roles: {list(rank_roles.keys())}")
            
            # Find role with case-insensitive matching
            target_role_id = None
            matched_rank_key = None
            
            for config_rank, role_id in rank_roles.items():
                if config_rank.lower() == activity_rank.lower():
                    target_role_id = role_id
                    matched_rank_key = config_rank
                    print(f"✅ Found matching role: '{config_rank}' -> {role_id}")
                    break
            
            if not target_role_id:
                print(f"❌ Rank '{activity_rank}' not found in config for {member.display_name}")
                print(f"🔍 Available ranks: {list(rank_roles.keys())}")
                return False
            
            target_role = member.guild.get_role(target_role_id)
            
            if not target_role:
                print(f"❌ Role with ID {target_role_id} not found in guild for rank '{activity_rank}'")
                return False
            
            print(f"🎯 Target role: {target_role.name} (ID: {target_role_id})")
            
            # Check if user already has this role
            if target_role in member.roles:
                print(f"✅ {member.display_name} already has role {target_role.name}")
                return True
            
            # Check key role requirement (skip if force is True)
            key_role_id = config.get('rank_sync_key_role')
            if key_role_id and not force:
                key_role = member.guild.get_role(key_role_id)
                if key_role and key_role not in member.roles:
                    print(f"⚠️ {member.display_name} doesn't have key role {key_role.name}, skipping sync")
                    return False
                elif not key_role:
                    print(f"⚠️ Key role with ID {key_role_id} not found in guild")
            elif force:
                print(f"🚀 Force mode: skipping key role check")
            
            # Remove other rank roles first
            roles_to_remove = []
            for role in member.roles:
                if role.id in rank_roles.values() and role.id != target_role_id:
                    roles_to_remove.append(role)
            
            if roles_to_remove:
                print(f"🔄 Removing old rank roles: {[role.name for role in roles_to_remove]}")
                await member.remove_roles(*roles_to_remove, reason="Rank synchronization")
                removed_names = [role.name for role in roles_to_remove]
                print(f"✅ Removed roles from {member.display_name}: {', '.join(removed_names)}")
            
            # Add new rank role
            print(f"➕ Adding role {target_role.name} to {member.display_name}")
            await member.add_roles(target_role, reason=f"Rank sync: detected '{activity_rank}' in game")
            print(f"✅ Added role {target_role.name} to {member.display_name}")
            
            # Log to audit if configured
            await self.log_rank_sync(member, activity_rank, target_role, roles_to_remove)
            
            return True
            
        except Exception as e:
            print(f"❌ Error syncing rank for {member.display_name}: {e}")
            return False
    
    async def log_rank_sync(self, member: discord.Member, detected_rank: str, 
                           new_role: discord.Role, removed_roles: List[discord.Role]):
        """Log rank synchronization to audit channel"""
        try:
            config = load_config()
            audit_channel_id = config.get('audit_channel')
            
            if not audit_channel_id:
                return
            
            audit_channel = member.guild.get_channel(audit_channel_id)
            if not audit_channel:
                return
            
            embed = discord.Embed(
                title="🎖️ Автоматическая синхронизация звания",
                description=f"Обнаружено изменение звания в игре",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="👤 Игрок",
                value=f"{member.mention} ({member.display_name})",
                inline=False
            )
            
            embed.add_field(
                name="🎖️ Обнаруженное звание",
                value=f"`{detected_rank}`",
                inline=True
            )
            
            embed.add_field(
                name="🆕 Назначена роль",
                value=new_role.mention,
                inline=True
            )
            
            if removed_roles:
                removed_names = [role.mention for role in removed_roles]
                embed.add_field(
                    name="🗑️ Удалены роли",
                    value="\n".join(removed_names),
                    inline=False
                )
            
            embed.set_footer(text="Автоматическая система синхронизации званий")
            
            await audit_channel.send(embed=embed)
            
        except Exception as e:
            print(f"⚠️ Failed to log rank sync: {e}")
    
    async def monitor_member_activity(self, member: discord.Member, force: bool = False):
        """Monitor a single member's activity for rank changes"""
        try:
            # Find game activity
            game_activity = None
            activity_text = None
            
            for activity in member.activities:
                if hasattr(activity, 'name') and activity.name:
                    # Check all possible fields that might contain rank information
                    possible_fields = ['details', 'state', 'large_text', 'small_text']
                    
                    for field_name in possible_fields:
                        if hasattr(activity, field_name):
                            field_value = getattr(activity, field_name)
                            if field_value and self.is_rmrp_arbat_server(field_value):
                                game_activity = activity
                                activity_text = field_value
                                print(f"🎮 Found RMRP activity in {field_name}: {field_value}")
                                break
                    
                    if game_activity:
                        break
            
            if not game_activity or not activity_text:
                print(f"🔍 No RMRP activity found for {member.display_name}")
                return
            
            # Extract rank from activity text
            detected_rank = self.extract_rank_from_activity(activity_text)
            
            if detected_rank:
                print(f"�️ Detected rank '{detected_rank}' for {member.display_name}")
                success = await self.sync_user_rank(member, detected_rank, force)
                
                if success:
                    print(f"✅ Successfully synced rank for {member.display_name}")
                else:
                    print(f"⚠️ Failed to sync rank for {member.display_name}")
            else:
                print(f"❓ No rank detected in activity for {member.display_name}: {activity_text}")
            
        except Exception as e:
            print(f"❌ Error monitoring activity for {member.display_name}: {e}")
            import traceback
            traceback.print_exc()
    
    async def monitor_all_activities(self, guild: discord.Guild):
        """Monitor all guild members' activities for rank synchronization"""
        print("🔍 Starting rank synchronization scan...")
        
        synced_count = 0
        checked_count = 0
        
        for member in guild.members:
            if member.bot:
                continue
                
            checked_count += 1
            
            try:
                old_roles = set(role.id for role in member.roles)
                await self.monitor_member_activity(member, False)  # Force=False for mass sync
                new_roles = set(role.id for role in member.roles)
                
                if old_roles != new_roles:
                    synced_count += 1
                
            except Exception as e:
                print(f"❌ Error checking {member.display_name}: {e}")
        
        print(f"✅ Rank sync completed: {synced_count} members synced out of {checked_count} checked")
        return synced_count, checked_count


# Initialize global rank sync manager
rank_sync_manager = None

def initialize_rank_sync(bot):
    """Initialize the rank synchronization system"""
    global rank_sync_manager
    rank_sync_manager = RankSyncManager(bot)
    print("✅ Rank synchronization system initialized")
    return rank_sync_manager

async def sync_ranks_for_guild(guild: discord.Guild) -> Tuple[int, int]:
    """Sync ranks for all members in a guild"""
    if not rank_sync_manager:
        print("❌ Rank sync manager not initialized")
        return 0, 0
    
    return await rank_sync_manager.monitor_all_activities(guild)

async def sync_ranks_for_member(member: discord.Member, force: bool = False) -> bool:
    """Sync ranks for a specific member"""
    if not rank_sync_manager:
        print("❌ Rank sync manager not initialized")
        return False
    
    await rank_sync_manager.monitor_member_activity(member, force)
    return True
