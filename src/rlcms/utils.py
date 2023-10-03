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

def export_image_to_drive(
    image,
    description="myExportImageTask",
    folder=None,
    fileNamePrefix=None,
    dimensions=None,
    region=None,
    scale=None,
    crs=None,
    crsTransform=None,
    maxPixels=None,
    shardSize=None,
    fileDimensions=None,
    skipEmptyTiles=None,
    fileFormat=None,
    formatOptions=None,
    **kwargs,
):
    """Creates a batch task to export an Image as a raster to Google Drive.

    Args:
        image: The image to be exported.
        description: Human-readable name of the task.
        folder: The name of a unique folder in your Drive account to
            export into. Defaults to the root of the drive.
        fileNamePrefix: The Google Drive filename for the export.
            Defaults to the name of the task.
        dimensions: The dimensions of the exported image. Takes either a
            single positive integer as the maximum dimension or "WIDTHxHEIGHT"
            where WIDTH and HEIGHT are each positive integers.
        region: The lon,lat coordinates for a LinearRing or Polygon
            specifying the region to export. Can be specified as a nested
            lists of numbers or a serialized string. Defaults to the image's
            region.
        scale: The resolution in meters per pixel. Defaults to the
            native resolution of the image assset unless a crsTransform
            is specified.
        crs: The coordinate reference system of the exported image's
            projection. Defaults to the image's default projection.
        crsTransform: A comma-separated string of 6 numbers describing
            the affine transform of the coordinate reference system of the
            exported image's projection, in the order: xScale, xShearing,
            xTranslation, yShearing, yScale and yTranslation. Defaults to
            the image's native CRS transform.
        maxPixels: The maximum allowed number of pixels in the exported
            image. The task will fail if the exported region covers more
            pixels in the specified projection. Defaults to 100,000,000.
        shardSize: Size in pixels of the tiles in which this image will be
            computed. Defaults to 256.
        fileDimensions: The dimensions in pixels of each image file, if the
            image is too large to fit in a single file. May specify a
            single number to indicate a square shape, or a tuple of two
            dimensions to indicate (width,height). Note that the image will
            still be clipped to the overall image dimensions. Must be a
            multiple of shardSize.
        skipEmptyTiles: If true, skip writing empty (i.e. fully-masked)
            image tiles. Defaults to false.
        fileFormat: The string file format to which the image is exported.
            Currently only 'GeoTIFF' and 'TFRecord' are supported, defaults to
            'GeoTIFF'.
        formatOptions: A dictionary of string keys to format specific options.
        **kwargs: Holds other keyword arguments that may have been deprecated
            such as 'crs_transform', 'driveFolder', and 'driveFileNamePrefix'.
    """

    if not isinstance(image, ee.Image):
        raise ValueError("Input image must be an instance of ee.Image")

    task = ee.batch.Export.image.toDrive(
        image,
        description,
        folder,
        fileNamePrefix,
        dimensions,
        region,
        scale,
        crs,
        crsTransform,
        maxPixels,
        shardSize,
        fileDimensions,
        skipEmptyTiles,
        fileFormat,
        formatOptions,
        **kwargs,
    )
    task.start()
    print(f"Export Started (Drive): {fileNamePrefix}")

def export_img_to_asset(image,
    description="myExportImageTask",
    assetId=None,
    pyramidingPolicy=None,
    dimensions=None,
    region=None,
    scale=None,
    crs=None,
    crsTransform=None,
    maxPixels=None,
    **kwargs):
    """Creates a task to export an EE Image to an EE Asset.

    Args:
        image: The image to be exported.
        description: Human-readable name of the task.
        assetId: The destination asset ID.
        pyramidingPolicy: The pyramiding policy to apply to each band in the
            image, a dictionary keyed by band name. Values must be
            one of: "mean", "sample", "min", "max", or "mode".
            Defaults to "mean". A special key, ".default", may be used to
            change the default for all bands.
        dimensions: The dimensions of the exported image. Takes either a
            single positive integer as the maximum dimension or "WIDTHxHEIGHT"
            where WIDTH and HEIGHT are each positive integers.
        region: The lon,lat coordinates for a LinearRing or Polygon
            specifying the region to export. Can be specified as a nested
            lists of numbers or a serialized string. Defaults to the image's
            region.
        scale: The resolution in meters per pixel. Defaults to the
            native resolution of the image assset unless a crsTransform
            is specified.
        crs: The coordinate reference system of the exported image's
            projection. Defaults to the image's default projection.
        crsTransform: A comma-separated string of 6 numbers describing
            the affine transform of the coordinate reference system of the
            exported image's projection, in the order: xScale, xShearing,
            xTranslation, yShearing, yScale and yTranslation. Defaults to
            the image's native CRS transform.
        maxPixels: The maximum allowed number of pixels in the exported
            image. The task will fail if the exported region covers more
            pixels in the specified projection. Defaults to 100,000,000.
        **kwargs: Holds other keyword arguments that may have been deprecated
            such as 'crs_transform'.
    """

    if isinstance(image, ee.Image) or isinstance(image, ee.image.Image):
        pass
    else:
        raise ValueError("Input image must be an instance of ee.Image")

    if isinstance(assetId, str):
        if assetId.startswith("users/") or assetId.startswith("projects/"):
            pass
        else:
            assert check_exists(assetId) == 0, f"{assetId} not a valid asset path"
            # assetId = f"{ee_user_id()}/{assetId}"

    task = ee.batch.Export.image.toAsset(
        image,
        description,
        assetId,
        pyramidingPolicy,
        dimensions,
        region,
        scale,
        crs,
        crsTransform,
        maxPixels,
        **kwargs,
    )
    task.start()
    print(f"Export Started (Asset): {assetId}")

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

def exportTableToDrive(collection:ee.FeatureCollection,description:str,folder:str,file_name_prefix:str,selectors:str):
    """export FeatureCollection to Google Drive"""
    task = ee.batch.Export.table.toDrive(
        collection=collection, 
        description=description, 
        folder=folder,
        fileNamePrefix=file_name_prefix,
        selectors=selectors)
    task.start()
    print(f'Export started (Drive): {folder}/{file_name_prefix}')
    return