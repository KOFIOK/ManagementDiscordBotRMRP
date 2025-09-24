"""
Rank hierarchy utilities for personnel management
"""

from utils.config_manager import load_config
from typing import Optional, Dict, List, Tuple
import discord


class RankHierarchy:
    """Utilities for working with rank hierarchy"""
    
    @staticmethod
    def get_rank_roles_dict() -> Dict[str, Dict]:
        """Get rank roles from config with support for both old and new formats"""
        config = load_config()
        rank_roles = config.get('rank_roles', {})
        
        # Auto-fix any remaining 'rank' keys to 'rank_level'
        fix_rank_level_keys()
        
        # Reload config after potential fix
        config = load_config()
        rank_roles = config.get('rank_roles', {})
        
        # Convert old format to new format if needed
        converted_roles = {}
        for rank_name, data in rank_roles.items():
            if isinstance(data, dict):
                # New format - ensure we have rank_level (not rank)
                if 'rank_level' in data:
                    converted_roles[rank_name] = data
                elif 'rank' in data:
                    # Fix old key name
                    converted_roles[rank_name] = {
                        'role_id': data.get('role_id'),
                        'rank_level': data.get('rank', 0)
                    }
                    print(f"🔄 RANK FIX: Converted '{rank_name}' from 'rank' to 'rank_level'")
                else:
                    converted_roles[rank_name] = {
                        'role_id': data.get('role_id'),
                        'rank_level': 0  # Default for missing hierarchy
                    }
            else:
                # Old format - just role_id
                converted_roles[rank_name] = {
                    'role_id': data,
                    'rank_level': 0  # Default rank for old entries
                }
        
        return converted_roles
    
    @staticmethod
    def get_sorted_ranks() -> List[Tuple[str, Dict]]:
        """Get ranks sorted by hierarchy (rank_level field)"""
        ranks = RankHierarchy.get_rank_roles_dict()
        return sorted(ranks.items(), key=lambda x: x[1]['rank_level'])
    
    @staticmethod
    def get_user_current_rank(member: discord.Member) -> Optional[str]:
        """Get user's current rank name from their roles"""
        if not hasattr(member, 'roles') or not member.roles:
            return None
            
        rank_roles = RankHierarchy.get_rank_roles_dict()
        
        # Find the highest rank role the user has
        user_rank = None
        highest_rank_level = -1
        
        for role in member.roles:
            for rank_name, rank_data in rank_roles.items():
                if role.id == rank_data['role_id']:
                    rank_level = rank_data['rank_level']
                    if rank_level > highest_rank_level:
                        highest_rank_level = rank_level
                        user_rank = rank_name
                        break
        
        return user_rank
    
    @staticmethod
    def get_next_rank(current_rank: str) -> Optional[str]:
        """Get the next rank in hierarchy (promotion)"""
        rank_roles = RankHierarchy.get_rank_roles_dict()
        
        if current_rank not in rank_roles:
            print(f"❌ RANK ERROR: Rank '{current_rank}' not found in rank_roles")
            print(f"📋 Available ranks: {list(rank_roles.keys())}")
            return None
        
        try:
            current_rank_level = rank_roles[current_rank]['rank_level']
            next_rank_level = current_rank_level + 1
            
            # Find rank with next level
            for rank_name, rank_data in rank_roles.items():
                if rank_data['rank_level'] == next_rank_level:
                    return rank_name
                    
            return None  # No higher rank exists
        except KeyError as e:
            print(f"❌ RANK ERROR: Missing key {e} in rank data for '{current_rank}'")
            print(f"📋 Rank data: {rank_roles[current_rank]}")
            return None
    
    @staticmethod
    def get_previous_rank(current_rank: str) -> Optional[str]:
        """Get the previous rank in hierarchy (demotion)"""
        rank_roles = RankHierarchy.get_rank_roles_dict()
        
        if current_rank not in rank_roles:
            print(f"❌ RANK ERROR: Rank '{current_rank}' not found in rank_roles")
            print(f"📋 Available ranks: {list(rank_roles.keys())}")
            return None
            
        try:
            current_rank_level = rank_roles[current_rank]['rank_level']
            previous_rank_level = current_rank_level - 1
            
            if previous_rank_level < 1:
                return None  # Can't go below rank 1
                
            # Find rank with previous level
            for rank_name, rank_data in rank_roles.items():
                if rank_data['rank_level'] == previous_rank_level:
                    return rank_name
                    
            return None  # No lower rank exists
        except KeyError as e:
            print(f"❌ RANK ERROR: Missing key {e} in rank data for '{current_rank}'")
            print(f"📋 Rank data: {rank_roles[current_rank]}")
            return None
    
    @staticmethod
    def get_rank_info(rank_name: str) -> Optional[Dict]:
        """Get full info about a rank"""
        rank_roles = RankHierarchy.get_rank_roles_dict()
        return rank_roles.get(rank_name)
    
    @staticmethod
    def get_available_ranks_list() -> List[str]:
        """Get list of all available rank names sorted by hierarchy"""
        sorted_ranks = RankHierarchy.get_sorted_ranks()
        return [rank_name for rank_name, _ in sorted_ranks]
    
    @staticmethod
    def validate_rank_transition(from_rank: str, to_rank: str) -> bool:
        """Validate if rank transition is valid (max ±1 level)"""
        rank_roles = RankHierarchy.get_rank_roles_dict()
        
        if from_rank not in rank_roles or to_rank not in rank_roles:
            return False
            
        from_level = rank_roles[from_rank]['rank_level']
        to_level = rank_roles[to_rank]['rank_level']
        
        # Allow transitions of ±1 level or same level (for corrections)
        level_diff = abs(to_level - from_level)
        return level_diff <= 1
    
    @staticmethod
    def get_rank_role_id(rank_name: str) -> Optional[int]:
        """Get Discord role ID for a rank"""
        rank_info = RankHierarchy.get_rank_info(rank_name)
        return rank_info['role_id'] if rank_info else None


