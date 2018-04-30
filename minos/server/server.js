#!/usr/bin/env node

var cmd = require('commander');
var fs = require('fs');
var net = require('net');
var SocketIO = require('socket.io');
var STK = require('sstk/ssc');
var wav = require('node-wav');

STK.Constants.defaultPalette = STK.Colors.palettes.d3_unknown_category18;
STK.Constants.setVirtualUnit(1);  // meters
STK.materials.Materials.DefaultMaterialType = THREE.MeshStandardMaterial;

cmd
  .version('0.0.1')
  .option('-p, --port [port]', 'Port to send simulator data [default: 1234]', 1234)
  .option('--ping_timeout [num]', 'Number of seconds between ping/pong before client timeout', STK.util.cmd.parseInt, 300)
  .option('--busywait [num]', 'Number of seconds to busy wait for a command (for pretending to be a busy server)', STK.util.cmd.parseInt)
  .parse(process.argv);

var port = cmd.port;
var sio = SocketIO(port, {
  pingTimeout: cmd.ping_timeout*1000
});

var sim;

console.log('Waiting for client connection on port ' + port);

STK.assets.AssetGroups.registerDefaults();
var assets = require('sstk/ssc/data/assets.json');
var assetsMap = STK.util.keyBy(assets, 'name');
STK.assets.registerCustomAssetGroupsSync(assetsMap, ['p5dScene', 'mp3d', '2d3ds']);

function createSimulator(params) {
  params = STK.util.mapKeys(params, function(v,k) { return _.camelCase(k); });
  var useLights = (params.useLights !== undefined) ? params.useLights : false;
  if (useLights) {
    STK.materials.Materials.DefaultMaterialType = THREE.MeshPhysicalMaterial;
  }
  var renderer = new STK.PNGRenderer({
    width: params.width,
    height: params.height,
    useAmbientOcclusion: params.useAmbientOcclusion,
    useLights: useLights,
    useShadows: params.useShadows,
    reuseBuffers: true
  });

  var simParams = STK.util.defaultsDeep(
    Object.create(null),
    {
      renderer: renderer,
      rendererType: STK.PNGRenderer,
      bufferType: Buffer, net: net, wav: wav, fs: STK.fs
    },
    params,
    { start: 'random', goal: 'random' }
  );
  return new STK.sim.Simulator(simParams);
}

var __typedArrayToType = {
  'Int8Array': 'int8',
  'Int16Array': 'int16',
  'Int32Array': 'int32',
  'Uint8Array': 'uint8',
  'Uint8ClampedArray': 'uint8',
  'Uint16Array': 'uint16',
  'Uint32Array': 'uint32',
  'Float32Array': 'float32',
  'Float64Array': 'float64'
};

function serializeForSocketIO(data) {
  // Minor serializing of data so that TypedArrays are passed in binary
  if (data != undefined) {
    // TODO: Indicate endianness
    var serialized = STK.util.cloneDeepWith(data, function (x,k) {
      if (x instanceof ArrayBuffer || x instanceof Buffer) {
        return x;
      } else if (x instanceof THREE.Vector2 || x instanceof THREE.Vector3 || x instanceof THREE.Vector4) {
        return x.toArray();
      } else if (x instanceof STK.geo.BBox) {
        return { min: x.min.toArray(), max: x.max.toArray() };
      } else if (x && x.constructor) {
        var t = __typedArrayToType[x.constructor.name];
        if (t) {
          return {type: 'array', datatype: t, length: x.length, data: x.buffer};
        }
      }
    });
    //console.log(serialized);
    return serialized;
  }
}

