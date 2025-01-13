# import os
# os.environ['OMP_NUM_THREADS'] = '1'

from shiny import App, render, ui, reactive
import shinyswatch
import pandas as pd
import geopandas as gpd
import folium
from jinja2 import Template
from geopy.distance import geodesic
import plotly.graph_objects as go
from shapely.geometry import Point
import branca.colormap as cm
from pathlib import Path

# Load and prepare csv data
def load_data(path):
    # Load CSV data
    data_cws = pd.read_csv(f"{path}/Coffee_Washing_Stations.csv")
    data_farmers = pd.read_csv(f"{path}/Coffee_farmers.csv")
    data_farms = pd.read_csv(f"{path}/Coffee_farms.csv")

    # Convert column names to lower case
    data_cws.columns = data_cws.columns.str.lower()
    data_farmers.columns = data_farmers.columns.str.lower()
    data_farms.columns = data_farms.columns.str.lower()
    
    data_cws = gpd.GeoDataFrame(
        data_cws, 
        geometry=gpd.GeoSeries.from_wkt(data_cws['geom']), 
        crs="EPSG:4326"
    ).drop('geom', axis=1)
    
    data_farms = gpd.GeoDataFrame(
        data_farms, 
        geometry=gpd.GeoSeries.from_wkt(data_farms['geom']), 
        crs="EPSG:4326"
    ).to_crs(epsg=32736) # convert to projected CRS to allow area calculation

    # Calculate farm areas
    data_farms['area'] = data_farms.area / 100
    
    # Calculate centroids for farms
    data_farms['geometry'] = data_farms.geometry.centroid 
    data_farms.to_crs(epsg=4326, inplace=True)
    data_farms = data_farms.drop('geom', axis=1)
    
    # Convert columns to numeric
    data_cws['actual_capacity'] = pd.to_numeric(data_cws['actual_capacity'])
    
    return data_cws, data_farmers, data_farms

# load geometry data
def load_geo_data(path):
    country = gpd.read_file(f"{path}/Rw_geodata_wgs84.gpkg", layer="country")
    lakes = gpd.read_file(f"{path}/Rw_geodata_wgs84.gpkg", layer="lakes")
    parks = gpd.read_file(f"{path}/Rw_geodata_wgs84.gpkg", layer="national_parks")
    districts = gpd.read_file(f"{path}/Rw_geodata_wgs84.gpkg", layer="districts")
    districts['district'] = districts['district'].str.lower() # Convert district names to lowercase   
    return country, lakes, parks, districts


