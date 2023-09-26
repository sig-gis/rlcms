import ee
import os
import re
from rlcms.composites import composite
from rlcms.utils import exportImgToAsset, check_exists
import argparse
import json

def main():
    ee.Initialize()
    parser = argparse.ArgumentParser(
    description="Create a Composite from one or multiple datasets",
    usage = "composite -a aoi/fc/path -d Landsat8 -s 2020-01-01 -e 2020-12-31 -o output/path --settings path/to/settings/file.txt "
    )
    
    parser.add_argument(
    "-a",
    "--aoi",
    type=str,
    required=True,
    help="The asset path to an aoi or reference polygon dataset"
    )
    
    parser.add_argument(
    "-d",
    "--data",
    type=str, 
    nargs='+',
    required=True,
    help="Dataset(s) to composite"
    )
    
    parser.add_argument(
    "-s",
    "--start",
    type=str,
    required=True,
    help="start date (yyyy-mm-dd)"
    )

    parser.add_argument(
    "-e",
    "--end",
    type=str,
    required=True,
    help="end date (yyyy-mm-dd)"
    )

    parser.add_argument(
    "-o",
    "--output",
    type=str,
    required=True,
    help="The full asset path for export"
    )

    parser.add_argument(
    "--settings",
    type=str,
    required=True,
    help="settings .txt file"
    )
    
    parser.add_argument(
    "--scale",
    type=int,
    required=True,
    help="Scale of output composite."
    )
    
    parser.add_argument(
    "--crs",
    type=str,
    required=False,
    help="CRS string in format of EPSG:xxxxx. Defaults to EPSG:4326"
    )
    
    parser.add_argument(
    "--dry_run",
    dest="dry_run",
    action="store_true",
    help="goes through checks and prints output asset path but does not export",
    )
    
    args = parser.parse_args()
    
    aoi_path = args.aoi
    data = args.data
    start = args.start
    end = args.end
    output = args.output
    scale = args.scale
    crs = args.crs
    settings_f = args.settings
    dry_run = args.dry_run
    
    output_folder = os.path.dirname(output)
   
    # parse txt file into settings dict that we'll pass to composite()
    with open(settings_f) as f:
        settings = json.load(f)
    
    # check output doesn't already exist (GEE by default prohibits overwrites)
    assert check_exists(output), f"Image already exsits: {output}"
    # check inputs exist
    assert check_exists(aoi_path) == 0, f"Check aoi exists: {aoi_path}"
    assert check_exists(output_folder) == 0, f"Check output folder exists: {output_folder}"
    # ensure start and end dates will work
    for date in [start,end]:
        r = re.compile('.{4}-.{2}-.{2}')
        if len(date) == 10:
            if r.match(date):
                pass
            else:
                raise ValueError(f"date string(s) don't match required format. Got: {date}")
        else:
            raise ValueError(f"date string(s) don't match required format. Got: {date}")
    
    aoi = ee.FeatureCollection(aoi_path)
    
    # multiple datasets requested, combining multiple composites
    if len(data) > 1: 
        composite_list = ([composite(dataset=d,
                        region=aoi,
                        start_date=start,
                        end_date=end,
                        **settings)
                        # prefix dataset name to every band, if data is an asset path we swap / for _
                        .regexpRename('^', f"{d.replace('/','_')}_") 
                            for d in data])
        
        img = ee.Image.cat(composite_list)
    
    # only one dataset requested
    else:
        img = composite(dataset=data[0],
                        region=aoi,
                        start_date=start,
                        end_date=end,
                        **settings)
    
    if dry_run:
        print(f"would export: {output}")
    
    else:
        if crs == None:
            task = ee.batch.Export.image.toAsset(image=img.image,
                                        description=os.path.basename(output),
                                        assetId=output,
                                        region=aoi.geometry(),
                                        scale=scale,
                                        maxPixels=1e12)
        else:
            task = ee.batch.Export.image.toAsset(image=img.image,
                                        description=os.path.basename(output),
                                        assetId=output,
                                        region=aoi.geometry(),
                                        scale=scale,
                                        maxPixels=1e12,
                                        crs=crs)
        task.start()
        print(f"Export started (Asset): {output}") 

if __name__ == "__main__":
    main()