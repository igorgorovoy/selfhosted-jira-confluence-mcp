#!/usr/bin/env python3
"""Test script for confluence_get_spaces functionality"""

from server import confluence_get_spaces

try:
    print("🔍 Fetching spaces list from Confluence...\n")
    result = confluence_get_spaces(limit=50)
    
    print(f"✅ Spaces found: {result['total']}")
    print(f"📊 Result size: {result['size']}")
    print(f"📄 Limit: {result['limit']}\n")
    
    print("📋 Spaces list:")
    print("-" * 80)
    
    for space in result['spaces']:
        print(f"\n🔹 {space['name']}")
        print(f"   Key: {space['key']}")
        print(f"   Type: {space['type']}")
        print(f"   Status: {space['status']}")
        if space.get('description'):
            desc = space['description']
            if isinstance(desc, str):
                desc = desc[:100] + "..." if len(desc) > 100 else desc
                print(f"   Description: {desc}")
    
    print("\n" + "=" * 80)
    print(f"✅ Successfully retrieved {len(result['spaces'])} spaces!")
    
except RuntimeError as e:
    print(f"❌ Error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()