# App UI
app_ui = ui.page_fluid(   
    ui.tags.style(
        """      
        /* Keep existing map container styles */
        .map-container {
            height: 770px !important;
            width: 100%;
            overflow: hidden;
            position: relative;
        }
        .map-container > * {
            height: 100% !important;
        }
        /* bg of the map tabs headers */
        .nav-tabs.card-header-tabs {
            background-color: #e4cfb3 !important;
            border-radius: 10px 10px 0 0 !important;
        }

        /* style of the headers of map tabs */
        .nav-tabs {
            border-bottom: none !important;
            padding: 10px 10px 0 10px !important;
            background-color: #f8f9fa !important;
        }

        .nav-tabs .nav-link {
            color: #495057 !important;
            border: none !important;
            border-radius: 8px 8px 0 0 !important;
            padding: 12px 20px !important;
            margin-right: 5px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease !important;
        }

        .nav-tabs .nav-link:hover:not(.active) {
            background-color: #e9ecef !important;
            border: none !important;
        }

        .nav-tabs .nav-link.active {
            background-color: #2c3e50 !important;
            color: white !important;
            border: none !important;
        }

        /* Make card body flush with tabs */
        .card-body {
            padding-top: 0 !important;
        }

        /* Enhanced metric cards styling */
        .metric-card, .card {
            border: none !important;
            border-radius: 10px !important;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
            transition: transform 0.2s ease-in-out !important;
            margin-bottom: 15px !important;
        }

        .metric-card:hover, .card:hover {
            transform: translateY(-3px);
        }

        .metric-card .card-header, .card .card-header {
            border-radius: 10px 10px 0 0 !important;
            padding: 12px 20px !important;
            font-size: 0.9rem !important;
            font-weight: 600 !important;
            letter-spacing: 0.5px !important;
            width: 100% !important;
            margin: 0 !important;
        }

        /* Card header colors */
        .farmers-header {
            background-color: #2c3e50 !important;
            color: white !important;
        }

        .women-header {
            background-color: #16a085 !important;
            color: white !important;
        }

        .youth-header {
            background-color: #a4d5af !important;
            color: white !important;
        }

        .hh-header {
            background-color: #b9cfbe !important;
            color: white !important;
        }

        .area-header {
            background-color: #2c3e50 !important;
            color: white !important;
        }

        /* Card body styling */
        .metric-value {
            padding: 20px !important;
            text-align: center !important;
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            color: #2c3e50 !important;
        }

        /* Labels and units */
        .metric-label {
            display: block;
            font-size: 0.8rem;
            color: #7f8c8d;
            margin-top: 5px;
        }

        .metric-trend {
            font-size: 0.9rem;
            color: #27ae60;
            margin-top: 5px;
        }

        .metric-trend.positive {
            color: #27ae60;
        }

        .metric-trend.negative {
            color: #e74c3c;
        }

        /* Chart card specific styling */
        .card:has(div.shiny-plot-output) {
            height: calc(33vh - 20px) !important;
            margin-bottom: 15px !important;
        }

        .card:has(div.shiny-plot-output) .card-body {
            padding: 10px !important;
            height: calc(100% - 45px) !important;
        }

        .shiny-plot-output {
            height: 100% !important;
            width: 100% !important;
        }
        """
    ),
    
    ui.row(
        ui.column(12,
            ui.div(
                ui.h2("Coffee Extension Activities Dashboard"),
                ui.h4("A dashboard to track key extension-related KPIs for Rwanda's coffee program")
            )
        )
    ),
    
    ui.layout_columns(
        ui.row(
            ui.column(3, 
                ui.card(
                    ui.card_header("Total Farmers", class_="farmers-header"),
                    ui.div(
                        ui.output_text("nbr_farmers"),
                        ui.span("registered coffee farmers", class_="metric-label"),
                        class_="metric-value"
                    ),
                    class_="metric-card"
                ),
                ui.card(
                    ui.card_header("Women Participation", class_="women-header"),
                    ui.div(
                        ui.output_text("nbr_farmers_women"),
                        ui.span("of total farmers are women", class_="metric-label"),
                        #ui.div("↑ 2.3% from last season", class_="metric-trend positive"),
                        class_="metric-value"
                    ),
                    class_="metric-card"
                ),
                ui.card(
                    ui.card_header("Youth Engagement", class_="youth-header"),
                    ui.div(
                        ui.output_text("nbr_farmers_young"),
                        ui.span("of all the farmers are young", class_="metric-label"),
                        #ui.div("↑ 1.8% from last season", class_="metric-trend positive"),
                        class_="metric-value"
                    ),
                    class_="metric-card"
                ),
                ui.card(
                    ui.card_header("Youth in Households", class_="hh-header"),
                    ui.div(
                        ui.output_text("youth_in_hh"),
                        ui.span("young people in farmers' households", class_="metric-label"),
                        class_="metric-value"
                    ),
                    class_="metric-card"
                )
            ),

            # Map tabs
            ui.column(6,
                ui.navset_card_tab(
                    ui.nav_panel("CWS View",                        
                        ui.div(                                               
                            ui.output_ui("map_cws"),
                            class_="map-container"
                        )
                    ),
                    ui.nav_panel("Coffee Farms View",
                        ui.div(
                            ui.output_ui("map_farms"),
                            class_="map-container"
                        )
                    ), id="map_tabs" 
                )
            ),

            ui.column(3,
                ui.row(
                    ui.card(
                        ui.card_header("Total Cultivated Area", class_="area-header"),
                        ui.div(
                            ui.output_text("farm_area"),
                            ui.span("Hectares", class_="metric-label"),
                            #ui.div("↑ 3.2% from last season", class_="metric-trend positive"),
                            class_="metric-value"
                        ),
                        class_="metric-card"
                    )
                ),
                ui.row(
                    ui.card(
                        ui.card_header("# Coffee trees per age", class_="women-header"),
                        ui.output_ui("coffee_trees_chart", height="260px")
                    )
                ),
                ui.row(
                    ui.card(
                        ui.card_header("# Farmers per training touch points", class_="hh-header"),
                        ui.output_ui("touch_points_chart", height="260px")
                    )
                )
            )
        )
    ),
    theme=shinyswatch.theme.flatly
)

