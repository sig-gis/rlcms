import os
import ee
import argparse
from rlcms.primitives import Primitives
from rlcms.utils import check_exists, export_img_to_asset
    
def main():
    ee.Initialize()
    
    parser = argparse.ArgumentParser(
    description="Generate Single Land Cover Image From Land Cover Primitives Image Collection",
    usage = "generate_LC -i path/to/input_primitive_collection -o output/path/to/landcover_image"
    )
    
    parser.add_argument(
    "-i",
    "--input",
    type=str,
    required=True,
    help="GEE asset path to input Primitives ImageCollection"
    )
    
    parser.add_argument(
    "-o",
    "--output",
    type=str,
    required=True,
    help="GEE asset path for export"
    )

    parser.add_argument(
    "-d",
    "--dry_run",
    dest="dry_run",
    action="store_true",
    help="goes through checks and prints output asset path but does not export.",
    )
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output
    dry_run = args.dry_run
    
    # If output Image exists already, throw error
    assert check_exists(output_path), f"Output image already exists: {output_path}"
    
    # If input ImageCollection does not exist, throw error
    assert check_exists(input_path) == 0, f"Input Primitives Collection does not exist: {input_path}"
    
    if dry_run:
            print(f"would export: {output_path}")
    else:
      prims = Primitives(asset_id=input_path)
      max = prims.assemble_max_probability()
      aoi = prims.collection.first().geometry().bounds()
      description = os.path.basename(output_path).replace('/','_')
      export_img_to_asset(image=max,
                          description=description,
                          assetId=output_path,
                          region=aoi)

if __name__ == "__main__":
   main()    