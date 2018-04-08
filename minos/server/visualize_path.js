#!/usr/bin/env node

var async = require('async');
var fs = require('fs');
var shell = require('shelljs');
var STK = require('sstk/ssc/stk-ssc');
var cmd = require('sstk/ssc/ssc-parseargs');
var THREE = global.THREE;
var _ = STK.util;

STK.Constants.setVirtualUnit(1);  // set to meters

cmd
  .version('0.0.1')
  .description('Visualize simulator episodes')
  .option('--input <file>', 'File with presampled episodes')
  .option('--ids <ids>', 'Set of scene ids to filter on', STK.util.cmd.parseList)
  .option('--episodes <ids>', 'Set of episode indices to filter on', STK.util.cmd.parseList)
  .option('--episodes_per_scene <n>', 'Limit to number of episodes per scene', STK.util.cmd.parseInt, 0)
  .option('--output_dir <dir>', 'Base directory for output files', '.')
  .option('--use_subdir [flag]','Put output into subdirectory per id [true]', STK.util.cmd.parseBoolean, true)
  .option('--allow_diag [flag]','Allow diagonal movement [true]', STK.util.cmd.parseBoolean, true)
  .option('--show_map_cost [flag]','Show map costs [false]', STK.util.cmd.parseBoolean, false)
  .option('--skip_existing', 'Skip rendering existing images [false]')
  .option('--source <source>', 'Scene or model source [default: p5dScene]', 'p5dScene')
  .optionGroups(['scene', 'render_options', 'render_views', 'color_by', 'asset_cache', 'config_file'])
  .parse(process.argv);

// Parse arguments and initialize globals
var renderer = new STK.PNGRenderer({
  width: cmd.width, height: cmd.height,
  useAmbientOcclusion: cmd.encode_index? false : cmd.use_ambient_occlusion,
  compress: cmd.compress_png, skip_existing: cmd.skip_existing,
  reuseBuffers: true
});
var assetManager = new STK.assets.AssetManager({
  autoAlignModels: false, autoScaleModels: false, assetCacheSize: cmd.assetCacheSize });
if (!cmd.input) {
  console.log('Please specify --input <file>');
  return;
}

STK.assets.AssetGroups.registerDefaults();
var assets = require('sstk/ssc/data/assets.json');
var assetsMap = _.keyBy(assets, 'name');
STK.assets.registerCustomAssetGroupsSync(assetsMap, [cmd.source]);
if (cmd.format) {
  STK.assets.AssetGroups.setDefaultFormat(cmd.format);
}

var assetGroup = assetManager.getAssetGroup(cmd.source);
if (!assetGroup) {
  console.log('Unrecognized asset source ' + cmd.source);
  return;
}

var extras = ['wall', 'navmap'];
var sceneDefaults = { includeCeiling: false, defaultMaterialType: THREE.MeshPhongMaterial, preload: extras };
if (cmd.scene) {
  sceneDefaults = _.merge(sceneDefaults, cmd.scene);
}
sceneDefaults.emptyRoom = cmd.empty_room;
sceneDefaults.archOnly = cmd.arch_only;

