Manage hardware profiles for PMOVES deployment across different devices.

Hardware profiles configure optimal settings for different deployment targets (RTX 3090 Ti, RTX 5090, Jetson Orin, CPU-only, etc.).

## Usage

Run this command when:
- Setting up a new deployment environment
- Switching between hardware configurations
- Checking which profile is active
- Auto-detecting hardware for profile suggestions

## Arguments

- `$ARGUMENTS` - Action and options:
  - `list` - List all available hardware profiles
  - `show <profile_id>` - Show detailed profile information
  - `detect` - Auto-detect hardware and suggest profiles
  - `apply <profile_id>` - Set the active profile
  - `current` - Display the currently active profile

## Implementation

Execute the appropriate command based on the action:

1. **List profiles:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli profile list
   ```

2. **Show profile details:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli profile show <profile_id>
   ```

3. **Auto-detect hardware:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli profile detect --top 3
   ```

4. **Apply a profile:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli profile apply <profile_id>
   ```

5. **Show current profile:**
   ```bash
   cd /home/pmoves/PMOVES.AI && python3 -m pmoves.tools.mini_cli profile current
   ```

## Profile Information

Each profile includes:
- **Hardware specs**: GPU, VRAM, CPU, RAM requirements
- **Compose overrides**: Docker compose files to include
- **Model bundles**: Recommended local models for the hardware
- **MCP adapters**: Compatible MCP toolkits
- **Notes**: Hardware-specific considerations

## Available Profiles

Common profile IDs:
- `rtx-3090-ti` - NVIDIA RTX 3090 Ti (24GB VRAM)
- `rtx-5090` - NVIDIA RTX 5090 (next-gen)
- `jetson-orin` - NVIDIA Jetson AGX Orin
- `cpu-only` - CPU-only deployment (no GPU)
- `cloud-gpu` - Cloud GPU instances

## Related Commands

- `/botz:init` - Environment initialization
- `/botz:mcp` - MCP toolkit management
- `/deploy:up` - Start services with profile settings

## Notes

- Profile settings affect which Docker compose overrides are used
- GPU profiles configure CUDA/cuDNN versions appropriately
- Active profile is persisted in `pmoves/data/profile/active.txt`
