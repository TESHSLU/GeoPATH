# GeoPATH Framework

GeoPATH is a GIS-based framework for spatial techno-economic assessment of energy systems in Switzerland. It evaluates potential placement, demand-supply matching, and spatial constraints for different energy technologies.

The framework was developed within the SWEET PATHFNDR and WinTES projects. Its core methodology for identifying and linking spatial clusters, energy system sites, and related infrastructure is described in the paper "Mapping Switzerland’s Energy Potential: A Data-Driven Geo-Analysis of Energy Technologies" by S. In-Albon, E. Schmitt, M. Siegwart, and J. Worlitschek, published at CISBAT 2025.

# 1. Installation Requirements


Install the required Python packages using pip:

pip install numpy
pip install pandas
pip install geopandas
pip install matplotlib
pip install shapely
pip install tqdm
pip install seaborn
pip install networkx
pip install pyproj
pip install folium
pip install pyvis
pip install contextily
pip install scipy
pip install pyarrow

(Optional but recommended for large datasets)
pip install rioxarray
pip install dask-geopandas

# 2. Basic User Inputs

All main user inputs are located at the top of PATHFNDR_main_framework.py:

- Square Size Settings:
  - sqr_size: Base square size in meters (e.g., 4000).
  - sqr_size_exp: Expansion size for selected areas (e.g., 6000).

- File Paths:
  - result_folder: Folder name for results.
  - data_energy_path: Folder with energy datasets (.gpkg files).
  - data_placement_path: Folder with placement datasets (.parquet files).

- Data Files:
  - dic_gpkg_data: Dictionary of energy-related datasets.
  - dic_gpkg_geo: Dictionary of placement-related datasets.

- Settings:
  - explore_raw_data: True/False to generate interactive HTML maps.
  - ReCalcData: True/False to force recalculation of spatial data.

- Model Selection:
  - lst_model: List of model class names to use (e.g., ['v_hydrogen_stor']).

# 3. Use-Case Definition

GeoPATH is designed for:

- Spatial filtering using binary boundary conditions.
- Assessing demand-supply potential and placement feasibility.
- Creating spatial networks for connections between supply and demand.
- Running parameter studies on spatial and technical constraints.

Model-specific rules are defined in energy_system_models.py where:

- dic_energy: Defines binary constraints on energy datasets.
- dic_place: Defines constraints on placement datasets.
- dic_obj: Links supply and demand with scaling factors.
- dic_clust: Defines clustering logic for demand or supply objects.

## Data Preprocessing for Complex Conditions

For placement data with multiple acceptable categories:

- Use change_placement_file.py to create a helper column:

Example:
- check_column: 'nutzung'
- values: [list of acceptable land uses]
- new_column: 'pathfndr_01' where 1 = matches any condition

In the main model:
es_model.dic_place = {
    ('lUsage', 'pathfndr_01') : ['eq', 1]
}

For energy data, the built-in class structure handles conditions directly.

# 4. Parameter Study Definition

The configuration in the GeoPATH file shows an example. The data that is referred there is not included.

Parameter studies are defined in dic_par_iteration:

Example:
dic_par_iteration = {
    'cluster_density': [70, 200, 400, 700, 1000],
}

Supported Parameters:
- cluster_distance
- cluster_density
- storage_coverage
- space_demand
- space_distance
- tilt_placement
- zone_placement

Each entry runs the full workflow iteratively over the specified values.

# 5. Result Definition

Outputs include:

- ✅ Geospatial Files (.gpkg):
  - Square maps with calculated data.
  - Filtered polygons after boundary conditions.
  - Placement areas.

- ✅ Tabular Results (.csv/.xlsx):
  - Summary metrics per parameter run:
    - Total demand, supply, connected demand.
    - Network length, value-to-length ratio.
    - Area and value metrics for placed systems.

- ✅ Visual Outputs:
  - Interactive maps (.html via folium).
  - PNG maps (matplotlib/contextily).
  - Network diagrams (pyvis).

- ✅ Backup Files:
  - Existing output files are renamed with timestamps if overwritten.

# 6. Folder Structure Example

/GeoPATH_Project/

├── 03_Results/

│   ├── 01_GeoPATH_Main/

│   │   ├── cluster_density/

│   │   │   ├── result_summary.csv

│   │   │   ├── BC_cluster_map.html

│   │   │   └── ...

│   └── ...

├── 02_Data/

│   ├── energy_data/

│   ├── placement_data/

│   └── ...

├── GeoPATH_main_framework.py

├── energy_system_models.py

├── change_placement_file.py

├── GeoPATH_raw_geodata_analysis.py


# 7. Running the Code

1. Configure user inputs in GeoPATH_main_framework.py.
2. (Optional) Preprocess placement data using change_placement_file.py.
3. (Optional) Explore datasets with GeoPATH_raw_geodata_analysis.py.
4. Run the framework.
5. Analyze results in your results folder.

# 8. Contact

For questions, contact: 

Malin Siegwart: malin.siegwart@hslu.ch

Emma Schmitt: emma.schmitt@hslu.ch 

