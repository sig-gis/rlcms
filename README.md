# Running Regional Land Cover Monitoring System Toolset
## Installation
Install with pip: 
```
pip install rlcms
```

# Testing Your Setup
Test that `earthengine-api` is setup and authenticated by checking the folder contents within one of your cloud projects. 
* In your shell, run:
```
earthengine set_project <project-name>
earthengine ls projects/project-name/assets
```

If you do not get an error and it returns a list of folders and assets similar to this then you are good to go! :tada:

# Tool Documentation

Each Command Line Interface (CLI) script tool can be run in your command-line terminal of choice. The user must provide values for each required command-line argument to control the analysis.
You can first run any script, only declaring the `-h` flag. This will bring up the help dialog with a usage example and a description of required command-line arguments. 

## **sample_pts**

Generate Random Sample Points From an ee.Image, Formatted for Collect Earth Online

The points are pre-formatted for use in Collect Earth Online. You can choose to export the points to Google Drive, to GEE Asset or both. 

example:
```
sample_pts -im input/path/to/image -band LANDCOVER -o output/path --n_points 100 --to_drive
```

## **composite**

Create a Composite from one or multiple datasets. 

The resulting band stack is needed for both extracting training data (using `train_test`) and as input stack for the primitive model training & inference (using `primitives` tool). 

There are many compositing options available, which you control in the CLI with your own settings .txt file. Follow this template [`composite_template_settings.txt`](/composite_template_settings.txt) to create your own file, then pass this file's path to `--settings`. 

If your AOI is a set of reference polygons and not one contiguous AOI polygon, set `multi_poly` to `true` in your `--settings` file - this will export band information only within each polygon's footprint. 

example:
```
composite -a aoi/fc/path -d Landsat8 -s 2020-01-01 -e 2020-12-31 -o output/path --settings path/to/settings/file.txt
```

## **train_test**

Extract Train and Test Point Data from an Input Image using a Reference Locations (can be Point or Polygon).

Generates stratified random samples from reference locations, splitting the sample points into train and test points if desired. The image bands from the provided image are extracted to every point. 

example:
```
train_test -ref path/to/reference_fc -im path/to/input/stack -band LANDCOVER --scale 10
                -o unique/output/path --class_values 1 2 3 4 5 6 7 8 --class_points 10 10 10 10 10 10 10
```

## **primitives**

Create Primitives For All Classes in Provided Training Data. 

This script trains probability models for each land cover class in your typology as provided by the numeric `--class_name` property in the provided reference data. It then exports these binary probability images one land cover at a time into a land cover 'Primitives' image collection. Model metrics are retained in the Images themselves as properties, which the user can choose to export to local files by setting a `--metrics_folder` local folder path during the run. 

example:
```
primitives -i path/to/input_stack -t path/to/training_data --class_name LANDCOVER -o path/to/output --metrics_folder local/folder/path
```

## **landcover**

Generate Single Land Cover Image From Land Cover Primitives Image Collection

This script takes a Primitives Image Collection and assembles a single-band land cover image from them using per-pixel max probability.

example:
```
landcover -i input/primitives/imagecollection/path -o output/path
```


