'use strict';
var async = require('async');
var expect = require('chai').expect;
var STK = require('sstk/ssc');
var net = require('net');
var wav = require('node-wav');

STK.Constants.setVirtualUnit(1);  // meters

STK.assets.AssetGroups.registerDefaults();
var assets = require('sstk/ssc/data/assets.json');
var assetsMap = _.keyBy(assets, 'name');
STK.assets.registerCustomAssetGroupsSync(assetsMap, ['p5dScene']);

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
    width: 84,
    height: 84
  }
);

var sceneIds = [
  '97e5acad8fbfc68d07994af069bd3211',
  '981325e48f5b3a710aa6c51dc2a7df38',
  'bcace184b4d72e5f9287862274a7c4b1',
  'e523ccf95822ab8b2e619f5bedb846dd'
];
async.forEachSeries(sceneIds, function(sceneId, cb) {
  var scene = { fullId: 'p5dScene.' + sceneId };
  describe('position ' + sceneId, function () {
    it('random', function (done) {
      console.time('Timing start');
      sim.configure({ scene: scene });
      sim.start(function (err, sceneState) {
        if (sceneState) {
          console.log('started... waiting for all images to load');
          console.time('Timing waitImages');
          // wait for textures to load
          STK.util.waitImagesLoaded(function () {
            console.timeEnd('Timing start');
            console.timeEnd('Timing waitImages');
            var start = sim.getAgent().getAgentFeetAt(sim.getState().start.position);
            var goal = sim.getAgent().getAgentFeetAt(sim.getState().getGoals().position);
            expect(sim.getState().isPositionAgentCanStandAt(start)).to.be.true;
            expect(sim.getState().isPositionAgentCanStandAt(goal)).to.be.true;
            done();
            cb();
          });
        } else {
          expect.fail('Error loading scene');
          done();
          cb();
        }
      });
    }).timeout(10000); // wait up to 10 seconds
  });
}, function(err, results) {
});
