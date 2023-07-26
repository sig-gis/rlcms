import ee
import os
from src.utils.s2process import s2process, s2process_refdata
from src.utils.exports import exportImgToAsset
from src.utils.check_exists import check_exists
import argparse

def main():
    ee.Initialize()
    parser = argparse.ArgumentParser(
    description="Create Sentinel-2 Composite for an AOI or reference polygons",
    usage = "01composite_s2 -a aoi/fc/path -y 2021 -o output/path"
    )
    
    parser.add_argument(
    "-a",
    "--aoi",
    type=str,
    required=True,
    help="The asset path to an aoi or reference polygon dataset"
    )
    
    parser.add_argument(
    "-y",
    "--year",
    type=int,
    required=True,
    help="Year of data to composite"
    )

    parser.add_argument(
    "-o",
    "--output",
    type=str,
    required=True,
    help="The full asset path for export"
    )

    # I think we want user to have control on output CRS but might make everything more complicated? 
    parser.add_argument(
    "-c",
    "--crs",
    type=str,
    required=False,
    help="CRS string in format of EPSG:xxxxx. Defaults to EPSG:4326"
    )

    parser.add_argument(
    "-p",
    "--polygons",
    dest="polygons",
    action="store_true",
    help="set this flag if your aoi (--aoi) is a multi-polygon dataset, not a single polygon AOI",
    )
    
    parser.add_argument(
    "-d",
    "--dry_run",
    dest="dry_run",
    action="store_true",
    help="goes through checks and prints output asset path but does not export",
    )
    
    args = parser.parse_args()
    
    year = args.year
    aoi_path = args.aoi
    output = args.output
    crs = args.crs
    polygons = args.polygons
    dry_run = args.dry_run

    output_folder = os.path.dirname(output)
    
    # check inputs
    assert check_exists(aoi_path) == 0, f"Check aoi exists: {aoi_path}"
    assert check_exists(output_folder) == 0, f"Check output folder exists: {output_folder}"
    assert len(str(year)) == 4, "year should conform to YYYY format"
    
    aoi = ee.FeatureCollection(aoi_path)

    if check_exists(output):
        
        if dry_run:
            print(f"would export: {output}")
        else:
            if polygons:
                # use s2process_refdata() to only process satellite data inside polygons, exporting to polygons' minimum bbox
                region = aoi.geometry().bounds()
                img = s2process_refdata(aoi,'LANDCOVER',year)
                exportImgToAsset(img=img,desc=os.path.basename(output),asset_id=output,region=region,scale=10,crs=crs)
 
            else:
                # use s2process() to process all satellite data inside the aoi, exporting to a 1km buffer of the aoi
                region = aoi.geometry().buffer(1000)
                img = s2process(aoi,year,year)
                exportImgToAsset(img=img,desc=os.path.basename(output),asset_id=output,region=region,scale=10,crs=crs)
    else:
        print(f"Image already exsits: {output}")

if __name__ == "__main__":
    main()