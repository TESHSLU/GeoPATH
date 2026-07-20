# -*- coding: utf-8 -*-
"""
Created on Wed May  8 13:41:48 2024
Function to create, save and open a map from a geodataframe
@author: Simon In-Albon
"""

import geopandas as gpd
import folium
import webbrowser
import os
import pandas as pd
import pyproj
from folium.plugins import FloatImage
from data_worker import string_operator_converter
import shapely
import re
import numpy as np

#%%
def map_plotter(geo_df, file_name, path):
    """
    Parameters
    ----------
    geo_df : GeoDataFrame % if it has a Multihead, the geometry must be: Level 0 = 'Basic' & Level 1 = 'geometry'
    
    file_name : str
        filen_name.html
    
    path : str
    ----------
    """
    #check if the given geo_df has a MultiHead
    if isinstance(geo_df.columns, pd.MultiIndex):
        # Flatten MultiHeader to single level
        # print ('----- MultiHeader DataFrame is flattend -----')      
        geo_df = geo_df.copy()
        geo_df.columns = ['_'.join(col).strip() for col in geo_df.columns.values]
        geo_df = geo_df.set_geometry('Basic_geometry')
        
    print ('----- Creating map of all polygons -----')      
    explore_map = geo_df.explore(legend=False)
    map_path = path+file_name
    explore_map.save(map_path)
    #open the map in a webbrowser
    print ('----- Open map of all polygons -----')
    current_directory = os.getcwd()
    os.chdir(path)
    webbrowser.open_new_tab(file_name)
    os.chdir(current_directory)

#%% Color Mapping with multi layer and choosen data information displayed

def color_map_plotter(geo_dfs, layer_names, file_name, path, display_columns=None, dic_BC = None, color_palette="tab10"):
    """
    Plot multiple GeoDataFrames on a single map with specified colors for each GeoDataFrame.

    Parameters:
    - geo_dfs: List of GeoDataFrames to plot.
    - colors: List of colors corresponding to each GeoDataFrame.
    - layer_names: [list of layer names for each GeoDataFrame]
    - file_name: Name of the output HTML file.
    - path: Directory to save the HTML file (default is current directory).
    - display_columns: List of columns to display in pop-ups and tooltips.
                       If None, defaults to all columns except 'Basic_geometry'.
    """   
    #check if the given geo_df has a MultiHead
    for j in range(len(geo_dfs)):
        if isinstance(geo_dfs[j].columns, pd.MultiIndex):
            # Flatten MultiHeader to single level
            # print ('----- MultiHeader DataFrame is flattend -----')      
            geo_dfs[j] = geo_dfs[j].copy()
            geo_dfs[j].columns = ['_'.join(col).strip() for col in geo_dfs[j].columns.values]
            geo_dfs[j] = geo_dfs[j].set_geometry('Basic_geometry')
    
    # Get colors from Matplotlib colormap
    cmap = plt.get_cmap(color_palette, len(geo_dfs))
    colors = [mcolors.to_hex(cmap(i)) for i in range(len(geo_dfs))]
    
    # convert every point or multipoint to a polygon
    def point_to_triangle(point, size):
        """Convert a point to a tiny triangular polygon."""
        x, y = point.x, point.y
        return shapely.geometry.Polygon([
            (x, y + size),  # Top vertex
            (x - size, y - size),  # Bottom-left vertex
            (x + size, y - size)   # Bottom-right vertex
        ])
    def multipoint_to_multipolygon(multipoint, size):
        """Convert a MultiPoint to a MultiPolygon with tiny triangles."""
        return shapely.geometry.MultiPolygon([point_to_triangle(point, size) for point in multipoint.geoms])
    
    # Apply conversion function based on geometry type
    def convert_geometry(geom, size):
        if geom.geom_type == "Point":
            return point_to_triangle(geom, size)
        elif geom.geom_type == "MultiPoint":
            return multipoint_to_multipolygon(geom, size)
        else:
            return geom
    
    combined_geometries = gpd.GeoSeries(pd.concat([df.geometry for df in geo_dfs.copy()], ignore_index=True))

    # Calculate the centroid of the combined geometries
    centroid = combined_geometries.unary_union.centroid
    lat, lon = pyproj.Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True).transform(centroid.x, centroid.y)
    # Create a map centered on the calculated centroid
    m = folium.Map(location=[lon, lat], zoom_start=9)

    # Function to style each feature based on the GeoDataFrame's color
    def make_style_function(color):
        return lambda feature: {
            'fillColor': color,
            'color': color,
            'weight': 1,
            'fillOpacity': 0.6,
        }

    # If no display_columns is provided, default to all columns except 'Basic_geometry'
    for i, (geo_df, color, layer_name) in enumerate(zip(geo_dfs, colors, layer_names)):
        
        points_df = geo_df[geo_df.geometry.geom_type.isin(["Point", "MultiPoint"])]
        # Add Points
        if not points_df.empty:
            # Replace the old point geometries with small triangles
            geo_df = geo_df.set_geometry(geo_df['geometry'].apply(lambda geom: convert_geometry(geom, size= 15)))            
            geo_df.set_crs("EPSG:2056", inplace=True)
            
        # Default behavior: use all columns except 'Basic_geometry'
        if display_columns is None:
            try:
                display_columns = [col for col in geo_df.columns if col not in ['Basic_geometry', 'geometry']]            
            except:
                display_columns = []

        # Ensure that only available columns are used
        valid_columns = [col for col in display_columns if col in geo_df.columns]

        # Add the GeoJSON layer to the map with popups and tooltips
        folium.GeoJson(
            geo_df,
            name=layer_name,
            style_function=make_style_function(color),
            # marker=folium.CircleMarker,
            popup=folium.GeoJsonPopup(fields=valid_columns),  # Show specified columns in pop-up
            tooltip=folium.GeoJsonTooltip(fields=valid_columns)  # Show specified columns in tooltip
        ).add_to(m)

    if dic_BC != None:
        #adding a textbox to the map
        title_box = 'Applied boundary conditions:'
        text_box1 = ''
        text_box2 = ''
        for key in dic_BC:
            text_box1 += key[0]+'_'+key[1]+' '+string_operator_converter(dic_BC[key][0])+' '+ f'{dic_BC[key][1]}</p><p>'
        #call the function that defines the style of the textbox
        text_macro = text_to_map(title_box, text_box1, text_box2)
        # Add the macro text element to the map
        m.get_root().add_child(text_macro)
        
    folium.LayerControl().add_to(m)
        
    # Save the map to an HTML file
    map_path = path+file_name
    m.save(map_path)
    #open the map in a webbrowser
    print ('----- Open map of all objects -----')
    current_directory = os.getcwd()
    os.chdir(path)
    webbrowser.open_new_tab(file_name)
    os.chdir(current_directory)
    
