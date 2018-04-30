#!/usr/bin/env node

var async = require('async');
var fs = require('fs');
var path = require('path');
var shell = require('shelljs');
var STK = require('sstk/ssc/stk-ssc');
var cmd = require('sstk/ssc/ssc-parseargs');
var THREE = global.THREE;

STK.Constants.setVirtualUnit(1);  // meters

cmd
  .version('0.0.1')
  .description('Check presampled start and goal are reachable')
  .option('--input <file>', 'CSV of sampled start and goal')
  .option('--output_dir <dir>', 'Base directory for output files', '.')
  .option('--save_grids', 'Save grids', STK.util.cmd.parseBoolean, false)
  .optionGroups(['scene', 'asset_cache', 'config_file'])
  .parse(process.argv);

// Parse arguments and initialize globals
// var renderer = new STK.PNGRenderer({
//   width: cmd.width, height: cmd.height,
//   useAmbientOcclusion: cmd.encode_index? false : cmd.use_ambient_occlusion,
//   compress: cmd.compress_png, skip_existing: cmd.skip_existing,
//   reuseBuffers: true
// });
var assetManager = new STK.assets.AssetManager({
  autoAlignModels: false, autoScaleModels: false, assetCacheSize: cmd.assetCacheSize });
if (!cmd.input) {
  console.log('Please specify --input <file>');
  return;
}

var assetSource = 'p5dScene';
STK.assets.AssetGroups.registerDefaults();
var assets = require('sstk/ssc/data/assets.json');
var assetsMap = _.keyBy(assets, 'name');
STK.assets.registerCustomAssetGroupsSync(assetsMap, [assetSource]);
if (cmd.format) {
  STK.assets.AssetGroups.setDefaultFormat(cmd.format);
}

var assetGroup = assetManager.getAssetGroup(assetSource);
if (!assetGroup) {
  console.log('Unrecognized asset source ' + assetSource);
  return;
}

var sceneDefaults = { includeCeiling: false, defaultMaterialType: THREE.MeshPhongMaterial };
if (cmd.scene) {
  sceneDefaults = _.merge(sceneDefaults, cmd.scene);
}
sceneDefaults.emptyRoom = cmd.empty_room;
sceneDefaults.archOnly = cmd.arch_only;

var simulator = new STK.sim.Simulator({
  navmap: {},
  bufferType: Buffer,
  fs: STK.fs
});

var archType =  STK.scene.SceneState.getArchType(sceneDefaults);
var outputDir = cmd.output_dir;
shell.mkdir('-p', outputDir);
var summaryfile = outputDir + '/' + path.basename(cmd.input).replace('.csv', '.' + archType + '.csv');

function validateShortestPath(state, cb) {
  var path = simulator.getState().getShortestPath();
  path.doors = path.doors || [];
  var rec = [state.index, path.isValid, path.distance || '', path.doors.length, path.doors.join(':')];
  console.log(rec.join(','));
  //cb();
  STK.fs.writeToFile(summaryfile, rec.join(',') + '\n', { append: true }, function() {
    cb();
  });
}

function checkState(state, cb) {
  // sceneId,room,startX,startY,startZ,startAngle,goalObjectId,goalX,goalY,goalZ
  // bd1cc2f61300546f5ec644ef62de1f07,0_2,-34.262,0.595,-37.103,2.253,0_10,-39.854,1.080,-42.030
  var oldSceneId = simulator.getState().getSceneId();
  var sceneId = assetSource + '.' + state.sceneId;
  simulator.configure({
    scene: _.defaults({ fullId: sceneId }, sceneDefaults),
    start: { position: [state.startX, state.startY, state.startZ], angle: state.startAngle },
    goal: { position: [state.goalX, state.goalY, state.goalZ], objectIds: state.goalObjectId }
  });

  var gridname = outputDir + '/' + state.sceneId + '.' + archType + '.grid.json';

  if (oldSceneId !== sceneId) {
    simulator.start(function () {
      STK.util.waitImagesLoaded(function () {
        var map = simulator.getState().getMap();
        if (cmd.save_grids) {
          STK.fs.writeToFile(gridname, JSON.stringify(map.graph.toJson()), function (err, res) {
            validateShortestPath(state, cb);
          });
        } else {
          setTimeout( function() { validateShortestPath(state, cb); }, 0);
        }
      });
    });
  } else {
    simulator.reset(function(err, sceneState) {
      setTimeout( function() { validateShortestPath(state, cb); }, 0);
    });
  }
}

function checkStates(states) {
  var total = _.size(states);
  async.forEachOfSeries(states, function (state, index, callback) {
    STK.util.checkMemory('Processing ' + state.sceneId + ' state ' + index + '/' + total);
    state.index = index;
    checkState(state, callback);
  }, function(err, result) {
    console.log('DONE');
  });
}

var episodeStates = STK.fs.loadDelimited(cmd.input).data;
var headers = ['index', 'validPath', 'distance', 'ndoors', 'doors'];
STK.fs.writeToFile(summaryfile, headers.join(',') + '\n', function() {
  checkStates(episodeStates);
});


