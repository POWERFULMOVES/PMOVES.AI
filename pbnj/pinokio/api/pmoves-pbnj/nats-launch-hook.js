// nats-launch-hook.js
// Publishes p7.nats.launch.v1 when a Pinokio app starts or stops.
// Usage from a launcher start/stop step:
//   { method: "script.start", params: { uri: "nats-launch-hook.js",
//     params: { room: "5090-voice.room.studio", app: "flute-gateway",
//       port: "8055", action: "started" } } }
module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        message: [
          "nats pub p7.nats.launch.v1 \"{\\\"room\\\":\\\"{{args.room}}\\\",\\\"app\\\":\\\"{{args.app}}\\\",\\\"port\\\":\\\"{{args.port}}\\\",\\\"action\\\":\\\"{{args.action}}\\\",\\\"ts\\\":\\\"{{new Date().toISOString()}}\\\"}\""
        ],
        env: {
          NATS_URL: "{{envs.NATS_URL || 'nats://localhost:4222'}}"
        }
      }
    },
    {
      method: "log",
      params: {
        text: "P7 launch event published: room={{args.room}} app={{args.app}} port={{args.port}} action={{args.action}}"
      }
    }
  ]
}