#%% Insert text to folium map

def text_to_map(title ,text1, text2):
    # Define the HTML content for the textbox
    html = f"""
        <div id='textbox' style='
            position: fixed; 
            top: 10px; 
            left: 50px; 
            width: 250px; 
            height: auto; 
            padding: 10px;
            background-color: white; 
            border:2px solid grey; 
            z-index:9999; 
            font-size: 14px;'>
            <h4>{title}</h4>
            <p>{text1}</p>
            <p>{text2}</p>
        </div>
    """
    
    # Use the branca element to inject the HTML
    from branca.element import Template, MacroElement
    
    # Create a Template object
    template = Template("""
    {% macro html(this, kwargs) %}
        """ + html + """
    {% endmacro %}
    """)
    
    macro = MacroElement()
    macro._template = template
    return macro

   
#%%
import folium
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from folium.plugins import MarkerCluster

def plot_multiple_gdfs(geo_dfs, layer_names, file_name, path, color_palette="tab10"):
    """
    Plot multiple GeoDataFrames on a single Folium map, each with a different color from a standard color palette.

    Parameters:
    - geo_dfs: List of GeoDataFrames to plot.
    - layer_names: List of names corresponding to each GeoDataFrame.
    - file_name: Name of the output HTML file.
    - path: Directory to save the HTML file.
    - color_palette: Name of the matplotlib colormap to use (default: 'tab10').
    """

    # Get colors from Matplotlib colormap
    cmap = plt.get_cmap(color_palette, len(geo_dfs))
    colors = [mcolors.to_hex(cmap(i)) for i in range(len(geo_dfs))]

    combined_geometries = gpd.GeoSeries(pd.concat([df.geometry for df in geo_dfs.copy()], ignore_index=True))

    # Calculate the centroid of the combined geometries
    centroid = combined_geometries.unary_union.centroid
    lat, lon = pyproj.Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True).transform(centroid.x, centroid.y)
    # Create a map centered on the calculated centroid
    m = folium.Map(location=[lon, lat], zoom_start=9)

    # Loop through each GeoDataFrame and add it to a separate Layer
    for i, (geo_df, color, layer_name) in enumerate(zip(geo_dfs, colors, layer_names)):
        
        # Separate different geometry types
        points_df = geo_df[geo_df.geometry.geom_type.isin(["Point", "MultiPoint"])]
        lines_df = geo_df[geo_df.geometry.geom_type.isin(["LineString", "MultiLineString"])]
        polygons_df = geo_df[geo_df.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

        # Create Feature Group for Layer Control
        feature_group = folium.FeatureGroup(name=f"{layer_name}").add_to(m)

        # Add Points
        if not points_df.empty:
            points_df = points_df.to_crs(epsg=4326)
            for _, row in points_df.iterrows():
                if row.geometry and not row.geometry.is_empty:
                    popup_content = row.drop("geometry").to_json()
                    popup_text = folium.Popup(popup_content, parse_html=True)                    
                    if row.geometry.geom_type == "MultiPoint":
                        for point in row.geometry.geoms:
                            folium.CircleMarker(
                                location=[point.y, point.x],
                                radius=5,
                                color=color,
                                fill=True,
                                fill_color=color,
                                fill_opacity=0.8,
                                popup=popup_text
                            ).add_to(feature_group)
                    else:
                        folium.CircleMarker(
                            location=[row.geometry.y, row.geometry.x],
                            radius=5,
                            color=color,
                            fill=True,
                            fill_color=color,
                            fill_opacity=0.8,
                            popup=popup_text
                        ).add_to(feature_group)

        # Add LineStrings using GeoJson
        if not lines_df.empty:
            folium.GeoJson(
                lines_df,
                name=f"{layer_name} - Lines",
                style_function=lambda feature, col=color: {
                    "color": col,
                    "weight": 2,
                    "opacity": 0.8,
                },
            ).add_to(feature_group)

        # Add Polygons using GeoJson
        if not polygons_df.empty:
            folium.GeoJson(
                polygons_df,
                name=f"{layer_name} - Polygons",
                style_function=lambda feature, col=color: {
                    "fillColor": col,
                    "color": col,
                    "weight": 1,
                    "fillOpacity": 0.6,
                },
            ).add_to(feature_group)

    # Add Layer Control
    folium.LayerControl(collapsed=False).add_to(m)

    # Save the map and open it
    map_path = path + file_name
    m.save(map_path)
    print(f'Map saved to {map_path}')


    #open the map in a webbrowser
    print ('----- Open map of all objects -----')
    current_directory = os.getcwd()
    os.chdir(path)
    webbrowser.open_new_tab(file_name)
    os.chdir(current_directory)
    
#%%
def plot_multiple_gdfs2(geo_dfs, layer_names, file_name, path, color_palette="tab10"):
    """
    Create an interactive map with multiple GeoDataFrames using .explore()

    Parameters:
    - geo_dfs: List of GeoDataFrames to plot.
    - colors: List of colors corresponding to each GeoDataFrame.
    - layer_names: List of names for each GeoDataFrame layer.
    - file_name: Name of the output HTML file.
    - path: Directory to save the HTML file.
    """
    # Get colors from Matplotlib colormap
    cmap = plt.get_cmap(color_palette, len(geo_dfs))
    colors = [mcolors.to_hex(cmap(i)) for i in range(len(geo_dfs))]
    
    # Assign layer names to each GeoDataFrame
    for geo_df, layer_name in zip(geo_dfs, layer_names):
        geo_df["Layer"] = layer_name  

    # Merge all GeoDataFrames into one
    combined_gdf = gpd.GeoDataFrame(pd.concat(geo_dfs, ignore_index=True))
    combined_gdf = combined_gdf.to_crs(epsg=4326)  # Convert to correct CRS

    # Debugging: Check if geometries exist
    if combined_gdf.empty or combined_gdf.geometry.is_empty.all():
        print("Warning: No valid geometries found. The map may be blank.")

    print(f"Total features in merged GeoDataFrame: {len(combined_gdf)}")
    
    # Calculate centroid for map centering (directly using EPSG:4326 coordinates)
    centroid = combined_gdf.geometry.unary_union.centroid
    lat, lon = centroid.y, centroid.x  # Use lat/lon directly

    print(f"Map center calculated at: {lat}, {lon}")

    # Create a map centered on the calculated centroid with an explicit tile layer
    base_map = folium.Map(location=[lat, lon], zoom_start=9, tiles="OpenStreetMap")

    # Ensure Layer column is a string before mapping colors
    combined_gdf["Layer"] = combined_gdf["Layer"].astype(str)

    # Define color mapping
    layer_color_map = dict(zip(layer_names, colors))
    combined_gdf["color"] = combined_gdf["Layer"].map(layer_color_map).fillna("#808080")

    # Debugging: Print first few rows
    print("Combined GeoDataFrame preview:")
    print(combined_gdf.head())

    # Attempt to add data using explore
    try:
        base_map = combined_gdf.explore(
            m=base_map,
            color=combined_gdf["color"],
            tooltip=list(combined_gdf.columns),
            popup=True,
            legend=True,
            name="All Layers"
        )
        print("Data added using .explore()")
    except Exception as e:
        print(f"Error adding data with .explore(): {e}")
        print("Falling back to manual GeoJson addition...")
        folium.GeoJson(combined_gdf, name="All Layers").add_to(base_map)


    # Add Layer Control
    folium.LayerControl(collapsed=False).add_to(base_map)

    # Save the map
    map_path = path + file_name
    print(f'Map saved to {map_path}')
    #open the map in a webbrowser
    print ('----- Open map of all objects -----')
    current_directory = os.getcwd()
    os.chdir(path)
    webbrowser.open_new_tab(file_name)
    os.chdir(current_directory)

#%% Multilayer plot

def final_map_plotter(lst_gdf, file_name, save_path, obj_color = True, add_layer_df= None, layer_name = None, color_palette="Dark2", show = True, open_map=True):
    
    if layer_name is None:
        layer_name = []
    if add_layer_df is None:
        add_layer_df = []
    
    if len(layer_name) == 0:
        index_list_gdf = []
        for k in lst_gdf:
            index_list_gdf.append(list(k.index))
        layer_name = extract_prefixes(index_list_gdf)
    
    # print(layer_name)
    cmap = plt.get_cmap(color_palette, len(lst_gdf))
    if len(add_layer_df) != 0:
        colors = [mcolors.to_hex(cmap(i)) for i in range(len(lst_gdf)+1)]
    else:
        colors = [mcolors.to_hex(cmap(i)) for i in range(len(lst_gdf))]
    print ('----- Creating map of all polygons -----')      
    m = lst_gdf[0].explore(
        color=colors[0],  # use red color on all points
        marker_kwds=dict(radius=5, fill=True),  # make marker radius 10px with fill
        name=layer_name[0],  # name of the layer in the map
        tiles=None
    )
    for k in range(1,len(lst_gdf)):
        lst_gdf[k].explore(
            m=m,  # pass the map object
            marker_kwds=dict(radius=5, fill=True),  # make marker radius 10px with fill
            color=colors[k],  # use red color on all points
            name=layer_name[k],  # name of the layer in the map
        )
        
    # IF add layer df is not empty:
    if len(add_layer_df) != 0:
        # create list of unique values in the column the user defined
        lst_add_layer = add_layer_df[0].loc[:,add_layer_df[1]].drop_duplicates().sort_values().tolist()
        lst_shades = generate_shades(colors[-1], len(lst_add_layer))
        for k in range(len(lst_add_layer)):
            if (k == len(lst_add_layer)-1) and (show == False):
                shown = True
            elif show == True:
                shown = True
            else:
                shown = False
            vars()[f'gdf_now_{k}'] = add_layer_df[0][add_layer_df[0].loc[:,add_layer_df[1]] == lst_add_layer[k]].copy()
            vars()[f'gdf_now_{k}'].explore(
                m=m,  # pass the map object
                color=lst_shades[k],  # use red color on all points
                marker_kwds=dict(radius=5, fill=True),  # make marker radius 10px with fill
                name=f'{add_layer_df[1]}: {lst_add_layer[k]}',  # name of the layer in the map
                show=shown
            )
            del vars()[f'gdf_now_{k}'] 
    folium.TileLayer("CartoDB positron", show=True).add_to(m)  # use folium to add alternative tiles
    folium.TileLayer("OpenStreetMap", show=False).add_to(m)

    folium.LayerControl().add_to(m)  # use folium to add layer control
    print ('----- Saving your precious map -----')
    m.save(save_path+file_name)    
    if open_map:
        print ('----- Open map of all polygons -----')
        current_directory = os.getcwd()
        os.chdir(save_path)
        webbrowser.open_new_tab(file_name) #open the map in a webbrowser
        os.chdir(current_directory)
    
#%%

def extract_prefixes(index_lists):
    seen = set()
    prefixes = []
    
    for index_list in index_lists:
        for index in index_list:
            match = re.match(r'^[A-Za-z]+', index)  # Match letters before the first digit
            if match:
                prefix = match.group()
                if prefix not in seen:
                    seen.add(prefix)
                    prefixes.append(prefix)  # Preserve order
    
    return prefixes
#%%
def generate_shades(base_color, n):
    """Generate `n` shades of a given base color in HEX format."""
    if n > 1:
        base_rgb = np.array(mcolors.to_rgb(base_color))  # Convert to RGB
        min_rgb = base_rgb * 0.3  # Ensure at least 30% of the base color remains
        shades = [((1 - (i / (n - 1))) * base_rgb + (i / (n - 1)) * min_rgb) for i in range(n)]  # Interpolate towards min_rgb
        hex_shades = [mcolors.to_hex(shade) for shade in shades]  # Convert to HEX
    else:
        hex_shades = [base_color]
    return hex_shades
