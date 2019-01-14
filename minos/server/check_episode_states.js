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
  .option('--dataset <dataset>', 'Scene or model dataset [default: p5dScene]', 'p5dScene')
  .option('--assets <filename>', 'Additional assets files')
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

var assetSource = cmd.dataset;
// Logic to register various assets below
// See sstk/ssc/data/assets.json for example of list of assets
var assetFiles = (cmd.assets != null)? [cmd.assets] : [];
STK.assets.registerAssetGroupsSync({
  assetSources: [cmd.dataset],
  assetFiles: assetFiles,
  skipDefault: false,
  includeAllAssetFilesSources: true
});
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
  // episodeId,task,sceneId,level,startX,startY,startZ,startAngle,startTilt,goalRoomId,goalRoomType,goalObjectId,goalObjectType,goalX,goalY,goalZ,goalAngle,goalTilt,dist,pathDist,pathNumDoors,pathDoorIds,pathNumRooms,pathRoomIndices
  // 0,o,6b44bbcb43326250350f27cd91c6f784,0,-37.753,0.595,-40.221,2.253,0,0_2,Toilet,0_5,door,-44.750,1.080,-39.375,0,0,7.065,8.094,0,,3,4:5:1
  var oldSceneId = simulator.getState().getSceneId();
  var sceneId = assetSource + '.' + state.sceneId;
  var task_id = state.task;
  var task_id_to_task = { p: 'point_goal', o: 'object_goal', r: 'room_goal' };
  if (task_id) {
    var task = task_id_to_task[task_id];
  } else {
    var task = 'point_goal';
  }
  var task_to_goaltype = { 'point_goal': 'position', 'object_goal': 'object', 'room_goal': 'room' };
  simulator.configure({
    task: task,
    scene: _.defaults({ fullId: sceneId, level: state.level }, sceneDefaults),
    start: { position: [state.startX, state.startY, state.startZ], angle: state.startAngle, tilt: state.startTilt },
    goal: { type: task_to_goaltype[task], position: [state.goalX, state.goalY, state.goalZ], angle: state.goalAngle,
            tilt: state.goalTilt, objectIds: state.goalObjectId, roomId: state.goalRoomId, roomType: state.goalRoomType }
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