# Define the server function
def server(input, output, session):
    # Load data
    geo_data_path = Path("E:/Users/faustin.gashakamba_o/Desktop/data_wgs84")
    coffee_data_path = Path("E:/Users/faustin.gashakamba_o/Desktop/Coffee Dashboard/data")
    country, lakes, parks, districts = load_geo_data(geo_data_path)
    data_cws, data_farmers, data_farms = load_data(coffee_data_path)

    @output
    @render.text
    def nbr_farmers():
        return str(len(data_farmers))
    
    @output
    @render.text
    def nbr_farmers_women():
        women = len(data_farmers[data_farmers['gender'] == 'female'])
        return f"{(women / len(data_farmers)) * 100:.1f}%"
    
    @output
    @render.text
    def nbr_farmers_young():
        young = len(data_farmers[data_farmers['age'].astype(int) < 30])
        return f"{(young / len(data_farmers)) * 100:.1f}%"
    
    @output
    @render.text
    def youth_in_hh():
        return str(data_farmers['young_in_hh'].dropna().astype(int).sum())
    
    # Initialize reactive value for coordinates
    clicked_coords = reactive.Value({'lat': None, 'lng': None})

    # Update the clicked coordinates variable
    @reactive.Effect
    @reactive.event(input.clicked_coords)
    def _():
        coords = input.clicked_coords()
        if coords is not None:
            clicked_coords.set({
                'lat': float(coords[0]),
                'lng': float(coords[1])
            })

    # Calculate reactive variables used for interactivity
    #------------------------------------------------
    #1. get the clicked district
    @reactive.Calc
    def selected_district():
        coords = clicked_coords.get()
        if coords['lat'] is not None and coords['lng'] is not None:
            point = gpd.GeoDataFrame(
                [{"geometry": Point(coords['lng'], coords['lat'])}],
                crs="EPSG:4326"
            )
            current_district = gpd.sjoin(districts, point, how="inner", predicate="intersects")
            return current_district
        return None
    
    #2. get the farms in the selected district
    @reactive.Calc
    def selected_farms():
        cur_district = selected_district()
        if cur_district is not None:
            distr_farms = gpd.sjoin(data_farms, cur_district.loc[:, ['district', 'geometry']], how="inner", predicate="intersects")
            return distr_farms
        return None
    
    #3. Get the nearest CWS to the clicked spot on the CWS map
    @reactive.Calc
    def selected_cws():
        clicked_spot = clicked_coords()
        if clicked_spot['lat'] is not None and clicked_spot['lng'] is not None:
            point_coords = (clicked_spot['lat'], clicked_spot['lng'])
            
            # Calculate distances from clicked point to all CWS locations
            distances = data_cws.geometry.apply(
                lambda x: geodesic(
                    point_coords,
                    (x.y, x.x)
                ).meters
            )
            
            # Get the index of the minimum distance
            nearest_idx = distances.idxmin()
            
            # Return the nearest CWS
            return data_cws.iloc[[nearest_idx]]
        return None
    
    # Add a reactive effect to reset selected_cws and selected-district to Null 
    # This will trigger whenever the map tab changes
    @reactive.Effect
    def _():
        input.map_tabs()
        clicked_coords.set({'lat': None, 'lng': None}) 

  
    @output
    @render.ui
    def map_cws():
        # Create a folium map centered at Rwanda's center
        m = folium.Map(location=[-1.9403, 29.8739], zoom_start=8) 

        # Style function for the country
        def style_country(feature):
            return {
                'fillColor': '#acbbb4', 
                'color': '#3f4b46',   
                'weight': 4,     
                'fillOpacity': 0.2
            }
        
        # Style function for the districts
        def style_districts(feature):
            return {
                'fillColor': '#acbbb4', 
                'color': '#3f4b46',   
                'weight': 2,     
                'fillOpacity': 0.2
            }
    
        # Style function for lakes
        def style_lakes(feature):
            return {
                'fillColor': '#37a3bd', 
                'color': '#345a6a',   
                'weight': 1,     
                'fillOpacity': 0.6
            }

        # Style function for national parks
        def style_parks(feature):
            return {
                'fillColor': '#13764b',  
                'color': '#006600',   
                'weight': 2,     
                'fillOpacity': 0.6
            }

        # Add base layers
        folium.GeoJson(country, name="Country boundary", 
                       style_function=style_country
                       ).add_to(m) 
        folium.GeoJson(districts, name="Districts", 
                       style_function=style_districts,
                       tooltip=folium.GeoJsonTooltip(fields=["district"])
                       ).add_to(m) 
        folium.GeoJson(parks, name="National parks", 
                       style_function=style_parks
                       ).add_to(m)
        folium.GeoJson(lakes, name="Lakes", 
                       style_function=style_lakes
                       ).add_to(m) 

        # Add farm points
        for idx, row in data_cws.iterrows():
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=2,
                color='#011e0b',
                fill=True,
                fillOpacity=0.6
            ).add_to(m)

        # hightlght farms in the selected district
        cur_cws = selected_cws()
        if cur_cws is not None and not cur_cws.empty:
            folium.CircleMarker(
                location=[cur_cws.geometry.y, cur_cws.geometry.x],
                radius=3,
                color='yellow',
                fill=True,
                fillOpacity=0.6
            ).add_to(m)

        # attach a click event handler which captures the coordinates of
        # the click location and sends them to shiny to update the clicked_coords variable
        map_name = m.get_name()
        code = """
        {% macro script(this,kwargs) %}
        function getLatLng(e){
            var lat = e.latlng.lat.toFixed(6),
                lng = e.latlng.lng.toFixed(6);
            parent.Shiny.setInputValue('clicked_coords', [lat, lng], {priority: 'event'});
        }; """ +  map_name + ".on('click', getLatLng){% endmacro %}"
        
        el = folium.MacroElement().add_to(m)
        el._template = Template(code)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        m.get_root().height = "100%"

        # return the map as a HTML object
        return ui.HTML(m._repr_html_())
    
    # Render the coffee farms map
    @output
    @render.ui
    def map_farms():
        # Create a folium map centered around Rwanda's centroid point
        m = folium.Map(location=[-1.9403, 29.8739], zoom_start=8) 
        
        # Style function for the country
        def style_country(feature):
            return {
                'fillColor': '#acbbb4', 
                'color': '#3f4b46',   
                'weight': 4,     
                'fillOpacity': 0.2
            }
        
        # Style function for the districts
        def style_districts(feature):
            return {
                'fillColor': '#acbbb4', 
                'color': '#3f4b46',   
                'weight': 2,     
                'fillOpacity': 0.2
            }
    
        # Style function for lakes
        def style_lakes(feature):
            return {
                'fillColor': '#37a3bd', 
                'color': '#345a6a',   
                'weight': 1,     
                'fillOpacity': 0.6
            }

        # Style function for national parks
        def style_parks(feature):
            return {
                'fillColor': '#13764b',  
                'color': '#006600',   
                'weight': 2,     
                'fillOpacity': 0.6
            }

        # Add base layers
        folium.GeoJson(country, name="Country boundary", 
                       style_function=style_country
                       ).add_to(m) 
        folium.GeoJson(districts, name="Districts", 
                       style_function=style_districts,
                       tooltip=folium.GeoJsonTooltip(fields=["district"])
                       ).add_to(m) 
        folium.GeoJson(parks, name="National parks", 
                       style_function=style_parks
                       ).add_to(m)
        folium.GeoJson(lakes, name="Lakes", 
                       style_function=style_lakes
                       ).add_to(m) 

        # Add the selected district layer
        style_selected_district = {
            'fillColor': '#ff7800',
            'color': '#000000',
            'weight': 2,
            'fillOpacity': 0.6
        }
        cur_district = selected_district()
        if cur_district is not None and not cur_district.empty:
            folium.GeoJson(
                cur_district,
                name="Selected District",
                style_function=lambda x: style_selected_district,
                tooltip=folium.GeoJsonTooltip(fields=["district"])
            ).add_to(m)

        # Add farm points
        for idx, row in data_farms.iterrows():
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=2,
                color='#011e0b',
                fill=True,
                fillOpacity=0.6
            ).add_to(m)

        # hightlght farms in the selected district
        cur_farms = selected_farms()
        if cur_farms is not None and not cur_farms.empty:
            for idx, row in cur_farms.iterrows():
                folium.CircleMarker(
                    location=[row.geometry.y, row.geometry.x],
                    radius=3,
                    color='blue',
                    fill=True,
                    fillOpacity=0.6
                ).add_to(m)

        # attach a click event handler which captures the coordinates of
        # the click location and sends them to shiny to update the clicked_coords variable
        map_name = m.get_name()
        code = """
        {% macro script(this,kwargs) %}
        function getLatLng(e){
            var lat = e.latlng.lat.toFixed(6),
                lng = e.latlng.lng.toFixed(6);
            parent.Shiny.setInputValue('clicked_coords', [lat, lng], {priority: 'event'});
        }; """ +  map_name + ".on('click', getLatLng){% endmacro %}"
        
        el = folium.MacroElement().add_to(m)
        el._template = Template(code)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        m.get_root().height = "100%"
            
        # return the map as a HTML object
        return ui.HTML(m._repr_html_())
        
    # Calculate the reactive variables and update related charts
    #==========================================================
    #1. Farm area info card
    @output
    @render.text
    def farm_area():
        current_tab = input.map_tabs() # check which map is currently in focus
        if current_tab == "Coffee Farms View":
            if selected_district() is not None:
                # Perform spatial join if a district is selected
                filtered_farms = gpd.sjoin(data_farms, selected_district().loc[:, ['district', 'geometry']], how="inner", predicate="intersects")
                total_area = filtered_farms['area'].sum()
            else:
                total_area = data_farms['area'].sum()
        elif current_tab == "CWS View":
            if selected_cws() is not None:
                cur_cws = str(selected_cws()['cws_id'].values[0])
                data_farmers_cws = data_farmers[data_farmers['cws_id'] == cur_cws]
                unique_national_ids = data_farmers_cws['national_id'].unique().tolist()
                filtered_farms = data_farms[data_farms['national_id'].isin(unique_national_ids)]
                total_area = filtered_farms['area'].sum()
            else:
                total_area = data_farms['area'].sum()
        else:
            total_area = data_farms['area'].sum()

        return f"{total_area:,.1f}" 

    # #2. Coffee trees chart
    @output
    @render.ui
    def coffee_trees_chart():
        # filter farms data based on the active tab and/or selected district-selected CWS
        current_tab = input.map_tabs()
        if current_tab == "Coffee Farms View":
            if selected_district() is not None:
                # Perform spatial filter if a district is selected
                data_farms_filtered = gpd.sjoin(data_farms, selected_district().loc[:, ['district', 'geometry']], how="inner", predicate="intersects")
            else:
                data_farms_filtered = data_farms
        elif current_tab == "CWS View":
            if selected_cws() is not None:
                cur_cws = str(selected_cws()['cws_id'].values[0])
                data_farmers_cws = data_farmers[data_farmers['cws_id'] == cur_cws]
                unique_national_ids = data_farmers_cws['national_id'].unique().tolist()
                data_farms_filtered = data_farms[data_farms['national_id'].isin(unique_national_ids)]
            else:
                data_farms_filtered = data_farms
        else:
            data_farms_filtered = data_farms

        # Prepare the data for ploting
        data = data_farms_filtered.groupby('age_range_coffee_trees')['nbr_coffee_trees'].sum().reset_index()
        
        # Create the plot using plotly
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=data['age_range_coffee_trees'],
            y=data['nbr_coffee_trees'],
            marker=dict(
                color='rgba(50, 171, 96, 0.6)',
                showscale=False,
                colorbar=dict(title='age_range_coffee_trees')
            )
        ))

        # re-arrange the bars in the proper trees' age groups order
        fig.update_layout(
            xaxis = dict(
                categoryorder='array',
                categoryarray=["less_3", "3_to_7", "8_to_15", "16_to_30", "more_30"]
            ),
            height=250,
            margin=dict(l=10, r=10, t=30, b=10),
            autosize=True,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        return ui.HTML(fig.to_html(full_html=False))

    # 3. training touchpoints chart  
    @output
    @render.ui
    def touch_points_chart():
        # filter farmers data based on the active tab and/or selected district-selected CWS
        current_tab = input.map_tabs()
        if current_tab == "Coffee Farms View":
            if selected_district() is not None:
                # Select the farmers in the selected district
                cur_district = str(selected_district()['district'].values[0])
                data_farmers_filtered = data_farmers[data_farmers['district'] == cur_district]
            else:
                data_farmers_filtered = data_farmers
        elif current_tab == "CWS View":
            if selected_cws() is not None:
                cur_cws = str(selected_cws()['cws_id'].values[0])
                data_farmers_filtered = data_farmers[data_farmers['cws_id'] == cur_cws]
            else:
                data_farmers_filtered = data_farmers
        else:
            data_farmers_filtered = data_farmers

        # Prepare the training data
        training_data = (
            data_farmers_filtered['training_topics']
            .str.split(' ')
            .explode()
            .value_counts()
            .reset_index()
        )
        # Rename columns for clarity
        training_data.columns = ['topic', 'count'] 
        data = training_data.sort_values('count', ascending=False)
       
        # Create the plotly plot
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=data['topic'],
            y=data['count'],
            marker=dict(
                color='rgba(50, 171, 96, 0.6)',
                colorscale='Greens',
                showscale=False,
                colorbar=dict(title='topic')
            )
        ))

        fig.update_layout(
            yaxis=dict(tickformat=','),
            xaxis=dict(tickangle=45),
            height=250,
            margin=dict(l=10, r=10, t=30, b=10),
            autosize=True,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )

        return ui.HTML(fig.to_html(full_html=False))

app = App(app_ui, server)
