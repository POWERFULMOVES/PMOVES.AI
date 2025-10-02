# In WSL2 Ubuntu terminal
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker to use NVIDIA runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

## Compose advice (GPU flags that actually work in docker-compose)

When using Docker Compose (not Swarm), prefer the modern GPU flag:

```
gpus: all
```

The `deploy.resources.reservations.devices` block is only honored by Docker Swarm. For docker-compose, it is ignored. If your environment is older, fall back to:

```
# runtime: nvidia
```

See the optimized examples under `compose/agent-zero/`:
- `docker-compose.gpu.optimized.yml` (general, works for Jetson/WSL/Linux)
- `docker-compose.gpu5090.optimized.yml` (high-end desktop, large shared memory)
- `compose.profiles.yml` (desktop/jetson profiles)

On Jetson (ARM64) ensure you use arm64-capable base images and install Jetson-compatible torch wheels if needed. Consider an L4T PyTorch base for services that embed models.

## WSL/Docker Desktop tips
- Enable GPU support in Docker Desktop.
- If services need to reach a host service (e.g., Supabase CLI at port 54321), use `host.docker.internal` and add:
  - `extra_hosts: ["host.docker.internal:host-gateway"]` in the service.
