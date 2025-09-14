#!/usr/bin/env python3
"""
Caravan Parks Enricher v2.0 - FULL Dataset Edition
Enriches ALL development-viable parks including Victoria (without size data)
"""

import pandas as pd
import googlemaps
import time
import json
import os
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, asdict
import logging
from fuzzywuzzy import fuzz
from dotenv import load_dotenv
import sys
import numpy as np

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enrichment_v2.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ParkDetails:
    """Structured data for a caravan park"""
    # Original data
    original_name: str
    latitude: float
    longitude: float
    state: str
    land_area_sqm: Optional[float] = None
    category: Optional[str] = None
    tourism_type: Optional[str] = None
    
    # Size estimation for VIC parks
    estimated_size: bool = False
    size_confidence: Optional[str] = None
    size_indicators: Optional[Dict] = None
    
    # Google Places enriched data
    google_place_id: Optional[str] = None
    google_name: Optional[str] = None
    google_confidence: float = 0.0
    
    # Contact details
    phone: Optional[str] = None
    phone_source: Optional[str] = None
    email: Optional[str] = None
    email_source: Optional[str] = None
    website: Optional[str] = None
    website_source: Optional[str] = None
    
    # Address details
    formatted_address: Optional[str] = None
    street_number: Optional[str] = None
    street_name: Optional[str] = None
    suburb: Optional[str] = None
    postcode: Optional[str] = None
    
    # Business details
    business_status: Optional[str] = None
    opening_hours: Optional[Dict] = None
    permanently_closed: bool = False
    
    # Reviews and ratings
    rating: Optional[float] = None
    total_reviews: Optional[int] = None
    reviews_summary: Optional[List[str]] = None
    
    # Development indicators
    price_level: Optional[int] = None
    types: Optional[List[str]] = None
    is_chain: bool = False
    chain_name: Optional[str] = None
    
    # Metadata
    last_updated: str = datetime.now().isoformat()
    api_calls_used: int = 0
    development_score: float = 0.0


