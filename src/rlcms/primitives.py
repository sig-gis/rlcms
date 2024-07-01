import ee
import os
import pandas as pd
from rlcms.utils import export_img_to_asset, export_image_to_drive
from ee.ee_exception import EEException
import subprocess

class Primitives:
    def __init__(self,
                 inputs=None,
                 training=None,
                 class_name=None,
                 asset_id=None):
        """
        Construct a Primitives ensemble, provided an input ee.Image stack containing feature bands and a training point FeatureCollection
        
        Args:
            inputs (str|ee.Image): input image stack
            training (str|ee.FeatureCollection): training data
            class_name (str): class property containing class labels (i.e. 1, 2, 3), currently only 'LANDCOVER' is supported
            asset_id (str): Optional, GEE asset path to pre-existing Primitives ee.ImageCollection. Useful for exporting intermediary output approach
        
        Returns: 
            Primitives object
        """
        
        # TODO: perform some checks and error handling for training point label formatting 
        def pre_format_pts(pts,class_name):
            # two things: 
            # 1. need to ensure that 'LANDCOVER' is the class_name, if not, set new property in each feature using that
            if class_name != 'LANDCOVER':
                # set user's class_name to 'LANDCOVER' so we don't need to pass custom class_name around to every function
                pts = pts.map(lambda p: p.set('LANDCOVER',p.get(class_name)))
            else:
                # check 'LANDCOVER' is a property in collection
                assert 'LANDCOVER' in pts.first().propertyNames().getInfo(), "'LANDCOVER' is not a property in the collection"
            # 2. ensure that value of 'LANDCOVER' is integer before converting to string
            def to_int(p):
                val = p.get('LANDCOVER')
                # is 'LANDCOVER' always going to be string? can we convert it to string without first knowing if its String or Number?
                int_val = ee.Number(val).round()
                return p.set('LANDCOVER',int_val)
            return pts.map(to_int)
        
        def format_pts(pts):
            """Turn a FC of training points containing full LC typology into a list of primitive point FCs, 
                    one point FC for each LC primitive"""
            # create sets of binary training pts for each class represented in the full training pts collection
            labels = ee.FeatureCollection(pts).aggregate_array('LANDCOVER').distinct().sort()
            def binaryPts(l):
                # create prim and non prim sets with filters, reset prim to 1, non-prim to 0
                prim = pts.filter(ee.Filter.eq('LANDCOVER',l)).map(lambda f: f.set('PRIM',1))
                non_prim = pts.filter(ee.Filter.neq('LANDCOVER',l)).map(lambda f: f.set('PRIM',0))
                return ee.FeatureCollection(prim).merge(non_prim)
            list_of_prim_pts = ee.List(labels).map(binaryPts)
            return list_of_prim_pts

        def gettop20(dict):
            # if total input features count < 20, take them all, otherwise take top 20 most important
            dict = ee.Dictionary(dict)
            values = dict.values().sort()
            cutoff = ee.Algorithms.If(values.size().gte(20),-20,values.size().multiply(-1))
            def kv_return(key,passedObj):
                passedObj = ee.List(passedObj)
                val = ee.Number(dict.get(key))
                retObj = ee.Algorithms.If(val.gte(cutoff),passedObj.add(key),passedObj)
                return retObj
            newl = dict.keys().iterate(kv_return,ee.List([]))
            return newl
        
        def RFprim(training_pts,input_stack):
            """Train and apply RF Probability classifier on a Primitive"""
            inputs = ee.Image(input_stack)
            samples = ee.FeatureCollection(training_pts)
            
            class_value = ee.Number(ee.Feature(samples.sort('PRIM',False).first()).get('LANDCOVER')) #get LC numeric value for the given primitive (i.e. 'PRIM':1, 'LANDCOVER':6) then map to its class label (i.e. 6: 'Water')
            
            # can experiment with classifier params for model performance
            classifier = ee.Classifier.smileRandomForest(
            numberOfTrees=100, 
            minLeafPopulation=1, 
            bagFraction=0.7, 
            seed=51515).setOutputMode('PROBABILITY')
            
            # train model with all features
            model = classifier.train(features=samples, 
                                    classProperty='PRIM', 
                                    inputProperties=inputs.bandNames() 
                                    )
            
            # store for model performance exploration
            oob_all = ee.Dictionary(model.explain()).get('outOfBagErrorEstimate')
            importance_all = ee.Dictionary(model.explain()).get('importance')
            
            # retrieve top 20 most important features
            top20 = gettop20(importance_all)
            
            # re-train model with top20 important features
            model = classifier.train(features=samples, 
                                    classProperty='PRIM', 
                                    inputProperties=top20
                                    )
            
            oob_top20 = ee.Dictionary(model.explain()).get('outOfBagErrorEstimate')
            importance_top20 = ee.Dictionary(model.explain()).get('importance')
            schema = ee.List(ee.Classifier(model).schema())
            output = (ee.Image(inputs)
                      .classify(model,'Probability')
                      # lists and dictionaries do not propagate thru as properties on Batch exported Images
                      .set('Primitive',class_value,
                           'importance',importance_top20, 
                           'schema',schema, 
                           'model',model,
                           'oobError',oob_top20, 
                           ))
            return output

        def primitives_to_collection(input_stack,
                                     training_pts,
                                     class_name):
            """
            Create LC Primitive image for each LC class in training points

            args:
                input_stack (ee.Image): of all covariates and predictor
                training_pts (ee.FeatureCollection): training pts containing full LC typology
                class_name (str): property name in training points containing model classes
            
            returns:
                ee.ImageCollection of Primitive ee.Images
            """

            input_stack = ee.Image(input_stack)
            training_pts = ee.FeatureCollection(training_pts)
            
            # list of distinct LANDCOVER values
            labels = training_pts.aggregate_array(class_name).distinct().sort().getInfo() # .sort() should fix Prims exporting out of order (i.e. 2,3,4,7,6)

            # converting to index of the list of distinct LANDCOVER primtive FC's (prim_pts below)
            indices = list(range(len(labels))) # handles dynamic land cover strata

            prim_list = []
            for i in indices: # running one LC class at a time
                prim_pts = ee.FeatureCollection(ee.List(format_pts(training_pts)).get(i)) # format training pts to 1/0 prim format
                img = RFprim(prim_pts,input_stack) # run RF primitive model, get output image and metrics
                prim_list.append(img)
            
            return ee.ImageCollection.fromImages(prim_list)
        
        # you can construct Primitives object from a pre-existing Primitives ImgColl
        if asset_id != None:
            try:
                primitives = ee.ImageCollection(asset_id)
                self.collection = primitives
                self.region = primitives.first().geometry().getInfo()
                self.training_data = None
            except: 
                raise(EEException)
        else:
            primitives = primitives_to_collection(inputs,training,class_name)
            self.collection = primitives
            self.region = ee.Image(inputs).geometry().getInfo()
            self.training_data = ee.FeatureCollection(training)
    
    def assemble_max_probability(self, remap_to:list=None):
        """
        Perform pixel-wise max probability assemblage method. At each pixel, the primitive with highest probability is returned in the assemblage image.
        If your desired land cover typology does not start with 1 and/or skips values, you must specify a remap_to list that matches the desired output land cover typology.
        e.g. remap_to=[1,2,3,6,11,12,13]            
        
        Args:
            remap_to: list, default=None, list of integers matching the desired output land cover typology

        Returns: ee.Image                            
        """
        def max_prob(image):
            
            maxProbClassification = (image.toArray()
                                    .arrayArgmax()
                                    .arrayFlatten([['classification']])
                                    .rename('classification')
                                    )
            return maxProbClassification
        
        image  = self.collection.toBands()
        max_probability = max_prob(image)
        output = max_probability.add(1) # shift values from 0-n to 1-n, where n = bands
        
        if remap_to != None:
            prims_count = self.collection.size().getInfo()
            remap_from = list(range(1,prims_count+1)) # values without a remap are 1 to n
            if len(remap_from) != len(remap_to):
                raise ValueError("remap_to must be the same length as the number of primitives in the collection", 
                                 f"remap_from: {len(remap_from)}, remap_to: {len(remap_to)}") 
            output = output.remap(remap_from, remap_to)
        else:
            pass
        return output.rename('LANDCOVER')
        
    def export_metrics(self,metrics_path):
            """
            Parse variable importance and OOB Error estimate from trained model, output to local files respectively
            Currently only works for Primitives objects in memory (not loaded from pre-existing ImgColl)
            """
            # Var Importance to csv file
            imgColl = self.collection
            to_list = ee.List(imgColl.toList(imgColl.size()))
            for i in list(range(imgColl.size().getInfo())):
                img = ee.Image(to_list.get(i))
                prim_value = str(img.get('Primitive').getInfo())
                
                # Variable Importance to .csv
                dct = ee.Dictionary(img.get('importance')).getInfo()
                _list = dct.values()
                idx = dct.keys()
                df = pd.DataFrame(_list, index = idx)
                df.to_csv(os.path.join(metrics_path,f"varImportancePrimitive{prim_value}.csv"))
                
                # OOB error to .txt file
                oob = img.get('oobError')
                with open(os.path.join(metrics_path,f'oobErrorPrimitive{prim_value}.txt'),mode='w') as f:
                    f.write(ee.String(ee.Number(oob).format()).getInfo())
                    f.close()
    
    def export_to_asset(self,
                        collection_assetId=None,
                        scale=None,
                        crs=None,
                        crsTransform=None,
                        maxPixels=None,
                        **kwargs):
        """
        Export Primitives to Asset as an ImageCollection
        
        Args:
            collection_assetId (str): output ImageCollection asset path 
            scale (int): export scale
            crs (str): export CRS ('EPSG:4326')
            crsTransform (list): export CRS Transform
            maxPixels (int): max Pixels
        
        Returns: 
            None, Submits all Export Image tasks for Primitive collection
        """
        
        # make the empty IC
        command = f'earthengine create collection {collection_assetId}'
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        exit_code = process.returncode
        if exit_code == 0:
            print(f"Created empty Primitives ImageCollection: {collection_assetId}")

        else:
            raise RuntimeError(f"Process failed with exit code {exit_code}",
                            f"Error message: {stdout.decode()}")
        
        # os.popen(f"earthengine create collection {collection_assetId}").read()
        prims_count = self.collection.size().getInfo()
        prims_list = ee.ImageCollection(self.collection).toList(prims_count)
        aoi = ee.Image(prims_list.get(0)).geometry()
        for i in list(range(prims_count)):
            prim = ee.Image(prims_list.get(i))
            desc = f"Primitive{str(ee.Image(prim).get('Primitive').getInfo())}" # this would need to be defined in the Prims img for-loop
            asset_id = f'{collection_assetId}/{desc}'
            export_img_to_asset(image=prim,
                                description=desc,
                                assetId=asset_id,
                                region=aoi,
                                scale=scale,
                                crs=crs,
                                crsTransform=None,
                                maxPixels=1e13)
            
        return
    
    def export_to_drive(self,
                        description,
                        folder,
                        fileNamePrefix,
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
                        **kwargs,):
        """
        Export Primitives to Drive as a Multi-band GeoTiff
        
        See rlcms.utils.export_img_to_drive() docs for Args
        
        Returns: 
            None, Submits all Export Image tasks for Primitive collection
        """
        
        prim_img = self.collection.toBands()
        export_image_to_drive(image=prim_img,
                                description=description,
                                folder=folder,
                                fileNamePrefix=fileNamePrefix,
                                dimensions=dimensions,
                                region=region,
                                scale=scale,
                                crs=crs,
                                crsTransform=crsTransform,
                                maxPixels=maxPixels,
                                shardSize=shardSize,
                                fileDimensions=fileDimensions,
                                skipEmptyTiles=skipEmptyTiles,
                                fileFormat=fileFormat,
                                formatOptions=formatOptions,
                                **kwargs,)
        return

    
    