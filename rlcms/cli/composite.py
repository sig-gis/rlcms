import ee
import os
import re
from rlcms.composites import composite
# from rlcms.s2process import s2process, s2process_refdata
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
    # nargs='+',
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
    
    # # I think we want user to have control on output CRS but might make everything more complicated? 
    parser.add_argument(
    "--crs",
    type=str,
    required=False,
    help="CRS string in format of EPSG:xxxxx. Defaults to EPSG:4326"
    )
    parser.add_argument(
    "--scale",
    type=int,
    required=False,
    help="Scale of output composite. Defaults to dataset's nominal scale"
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
    crs = args.crs
    scale = args.scale
    settings_f = args.settings
    crs = args.crs
    dry_run = args.dry_run
    
    output_folder = os.path.dirname(output)
   
    # parse txt file into settings dict that we'll pass to composite()
    with open(settings_f) as f:
        settings = json.load(f)
    
    # check inputs
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

    # catches overwrite output error before submitting task
    if check_exists(output):
        if dry_run:
            print(f"would export: {output}")
        else:
            
            img = composite(dataset=data,
                            region=aoi,
                            start_date=start,
                            end_date=end,
                            **settings)
            
            # does the img actually have any values?
            pts = img.reduceRegions(**{'collection':aoi,
                                    'reducer':ee.Reducer.mean(),
                               'scale':1e3})
            print(pts.aggregate_array('blue_mean').getInfo())
            # [559.2604616759781]
            # yes.. 
            
            # something wrong with exort
            # this works 
            # basically we need to handle scale and crs args otherwise their defaults are 
            # not what you want (scale especially, defaults to 1000)
            # so we need to either infer or pull out best guess scale or ask user to specify every time
            task = ee.batch.Export.image.toAsset(image=img,
                                          description=os.path.basename(output),
                                          assetId=output,
                                           region=aoi.geometry(),
                                        #   scale=30,
                                          maxPixels=1e12)
            task.start()
            print(f"Export started (Asset): {output}") 
            
            # wtf is wrong with this func why is it exporting empty images
            # exportImgToAsset(img=img,
            #                  desc=os.path.basename(output),
            #                  asset_id=output,
            ##                  region=aoi.geometry(),#aoi.geometry(),#.bounds(),
            #                  )
    else:
        print(f"Image already exsits: {output}")

if __name__ == "__main__":
    main()