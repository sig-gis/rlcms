#%%
import os
import ee
import argparse
import numpy as np
import rlcms.sampling as sampling
from rlcms.utils import check_exists, exportTableToAsset, exportTableToDrive

## GLOBAL VARS
scale = 10 # for Sentinel2

def main():
    ee.Initialize()

    parser = argparse.ArgumentParser(
    description="Generate Random Sample Points From an ee.Image, Formatted for Collect Earth Online",
    usage = "sample_pts -im input/path/to/image -band LANDCOVER -o output/path --n_points 100 --to_drive"
    )
    
    parser.add_argument(
    "-im",
    "--input_image",
    type=str,
    required=True,
    help="asset path to image you are sampling from"
    )
    
    # added this required arg for greater flexibility. default behavior of .stratifiedSample() is to use image's first band
    # most LC images will only have one band but in case the img doesn't this ensures correct behavior..
    parser.add_argument(
    "-band",
    "--class_band",
    type=str,
    required=True,
    help="class band name to use for stratification"
    )

    parser.add_argument(
    "-oa",
    "--output_asset",
    type=str,
    required=False,
    help="The output GEE asset path for export."
    )
    
    parser.add_argument(
    "-od",
    "--output_drive",
    type=str,
    required=False,
    help="The output google drive path for export."
    )
    parser.add_argument(
    "--n_points",
    type=int,
    required=False,
    help="Number of points per class. Default: 100"
    )

    parser.add_argument(
    '--class_values', 
    type=int, 
    nargs='+',
    required=False,
    help="list of unique LANDCOVER values in input Feature Collection"
    )

    parser.add_argument(
    "--class_points",
    type=int,
    nargs='+',
    required=False,
    help="number of samples to collect per class"
    )
    
    parser.add_argument(
    "-r",
    "--reshuffle",
    dest="reshuffle",
    action="store_true",
    help="randomizes seed used in all functions",
    )

    parser.add_argument(
    "-d",
    "--dry_run",
    dest="dry_run",
    action="store_true",
    help="goes through checks and prints output asset path but does not export.",
    )

    args = parser.parse_args()
    
    input_path = args.input_image
    class_band = args.class_band
    output_asset = args.output_asset
    output_drive = args.output_drive
    n_points = args.n_points
    class_values = args.class_values
    class_points = args.class_points
    reshuffle = args.reshuffle
    dry_run = args.dry_run

    # perform checks
    assert check_exists(input_path) == 0, f"Check input FeatureCollection exists: {input_path}"
    # GEE won't make parents for you
    if output_asset:
        output_asset_folder = os.path.dirname(output_asset)
        assert check_exists(output_asset_folder) == 0, f"Check GEE output asset's folder exists: {output_asset_folder}"
    
    # value checks if class_values and class_points args are both provided
    if ((class_values != None) and (class_points != None)):
        
        # class_values and class_points must be equal length
        if len(class_values) != len(class_points):
            print(f"Error: class_points and class_values are of unequal length: {class_values} {class_points}")
            exit()
        # class_values and class_points provided so we'll override n_points, 
        # but ee.Image.stratifiedSample() still requires it so we set to default
        n_points=100
    
    # if only one is provided, error 
    elif (class_values != None and class_points == None) or (class_values == None and class_points != None):
        print(f"Error: class_values and class_points args are codependent, provide both or neither. class_values:{class_values}, class_points:{class_points}")
    
    # if neither class_values nor class_points provided, n_points must be provided, otherwise we set a default n_points value 
    else:
        if n_points != None:
            pass
        else:
            n_points=100
            print(f"Warning: Defaulting to equal allocation of default n: {n_points}. Set n_points or class_values and class_points to control sample allocation.")
            
    
    img = ee.Image(input_path)
    bbox = img.geometry().bounds() # region
    # default seed is set, will re-randomize seed if reshuffle==True
    seed=90210
    if reshuffle:
        np.random.RandomState()
        seed = np.random.randint(low=1,high=1e6)
        print(f"reshuffled new seed: {seed}")
    
    
    samples = sampling.strat_sample(img=img,
                                    class_band=class_band,
                                    region=bbox,
                                    scale=scale, # 10, hard coded set at top of script, can make this a user arg for greater flexibility
                                    seed=seed, 
                                    n_points=n_points,
                                    class_values=class_values,
                                    class_points=class_points)

   
    selectors = 'LON,LAT,PLOTID,SAMPLEID,'+class_band
    
    # to GEE Asset only
    if output_asset!=None and output_drive==None:
        desc = os.path.basename(output_asset)+'-Asset'
        if dry_run:
            print(f"would export (Asset): {output_asset}")
            exit()
        else:
            exportTableToAsset(samples,desc,output_asset)
    
    # to Google Drive only
    elif output_asset==None and output_drive!=None:
        # user might not provide a GEE asset conforming path as output if toAsset not their intent
        drive_folder = os.path.dirname(output_drive)
        drive_basename = os.path.basename(output_drive)
        drive_desc = drive_basename+'-Drive'
        if dry_run:
            print(f"would export (Drive): {output_drive}")
            exit()
        else:
            exportTableToDrive(samples,drive_desc,drive_folder,drive_basename,selectors)
    
    # export both to GEE Asset and Google Drive
    elif output_asset!=None and output_drive!=None: 
        asset_desc = os.path.basename(output_asset)+'-Asset'
        drive_folder = os.path.dirname(output_drive)
        drive_basename = os.path.basename(output_drive)
        drive_desc = drive_basename+'-Drive'
        if dry_run:
            print(f"would export (Asset): {output_asset}")
            print(f"would export (Drive): {output_drive}")
            exit()
        else:
            exportTableToAsset(samples,asset_desc,output_asset)
            exportTableToDrive(samples,drive_desc,drive_folder,drive_basename,selectors)
    # neither output paths specified
    else:
        raise RuntimeError(f"No output paths provided, user must provide at least one of the following two arguments:\n -oa/--output_asset  -od/--output_drive")        
if __name__ == "__main__":
    main()
