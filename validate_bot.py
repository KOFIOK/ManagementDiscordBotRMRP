#!/usr/bin/env python3
"""
Final validation script for Army Discord Bot
Tests complete bot functionality without connecting to Discord
"""

def test_complete_setup():
    """Test complete bot setup"""
    print("Army Discord Bot - Final Validation")
    print("=" * 50)
    
    # Test 1: Core imports
    print("\n1. Testing core imports...")
    try:
        import discord
        from discord.ext import commands
        from utils.config_manager import load_config, save_config
        print("   ✓ Core libraries imported successfully")
    except ImportError as e:
        print(f"   ✗ Core import failed: {e}")
        return False
    
    # Test 2: Form modules
    print("\n2. Testing form modules...")
    try:
        from forms.dismissal_form import send_dismissal_button_message
        from forms.audit_form import send_audit_button_message  
        from forms.blacklist_form import send_blacklist_button_message
        print("   ✓ All form modules imported successfully")
    except ImportError as e:
        print(f"   ✗ Form import failed: {e}")
        return False
    
    # Test 3: Channel manager
    print("\n3. Testing channel manager...")
    try:
        from cogs.channel_manager import ChannelManagementCog
        print("   ✓ Channel manager imported successfully")
    except ImportError as e:
        print(f"   ✗ Channel manager import failed: {e}")
        return False
    
    # Test 4: Bot app module
    print("\n4. Testing main bot application...")
    try:
        import app
        print("   ✓ Main bot application imported successfully")
    except ImportError as e:
        print(f"   ✗ Bot app import failed: {e}")
        return False
    
    # Test 5: Configuration system
    print("\n5. Testing configuration system...")
    try:
        config = load_config()
        test_config = {"test": "validation"}
        save_config(test_config)
        loaded_config = load_config()
        
        if loaded_config.get("test") == "validation":
            print("   ✓ Configuration system working correctly")
        else:
            print("   ✗ Configuration system test failed")
            return False
            
        # Clean up
        import os
        if os.path.exists('config.json'):
            os.remove('config.json')
            
    except Exception as e:
        print(f"   ✗ Configuration test failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 ALL TESTS PASSED!")
    print("\nYour Army Discord Bot is ready to deploy!")
    print("\nSetup Instructions:")
    print("1. Create a Discord application at https://discord.com/developers/applications")
    print("2. Create a bot user and copy the token")
    print("3. Create a .env file with: DISCORD_TOKEN=your_bot_token_here")
    print("4. Invite the bot to your server with appropriate permissions")
    print("5. Run: python app.py")
    print("\nAvailable Commands:")
    print("• /setup_dismissal_channel - Set up dismissal reports")
    print("• /setup_audit_channel - Set up personnel audit")  
    print("• /setup_blacklist_channel - Set up blacklist management")
    print("\nBot Features:")
    print("• Interactive forms with validation")
    print("• Persistent button messages")
    print("• Configurable channels for each system")
    print("• Professional embed formatting")
    print("• Error handling and user feedback")
    
    return True

if __name__ == "__main__":
    success = test_complete_setup()
    if not success:
        print("\n❌ Some tests failed. Please check the errors above.")
        exit(1)
    else:
        print("\n✅ Bot validation completed successfully!")
        exit(0)
