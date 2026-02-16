#!/usr/bin/env python3
"""
Integration script to add Google enrichment to existing Caravan_Scraper pipeline
This becomes Step 6 after classification
"""

import argparse
import pandas as pd
import sys
import os
from pathlib import Path

def integrate_google_enrichment():
    """
    Integrates Google Places enrichment with existing pipeline
    
    Existing pipeline:
    1. overpass_fetch → OSM data
    2. brands.run_all → Brand sources
    3. merge_dedupe → Combined data
    4. area_nsw/qld → Land parcels
    5. classify → Categories
    
    This adds:
    6. google_enrich → Contact details, reviews, scores
    """
    
    parser = argparse.ArgumentParser(description='Add Google enrichment to pipeline')
    parser.add_argument('--in', dest='input', required=True, 
                       help='Input CSV from classify step')
    parser.add_argument('--out', required=True,
                       help='Output CSV with Google enrichment')
    parser.add_argument('--api-key', help='Google API key (or use .env)')
    parser.add_argument('--limit', type=int, default=2000,
                       help='API call limit')
    
    args = parser.parse_args()
    
    # Import the enricher (assuming it's in src/)
    sys.path.insert(0, str(Path(__file__).parent))
    from enrich_with_google_v2 import EnhancedCaravanParkEnricher
    
    # Load classified data
    print(f"Loading classified data from {args.input}")
    df = pd.read_csv(args.input)
    
    # Get API key
    if args.api_key:
        api_key = args.api_key
    else:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("ERROR: No API key provided. Use --api-key or set in .env")
        return 1
    
    # Initialize enricher
    enricher = EnhancedCaravanParkEnricher(api_key)
    enricher.api_limit = args.limit
    
    # Process each park
    enriched_data = []
    for idx, row in df.iterrows():
        if enricher.api_calls >= enricher.api_limit:
            print(f"API limit reached at {idx}/{len(df)}")
            break
            
        park = enricher.enrich_park(row)
        
        # Merge with existing data
        enriched_row = row.to_dict()
        enriched_row.update({
            'google_place_id': park.google_place_id,
            'google_confidence': park.google_confidence,
            'phone_enriched': park.phone or row.get('phone'),
            'email_enriched': park.email or row.get('email'),
            'website_enriched': park.website or row.get('website'),
            'rating': park.rating,
            'total_reviews': park.total_reviews,
            'business_status': park.business_status,
            'permanently_closed': park.permanently_closed,
            'is_chain': park.is_chain,
            'chain_name': park.chain_name,
            'development_score': park.development_score
        })
        
        enriched_data.append(enriched_row)
        
        if (idx + 1) % 50 == 0:
            print(f"Processed {idx + 1}/{len(df)}")
    
    # Save enriched data
    enriched_df = pd.DataFrame(enriched_data)
    enriched_df.to_csv(args.out, index=False)
    print(f"Saved enriched data to {args.out}")
    
    # Print summary
    print("\nEnrichment Summary:")
    print(f"Parks processed: {len(enriched_df)}")
    print(f"Phone numbers found: {enriched_df['phone_enriched'].notna().sum()}")
    print(f"Websites found: {enriched_df['website_enriched'].notna().sum()}")
    print(f"Chains identified: {enriched_df['is_chain'].sum()}")
    print(f"High opportunity (70+): {(enriched_df['development_score'] > 70).sum()}")
    
    return 0

if __name__ == "__main__":
    sys.exit(integrate_google_enrichment())
