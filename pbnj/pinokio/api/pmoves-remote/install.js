module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "docker compose -f docker-compose.remote.yml pull"
        ]
      }
    },
    {
      when: "{{!exists('../../pmoves/env.tier-vpn')}}",
      method: "shell.run",
      params: {
        path: "../../pmoves",
        message: [
          "cp env.tier-vpn.example env.tier-vpn"
        ]
      }
    },
    {
      method: "notify",
      params: {
        html: "Remote stack images pulled and env.tier-vpn initialized. Edit env.tier-vpn with your API keys before starting.",
        type: "success"
      }
    }
  ]
}
