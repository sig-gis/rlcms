import argparse
import os
from rlcms.utils import check_exists, exportTableToAsset
from rlcms.sampling import strat_sample_w_extraction, strat_sample_from_reference, split_train_test
import ee
import numpy as np
ee.Initialize()

def main():
    parser = argparse.ArgumentParser(
    description="Extract Train and Test Point Data from an Input Image within Reference Data Locations",
    usage = """train_test -ref path/to/reference_fc -im path/to/input/stack -band LANDCOVER --scale 10
                -o unique/output/path --class_values 1 2 3 4 5 6 7 8 --class_points 10 10 10 10 10 10 10"""
    )
    
    parser.add_argument(
    "-ref",
    "--reference_data",
    type=str,
    required=True,
    help="The full GEE asset path to the reference data"
    )
    
    parser.add_argument(
    "-im",
    "--input_img",
    type=str,
    required=True,
    help="The full asset path to the input stack ee.Image"
    )

    parser.add_argument(
    "-band",
    "--class_band",
    type=str,
    required=True,
    help="class band name to use for stratification"
        )
    
    parser.add_argument(
    "-s",
    "--scale",
    type=int,
    required=True,
    help="scale to conduct sampling (meters)"
    )
    
    parser.add_argument(
    "-c",
    "--crs",
    type=str,
    required=False,
    help="CRS string in format of EPSG:xxxxx. Defaults to EPSG:4326"
    )
    
    parser.add_argument(
    "-o",
    "--output",
    type=str,
    required=True,
    help="The output asset path basename for export"
    )
    
    parser.add_argument(
    '--class_values', 
    type=int, 
    nargs='+',
    required=True,
    help="list of unique LANDCOVER values in input Feature Collection"
    )

    parser.add_argument(
    "--class_points",
    type=int,
    nargs='+',
    required=True,
    help="number of samples to collect per class"
    )
    
    parser.add_argument(
    "-ns",
    "--no_split",
    dest="no_split",
    action="store_true",
    help="don't split extracted points into train and test",
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
    help="goes through checks and prints output asset path but does not export",
    )
    
    args = parser.parse_args()
    
    input_fc = args.reference_data
    input_img = args.input_img
    class_band = args.class_band
    output = args.output
    scale = args.scale
    crs = args.crs
    class_values = args.class_values
    class_points = args.class_points
    dry_run = args.dry_run
    no_split = args.no_split
    reshuffle = args.reshuffle

    # perform checks
    output_folder = os.path.dirname(output)
    
    assert check_exists(input_fc) == 0, f"Check input FeatureCollection exists: {input_fc}"
    assert check_exists(output_folder) == 0, f"Check output folder exists: {output_folder}"
    assert check_exists(input_img) == 0, f"Check input image exists: {input_img}"

    # class_values and class_points must be equal length
    if len(class_values) != len(class_points):
        raise ValueError(f"Error: class_points and class_values are of unequal length: {class_values} {class_points}")
        
    # user may not want to sample all classes, but provide warning to catch user error
    class_values_actual = ee.FeatureCollection(input_fc).aggregate_array('LANDCOVER').distinct().sort().getInfo()
    if class_values_actual != class_values:
        print(f"Warning: All classes in the reference dataset will not be sampled with class_values provided by user (EE-Reported class_values:{class_values_actual}). Processing will continue.")

    if dry_run:
        if no_split:
            print(f"would export (Asset): {output}")
            exit()
        else:
            print(f"would export (Asset): {output}_[train|test]_pts")
            exit()
    else:
        # default seed is set, will re-randomize seed if reshuffle==True
        seed=90210
        if reshuffle:
            np.random.RandomState()
            seed = np.random.randint(low=1,high=1e6)
            print(f"reshuffled new seed: {seed}")
        
        image = ee.Image(input_img)
        fc = ee.FeatureCollection(input_fc)
        pts = strat_sample_from_reference(img=image,
                                         collection=fc,
                                         class_band=class_band, 
                                         scale=scale, 
                                         crs=crs, 
                                         seed=seed,
                                         class_values=class_values,
                                         class_points=class_points)
        
        if no_split==False: # split into train and test pts
            train,test = split_train_test(pts,seed)
            train_assetid = f"{output}_train_pts"
            train_description = os.path.basename(train_assetid).replace('/','_')
            exportTableToAsset(train,train_description,train_assetid)

            test_assetid = f"{output}_test_pts"
            test_description = os.path.basename(test_assetid).replace('/','_')
            exportTableToAsset(test,test_description,test_assetid)
        
        else: # export all pts as is
            assetid = f"{output}"
            description = os.path.basename(assetid).replace('/','_')
            exportTableToAsset(pts,description,assetid)
        
if __name__ == "__main__":
    main()