class EnhancedCaravanParkEnricher:
    """Enhanced enricher that handles Victoria and identifies chains"""
    
    CHAIN_PATTERNS = {
        'BIG4': r'BIG\s?4|Big\s?4',
        'NRMA': r'NRMA',
        'Discovery Parks': r'Discovery',
        'Top Tourist': r'Top\s?Tourist',
        'Ingenia': r'Ingenia',
        'Reflections': r'Reflections',
        'G\'day': r'G\'?day',
        'Tasman': r'Tasman'
    }
    
    def __init__(self, api_key: str):
        """Initialize with Google API key"""
        self.gmaps = googlemaps.Client(key=api_key)
        self.api_calls = 0
        self.api_limit = 2000  # Increased for larger dataset
        self.cache_file = 'google_places_cache_v2.json'
        self.cache = self.load_cache()
        
    def load_cache(self) -> Dict:
        """Load cached API responses"""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_cache(self):
        """Save cache to disk"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def identify_chain(self, name: str) -> Tuple[bool, Optional[str]]:
        """Identify if park belongs to a chain"""
        if pd.isna(name):
            return False, None
            
        import re
        for chain_name, pattern in self.CHAIN_PATTERNS.items():
            if re.search(pattern, name, re.IGNORECASE):
                return True, chain_name
        return False, None
    
    def estimate_size_from_indicators(self, place_data: Dict) -> Dict:
        """Estimate park size for Victoria based on Google data"""
        indicators = {}
        confidence = 'low'
        estimated_size = None
        
        if place_data:
            # Review count as size proxy
            reviews = place_data.get('user_ratings_total', 0)
            if reviews > 500:
                indicators['review_based'] = 'large'
                estimated_size = 200000  # 20ha estimate
                confidence = 'medium'
            elif reviews > 200:
                indicators['review_based'] = 'medium'
                estimated_size = 150000  # 15ha estimate
                confidence = 'medium'
            elif reviews > 50:
                indicators['review_based'] = 'small-medium'
                estimated_size = 100000  # 10ha estimate
                confidence = 'low'
            
            # Price level indicator
            price = place_data.get('price_level')
            if price and price >= 3:
                indicators['price_based'] = 'premium'
                if estimated_size:
                    estimated_size *= 1.5
            
            # Types can indicate size
            types = place_data.get('types', [])
            if 'rv_park' in types or 'campground' in types:
                indicators['type_based'] = 'likely_large'
                if not estimated_size:
                    estimated_size = 120000  # 12ha default
        
        return {
            'estimated_size_sqm': estimated_size or 100000,  # 10ha default
            'confidence': confidence,
            'indicators': indicators
        }
    
    def find_place(self, name: str, lat: float, lng: float, state: str) -> Optional[Dict]:
        """Find a place using Google Places API with smart matching"""
        
        # Check cache first
        cache_key = f"{name}_{lat}_{lng}"
        if cache_key in self.cache:
            logger.info(f"Using cached result for {name}")
            return self.cache[cache_key]
        
        # Check API limit
        if self.api_calls >= self.api_limit:
            logger.warning(f"API limit reached ({self.api_limit} calls)")
            return None
        
        try:
            # Enhanced search for chains
            is_chain, chain_name = self.identify_chain(name)
            
            search_queries = [
                f"{name} caravan park {state}",
                name,
                f"{name} holiday park",
                f"{name} tourist park"
            ]
            
            if is_chain:
                search_queries.insert(0, f"{chain_name} {name}")
            
            best_match = None
            best_score = 0
            
            for query in search_queries:
                result = self.gmaps.find_place(
                    input=query,
                    input_type='textquery',
                    location_bias=f"circle:5000@{lat},{lng}",
                    fields=['place_id', 'name', 'geometry', 'types', 'business_status']
                )
                self.api_calls += 1
                
                if result['candidates']:
                    candidate = result['candidates'][0]
                    
                    # Calculate match score
                    name_similarity = fuzz.ratio(name.lower(), candidate.get('name', '').lower())
                    
                    # Check distance
                    if 'geometry' in candidate:
                        clat = candidate['geometry']['location']['lat']
                        clng = candidate['geometry']['location']['lng']
                        distance = ((lat - clat)**2 + (lng - clng)**2)**0.5
                        distance_score = max(0, 100 - distance * 1000)
                    else:
                        distance_score = 50
                    
                    # Bonus for chains
                    chain_bonus = 20 if is_chain and chain_name.lower() in candidate.get('name', '').lower() else 0
                    
                    total_score = (name_similarity * 0.6) + (distance_score * 0.3) + chain_bonus
                    
                    if total_score > best_score:
                        best_score = total_score
                        best_match = candidate
                
                if best_score > 75:  # Good enough match
                    break
            
            if best_match and best_score > 50:  # Lower threshold for VIC parks
                place_details = self.get_place_details(best_match['place_id'])
                self.api_calls += 1
                
                if place_details:
                    place_details['confidence_score'] = best_score
                    
                    # Cache the result
                    self.cache[cache_key] = place_details
                    self.save_cache()
                    
                    return place_details
            
            # Cache negative result
            self.cache[cache_key] = None
            self.save_cache()
            
        except Exception as e:
            logger.error(f"Error finding place {name}: {e}")
        
        return None
    
    def get_place_details(self, place_id: str) -> Optional[Dict]:
        """Get detailed information about a place"""
        try:
            result = self.gmaps.place(
                place_id=place_id,
                fields=[
                    'name', 'formatted_address', 'formatted_phone_number',
                    'international_phone_number', 'website', 'rating',
                    'user_ratings_total', 'price_level', 'types',
                    'opening_hours', 'business_status', 'address_components',
                    'reviews', 'geometry', 'url', 'plus_code'
                ]
            )
            
            if result['status'] == 'OK':
                return result['result']
            
        except Exception as e:
            logger.error(f"Error getting place details: {e}")
        
        return None
    
    def calculate_development_score(self, park: ParkDetails) -> float:
        """Enhanced scoring that accounts for Victoria and chains"""
        score = 0
        
        # Size score (adjusted for VIC)
        if park.state == 'VIC' and park.estimated_size:
            # Assume VIC holiday parks are viable
            score += 20
            if park.size_confidence == 'medium':
                score += 5
        elif park.land_area_sqm:
            size_ha = park.land_area_sqm / 10000
            if size_ha > 50:
                score += 30
            elif size_ha > 20:
                score += 20
            elif size_ha > 8:
                score += 10
        
        # Chain bonus (easier to negotiate portfolio deals)
        if park.is_chain:
            score += 15
        
        # Contact availability (max 20 points)
        if park.phone:
            score += 10
        if park.email or park.website:
            score += 10
        
        # Review indicators (max 25 points)
        if park.rating:
            if park.rating < 3.5:
                score += 25  # Poor reviews = opportunity
            elif park.rating < 4.0:
                score += 15
            elif park.rating < 4.5:
                score += 5
        
        # Business status (max 25 points)
        if park.permanently_closed:
            score += 25
        elif park.business_status == 'OPERATIONAL':
            score += 10
        
        # Victoria bonus (untapped market)
        if park.state == 'VIC':
            score += 10
        
        return min(score, 100)
    
    def enrich_park(self, row: pd.Series) -> ParkDetails:
        """Enrich a single park with Google Places data"""
        
        park = ParkDetails(
            original_name=row.get('name', row.get('Name', 'Unknown')),
            latitude=row['latitude'],
            longitude=row['longitude'],
            state=row['state'],
            land_area_sqm=row.get('land_area_sqm') if pd.notna(row.get('land_area_sqm')) else None,
            category=row.get('category'),
            tourism_type=row.get('tourism')
        )
        
        # Check if it's a chain
        park.is_chain, park.chain_name = self.identify_chain(park.original_name)
        
        # Keep existing data if available
        if pd.notna(row.get('phone')):
            park.phone = row['phone']
            park.phone_source = 'original'
        if pd.notna(row.get('email')):
            park.email = row['email']
            park.email_source = 'original'
        if pd.notna(row.get('website')):
            park.website = row['website']
            park.website_source = 'original'
        
        # Skip if no name
        if park.original_name == 'Unknown' or pd.isna(park.original_name):
            logger.warning(f"Skipping park with no name at {park.latitude}, {park.longitude}")
            return park
        
        # Find and enrich with Google data
        place_data = self.find_place(
            park.original_name,
            park.latitude,
            park.longitude,
            park.state
        )
        
        if place_data:
            # Update park details
            park.google_place_id = place_data.get('place_id')
            park.google_name = place_data.get('name')
            park.google_confidence = place_data.get('confidence_score', 0)
            
            # Contact details
            if not park.phone and place_data.get('formatted_phone_number'):
                park.phone = place_data['formatted_phone_number']
                park.phone_source = 'google'
            
            if not park.website and place_data.get('website'):
                park.website = place_data['website']
                park.website_source = 'google'
            
            # Address components
            park.formatted_address = place_data.get('formatted_address')
            
            if 'address_components' in place_data:
                for component in place_data['address_components']:
                    types = component.get('types', [])
                    if 'street_number' in types:
                        park.street_number = component['long_name']
                    elif 'route' in types:
                        park.street_name = component['long_name']
                    elif 'locality' in types:
                        park.suburb = component['long_name']
                    elif 'postal_code' in types:
                        park.postcode = component['long_name']
            
            # Business details
            park.business_status = place_data.get('business_status')
            park.permanently_closed = park.business_status == 'CLOSED_PERMANENTLY'
            park.opening_hours = place_data.get('opening_hours')
            
            # Reviews
            park.rating = place_data.get('rating')
            park.total_reviews = place_data.get('user_ratings_total')
            
            # Development indicators
            park.price_level = place_data.get('price_level')
            park.types = place_data.get('types', [])
            
            # For Victoria parks without size, estimate it
            if park.state == 'VIC' and not park.land_area_sqm:
                size_est = self.estimate_size_from_indicators(place_data)
                park.land_area_sqm = size_est['estimated_size_sqm']
                park.estimated_size = True
                park.size_confidence = size_est['confidence']
                park.size_indicators = size_est['indicators']
            
            park.api_calls_used = 2
            
            logger.info(f"Enriched {park.original_name} ({park.state}) - confidence: {park.google_confidence:.1f}%")
        else:
            logger.warning(f"No Google data for {park.original_name} ({park.state})")
        
        # Calculate development score
        park.development_score = self.calculate_development_score(park)
        
        return park


def load_full_dataset():
    """Load and filter the complete dataset including Victoria"""
    
    print("\n📂 Loading complete dataset...")
    
    # Try multiple file locations
    file_paths = [
        '/mnt/user-data/uploads/Caravan_Parks_List.xlsx',
        'Caravan_Parks_List.xlsx',
        './Caravan_Parks_List.xlsx'
    ]
    
    df = None
    for path in file_paths:
        if os.path.exists(path):
            df = pd.read_excel(path, sheet_name='caravan_parks_master')
            print(f"✅ Loaded from: {path}")
            break
    
    if df is None:
        print("❌ Could not find data file!")
        return None
    
    print(f"Total entries: {len(df)}")
    
    # Smart filtering for development opportunities
    print("\n🔍 Filtering for development opportunities...")
    
    # Parks with size >8ha
    large_parks = df[df['land_area_sqm'] > 80000].copy()
    print(f"Parks >8ha: {len(large_parks)}")
    
    # Victoria holiday/caravan parks (no size filter)
    vic_parks = df[
        (df['state'] == 'VIC') & 
        ((df['category'].isin(['holiday', 'unknown'])) | 
         (df['tourism'] == 'caravan_site'))
    ].copy()
    print(f"Victoria opportunities: {len(vic_parks)}")
    
    # Combine and deduplicate
    all_opportunities = pd.concat([large_parks, vic_parks]).drop_duplicates()
    
    # Filter for actual commercial parks
    filtered = all_opportunities[
        (all_opportunities['category'].isin(['holiday', 'unknown', 'built_community'])) |
        (all_opportunities['tourism'] == 'caravan_site')
    ]
    
    print(f"\n✅ Total development opportunities: {len(filtered)}")
    print(f"By state:")
    print(filtered['state'].value_counts())
    
    return filtered


def main():
    """Main enrichment process for full dataset"""
    
    # Load environment variables
    load_dotenv()
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("\n❌ ERROR: No Google API key found!")
        print("Please follow GOOGLE_API_SETUP.md")
        print("Then create .env file with: GOOGLE_API_KEY=your_key_here")
        sys.exit(1)
    
    # Load complete dataset
    df = load_full_dataset()
    if df is None:
        sys.exit(1)
    
    # Prioritize processing
    print("\n📊 Processing priority:")
    print("1. Chain parks (high value)")
    print("2. Parks with no contact info")
    print("3. Victoria parks (untapped market)")
    
    # Initialize enricher
    enricher = EnhancedCaravanParkEnricher(api_key)
    
    # Identify chains for priority processing
    df['is_chain'] = df['name'].apply(
        lambda x: enricher.identify_chain(x)[0] if pd.notna(x) else False
    )
    
    # Sort by priority
    df['has_contact'] = df['phone'].notna() | df['website'].notna()
    df['priority'] = (
        df['is_chain'].astype(int) * 3 +  # Chains get highest priority
        (~df['has_contact']).astype(int) * 2 +  # No contact info
        (df['state'] == 'VIC').astype(int)  # Victoria bonus
    )
    df = df.sort_values('priority', ascending=False)
    
    print(f"\n🔍 Starting enrichment...")
    print(f"API budget: {enricher.api_limit} calls")
    print(f"Chain parks identified: {df['is_chain'].sum()}")
    
    enriched_parks = []
    
    for idx, row in df.iterrows():
        if enricher.api_calls >= enricher.api_limit:
            print(f"\n⚠️ API limit reached. Processed {len(enriched_parks)}/{len(df)} parks")
            break
        
        print(f"\nProcessing {len(enriched_parks)+1}/{len(df)}: {row.get('name', 'Unknown')} ({row['state']})")
        park = enricher.enrich_park(row)
        enriched_parks.append(asdict(park))
        
        # Small delay
        time.sleep(0.3)
        
        # Save progress every 50 parks
        if len(enriched_parks) % 50 == 0:
            print(f"\n💾 Saving progress... API calls: {enricher.api_calls}")
            pd.DataFrame(enriched_parks).to_csv('enriched_full_progress.csv', index=False)
    
    # Create final dataframe
    enriched_df = pd.DataFrame(enriched_parks)
    
    # Sort by development score
    enriched_df = enriched_df.sort_values('development_score', ascending=False)
    
    # Save results
    output_file = f'enriched_caravan_parks_FULL_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    enriched_df.to_excel(output_file, index=False)
    print(f"\n✅ Enrichment complete! Results saved to {output_file}")
    
    # Print summary statistics
    print("\n📊 Enrichment Summary:")
    print(f"Total parks processed: {len(enriched_df)}")
    print(f"Parks by state:")
    print(enriched_df['state'].value_counts())
    print(f"\nChain parks found: {enriched_df['is_chain'].sum()}")
    print(f"Parks with phone: {enriched_df['phone'].notna().sum()}")
    print(f"Parks with email: {enriched_df['email'].notna().sum()}")
    print(f"Parks with website: {enriched_df['website'].notna().sum()}")
    print(f"Permanently closed: {enriched_df['permanently_closed'].sum()}")
    print(f"Average score: {enriched_df['development_score'].mean():.1f}")
    print(f"High opportunity (70+): {len(enriched_df[enriched_df['development_score'] > 70])}")
    
    # Top opportunities by state
    print("\n🏆 Top 5 opportunities per state:")
    for state in enriched_df['state'].unique():
        state_df = enriched_df[enriched_df['state'] == state].head(5)
        print(f"\n{state}:")
        for _, park in state_df.iterrows():
            chain_tag = f"[{park['chain_name']}]" if park['is_chain'] else ""
            print(f"  - {park['original_name']} {chain_tag} (Score: {park['development_score']:.0f})")
    
    return enriched_df


if __name__ == "__main__":
    df = main()
