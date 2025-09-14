#!/usr/bin/env python3
"""
Interactive Dashboard for Caravan Park Development Opportunities
Run with: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# Page configuration
st.set_page_config(
    page_title="Caravan Parks Development Finder",
    page_icon="🏕️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .high-opportunity {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    """Load the enriched caravan parks data"""
    # Try to load the most recent enriched file
    files = [f for f in os.listdir('.') if f.startswith('enriched_caravan_parks_') and f.endswith('.xlsx')]
    
    if files:
        latest_file = sorted(files)[-1]
        df = pd.read_excel(latest_file)
    else:
        # Fall back to original data if no enriched version exists
        df = pd.read_excel('/mnt/user-data/uploads/Caravan_Parks_List.xlsx')
        
        # Add placeholder development score if not present
        if 'development_score' not in df.columns:
            df['development_score'] = 50  # Default score
    
    # Calculate size in hectares
    df['size_ha'] = df['land_area_sqm'] / 10000
    
    # Create size categories
    df['size_category'] = pd.cut(
        df['size_ha'],
        bins=[0, 10, 20, 50, 100, float('inf')],
        labels=['Small (8-10ha)', 'Medium (10-20ha)', 'Large (20-50ha)', 
                'Very Large (50-100ha)', 'Massive (100+ha)']
    )
    
    return df


def create_map(df_filtered):
    """Create an interactive map of caravan parks"""
    
    # Calculate center point
    center_lat = df_filtered['latitude'].mean()
    center_lon = df_filtered['longitude'].mean()
    
    # Create map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=6)
    
    # Add markers with color coding based on development score
    for idx, row in df_filtered.iterrows():
        # Determine marker color based on development score
        score = row.get('development_score', 50)
        if score >= 80:
            color = 'red'  # Hot opportunity
            icon = 'fire'
        elif score >= 60:
            color = 'orange'  # Good opportunity
            icon = 'star'
        elif score >= 40:
            color = 'blue'  # Moderate opportunity
            icon = 'info-sign'
        else:
            color = 'gray'  # Low opportunity
            icon = 'home'
        
        # Create popup text
        popup_html = f"""
        <div style="width: 300px;">
            <h4>{row.get('Name', 'Unknown')}</h4>
            <p><b>State:</b> {row['state']}</p>
            <p><b>Size:</b> {row['size_ha']:.1f} hectares</p>
            <p><b>Development Score:</b> {score:.0f}/100</p>
            <p><b>Phone:</b> {row.get('phone', 'Not available')}</p>
            <p><b>Website:</b> {row.get('website', 'Not available')}</p>
            <p><b>Rating:</b> {row.get('rating', 'N/A')}</p>
        </div>
        """
        
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{row.get('Name', 'Unknown')} - Score: {score:.0f}",
            icon=folium.Icon(color=color, icon=icon)
        ).add_to(m)
    
    return m


def main():
    """Main dashboard application"""
    
    # Header
    st.markdown('<h1 class="main-header">🏕️ Caravan Parks Development Opportunities</h1>', 
                unsafe_allow_html=True)
    
    # Load data
    df = load_data()
    
    # Sidebar filters
    st.sidebar.header("🔍 Filter Options")
    
    # State filter
    states = st.sidebar.multiselect(
        "Select States",
        options=df['state'].unique(),
        default=df['state'].unique()
    )
    
    # Size filter
    size_range = st.sidebar.slider(
        "Size Range (hectares)",
        min_value=float(df['size_ha'].min()),
        max_value=min(float(df['size_ha'].max()), 500),  # Cap at 500ha for UI
        value=(8.0, 100.0),
        step=1.0
    )
    
    # Development score filter
    if 'development_score' in df.columns:
        score_range = st.sidebar.slider(
            "Development Score",
            min_value=0,
            max_value=100,
            value=(60, 100),
            step=5
        )
    else:
        score_range = (0, 100)
    
    # Contact availability filter
    st.sidebar.subheader("Contact Availability")
    has_phone = st.sidebar.checkbox("Has Phone Number")
    has_email = st.sidebar.checkbox("Has Email")
    has_website = st.sidebar.checkbox("Has Website")
    
    # Business status filter
    if 'permanently_closed' in df.columns:
        show_closed = st.sidebar.checkbox("Show Closed Parks", value=True)
    else:
        show_closed = True
    
    # Apply filters
    df_filtered = df[
        (df['state'].isin(states)) &
        (df['size_ha'] >= size_range[0]) &
        (df['size_ha'] <= size_range[1])
    ]
    
    if 'development_score' in df.columns:
        df_filtered = df_filtered[
            (df_filtered['development_score'] >= score_range[0]) &
            (df_filtered['development_score'] <= score_range[1])
        ]
    
    if has_phone:
        df_filtered = df_filtered[df_filtered['phone'].notna()]
    if has_email:
        df_filtered = df_filtered[df_filtered['email'].notna()]
    if has_website:
        df_filtered = df_filtered[df_filtered['website'].notna()]
    
    if not show_closed and 'permanently_closed' in df.columns:
        df_filtered = df_filtered[~df_filtered['permanently_closed']]
    
    # Main content area
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📊 Overview", "🗺️ Map View", "📈 Analytics", "🎯 Top Opportunities", "📧 Export for Outreach"]
    )
    
    with tab1:
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Parks", len(df_filtered))
        with col2:
            avg_size = df_filtered['size_ha'].mean()
            st.metric("Avg Size", f"{avg_size:.1f} ha")
        with col3:
            contact_rate = (df_filtered['phone'].notna().sum() / len(df_filtered) * 100) if len(df_filtered) > 0 else 0
            st.metric("Contact Rate", f"{contact_rate:.1f}%")
        with col4:
            if 'development_score' in df_filtered.columns:
                high_opportunity = len(df_filtered[df_filtered['development_score'] >= 70])
                st.metric("High Opportunity", high_opportunity)
            else:
                st.metric("High Opportunity", "N/A")
        
        # Distribution charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Size distribution
            fig_size = px.histogram(
                df_filtered,
                x='size_ha',
                nbins=30,
                title="Park Size Distribution",
                labels={'size_ha': 'Size (hectares)', 'count': 'Number of Parks'}
            )
            fig_size.update_layout(showlegend=False)
            st.plotly_chart(fig_size, use_container_width=True)
        
        with col2:
            # State distribution
            state_counts = df_filtered['state'].value_counts()
            fig_state = px.pie(
                values=state_counts.values,
                names=state_counts.index,
                title="Parks by State"
            )
            st.plotly_chart(fig_state, use_container_width=True)
    
    with tab2:
        st.subheader("Interactive Map of Caravan Parks")
        
        # Map controls
        col1, col2 = st.columns([3, 1])
        with col2:
            st.info(f"📍 Showing {len(df_filtered)} parks\n\n"
                   "🔴 Hot opportunities (80+)\n"
                   "🟠 Good opportunities (60-79)\n"
                   "🔵 Moderate (40-59)\n"
                   "⚫ Low priority (<40)")
        
        # Display map
        if len(df_filtered) > 0:
            map_display = create_map(df_filtered)
            st_folium(map_display, width=1200, height=600)
        else:
            st.warning("No parks match the current filters")
    
    with tab3:
        st.subheader("Development Analytics")
        
        if 'development_score' in df_filtered.columns:
            # Development score vs size scatter
            fig_scatter = px.scatter(
                df_filtered,
                x='size_ha',
                y='development_score',
                color='state',
                size='size_ha',
                hover_data=['Name', 'phone', 'website'],
                title="Development Score vs Park Size",
                labels={'size_ha': 'Size (hectares)', 'development_score': 'Development Score'}
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
            
            # Score distribution by state
            fig_box = px.box(
                df_filtered,
                x='state',
                y='development_score',
                title="Development Score Distribution by State"
            )
            st.plotly_chart(fig_box, use_container_width=True)
        
        # Size categories analysis
        if 'size_category' in df_filtered.columns:
            size_cat_counts = df_filtered['size_category'].value_counts()
            fig_cat = px.bar(
                x=size_cat_counts.index,
                y=size_cat_counts.values,
                title="Parks by Size Category",
                labels={'x': 'Size Category', 'y': 'Number of Parks'}
            )
            st.plotly_chart(fig_cat, use_container_width=True)
    
    with tab4:
        st.subheader("🎯 Top Development Opportunities")
        
        # Sort by development score
        if 'development_score' in df_filtered.columns:
            top_parks = df_filtered.nlargest(20, 'development_score')
        else:
            top_parks = df_filtered.nlargest(20, 'size_ha')
        
        # Display top opportunities
        for idx, park in top_parks.iterrows():
            with st.expander(f"🏕️ {park.get('Name', 'Unknown')} - Score: {park.get('development_score', 'N/A')}"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write("**Location Details:**")
                    st.write(f"- State: {park['state']}")
                    st.write(f"- Coordinates: {park['latitude']:.4f}, {park['longitude']:.4f}")
                    st.write(f"- Size: {park['size_ha']:.1f} hectares")
                
                with col2:
                    st.write("**Contact Information:**")
                    st.write(f"- Phone: {park.get('phone', 'Not available')}")
                    st.write(f"- Email: {park.get('email', 'Not available')}")
                    st.write(f"- Website: {park.get('website', 'Not available')}")
                
                with col3:
                    st.write("**Business Metrics:**")
                    st.write(f"- Rating: {park.get('rating', 'N/A')}")
                    st.write(f"- Reviews: {park.get('total_reviews', 'N/A')}")
                    st.write(f"- Status: {park.get('business_status', 'Unknown')}")
    
    with tab5:
        st.subheader("📧 Export for Mail Merge")
        
        # Selection options
        export_options = st.radio(
            "Select parks to export:",
            ["Current filtered selection", "Top 50 by score", "Custom selection"]
        )
        
        if export_options == "Current filtered selection":
            export_df = df_filtered
        elif export_options == "Top 50 by score":
            if 'development_score' in df_filtered.columns:
                export_df = df_filtered.nlargest(50, 'development_score')
            else:
                export_df = df_filtered.nlargest(50, 'size_ha')
        else:
            # Custom selection
            selected_parks = st.multiselect(
                "Select specific parks:",
                options=df_filtered['Name'].dropna().tolist()
            )
            export_df = df_filtered[df_filtered['Name'].isin(selected_parks)]
        
        # Fields to export
        st.write("**Select fields to include:**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            include_name = st.checkbox("Name", value=True)
            include_phone = st.checkbox("Phone", value=True)
            include_email = st.checkbox("Email", value=True)
        
        with col2:
            include_address = st.checkbox("Address", value=True)
            include_website = st.checkbox("Website", value=True)
            include_size = st.checkbox("Size", value=True)
        
        with col3:
            include_score = st.checkbox("Development Score", value=True)
            include_state = st.checkbox("State", value=True)
            include_coords = st.checkbox("Coordinates", value=False)
        
        # Prepare export dataframe
        export_columns = []
        if include_name:
            export_columns.append('Name')
        if include_phone:
            export_columns.append('phone')
        if include_email:
            export_columns.append('email')
        if include_address and 'formatted_address' in export_df.columns:
            export_columns.append('formatted_address')
        if include_website:
            export_columns.append('website')
        if include_size:
            export_columns.append('size_ha')
        if include_score and 'development_score' in export_df.columns:
            export_columns.append('development_score')
        if include_state:
            export_columns.append('state')
        if include_coords:
            export_columns.extend(['latitude', 'longitude'])
        
        # Filter columns that exist
        export_columns = [col for col in export_columns if col in export_df.columns]
        
        if export_columns:
            final_export = export_df[export_columns].copy()
            
            # Preview
            st.write(f"**Preview ({len(final_export)} parks):**")
            st.dataframe(final_export.head(10))
            
            # Download button
            csv = final_export.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV for Mail Merge",
                data=csv,
                file_name=f"caravan_parks_mailmerge_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
            
            # Email template suggestion
            with st.expander("📝 Suggested Email Template"):
                st.text_area(
                    "Copy this template for your mail merge:",
                    value="""Subject: Development Opportunity - [Name]

Dear [Name] Management,

I am reaching out regarding potential development opportunities for caravan and holiday parks in [state].

We specialize in upgrading and modernizing caravan park facilities to meet growing tourism demand. Your property at [Name] caught our attention due to its strategic location and significant land area of [size_ha] hectares.

I would love to discuss how we could work together to:
- Modernize existing facilities
- Expand accommodation options
- Improve guest amenities
- Increase operational efficiency

Would you be available for a brief call next week to explore potential opportunities?

Best regards,
[Your Name]
[Your Company]
[Your Phone]""",
                    height=400
                )


if __name__ == "__main__":
    main()
