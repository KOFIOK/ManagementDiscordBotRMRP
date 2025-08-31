"""
Optimized rank synchronization system for large servers
"""
import asyncio
import time
import discord
from typing import Dict, Set, Optional
from datetime import datetime, timedelta
from utils.config_manager import load_config
from utils.rank_sync import RankSyncManager


class OptimizedRankSync:
    """Optimized rank synchronization for large servers"""
    
    def __init__(self, bot):
        self.bot = bot
        self.rank_manager = RankSyncManager(bot)
        
        # Performance settings
        self.batch_size = 50  # Process N members at once
        self.check_interval = 300  # Check every 5 minutes
        self.activity_cache = {}  # Cache previous activities
        self.last_sync = {}  # Track last sync times per user
        self.rate_limit_delay = 0.5  # Delay between API calls
        
        # Sync modes
        self.sync_modes = {
            'realtime': False,      # Real-time on activity change (expensive)
            'periodic': True,       # Periodic batch checks (recommended)
            'manual': True,         # Manual commands only
        }
        
        # Activity monitoring
        self.activity_queue = asyncio.Queue()
        self.processing_queue = False
        
    async def start_optimized_monitoring(self):
        """Start optimized monitoring system"""
        print("🎖️ Starting optimized rank synchronization system...")
        
        # Start periodic sync if enabled
        if self.sync_modes['periodic']:
            asyncio.create_task(self.periodic_sync_loop())
            print("✅ Periodic sync enabled (every 5 minutes)")
        
        # Start activity queue processor if real-time is enabled
        if self.sync_modes['realtime']:
            asyncio.create_task(self.process_activity_queue())
            print("✅ Real-time sync enabled (performance impact warning)")
        
        print(f"📊 Sync settings: Batch size {self.batch_size}, Interval {self.check_interval}s")
    
    async def periodic_sync_loop(self):
        """Periodic batch synchronization loop"""
        await asyncio.sleep(60)  # Wait 1 minute after startup
        
        while True:
            try:
                await asyncio.sleep(self.check_interval)
                await self.batch_sync_active_players()
                
            except Exception as e:
                print(f"❌ Error in periodic sync loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def batch_sync_active_players(self):
        """Sync only currently active RMRP players in batches"""
        if not self.bot.guilds:
            return
            
        guild = self.bot.guilds[0]  # Main guild
        active_players = self.get_active_rmrp_players(guild)
        
        if not active_players:
            print("🎖️ No active RMRP players found for sync")
            return
        
        print(f"🔄 Starting batch sync for {len(active_players)} active players...")
        synced_count = 0
        
        # Process in batches to avoid rate limits
        for i in range(0, len(active_players), self.batch_size):
            batch = active_players[i:i + self.batch_size]
            
            for member in batch:
                try:
                    # Check if sync is needed (activity changed or long time passed)
                    if self.should_sync_member(member):
                        old_roles = set(role.id for role in member.roles)
                        await self.rank_manager.monitor_member_activity(member)
                        new_roles = set(role.id for role in member.roles)
                        
                        if old_roles != new_roles:
                            synced_count += 1
                            self.last_sync[member.id] = time.time()
                        
                        # Update activity cache
                        self.cache_member_activity(member)
                    
                    await asyncio.sleep(self.rate_limit_delay)
                    
                except Exception as e:
                    print(f"❌ Error syncing {member.display_name}: {e}")
            
            # Small delay between batches
            if i + self.batch_size < len(active_players):
                await asyncio.sleep(2)
        
        if synced_count > 0:
            print(f"✅ Batch sync completed: {synced_count} players synced")
        else:
            print("ℹ️ Batch sync completed: no changes needed")
    
    def get_active_rmrp_players(self, guild: discord.Guild) -> list:
        """Get list of members currently playing on RMRP Arbat with key role"""
        active_players = []
        
        # Get key role from config
        config = load_config()
        key_role_id = config.get('rank_sync_key_role')
        key_role = guild.get_role(key_role_id) if key_role_id else None
        
        for member in guild.members:
            if member.bot:
                continue
            
            # Check if member has key role (if configured)
            if key_role and key_role not in member.roles:
                continue
                
            # Check if member has RMRP activity
            for activity in member.activities:
                if (hasattr(activity, 'details') and activity.details and
                    self.rank_manager.is_rmrp_arbat_server(activity.details)):
                    active_players.append(member)
                    break
        
        return active_players
    
    def should_sync_member(self, member: discord.Member) -> bool:
        """Determine if member needs synchronization"""
        current_time = time.time()
        
        # Always sync if never synced
        if member.id not in self.last_sync:
            return True
        
        # Force sync if too much time passed (1 hour)
        if current_time - self.last_sync[member.id] > 3600:
            return True
        
        # Check if activity changed
        current_activity = self.get_member_rmrp_activity(member)
        cached_activity = self.activity_cache.get(member.id)
        
        if current_activity != cached_activity:
            return True
        
        return False
    
    def get_member_rmrp_activity(self, member: discord.Member) -> Optional[str]:
        """Get member's current RMRP activity details"""
        for activity in member.activities:
            if (hasattr(activity, 'details') and activity.details and
                self.rank_manager.is_rmrp_arbat_server(activity.details)):
                return activity.details
        return None
    
    def cache_member_activity(self, member: discord.Member):
        """Cache member's current activity for comparison"""
        activity = self.get_member_rmrp_activity(member)
        self.activity_cache[member.id] = activity
    
    async def queue_activity_check(self, member: discord.Member):
        """Queue member for activity check (real-time mode)"""
        if not self.sync_modes['realtime']:
            return
            
        try:
            await self.activity_queue.put(member)
        except:
            pass  # Queue full, skip this check
    
    async def process_activity_queue(self):
        """Process queued activity checks"""
        await asyncio.sleep(30)  # Wait after startup
        
        while True:
            try:
                # Process queue in batches to avoid spam
                members_to_check = []
                
                # Collect batch
                for _ in range(min(10, self.activity_queue.qsize())):
                    try:
                        member = await asyncio.wait_for(self.activity_queue.get(), timeout=1.0)
                        members_to_check.append(member)
                    except asyncio.TimeoutError:
                        break
                
                # Process batch
                if members_to_check:
                    for member in members_to_check:
                        if self.should_sync_member(member):
                            await self.rank_manager.monitor_member_activity(member)
                            self.cache_member_activity(member)
                            self.last_sync[member.id] = time.time()
                            await asyncio.sleep(0.1)
                
                await asyncio.sleep(5)  # Wait between batch processing
                
            except Exception as e:
                print(f"❌ Error processing activity queue: {e}")
                await asyncio.sleep(10)
    
    async def manual_sync_all(self) -> tuple:
        """Manual sync for all active players (command triggered)"""
        if not self.sync_modes['manual']:
            return 0, 0
            
        guild = self.bot.guilds[0]
        active_players = self.get_active_rmrp_players(guild)
        
        if not active_players:
            return 0, 0
        
        synced_count = 0
        checked_count = len(active_players)
        
        print(f"🔄 Manual sync started for {checked_count} active players...")
        
        for member in active_players:
            try:
                old_roles = set(role.id for role in member.roles)
                await self.rank_manager.monitor_member_activity(member)
                new_roles = set(role.id for role in member.roles)
                
                if old_roles != new_roles:
                    synced_count += 1
                
                self.cache_member_activity(member)
                self.last_sync[member.id] = time.time()
                
                await asyncio.sleep(self.rate_limit_delay)
                
            except Exception as e:
                print(f"❌ Error in manual sync for {member.display_name}: {e}")
        
        return synced_count, checked_count
    
    async def get_sync_stats(self) -> dict:
        """Get synchronization statistics"""
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return {}
        
        active_players = self.get_active_rmrp_players(guild)
        
        # Get key role info
        config = load_config()
        key_role_id = config.get('rank_sync_key_role')
        key_role = guild.get_role(key_role_id) if key_role_id else None
        key_role_members = len([m for m in guild.members if key_role and key_role in m.roles]) if key_role else 0
        
        return {
            'total_members': len(guild.members),
            'key_role_members': key_role_members,
            'key_role_name': key_role.name if key_role else None,
            'key_role_configured': key_role_id is not None,
            'active_rmrp_players': len(active_players),
            'cached_activities': len(self.activity_cache),
            'synced_members': len(self.last_sync),
            'realtime_enabled': self.sync_modes['realtime'],
            'periodic_enabled': self.sync_modes['periodic'],
            'queue_size': self.activity_queue.qsize() if hasattr(self.activity_queue, 'qsize') else 0,
            'batch_size': self.batch_size,
            'check_interval': self.check_interval
        }
    
    def configure_sync_mode(self, realtime: bool = None, periodic: bool = None, manual: bool = None):
        """Configure sync modes"""
        if realtime is not None:
            self.sync_modes['realtime'] = realtime
        if periodic is not None:
            self.sync_modes['periodic'] = periodic  
        if manual is not None:
            self.sync_modes['manual'] = manual
        
        print(f"🎖️ Sync modes updated: {self.sync_modes}")


# Global optimized sync instance
optimized_rank_sync = None

def initialize_optimized_rank_sync(bot):
    """Initialize optimized rank sync system"""
    global optimized_rank_sync
    optimized_rank_sync = OptimizedRankSync(bot)
    return optimized_rank_sync

async def start_optimized_monitoring():
    """Start optimized monitoring"""
    if optimized_rank_sync:
        await optimized_rank_sync.start_optimized_monitoring()