sio.on('connection', function (socket) {
  console.log('Client ' + socket.id + ' connected on port ' + port);

  // Predefined events
  socket.on('disconnect', function (reason) {
    console.warn('Client disconnected', reason);
  });

  socket.on('error', function (err) {
    console.error('Socket.io error', err);
  });

  // Custom events
  socket.on('init', function (params, respCb) {
    if (!sim) {
      sim = createSimulator(params);
    }
    respCb({ status: 'OK', message: 'initialized' });
  });

  socket.on('start', function (params, respCb) {
    if (cmd.busywait > 0) {
      STK.util.busywait(cmd.busywait);
    }
    if (!sim) {
      sim = createSimulator(params);
    }

    STK.util.checkMemory('starting');
    console.time('Timing start');
    sim.start(function (err, sceneState) {
      if (sceneState) {
        console.log('started... waiting for all images to load');
        console.time('Timing waitImages');
        // wait for textures to load
        STK.util.waitImagesLoaded(function () {
          console.timeEnd('Timing waitImages');
          sim.getEpisodeInfo({}, function(err, summary) {
            console.timeEnd('Timing start');
            if (err) {
              respCb({ status: 'error', message: err });
            } else {
              respCb({status: 'OK', data: serializeForSocketIO(summary)});
            }
          });
        });
      } else {
        respCb({ status: 'error', message: err });
      }
    });
  });

  socket.on('reset', function (p, respCb) {
    if (sim) {
      //console.time('Timing reset');
      sim.reset(function(err, sceneState) {
        if (sceneState) {
          // wait for textures to load (maybe new objects were loaded)
          //console.log('reset... waiting for all images to load');
          //console.time('Timing waitImages');
          STK.util.waitImagesLoaded(function () {
            //console.timeEnd('Timing waitImages');
            sim.getEpisodeInfo({}, function(err, summary) {
              //console.timeEnd('Timing reset');
              if (err) {
                respCb({ status: 'error', message: err });
              } else {
                respCb({status: 'OK', data: serializeForSocketIO(summary)});
              }
            });
          });
        } else {
          respCb({status: 'error', message: err});
        }
      });
    } else {
      console.error('Simulator is not initialized yet!');
      respCb({ status: 'error', message: 'Simulator is not initialized yet!' });
    }
  });

  socket.on('configure', function (opts, respCb) {
    if (sim) {
      var data = sim.configure(opts);
      // Returns current options, omitting stuff that the client don't care about like the renderer and simpleRenderer
      respCb({ status: 'OK', data: serializeForSocketIO(data) });
    } else {
      console.error('Simulator is not initialized yet!');
      respCb({ status: 'error', message: 'Simulator is not initialized yet!' });
    }
  });

  socket.on('action', function (action, respCb) {
    if (cmd.busywait > 0) {
      STK.util.busywait(cmd.busywait);
    }
    if (sim && sim.isReady()) {
      //console.time('step');
      sim.step(action, 1, function(err, data) {
        //console.timeEnd('step');
        if (err) {
          respCb({ status: 'error', message: err });
        } else {
          var serialized = serializeForSocketIO(data);
          if (STK.util.size(serialized) === 0) {
            console.error('Sending message with empty data: ', serialized, data);
          }
          respCb({ status: 'OK', data: serialized });
        }
      });
    } else {
      console.error('Simulator is not started yet!');
      respCb({ status: 'error', message: 'Simulator is not started yet!' });
    }
  });

  socket.on('move_to', function (p, respCb) {
    if (sim) {
      var data = sim.getAgent().moveTo(p);
      respCb({ status: 'OK', data: serializeForSocketIO(data) });
    } else {
      console.error('Simulator is not initialized yet!');
      respCb({ status: 'error', message: 'Simulator is not initialized yet!' });
    }
  });

  socket.on('set_goal', function (goal, respCb) {
    if (sim) {
      var data = sim.getState().setGoal(goal);
      respCb({ status: 'OK', data: serializeForSocketIO(data) });
    } else {
      console.error('Simulator is not initialized yet!');
      respCb({ status: 'error', message: 'Simulator is not initialized yet!' });
    }
  });

  socket.on('get_scene_data', function (p, respCb) {
    if (sim) {
      sim.getEpisodeInfo({}, function(err, summary) {
        if (err) {
          respCb({ status: 'error', message: err });
        } else {
          respCb({status: 'OK', data: serializeForSocketIO(summary)});
        }
      });
    } else {
      console.error('Simulator is not initialized yet!');
      respCb({ status: 'error', message: 'Simulator is not initialized yet!' });
    }
  });

  socket.on('get_observation_metadata', function (p, respCb) {
    if (sim) {
      var meta = sim.getObservationMetadata();
      respCb({ status: 'OK', data: serializeForSocketIO(meta)});
    } else {
      console.error('Simulator is not initialized yet!');
      respCb({ status: 'error', message: 'Simulator is not initialized yet!' });
    }
  });

  socket.on('get_action_trace', function (p, respCb) {
    if (sim) {
      var data = sim.getActionTrace();
      respCb({ status: 'OK', data: serializeForSocketIO(data) });
    } else {
      console.error('Simulator is not initialized yet!');
      respCb({ status: 'error', message: 'Simulator is not initialized yet!' });
    }
  });

  socket.on('seed', function (p, respCb) {
    // Set seed
    if (sim) {
      sim.seed(p);
      respCb({ status: 'OK', data: true });
    } else {
      console.error('Simulator is not initialized yet!');
      respCb({ status: 'error', message: 'Simulator is not initialized yet!' });
    }
  });

  socket.on('close', function (data, respCb) {
    if (!sim) { console.error('Simulator is not started yet!'); }
    console.log('Received close signal. Shutting down simulator server...');
    sim.close();
    console.log('Closed simulator');
    respCb({ status: 'OK', message: 'closed' });
    //sio.close();
  });
});
