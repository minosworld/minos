#!/usr/bin/env node

var async = require('async');
var cmd = require('commander');
var SocketIO = require('socket.io');
var STK = require('sstk/ssc');
var rng = new STK.math.RNG({overrideMathRandom: true});
require('better-require')('json yaml');
rng.seed(0);

cmd
  .version('0.0.1')
  .option('-p, --port [port]', 'Port to send pixels [default: -1]', -1)
  .option('-w, --width [width]', 'Output image width [84]', STK.util.cmd.parseInt, 84)
  .option('-h, --height [height]', 'Output image height [84]', STK.util.cmd.parseInt, 84)
  .option('--source [source]', 'Scene data source [p5dScene]', 'p5dScene')
  .option('--id [id]', 'Scene id [default: 0020d9dab70c6c8cfc0564c139c82dce]', '0020d9dab70c6c8cfc0564c139c82dce')
  .option('--color_encoding [rgba|gray]', 'Type of frame output', 'gray')
  .option('--num_steps [num]', 'Number of steps to simulate', STK.util.cmd.parseInt, 1000)
  .option('--navmap', 'Use navmap')
  .option('--ping_timeout [num]', 'Number of seconds between ping/pong before client timeout', STK.util.cmd.parseInt, 300)
  .option('--busywait [num]', 'Number of seconds to busywait for a command (for debugging busy server)', STK.util.cmd.parseInt)
  .parse(process.argv);

var fullId = cmd.source + '.' + cmd.id;
console.log(fullId);

STK.assets.AssetGroups.registerDefaults();
var assets = require('sstk/ssc/data/assets.json');
var assetsMap = _.keyBy(assets, 'name');
STK.assets.registerCustomAssetGroupsSync(assetsMap, ['p5dScene']);

var defaultSensorConfig = require('../config/sensors.yml');

function createSimulator(params) {
  var renderer = new STK.PNGRenderer({
    width: params.width,
    height: params.height,
    useAmbientOcclusion: false,
    reuseBuffers: true
  });

  return new STK.sim.Simulator({
    scene: { fullId: 'p5dScene.' + params.id },
    renderer: renderer,
    observations: params.observations,
    sensors: defaultSensorConfig,
    color_encoding: params.color_encoding,
    seed: rng.random(),
    start: params.start || 'random',
    goal: params.goal || 'random',
    audio: params.audio,
    navmap: params.navmap,
    rendererType: STK.PNGRenderer,
    width: params.width,
    height: params.height,
    bufferType: Buffer,
    fs: STK.fs
  });
}

var sim = createSimulator(cmd);

function randomStep(cb) {
  var frameSkip = 1;
  var stepSize = 0.05 * STK.Constants.metersToVirtualUnit;
  var r = Math.random();
  if (r < 0.3) {  // turn
    var ang = (Math.random() - 0.5) * Math.PI / 10;
    sim.step({ name: 'turnRight', angle: ang }, frameSkip, function (err, result) {
      cb(err, result);
    });
  } else {  // go forward
    sim.step({ name: 'forwards', distance: stepSize }, frameSkip, function (err, result) {
      if (result.observation.collision) {
        sim.step({ name: 'turnRight', angle: Math.PI }, 48 /* HACK to get large turn*/, function (turnErr, turnResult) {
          cb(turnErr, turnResult);
        });
      } else {
        cb(err, result);
      }
    });
  }
}

sim.start(function (err, sceneState) {
  STK.util.waitImagesLoaded(function () {  // wait for textures to load
    if (cmd.port < 0) {  // standalone mode
      var startTime = new Date();
      var i = 0;
      async.whilst(
        function () { return i < cmd.num_steps; },
        function (cb) {
          i++;
          randomStep(cb);
        },
        function (err, result) {
          var timeSec = (new Date() - startTime) / 1000;  // ms to sec
          console.log('standalone, ' + timeSec + 's fps=' + cmd.num_steps / timeSec);
        }
      );
    } else {  // server mode
      console.log('Waiting for client connection on port ' + cmd.port);
      var sio = SocketIO(cmd.port, {
        pingTimeout: cmd.ping_timeout*1000
      });
      sio.on('connection', function (socket) {
        console.log('Client connected on port ' + cmd.port);
        socket.on('disconnect', function (reason) {
          console.warn('Client disconnected', reason);
        });
        socket.on('error', function (err) {
          console.error('Socket.io error', err);
        });
        socket.on('action', function () {
          if (cmd.busywait > 0) {
            STK.util.busywait(cmd.busywait);
          }
          randomStep(function (err, result) {
            socket.emit('observation', result);
          });
        });

        socket.on('stop', function () {
          console.log('Received stop. Shutting down.');
          sio.close();
        });
      });
    }
  });
});
