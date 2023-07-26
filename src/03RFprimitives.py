import ee
import os
from pathlib import Path
import argparse
from src.utils.check_exists import check_exists
from src.utils.primitives import primitives_to_collection

def main():
    ee.Initialize()

    parser = argparse.ArgumentParser(
    description="Create Land Cover Primitives For All Classes in Provided Training Data",
    usage = "03RFprimitives -i path/to/input_stack -t path/to/training_data -o path/to/output"
    )
    
    parser.add_argument(
        "-i",
        "--input_stack",
        type=str,
        required=True,
        help="full asset path to input stack"
    )
    
    parser.add_argument(
    "-t",
    "--training_data",
    type=str, 
    nargs='+',
    required=True,
    help="full asset path(s) to training point dataset(s)"
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
        help="The output asset path of the primitives image collection."
    )

    parser.add_argument(
        "-d",
        "--dry_run",
        dest="dry_run",
        action="store_true",
        help="goes through checks and prints paths to outputs but does not export them.",
        )

    args = parser.parse_args()

    input_stack_path = args.input_stack
    train_paths = args.training_data
    output = args.output
    crs = args.crs
    dry_run = args.dry_run

    # Run Checks
    # Check input stack exists
    assert check_exists(input_stack_path) == 0, f"Check input_stack asset exists: {input_stack_path}"
    
    # Check training data exists
    for train_path in train_paths:
        assert check_exists(train_path) == 0, f"Check training_data asset exists: {train_path}"
             
    img_coll_path = output
    output_folder = os.path.dirname(output)
    # check output folder exists
    assert check_exists(output_folder) == 0, f"Check parent folder exists: {output_folder}"
    
    # don't allow ee.Image exports to pre-existing ee.ImageCollections
    if check_exists(img_coll_path) == 0:
        raise AssertionError(f"Primitives ImageCollection already exists: {img_coll_path}")

    # Construct local 'metrics' folder path from -o output or a default name if not provided
    cwd = os.getcwd()
    metrics_path = os.path.join(cwd,"metrics",os.path.basename(img_coll_path))

    # print output locations and exit
    if dry_run: 
        print(f"Would Export Primitives ImageCollection to: {img_coll_path}\n")
        print(f"Would Export Model Metrics to: {metrics_path}\n")
        exit()
    
    else:
        # make local metrics folder
        if not os.path.exists(metrics_path):
            Path(metrics_path).mkdir(parents=True)
        print(f"Metrics will be exported to: {metrics_path}\n")
        
        input_stack = ee.Image(input_stack_path)
        
        if len(train_paths) > 1:
            print(f'Merging training datasets together: {train_paths}\n')
            # we must construct the ee.FeatureCollection's and merge them together
            training_data = ee.FeatureCollection(train_paths[0])
            for i in train_paths[1:]:
                training_data = training_data.merge(i)
        else:
            training_data = ee.FeatureCollection(train_paths[0])
        
        # run primitives models
        primitives_to_collection(input_stack=input_stack,
                                 training_pts=training_data,
                                 output_ic=img_coll_path,
                                 metrics_path=metrics_path,
                                 crs=crs)

if __name__=="__main__":
    main()