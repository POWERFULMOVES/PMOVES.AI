# RustDesk Configuration Drop-In

Place a `server.conf` file in this directory before imaging a machine to pre-seed RustDesk with your relay/ID server settings.
The Windows post-install script copies it into `%AppData%\RustDesk\config\RustDesk2\RustDesk\config\server.conf` for the first
signed-in user.

The file should be exported from an existing RustDesk install or follow the structure:

```
[server]
id_server=your-id.example.com
relay_server=your-relay.example.com
key=YOUR_PUBLIC_KEY
```

Do **not** commit secrets to the repository—keep `server.conf` on the provisioning media only.
