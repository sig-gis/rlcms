import os
import ee
import argparse
from src.utils.assemblage import maxProbClassifyFromImageCollection
from src.utils.check_exists import check_exists
from src.utils.exports import exportImgToAsset
    
def main():
    ee.Initialize()
    
    parser = argparse.ArgumentParser(
    description="Generate Single Land Cover Image From Land Cover Primitives Image Collection",
    usage = "04generate_LC -i path/to/input_primitive_collection -o output/path/to/landcover_image"
    )
    
    parser.add_argument(
    "-i",
    "--input",
    type=str,
    required=True,
    help="GEE asset path to input Primitives ImageCollection"
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
    crs = args.crs
    dry_run = args.dry_run
    
    # If output Image exists already, throw error
    assert check_exists(output_path), f"Output image already exists: {output_path}"
    
    # If input ImageCollection does not exist, throw error
    assert check_exists(input_path) == 0, f"Input Primitives Collection does not exist: {input_path}"
    
    if dry_run:
            print(f"would export: {output_path}")
    else:
      prims = ee.ImageCollection(input_path)
      max = maxProbClassifyFromImageCollection(prims)
      aoi = prims.first().geometry().bounds()
      description = os.path.basename(output_path).replace('/','_')
      exportImgToAsset(img=max,desc=description,asset_id=output_path,region=aoi,scale=10,crs=crs)

if __name__ == "__main__":
   main()    