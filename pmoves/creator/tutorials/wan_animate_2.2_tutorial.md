# WAN Animate 2.2 v2 - Complete Tutorial Guide

**Video Source:** [THE NEW NSFW FREE IMAGE TO VIDEO KING IS HERE! OMG!](https://www.youtube.com/watch?v=apd68jTrxYc)  
**Creator:** Aitrepreneur  
**Duration:** 27 minutes

---

## Overview

WAN Animate 2.2 v2 is an amazing open-source video generation model that can:
- Replace a person in a video with just a single reference image
- Extract motion from one character and apply it perfectly to another character
- Replace specific objects, clothing, or elements in videos with pinpoint precision
- Transfer motion from video to static images

---

## Table of Contents

1. [Installation Methods](#installation-methods)
2. [Workflow Setup](#workflow-setup)
3. [Basic Usage - Character Replacement](#basic-usage---character-replacement)
4. [Motion Transfer (Video to Image)](#motion-transfer-video-to-image)
5. [Understanding the Workflow](#understanding-the-workflow)
6. [Masking Methods](#masking-methods)
7. [Advanced Techniques](#advanced-techniques)
8. [RunPod Cloud Setup](#runpod-cloud-setup)

---

## Installation Methods

### Method 1: One-Click Installer (Patreon Supporters)

**[Screenshot: Patreon installer download page]**

1. Download the one-click installer file from Patreon
2. Double-click the downloaded file
3. The installer automatically:
   - Downloads and installs ComfyUI
   - Installs all missing nodes and models
   - Installs Triton for faster generation
   - Installs Sage Attention for speed optimization

**Additional Installers Available:**
- Separate models and nodes installer (if you already have ComfyUI installed)
- Triton and Sage Attention standalone installer

**[Screenshot: Installation progress window]**

### Method 2: Manual Installation

Link available in the video description: [Pastebin Manual Installation Guide](https://pastebin.com/sjN3JzbC)

### Post-Installation Steps

1. Update ComfyUI to the latest version:
   - Navigate to the `update` folder
   - Run `update_comfyui.bat`

**[Screenshot: Update folder with bat file highlighted]**

2. Download the special WAN Animate workflow from Patreon
3. Drag and drop the workflow file into ComfyUI

**[Screenshot: ComfyUI interface with workflow loaded]**

---

## Workflow Setup

### Step 1: Upload Video Reference

**[Screenshot: Video upload node]**

- Click the upload button to select your reference video
- This is the video containing the character you want to replace OR the motion you want to extract

### Step 2: Set Resolution

**Recommended Resolutions:**
- **Vertical:** 480 x 832
- **Horizontal:** 832 x 480
- **Square:** 512 x 512

**Optional Settings:**
- **Frame Load Cap:** Limits the number of frames to generate (useful for quick tests)

**[Screenshot: Resolution settings panel]**

### Step 3: Upload Reference Image

**[Screenshot: Reference image upload node]**

Upload the character/object that will:
- Replace the character in your video, OR
- Receive the motion from the video

---

## Basic Usage - Character Replacement

### Example: Replacing a Woman in a Video

1. **Upload your video** containing the character to replace
2. **Set correct width and height** (e.g., 480 x 832)
3. **Upload reference image** of the new character
4. **Scroll down and enable masking option**
5. **Write a simple prompt** (e.g., "the woman is talking")
6. **Select correct mask and background image**
7. **Click Run**

**[Screenshot: Before - Original video frame]**
**[Screenshot: After - Replaced character frame]**

### Result
The character in the original video is replaced with your reference image character while maintaining the same motion and movements.

---

## Motion Transfer (Video to Image)

### Transferring Motion Without Character Replacement

1. **Upload video** with the motion you want to extract
2. **Upload reference image** (the character that will receive the motion)
3. **Disable the masking option** (this is crucial!)
4. **Write your prompt**
5. **Click Run**

**[Screenshot: Motion transfer settings with masking disabled]**

### Result
Your static reference image now moves with the motion from the original video, but the character itself remains your reference image.

**[Screenshot: Motion transferred to new character]**

---

## Understanding the Workflow

### Key Parameters

#### Triton Compiler
- **Location:** Side panel in Step 3
- **Purpose:** Makes generation much faster
- **Requirement:** Triton must be installed for Windows
- **Alternative:** Disable if not installed (will still work, just slower)

**[Screenshot: Triton compiler setting]**

#### Sage Attention
- **Recommended:** Select "Sage Attention" if installed
- **Alternative:** Select "SGPA" if Sage Attention causes errors
- **Note:** Sage Attention provides faster generation

**[Screenshot: Attention mode dropdown]**

#### LoRA Loader
Two LoRAs are used:

1. **Lite to X** - Always use this, never change
2. **Relight LoRA** - Controls lighting integration (explained later)

**[Screenshot: LoRA loader nodes]**

#### Prompt Guidelines
- **Keep it simple!** Just describe the basic action
- ✅ Good: "the woman is talking"
- ✅ Good: "the character is dancing"
- ❌ Bad: Long detailed paragraph

**[Screenshot: Prompt input field]**

#### VRAM Management
**Video Block Swap Setting:**
- Offloads model processing from VRAM to RAM
- **Default:** Keep low for high VRAM GPUs (16GB+)
- **8-12GB GPUs:** Increase to ~40 if you have 64GB+ RAM
- Allows you to run the model without quantization

**[Screenshot: Video block swap parameter]**

---

## Masking Methods

### Method 1: Automatic Character Masking

**When to Use:**
- Quick character replacements
- When you want to replace an entire moving character

**Setup:**
1. Enable "Auto Character Masking" option
2. Set "Get Mask" to value: **mask**
3. Set "Background Image" to value: **background image**
4. Adjust "Expand Mask" value (default: 80)

**[Screenshot: Auto masking settings panel]**

**Expand Mask Values:**
- **10-20:** Smaller mask, tighter fit
- **80:** Default, provides good coverage
- **100+:** Larger mask for characters with flowing hair, loose clothing

**Important:** If parts of your character are cut off (like hair), increase the expand mask value!

**[Screenshot: Comparison - mask too small vs proper mask]**

---

### Method 2: SECC Masking (Recommended!)

**Why SECC is Better:**
- Perfectly masks single objects throughout entire video
- Works even when scenes change completely
- Can track and mask very specific elements
- Most precise masking available

**[Screenshot: SECC tracking example - white dog tracked through scene changes]**

#### SECC Setup Process

**Step 1: Prepare the Mask**

1. **Disable all options** in the workflow except "SEC Part 1"
2. Make sure you have your video and reference image loaded
3. **Click Run**

**[Screenshot: Workflow with only SEC Part 1 enabled]**

4. A new image will appear
5. **Click "New Canvas"**

**[Screenshot: New Canvas button]**

**Step 2: Mark Your Points**

**Green Points (What to Mask):**
- Hold **SHIFT** + **LEFT CLICK** to place green points
- Place points on everything you want to MASK
- Aim for 20-30 points, but you can use more or less

**[Screenshot: Image with green points placed on target]**

**Red Points (What to Keep):**
- Hold **SHIFT** + **RIGHT CLICK** to place red points
- Place points on everything you DON'T want to mask
- Place red points around and away from the target

**[Screenshot: Image with both green and red points]**

**Step 3: Generate the Mask**

1. **Enable SEC Part 2** connection
2. **Enable everything** in the workflow
3. Adjust **Expand Mask** if needed (10-20 typical)
4. **Click Run**

**[Screenshot: SEC masking result]**

---

### SECC Advanced Examples

#### Example 1: Replace Clothing Only

**Scenario:** Replace a white shirt with a red dress

1. Upload video of person wearing white shirt
2. Upload reference image of red dress
3. Disable everything except SEC Part 1
4. Click Run → New Canvas
5. Place **green points ONLY on the white shirt**
6. Place **red points** on face, arms, background
7. Enable SEC Part 2 and full workflow
8. Prompt: "the woman wearing a red dress is talking"
9. Click Run

**[Screenshot: Before - white shirt]**
**[Screenshot: After - red dress]**

**Result:** Only the clothing changes, everything else stays the same!

---

#### Example 2: Replace Pants

**Scenario:** Replace gray pants with colorful pants on dancing person

1. Upload dancing video (250 frames)
2. Upload reference image of colorful pants
3. SEC Part 1 → Run → New Canvas
4. Place **green points only on the pants**
5. Place **red points** on person, background
6. Enable SEC Part 2 and workflow → Run

**[Screenshot: Gray pants → Colorful pants transformation]**

**Result:** Pants color changed while maintaining all movement perfectly!

---

#### Example 3: Replace Animals/Objects

**Scenario:** Replace real dog with cartoon dog

1. Upload video of real dog
2. Upload reference image of cartoon dog
3. SEC Part 1 → Run → New Canvas
4. Place **green points on the dog**
5. Place **red points on background, floor, surroundings**
6. Enable SEC Part 2 and workflow
7. Prompt: "the white 3D cartoon dog is playing"
8. Click Run

**[Screenshot: Real dog → Cartoon dog transformation]**

**Note:** Adjust mask size for best results. If mask is too large, unwanted transformations may occur.

---

## Advanced Techniques

### Handling Characters Without Faces

**Problem:** If your character doesn't have facial features (like a helmet, mask, or stylized character), the default settings may try to add a face.

**[Screenshot: Incorrect - face added to faceless character]**

**Solution:**

1. Locate these three nodes in the workflow:
   - Gate Face Image node
   - Related face processing nodes
2. Click on each node and select **"Bypass"** icon
3. This disables face motion/detection

**[Screenshot: Nodes to bypass highlighted]**

4. **Increase the mask value** (the character may appear skinny without adjustment)
5. Click Run

**[Screenshot: Correct - faceless character maintained]**

**Result:** Character maintains its faceless appearance with proper movement!

---

### WAN Animate Relight LoRA

**Purpose:** Integrates your character's lighting and colors with the scene

#### With Relight Enabled (Default)
- Character lighting adapts to match the scene
- Colors may shift to match scene ambiance
- More natural integration

**[Screenshot: Character with relight applied]**

#### With Relight Disabled (Strength = 0)
- Character maintains original reference colors
- Lighting remains as in reference image
- Less scene integration, more accurate to original

**[Screenshot: Character without relight]**

**How to Adjust:**
1. Locate the Relight LoRA node
2. Set **Strength to 0** to disable
3. Keep default (~1.0) to enable

**[Screenshot: Relight LoRA strength parameter]**

**Recommendation:** Try both and see which fits your project better!

---

## Common Workflows Summary

### Workflow A: Full Character Replacement
```
✅ Video uploaded
✅ Reference image uploaded
✅ Masking enabled (Auto or SECC)
✅ Prompt written
✅ Face nodes active (if character has face)
```

**[Screenshot: Full replacement workflow]**

---

### Workflow B: Motion Transfer Only
```
✅ Video uploaded (for motion extraction)
✅ Reference image uploaded (receives motion)
❌ Masking DISABLED
✅ Prompt written
✅ Face nodes active
```

**[Screenshot: Motion transfer workflow]**

---

### Workflow C: Specific Element Replacement
```
✅ Video uploaded
✅ Reference image of replacement element
✅ SECC masking (precise point selection)
✅ Specific prompt (e.g., "wearing red dress")
✅ Face nodes bypassed if replacing non-face elements
```

**[Screenshot: Element replacement workflow]**

---

## RunPod Cloud Setup

### Why Use RunPod?
- No powerful GPU required
- Runs as if on your local computer
- Access from anywhere

### Setup Instructions

#### 1. Create Account
- Use link in video description for RunPod
- Create new account

**[Screenshot: RunPod signup page]**

#### 2. Select GPU
1. Click **"Pods"**
2. Choose GPU with **at least 24GB VRAM** (e.g., RTX 4090)

**[Screenshot: GPU selection screen]**

#### 3. Configure Template
1. Click **"Change Template"**
2. Search for **"Aitrepreneur"**
3. Select the **ComfyUI template**

**[Screenshot: Template selection]**

#### 4. Set Storage
1. Click **"Edit"**
2. Set **Container Disk: 80GB**
3. Set **Volume Disk: 80GB**
4. Click **"Set Overrides"**

**[Screenshot: Storage configuration]**

#### 5. Deploy
1. Click **"Deploy On Demand"**
2. Wait for deployment to complete

**[Screenshot: Deployment progress]**

#### 6. Update ComfyUI
1. Click on your pod
2. Click **"Manager"**
3. Click **"Update All"**

**[Screenshot: Manager update screen]**

#### 7. Monitor Progress (Optional)
1. Go back
2. Click terminal icon
3. Navigate to **"logs"** folder
4. Click terminal icon
5. Copy and paste monitoring command
6. Watch step-by-step progress

**[Screenshot: Terminal with update logs]**

#### 8. Restart
1. After update completes
2. Go back → Click **"Restart"**
3. Click **"OK"**
4. Press **F5** to refresh

**[Screenshot: Restart confirmation]**

#### 9. Install WAN Animate (Patreon Method)

**For Patreon Supporters:**

1. Download special RunPod one-click installer from Patreon
2. Navigate to **config folder** in workspace
3. **Drag and drop** installer file into workspace
4. Click **"New Launcher"** → **"New Terminal"**
5. Copy and paste the two command lines from Patreon post
6. Press **Enter**

**[Screenshot: Terminal with installation commands]**

7. Wait for installation to complete
8. Go back → Click **"Manager"** → **"Restart"**
9. Press **F5** to refresh
10. Drag and drop the workflow into ComfyUI

**[Screenshot: WAN Animate running on RunPod]**

**Done!** WAN Animate 2.2 is now running on RunPod as if it were on your local computer!

---

## Tips and Best Practices

### 1. Prompt Writing
- Keep prompts simple and descriptive
- Focus on the action: "talking", "dancing", "walking"
- Mention specific clothing if replacing: "wearing red dress"

### 2. Mask Expansion
- Start with default value (80 for auto masking)
- Increase if character parts are cut off
- Decrease for tighter, more precise masking

### 3. Resolution Selection
- Match your source video resolution when possible
- Use standard aspect ratios (vertical, horizontal, square)
- Higher resolution = longer generation time

### 4. Frame Count
- Use Frame Load Cap for testing (shorter videos)
- Full videos can be 200+ frames
- Balance quality needs with generation time

### 5. SECC Point Placement
- More points = better accuracy (but diminishing returns)
- Ensure complete coverage of target area
- Red points prevent unwanted masking

### 6. Performance Optimization
- Enable Triton if installed (Windows)
- Use Sage Attention for speed
- Adjust Video Block Swap based on your VRAM/RAM

### 7. Troubleshooting
- Hair getting cut off? → Increase expand mask
- Face appearing when it shouldn't? → Bypass face nodes
- Character too dark/light? → Adjust Relight LoRA strength
- Mask not precise enough? → Switch from Auto to SECC masking

---

## Conclusion

WAN Animate 2.2 v2 is an incredibly powerful tool for:
- ✅ Character replacement in videos
- ✅ Motion transfer from video to image
- ✅ Precise object/clothing replacement
- ✅ Creative video transformations

The workflow provides complete control while being beginner-friendly with sensible defaults.

**Key Takeaways:**
- Start simple with auto masking
- Graduate to SECC for precision work
- Experiment with different prompts and settings
- Use RunPod if you lack local GPU power

---

## Resources

- **Patreon:** [https://www.patreon.com/aitrepreneur](https://www.patreon.com/aitrepreneur)
- **Discord:** [Join Server](https://discord.gg/3ErYSdyUPt)
- **RunPod:** [Sign Up Link](https://bit.ly/runpodAi)
- **Manual Installation:** [Pastebin Guide](https://pastebin.com/sjN3JzbC)
- **Previous OVI Video:** [Recommended Tutorial](https://youtu.be/2SvPfkXs3Nk)

---

## Credits

**Video Creator:** Aitrepreneur  
**Original Video:** [Watch on YouTube](https://www.youtube.com/watch?v=apd68jTrxYc)  
**Tutorial Based On:** Full video transcript

---

*Note: This tutorial is based on the video transcript. For actual screenshots and visual examples, please watch the original video at the link provided above.*