def migrate_old_rank_format():
    """Migrate old rank format to new format with hierarchy"""
    config = load_config()
    rank_roles = config.get('rank_roles', {})
    
    # Check if migration is needed
    needs_migration = False
    for data in rank_roles.values():
        if not isinstance(data, dict):
            needs_migration = True
            break
    
    if not needs_migration:
        return False
        
    print("🔄 Migrating rank roles to new format with hierarchy...")
    
    # Default hierarchy for migration
    default_hierarchy = {
        "Рядовой": 1,
        "Ефрейтор": 2,
        "Мл. Сержант": 3,
        "Младший Сержант": 3,
        "Сержант": 4,
        "Ст. Сержант": 5,
        "Старший Сержант": 5,
        "Старшина": 6,
        "Прапорщик": 7,
        "Ст. Прапорщик": 8,
        "Старший Прапорщик": 8,
        "Мл. Лейтенант": 9,
        "Младший Лейтенант": 9,
        "Лейтенант": 10,
        "Ст. Лейтенант": 11,
        "Старший Лейтенант": 11,
        "Капитан": 12,
        "Майор": 13,
        "Подполковник": 14,
        "Полковник": 15,
        "Генерал-Майор": 16,
        "Генерал-майор": 16,
        "Генерал-Лейтенант": 17,
        "Генерал-лейтенант": 17,
        "Генерал-Полковник": 18,
        "Генерал-полковник": 18,
        "Генерал Армии": 19
    }
    
    # Convert to new format
    migrated_ranks = {}
    for rank_name, role_id in rank_roles.items():
        if isinstance(role_id, dict):
            # Already new format
            migrated_ranks[rank_name] = role_id
        else:
            # Old format - convert
            rank_level = default_hierarchy.get(rank_name, 0)
            migrated_ranks[rank_name] = {
                'role_id': role_id,
                'rank_level': rank_level  # Fixed field name
            }
    
    # Save migrated config
    config['rank_roles'] = migrated_ranks
    from utils.config_manager import save_config
    save_config(config)
    
    print("✅ Rank roles migration completed!")
    return True


def fix_rank_level_keys():
    """Fix any remaining 'rank' keys to 'rank_level' keys in config"""
    from utils.config_manager import save_config
    config = load_config()
    rank_roles = config.get('rank_roles', {})
    
    changes_made = False
    fixed_ranks = {}
    
    for rank_name, data in rank_roles.items():
        if isinstance(data, dict):
            if 'rank' in data and 'rank_level' not in data:
                # Fix the key name
                fixed_ranks[rank_name] = {
                    'role_id': data.get('role_id'),
                    'rank_level': data.get('rank')
                }
                changes_made = True
                print(f"🔧 FIXED: '{rank_name}' - changed 'rank' to 'rank_level'")
            else:
                # Keep as is
                fixed_ranks[rank_name] = data
        else:
            # Old format, keep as is
            fixed_ranks[rank_name] = data
    
    if changes_made:
        config['rank_roles'] = fixed_ranks
        save_config(config)
        print("✅ Fixed rank_level keys in config!")
        return True
    else:
        print("ℹ️  No rank key fixes needed.")
        return False