var cameraConfig = _.defaults(Object.create(null), cmd.camera || {}, {
  type: 'perspective',
  fov: 50,
  near: 0.1*STK.Constants.metersToVirtualUnit,
  far: 400*STK.Constants.metersToVirtualUnit
});
var defaultViewIndex = 4; // Top down view
var agent = new STK.sim.FirstPersonAgent();
function visualizeEpisodes(episodesByScene) {
  var index = 0;
  var total = _.size(episodesByScene);
  async.forEachOfSeries(episodesByScene, function (episodes, sceneId, callback) {
    var fullId = cmd.source + '.' + sceneId;
    index++;
    STK.util.clearCache();
    STK.util.checkMemory('Processing ' + fullId + ' scene ' + index + '/' + total);
    // Create THREE scene
    var scene = new THREE.Scene();
    var light = STK.gfx.Lights.getDefaultHemisphereLight(true, false);
    var camera = STK.gfx.Camera.fromJson(cameraConfig, cmd.width, cmd.height);
    scene.add(light);
    scene.add(camera);
    var cameraControls = new STK.controls.CameraControls({
      camera: camera,
      container: renderer.canvas,
      controlType: 'none',
      cameraPositionStrategy: 'positionByCentroid' //'positionByCentroid'
    });

    var idParts = fullId.split('.');
    var id = idParts[idParts.length-1];
    var outputDir = cmd.output_dir;
    if (cmd.use_subdir) {
      outputDir = outputDir + '/' + id;
      if (cmd.skip_existing && shell.test('-d', outputDir)) {
        console.warn('Skipping existing output at: ' + outputDir);
        setTimeout(function () {
          callback();
        });
        return;
      }
    }
    var basename = outputDir + '/' + id;
    shell.mkdir('-p', outputDir);

    var info = _.defaultsDeep({ fullId: fullId }, sceneDefaults);
    assetManager.loadAsset(info, function (err, asset) {
      var sceneState;
      if (asset instanceof STK.scene.SceneState) {
        sceneState = asset;
      } else if (asset instanceof STK.model.ModelInstance) {
        sceneState = new STK.scene.SceneState();
        var modelInstance = asset;
        console.time('toGeometry');
        // Ensure is normal geometry (for some reason, BufferGeometry not working with ssc)
        STK.geo.Object3DUtil.traverseMeshes(modelInstance.object3D, false, function(m) {
          m.geometry = STK.geo.GeometryUtil.toGeometry(m.geometry);
        });
        console.timeEnd('toGeometry');
        sceneState.addObject(modelInstance);
        sceneState.info = modelInstance.model.info;
      } else {
        console.error("Unsupported asset type " + fullId, asset);
        return;
      }
      sceneState.compactify();  // Make sure that there are no missing models

      scene.add(sceneState.fullScene);
      var sceneBBox = STK.geo.Object3DUtil.getBoundingBox(sceneState.fullScene);
      var bbdims = sceneBBox.dimensions();
      console.log('Loaded ' + sceneState.getFullID() +
        ' bbdims: [' + bbdims.x + ',' + bbdims.y + ',' + bbdims.z + ']');

      var outbasename = cmd.color_by? (basename + '.' + cmd.color_by) : basename;
      if (cmd.encode_index) {
        outbasename = outbasename + '.encoded';
      }
      var navscene = null;
      for (var i = 0; i < extras.length; i++) {
        var extra = extras[i];
        var extraInfo = sceneState.info[extra];
        if (extraInfo) {
          if (extraInfo.assetType === 'wall') {
            if (extraInfo.data) {
              var walls = extraInfo.data;
              STK.scene.SceneUtil.visualizeWallLines(sceneState, walls);
            } else {
              console.warn('No wall for scene ' + fullId);
            }
          } else if (extraInfo.assetType === 'navmap') {
            var collisionProcessor = STK.sim.CollisionProcessorFactory.createCollisionProcessor();
            if (extraInfo.data) {
              navscene = new STK.nav.NavScene({
                sceneState: sceneState,
                allowDiagonalMoves: cmd.allow_diag,
                tileOverlap: 0.25,
                baseTileHeight: collisionProcessor.traversableFloorHeight * STK.Constants.metersToVirtualUnit,
                isValid: function (position) {
                  return collisionProcessor.isPositionInsideScene(sceneState, position);
                }
              });
            } else {
              console.warn('No navmap for scene ' + fullId);
            }
          } else {
            console.warn('Unsupported extra ' + extra);
          }
        } else {
          console.warn('No info for extra ' + extra);
        }
      }

      var wrappedCallback = function() {
        STK.geo.Object3DUtil.dispose(scene);
        callback();
      };

      function render(outbasename, cb) {
        var renderOpts = {
          cameraControls: cameraControls,
          targetBBox: sceneBBox,
          basename: outbasename,
          angleStep: cmd.turntable_step,
          framerate: cmd.framerate,
          tilt: cmd.tilt,
          skipVideo: cmd.skip_video,
          callback: cb
        };

        STK.util.checkMemory('Rendering ' + outbasename);
        if (cmd.render_all_views) {
          renderer.renderAllViews(scene, renderOpts);
        } else if (cmd.render_turntable) {
          // farther near for scenes to avoid z-fighting
          //camera.near = 400;
          renderer.renderTurntable(scene, renderOpts);
        } else {  // top down view is default
          var views = cameraControls.generateViews(sceneBBox, cmd.width, cmd.height);
          cameraControls.viewTarget(views[defaultViewIndex]);  // top down view
          //cameraControls.viewTarget({ targetBBox: sceneBBox, viewIndex: 4, distanceScale: 1.1 });
          renderer.renderToPng(scene, camera, outbasename);
          setTimeout( function() { cb(); }, 0);
        }
      }

      function onDrained() {
        var count = 0;
        var nepisodes = cmd.episodes_per_scene > 0? Math.max(cmd.episodes_per_scene, episodes.length) : episodes.length;
        async.whilst(function() {
          return count < nepisodes;
        }, function(cb) {
          var episode = episodes[count];
          console.log('episode', episode.episodeId, episode.start, episode.goal);
          var name = outbasename + '.' + count + '.' + episode.episodeId;
          agent.moveTo(episode.start);
          navscene.reset(agent, episode.start, [episode.goal]);
          // Add visualization of episodes with shortest path
          navscene.visualizePathCost({ showPathOnly: !cmd.show_map_cost });
          count++;
          render(name, cb);
        }, function(err, n) {
          wrappedCallback();
        });
      }

      function waitImages() {
        STK.util.waitImagesLoaded(onDrained);
      }

      if (cmd.color_by) {
        STK.scene.SceneUtil.colorScene(sceneState, cmd.color_by, {
          color: cmd.color,
          loadIndex: { index: cmd.index, objectIndex: cmd.object_index },
          encodeIndex: cmd.encode_index,
          writeIndex: cmd.write_index? basename : null,
          fs: STK.fs,
          callback: function() { waitImages(); }
        });
      } else {
        waitImages();
      }
    });
  }, function (err, results) {
    console.log('DONE');
  });
}

var s = STK.Constants.metersToVirtualUnit;
var episodes = STK.fs.loadDelimited(cmd.input).data;
STK.util.each(episodes, function(episode,index) {
  episode.episodeId = index;
});
if (cmd.episodes) {
  var episodeIds = STK.util.map(cmd.episodes, function(x) { return parseInt(x); });
  episodes = STK.util.filter(episodes, function(episode) {
    return episodeIds.indexOf(episode.episodeId) >= 0;
  });
}  
if (cmd.ids) {
  episodes = STK.util.filter(episodes, function(episode) {
    return cmd.ids.indexOf(episode.sceneId) >= 0;
  });
}
STK.util.forEach(episodes, function(episode) {
  episode.start = { position: new THREE.Vector3(episode.startX*s, episode.startY*s, episode.startZ*s), angle: episode.startAngle };
  episode.goal = { position: new THREE.Vector3(episode.goalX*s, episode.goalY*s, episode.goalZ*s), objectId: episode.goalObjectId };
});
episodesByScenes = STK.util.groupBy(episodes, function (r) {
  return r.sceneId;
});
console.log('Visualize ' + episodes.length + ' episodes for ' + STK.util.size(episodesByScenes) + ' scene');
visualizeEpisodes(episodesByScenes);

