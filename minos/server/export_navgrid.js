#!/usr/bin/env node

var async = require('async');
var fs = require('fs');
var path = require('path');
var PNG = require('pngjs').PNG;
var shell = require('shelljs');
var STK = require('sstk/ssc/stk-ssc');
var cmd = require('sstk/ssc/ssc-parseargs');
var THREE = global.THREE;
var _ = STK.util;

STK.Constants.setVirtualUnit(1);  // meters
STK.Constants.defaultPalette = STK.Colors.palettes.d3_unknown_category18; // palette with gray as first color
STK.util.disableImagesLoading();  // Don't need to load texture images

cmd
  .version('0.0.1')
  .description('Export navigation grids')
  .option('--input <file>', 'Input file of scene ids')
  .option('--ids <ids>', 'List of scene ids', STK.util.cmd.parseList)
  .option('--output_dir <dir>', 'Base directory for output files', '.')
  .option('--dataset <dataset>', 'Default asset dataset', 'p5dScene')
  .option('--cell_size <m>', 'Cell size', STK.util.cmd.parseFloat)
  .option('--agent_radius <m>', 'Agent radius', STK.util.cmd.parseFloat)
  .option('--agent_height <m>', 'Agent height', STK.util.cmd.parseFloat)
  .option('--refine <gridType>', 'Refine navgrid starting from some precomputed grids')
  .option('--use_cell_floor_height [flag]', 'Whether to use the cell floor height for feet position', STK.util.cmd.parseBoolean, false)
  .option('--estimate_floor_height [flag]', 'Whether to use the estimate correct floor height for points not in rooms', STK.util.cmd.parseBoolean, false)
  .option('--sample_upward_surfaces [flag]', 'Whether to use sample upward surfaces when estimating floor height', STK.util.cmd.parseBoolean, false)
  .option('--adjust_room_index [flag]', 'Whether to use refine and adjust room index', STK.util.cmd.parseBoolean, false)
  .option('--update_weights [flag]', 'Whether to update weights', STK.util.cmd.parseBoolean, false)
  .optionGroups(['scene', 'asset_cache', 'config_file'])
  .parse(process.argv);

var assetManager = new STK.assets.AssetManager({
  autoAlignModels: false, autoScaleModels: false, assetCacheSize: cmd.assetCacheSize });
if (!cmd.input && !cmd.ids) {
  console.log('Please specify --input <file> or --ids <ids>');
  return;
}

var sceneDefaults = { includeCeiling: false, defaultMaterialType: THREE.MeshPhongMaterial };
if (cmd.scene) {
  sceneDefaults = _.merge(sceneDefaults, cmd.scene);
}
sceneDefaults.emptyRoom = cmd.empty_room;
sceneDefaults.archOnly = cmd.arch_only;

var simulator = new STK.sim.Simulator({
  agent: { height: cmd.agent_height, radius: cmd.agent_radius},
  navmap: {
    recompute: cmd.refine? false : true,
    mapName: cmd.refine,
    refineGrid: cmd.refine? {
      radius: cmd.agent_radius? cmd.agent_radius*STK.Constants.metersToVirtualUnit : null,
      adjustRoomIndex: cmd.adjust_room_index, estimateFloorHeight: cmd.estimate_floor_height,
      updateWeights: cmd.update_weights,
    } : null,
    cellSize: cmd.cell_size,
    estimateFloorHeight: cmd.estimate_floor_height? {
      numSamples: 2000000, maxDist: 0.2*STK.Constants.metersToVirtualUnit, kNeighbors: 4,
      sampleUpwardSurfaces: cmd.sample_upward_surfaces,
      verticalOffset: 0.05*STK.Constants.metersToVirtualUnit,
      maxVerticalDist: 0.4*STK.Constants.metersToVirtualUnit,
    } : null,
    useCellFloorHeight: cmd.use_cell_floor_height
  },
  bufferType: Buffer,
  fs: STK.fs
});

var archType =  STK.scene.SceneState.getArchType(sceneDefaults);

