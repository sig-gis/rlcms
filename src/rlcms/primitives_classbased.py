import ee
import os
import pandas as pd
from rlcms.utils import export_img_to_asset, export_image_to_drive

class Primitives:
    def __init__(self,inputs,training,class_name):

        def format_pts(pts):
            """Turn a FC of training points containing full LC typology into a list of primitive point FCs, 
                    one point FC for each LC primitive"""
            # create sets of binary training pts for each class represented in the full training pts collection
            labels = ee.FeatureCollection(pts).aggregate_array('LANDCOVER').distinct()
            def binaryPts(l):
                # create prim and non prim sets with filters, reset prim to 1, non-prim to 0
                prim = pts.filter(ee.Filter.eq('LANDCOVER',l)).map(lambda f: f.set('PRIM',1))
                non_prim = pts.filter(ee.Filter.neq('LANDCOVER',l)).map(lambda f: f.set('PRIM',0))
                return ee.FeatureCollection(prim).merge(non_prim)
            list_of_prim_pts = ee.List(labels).map(binaryPts)
            return list_of_prim_pts

        def gettop20(dict):
            dict = ee.Dictionary(dict)
            values = dict.values().sort()
            cutoff = values.get(-20)
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
            
            class_value = ee.String(ee.Number.format(ee.Feature(samples.sort('PRIM',False).first()).get('LANDCOVER'))) #get LC numeric value for the given primitive (i.e. 'PRIM':1, 'LANDCOVER':6) then map to its class label (i.e. 6: 'Water')
            
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
                                     class_name
                                    #  output_ic,
                                    #  metrics_path,
                                    #  crs
                                     ):
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
            labels = training_pts.aggregate_array(class_name).distinct().getInfo()
            
            # converting to index of the list of distinct LANDCOVER primtive FC's (prim_pts below)
            indices = list(range(len(labels))) # handles dynamic land cover strata
            
            prim_list = []
            for i in indices: # running one LC class at a time
                prim_pts = ee.FeatureCollection(ee.List(format_pts(training_pts)).get(i)) # format training pts to 1/0 prim format
                img = RFprim(prim_pts,input_stack) # run RF primitive model, get output image and metrics
                prim_list.append(img)
            
            return ee.ImageCollection.fromImages(prim_list)
        
        
        
        primitives = primitives_to_collection(inputs,training,class_name)

        self.collection = primitives
        self.region = ee.Image(inputs).geometry().getInfo()
        self.training_data = ee.FeatureCollection(training)

    def assemble_max_probability(self):
        """
        Take Image Collection of RF Primitives, perform pixel-wise maximum of all Primitive probability images to return single-band LC image
        Array computation returns img values from 0 to n-1 due to 0-base indexing, so we .add(1) to match LC strata
            
        Args:
            image: multiband image of probabilities
            remapNum: list, list of intergers 0-N matching the number of probability bands
            originalNum: list, list of inergers n-N matching the number of probability bands
                        that represent their desired map values

        Returns: ee.Image of Land Cover                            
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
        output = max_probability.add(1).rename('LANDCOVER')
        return output
        

            
    
    def metrics_to_df(self):
            """Parse variable importance and OOB Error estimate from trained model, output to local files respectively"""
            # Var Importance to csv file
            # retrieve imgColl
            imgColl = self.collection
            to_list = ee.List(imgColl.toList(imgColl.size()))
            def df_from_props(props:dict):
                keys = props.keys()
                values = props.values()
                df = pd.DataFrame(values,index=keys)
                return df
            df = pd.DataFrame()
            for i in list(range(imgColl.size().getInfo())):
                image = ee.Image(ee.List(to_list).get(i))
                properties = image.toDictionary().getInfo()
                df_next = df_from_props(properties)
                # TODO:
                # each df has exact same index so merging them will contain identical row names, we
                # want pxn dim where p is number of primitives along the rows and n is the properties as columns 
                # print(df.head())
                df = pd.concat([df,df_next])
                #break
            return df
            # dct = imp.getInfo()
            # list = dct.values()
            # idx = dct.keys()
            # df = pd.DataFrame(list, index = idx)
            # lc_class = str(ee.Image(img).get('Class').getInfo())
            # df.to_csv(f"{metrics_path}/varImportanceClass{lc_class}.csv")
            # # OOB error to txt file
            # with open(os.path.join(metrics_path,f'oobErrorClass{lc_class}.txt'),mode='w') as f:
            #     f.write(ee.String(ee.Number(oob).format()).getInfo())
            #     f.close()

    def metrics_to_df_clean(self):
            """Parse variable importance and OOB Error estimate from trained model, output to local files respectively"""
            def remap_keys(d):
                """
                solves a QA property problem for ee_treatments(): we have duplicate key names in the properties dict 
                when multiple ee_treatments() results are combined together.
                So we create a unique identifier from 'yearInterval' and remove 'yearInterval' as a property itself.
                example: 'PropertyName': PropertyValue becomes 'yearInterval1PropertyName': PropertyValue
                """
                d = ee.Dictionary(d)
                prim_key = (ee.String('Primitive')
                .cat(ee.String(ee.Dictionary(d).get('Primitive'))))
                keys = d.keys().slice(1) # depends on yearInterval property being in index position 7 of property list returned by ee_treatments()
                values = d.values().slice(1)
                remapped_keys = keys.map(lambda s: ee.String(prim_key).cat(s))
                return ee.Dictionary.fromLists(remapped_keys,values)
            
            # Var Importance to csv file
            # retrieve imgColl
            imgColl = self.collection
            to_list = ee.List(imgColl.toList(imgColl.size()))
            def df_from_props(props:ee.Dictionary):
                # this is the row idx
                _dict = remap_keys(props).getInfo()
                print(_dict)
                # prim_key = f"Primitive{props['Primitive']}"
                # print('prim_key',prim_key)
                # # these are the columns (removing Primitives)
                # columns = list(props.keys()).remove('Primitive')
                # print('columns',columns)
                # print(type(columns))
                # values = props.values()
                # df = pd.DataFrame(values,index=prim_key)
                return _dict
            df = pd.DataFrame()
            for i in list(range(imgColl.size().getInfo())):
                image = ee.Image(ee.List(to_list).get(i))
                properties = image.toDictionary()#.getInfo()
                df_next = df_from_props(properties)
                # each df has exact same index so merging them will result in something like 
                print(df_next)
                # print(df.head())
                df = pd.concat([df,df_next])
                break
            return df
    
           

    def combine_dicts(d):
        d = ee.Dictionary(d)
        return d.keys().zip(d.values())
        
    
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
        print(f"Creating empty Primitives ImageCollection: {collection_assetId}.\n")
        os.popen(f"earthengine create collection {collection_assetId}").read()
        prims_count = self.collection.size().getInfo()
        prims_list = ee.ImageCollection(self.collection).toList(prims_count)
        aoi = ee.Image(prims_list.get(0)).geometry()
        for i in list(range(prims_count)):
            prim = ee.Image(prims_list.get(i))
            desc = f"Primitive{ee.Image(prim).getString('Primitive').getInfo()}" # this would need to be defined in the Prims img for-loop
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

    
    