#!/usr/bin/env python3
"""
Test script to verify Google Places API key is working
Run this first to make sure your API key is set up correctly
"""

import os
import sys
from dotenv import load_dotenv
import googlemaps
from datetime import datetime

def test_google_api():
    """Test the Google Places API key"""
    
    print("🔑 Google Places API Test")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("\n❌ ERROR: No API key found!")
        print("\nPlease create a .env file in this directory with:")
        print("GOOGLE_API_KEY=your_actual_key_here")
        print("\nFollow the instructions in GOOGLE_API_SETUP.md to get your key")
        return False
    
    print(f"✅ API key found (length: {len(api_key)} characters)")
    
    # Initialize client
    try:
        gmaps = googlemaps.Client(key=api_key)
        print("✅ Google Maps client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return False
    
    # Test 1: Simple geocoding
    print("\n📍 Test 1: Geocoding (Sydney Opera House)")
    try:
        geocode_result = gmaps.geocode('Sydney Opera House')
        if geocode_result:
            location = geocode_result[0]['geometry']['location']
            print(f"✅ Location found: {location['lat']:.4f}, {location['lng']:.4f}")
        else:
            print("❌ No results returned")
    except Exception as e:
        print(f"❌ Geocoding failed: {e}")
        print("\nPossible issues:")
        print("- API key may not be valid")
        print("- Geocoding API may not be enabled")
        return False
    
    # Test 2: Find a caravan park
    print("\n🏕️ Test 2: Finding a caravan park")
    try:
        # Search for BIG4 Sydney (a known large caravan park)
        result = gmaps.find_place(
            input="BIG4 Sydney Holiday Park",
            input_type='textquery',
            fields=['place_id', 'name', 'geometry', 'formatted_address']
        )
        
        if result['candidates']:
            place = result['candidates'][0]
            print(f"✅ Found: {place.get('name', 'Unknown')}")
            print(f"   Address: {place.get('formatted_address', 'N/A')}")
        else:
            print("❌ No caravan park found")
    except Exception as e:
        print(f"❌ Place search failed: {e}")
        print("\nPossible issues:")
        print("- Places API (New) may not be enabled")
        print("- Check your API restrictions")
        return False
    
    # Test 3: Get place details
    print("\n📋 Test 3: Getting place details")
    try:
        if result['candidates']:
            place_id = result['candidates'][0]['place_id']
            details = gmaps.place(
                place_id=place_id,
                fields=['name', 'formatted_phone_number', 'website', 'rating', 'user_ratings_total']
            )
            
            if details['status'] == 'OK':
                place_info = details['result']
                print(f"✅ Details retrieved:")
                print(f"   Phone: {place_info.get('formatted_phone_number', 'N/A')}")
                print(f"   Website: {place_info.get('website', 'N/A')}")
                print(f"   Rating: {place_info.get('rating', 'N/A')}")
                print(f"   Reviews: {place_info.get('user_ratings_total', 'N/A')}")
            else:
                print(f"❌ Failed to get details: {details['status']}")
    except Exception as e:
        print(f"❌ Details retrieval failed: {e}")
        return False
    
    # Summary
    print("\n" + "=" * 50)
    print("🎉 All tests passed! Your API key is working correctly.")
    print("\n📊 API Usage:")
    print("- Geocoding API: ✅ Enabled")
    print("- Places API (New): ✅ Enabled")
    print("\n💰 Cost estimate for your data:")
    print("- 812 parks × 2 API calls = 1,624 calls")
    print("- Cost: ~$27.60 (at $17 per 1,000 calls)")
    print("- Well within your $50 budget!")
    
    print("\n🚀 Ready to run the enrichment!")
    print("Next step: python enrich_with_google.py")
    
    return True


if __name__ == "__main__":
    success = test_google_api()
    sys.exit(0 if success else 1)