function loadAssetGroups(assetSources) {
  STK.assets.AssetGroups.registerDefaults();
  var assets = require('sstk/ssc/data/assets.json');
  var assetsMap = _.keyBy(assets, 'name');
  STK.assets.registerCustomAssetGroupsSync(assetsMap, assetSources);
  if (cmd.format) {
    STK.assets.AssetGroups.setDefaultFormat(cmd.format);
  }

  var unknownAssetSources = [];
  for (var i = 0; i < assetSources.length; i++) {
    var assetSource = assetSources[0];
    var assetGroup = assetManager.getAssetGroup(assetSource);
    if (!assetGroup) {
      unknownAssetSources.push(assetSource);
    }
  }
  return unknownAssetSources.length? unknownAssetSources : null;
}

function writePNG(pngFile, pixels, encodingFn) {
  var png = new PNG({ width: pixels.width, height: pixels.height });
  for (var i = 0; i < pixels.data.length; i++) {
    var d = pixels.data[i];
    var v = encodingFn(d);
    var j = i*4;
    png.data[j] = v[0];
    png.data[j+1] = v[1];
    png.data[j+2] = v[2];
    png.data[j+3] = v[3];
  }
  var buff = PNG.sync.write(png);
  fs.writeFileSync(pngFile, buff);
  console.log('Saved ' + pngFile);
}

function exportNavGrid(compositeSceneId, cb) {
  // sceneId,room,startX,startY,startZ,startAngle,goalObjectId,goalX,goalY,goalZ
  // bd1cc2f61300546f5ec644ef62de1f07,0_2,-34.262,0.595,-37.103,2.253,0_10,-39.854,1.080,-42.030
  var sceneId = compositeSceneId.id;
  var fullId = compositeSceneId.fullId;
  simulator.configure({
    scene: _.defaults({ fullId: fullId }, sceneDefaults),
    start: 'random',
    goal: 'random'
  });

  var outputDir = cmd.output_dir + '/' + sceneId;
  shell.mkdir('-p', outputDir);
  var gridname = outputDir + '/' + sceneId + '.' + archType + '.grid.json';

  simulator.start(function () {
    STK.util.waitImagesLoaded(function () {
      var map = simulator.getState().getMap();
      var cellAttributes = simulator.getState().navscene.cellAttributes;
      var pixelTypes = ['tileWeight'].concat(_.keys(cellAttributes));
      for (var j = 0; j < pixelTypes.length; j++) {
        var pixelType = pixelTypes[j];
        var pixels = map.graph.toPixels((pixelType === 'tileWeight')? null : pixelType);
        var encodingFn = simulator.getState().navscene.getEncodeDataFn(pixelType);
        if (pixels) {
          if (!Array.isArray(pixels)) {
            pixels = [pixels];
          }
          for (var i = 0; i < pixels.length; i++) {
            var basename = outputDir + '/' + sceneId + '_' + +i + '.';
            if (pixelType !== 'tileWeight') {
              basename += pixelType + '.';
            }
            writePNG(basename + archType + '.grid.png', pixels[i], encodingFn);
          }
        }
      }
      STK.fs.writeToFile(gridname, JSON.stringify(map.graph.toJson()), cb);
    });
  });
}

function exportNavGrids(sceneIds) {
  var total = _.size(sceneIds);
  async.forEachOfSeries(sceneIds, function (sceneId, index, callback) {
    STK.util.checkMemory('Processing ' + sceneId.fullId + ' state ' + index + '/' + total);
    exportNavGrid(sceneId, callback);
  }, function(err, result) {
    console.log('DONE');
  });
}

var sceneIds = cmd.ids;
if (!sceneIds) {
  sceneIds = cmd.input.endsWith('.txt') ? STK.fs.readLines(cmd.input) :
    STK.util.map(STK.fs.loadDelimited(cmd.input).data, function (s) {
      return s.id;
    });
}
var compositeSceneIds = STK.util.map(sceneIds, function(id) {
  return STK.assets.AssetManager.toSourceId(cmd.dataset, id);
});
var assetSources = STK.util.keys(STK.util.groupBy(compositeSceneIds, 'source'));
var unknownAssetGroups = loadAssetGroups(assetSources);
if (!unknownAssetGroups) {
  exportNavGrids(compositeSceneIds);
} else {
  console.log('Unrecognized asset sources ' + unknownAssetGroups.join(','));
  console.log('Please check your scene ids before proceeding!');
}
