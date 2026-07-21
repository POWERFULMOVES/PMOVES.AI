// nats-session-hook.js
// Publishes p7.nats.session.v1 to the PMOVES NATS bus when called from a
// Pinokio launcher. Accepts args: node_id, room, action
// (start|started|pause|resume|end|stop|stopped|archive).
// Usage from another script step:
//   { method: "script.start", params: { uri: "nats-session-hook.js",
//     params: { node_id: "pmoves-4090", room: "5090-voice.room.studio",
//       action: "started" } } }
module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        message: [
          "nats pub p7.nats.session.v1 \"{\\\"node\\\":\\\"{{args.node_id}}\\\",\\\"room\\\":\\\"{{args.room}}\\\",\\\"action\\\":\\\"{{args.action}}\\\",\\\"ts\\\":\\\"{{new Date().toISOString()}}\\\"}\""
        ],
        env: {
          NATS_URL: "{{envs.NATS_URL || 'nats://localhost:4222'}}"
        }
      }
    },
    {
      method: "log",
      params: {
        text: "P7 session event published: node={{args.node_id}} room={{args.room}} action={{args.action}}"
      }
    }
  ]
}
