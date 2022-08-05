# Running KAZA Regional Land Cover Monitoring System

# Python Environment setup

### The only required python packages that do not ship with a python install is `earthengine-api`. Install this package with pip (`pip install earthengine-api`) or conda (`conda install -c conda-forge earthengine-api` ).

#
# Asset Management
### We will organize our Earth Engine assets (files) in an EE cloud project. We have AOIs, input stacks, output land cover product, and reference samples. We will have this basic structure setup already.

#![kaza_readme_folderOrg](https://user-images.githubusercontent.com/51868526/183120715-58a6c92d-79fe-4345-9e26-c821978fa485.JPG)

# Workflow

## The following workflow is executed for each region in KAZA (script name in parenthesis if applicable):
### 1) Generate and interpret land cover reference samples for training and testing data using Collect Earth Online (01sample_pts.py)
### 2) Generate input data stack from chosen sensor used by the model (02sentinel2_sr.py ** currently only using Sentinel data)
### 3) Create land cover primitives (03RFprimitives.py)
### 4) Construct categorical land cover map from the set of land cover primitives (04generate_LC.py)
### 5) Conduct accuracy assessment (05accuracy.py)
### 6) Estimate area of each land cover class
#
# Scripts

## Each script will be run on the command-line and take a few user-provided arguments. The output Earth Engine asset from a given script must complete before the next script is run.

## Here is a list of arguments the scripts will require:
* project - name of cloud project to operate from and export to (i.e. SNMC)
* aoi_s - the unique aoi string identifier for the region (e.g. SNMC)
* year - year that you are running the land cover model for
* sensor - one of "S2" or "planet", determines which sensor the input data is compiled from

## Some scripts will require all of these, while others will require only a subset. To determine which arguments the 02Sentinel2_sr.py script requires, for instance, in your command-line shell type `python 02sentinel2_sr.py -h` declaring the help flag. This will bring up the usage example and the arguments the script requires.

![kaza_readme_cmdline](https://user-images.githubusercontent.com/51868526/183121578-5ed97acd-af15-4d17-94d6-00fd00487427.JPG)