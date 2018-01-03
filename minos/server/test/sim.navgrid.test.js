'use strict';
var async = require('async');
var expect = require('chai').expect;
var STK = require('sstk/ssc');
var net = require('net');
var wav = require('node-wav');
var shell = require('shelljs');

var testOutputDir = __dirname + '/output/navgrid';

STK.Constants.setVirtualUnit(1);  // meters

STK.assets.AssetGroups.registerDefaults();
var assets = require('sstk/ssc/data/assets.json');
var assetsMap = _.keyBy(assets, 'name');
STK.assets.registerCustomAssetGroupsSync(assetsMap, ['p5dScene', 'mp3d']);

function createSimulator(params) {
  var renderer = new STK.PNGRenderer({
    width: params.width,
    height: params.height,
    useAmbientOcclusion: false,
    reuseBuffers: true
  });

  var simParams = _.defaultsDeep(
    Object.create(null),
    { renderer: renderer, rendererType: STK.PNGRenderer,
      bufferType: Buffer, net: net, wav: wav, fs: STK.fs },
    params,
    { start: 'random', goal: 'random' }
  );
  return new STK.sim.Simulator(simParams);
}

var sim = createSimulator(
  {
    navmap: { recompute: true },
    width: 84,
    height: 84
  }
);

var scenes = [
 { sceneId: 'p5dScene.0020d9dab70c6c8cfc0564c139c82dce', levels: [{ nrooms: 0, gridWidth: 26, gridHeight: 16 }] },
 { sceneId: 'p5dScene.61bb855d31b00fe58987d943cc021eec', levels: [{gridWidth: 31, gridHeight: 63}, {gridWidth: 37, gridHeight: 64}] },
 { sceneId: 'mp3d.17DRP5sb8fy', house: true, levels: [{gridWidth: 21, gridHeight: 41}] },
 { sceneId: 'mp3d.1LXtFkjw3qL', house: true, levels: [{gridWidth: 54, gridHeight: 24}, {gridWidth: 54, gridHeight: 29}, {gridWidth: 37, gridHeight: 15}] },
 { sceneId: 'mp3d.wc2JMjhGNzB', house: true, levels: [{gridWidth: 69, gridHeight: 85}, {gridWidth: 48, gridHeight: 31}, {gridWidth: 11, gridHeight: 11}] }
];

if (shell.test('-d', testOutputDir)) {
  shell.rm('-rf', testOutputDir);
}
shell.mkdir('-p', testOutputDir);

STK.util.disableImagesLoading();  // Don't need to load texture images
async.forEachSeries(scenes, function(expectedScene, cb) {
  var sceneId = expectedScene.sceneId;
  var scene = { fullId: sceneId };
  describe('navgrid ' + sceneId, function () {
    it('navgrid create/load/save ' + sceneId, function (done) {
      console.time('Timing start');
      sim.configure({ scene: scene, navmap: { cellSize: 0.4, useCellFloorHeight: true }, agent: { radius: 0.2 } });
      sim.start(function (err, sceneState) {
        if (sceneState) {
          if (expectedScene.house) {
            expect(sceneState.house, 'missing house').to.exist;
            expect(sceneState.house.object3D, 'missing house geometry').to.exist;
          }
          if (expectedScene.levels) {
            expect(sceneState.getLevels().length, 'number of levels').to.be.eql(expectedScene.levels.length);
          }

          console.log('started... waiting for all images to load');
          console.time('Timing waitImages');
          // wait for textures to load
          STK.util.waitImagesLoaded(function () {
            console.timeEnd('Timing start');
            console.timeEnd('Timing waitImages');
            var navscene = sim.getState().navscene;
            expect(navscene, 'navscene for ' + sceneId).to.exist;
            var json = navscene.grid.toJson();
            STK.fs.writeToFile(testOutputDir + '/' + sceneId + '.navgrid.json', JSON.stringify(json), function() {
              if (expectedScene.levels) {
                // Check each level
                for (var i = 0; i < expectedScene.levels.length; i++) {
                  var expectedLevel = expectedScene.levels[i];
                  var gridLevel = (expectedScene.levels.length > 1)? navscene.grid.getLevel(i) : navscene.grid;
                  expect(gridLevel.width, 'navscene grid width for ' + sceneId + ' level ' + i).to.eql(expectedLevel.gridWidth);
                  expect(gridLevel.height, 'navscene grid height for ' + sceneId + ' level ' + i).to.eql(expectedLevel.gridHeight);
                }
              }
              var loadedGrid = navscene.__parseGrid(json);
              // Clear subscribers
              //navscene.grid.Unsubscribe(STK.PubSub.ALL, navscene.grid);
              //loadedGrid.Unsubscribe(STK.PubSub.ALL, loadedGrid);
              //expect(loadedGrid, 'loaded grid for ' + sceneId).to.deep.equal(navscene.grid);
              STK.geo.Object3DUtil.dispose(sceneState.fullScene);

              done();
              cb();
            });
          });
        } else {
          expect.fail('Error loading scene');
          done();
          cb();
        }
      });
    }).timeout(600000); // wait up to 10 minutes
  });
}, function(err, results) {
});
