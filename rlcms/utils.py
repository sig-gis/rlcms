import ee
import json
ee.Initialize()

def parse_settings(settings):
    if isinstance(settings,str): # file path string
        # print('is a file on their computer')
        # print(settings)
        try:
            with open(settings,mode='r') as f:
                data = f.read()
            # reconstructing the data as a dictionary
            settings = json.loads(data)
        except:
            raise RuntimeError(f'Could not parse file path: {settings}')  
    else: 
        raise TypeError(f'expects a str, got: {type(settings)}')
    
    return settings

def check_exists(ee_path:str):
    try:
        ee.data.getAsset(ee_path)
        return 0 # does exist returns 0/False
    except ee.ee_exception.EEException:
        return 1 # doesn't exist returns 1/True

def exportImgToAsset(img,desc,asset_id,region,scale,crs:None):
    """Export Image to GEE Asset"""
    export_region = region
    task = ee.batch.Export.image.toAsset(
        image=ee.Image(img),
        description=desc,
        assetId=asset_id,
        region=export_region.getInfo()['coordinates'],
        scale=scale,
        crs=crs,
        maxPixels=1e13)
    task.start()
    print(f"Export started (Asset): {asset_id}") 
    return

def exportTableToAsset(collection:ee.FeatureCollection,description:str,asset_id:str):
    """Export FeatureCollection to GEE Asset"""
    if check_exists(asset_id) == 1:
        task = ee.batch.Export.table.toAsset(
            collection=collection,
            description=description,
            assetId=asset_id,
            )
        task.start()
        print(f'Export started (Asset): {asset_id}')
    else:
        print(f"{asset_id} already exists")
    
    return

def exportTableToDrive(collection:ee.FeatureCollection,description:str,folder:str,selectors:str):
    """export FeatureCollection to Google Drive"""
    task = ee.batch.Export.table.toDrive(
        collection=collection, 
        description=description, 
        folder=folder,
        fileNamePrefix=description,
        selectors=selectors)
    task.start()
    print(f'Export started (Drive): {folder}/{description}')
    return