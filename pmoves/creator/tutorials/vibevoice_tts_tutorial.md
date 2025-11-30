# VibeVoice - Perfect Local TTS AI Voice Cloning Tutorial

**Video Source:** [RIP ELEVENLABS! Create PERFECT TTS AI Voices LOCALLY For FREE!](https://www.youtube.com/watch?v=XtaPZmlyMMw)  
**Creator:** Aitrepreneur  
**Duration:** 30 minutes

---

## Overview

VibeVoice is the ultimate free, local text-to-speech (TTS) solution that can:
- Clone any voice from just 10 seconds of audio
- Generate speech in multiple languages (English, French, Spanish, German, Japanese, Dutch, Russian, and more)
- Create realistic conversations between multiple speakers
- Produce near-perfect quality rivaling paid services like ElevenLabs
- Run completely on your local computer or cloud (RunPod)

**Bonus:** Combine with RVC (Retrieval-based Voice Conversion) for even better results!

---

## Table of Contents

1. [Platform Options](#platform-options)
2. [VibeVoice Web UI Tutorial](#vibevoice-web-ui-tutorial)
3. [Voice Cloning Basics](#voice-cloning-basics)
4. [Multi-Speaker Conversations](#multi-speaker-conversations)
5. [Multi-Language Support](#multi-language-support)
6. [Enhancing with RVC](#enhancing-with-rvc)
7. [ComfyUI Workflow](#comfyui-workflow)
8. [RunPod Installation](#runpod-installation)
9. [Best Practices](#best-practices)

---

## Platform Options

### Option 1: Standalone Web UI
**Best For:**
- Single speaker, highest quality
- Simple, easy-to-use interface
- Quick voice cloning tasks

**[Screenshot: VibeVoice Web UI interface]**

### Option 2: ComfyUI Workflow
**Best For:**
- Multiple speakers (more stable)
- Automated RVC integration
- Advanced workflows
- Better for 3+ speakers

**[Screenshot: ComfyUI workflow with VibeVoice nodes]**

### Quality Comparison
- **Web UI:** Better single-speaker quality
- **ComfyUI:** Better multi-speaker stability, fewer audio glitches with 3+ speakers

---

## VibeVoice Web UI Tutorial

### Initial Setup

**[Screenshot: Web UI main interface]**

#### Step 1: Download the Model

1. Scroll to the bottom of the interface
2. Click **"Download Model"**
3. Wait a few minutes for the model to download (large file)

**[Screenshot: Download model button]**

#### Step 2: Load the Model

1. Scroll back up
2. Make sure **"VibeVoice Large"** is selected in dropdown
3. Click **"Load Selected Model"**
4. Wait for confirmation that model is loaded

**[Screenshot: Model selection and load button]**

---

### Basic Voice Cloning

#### Using Pre-Loaded Voices

1. Choose **number of speakers** (start with 1)
2. Select from **standard voice options**
3. Enter your script/text
4. Click **"Generate Podcast"**

**[Screenshot: Speaker selection with standard voices]**

---

#### Creating Custom Voice Clone

**Step 1: Prepare Audio Sample**

Requirements:
- **Length:** At least 10 seconds (longer is better, up to 30 seconds recommended)
- **Quality:** Clear, minimal background noise
- **Format:** MP3, WAV, or other common audio formats
- **Content:** Clean speech (no music, effects, or multiple speakers)

**[Screenshot: Audio file selection button]**

**Step 2: Upload and Configure**

1. Click **upload button** for custom voice
2. Select your audio file
3. **Create a name** for the voice (e.g., "trump", "snake", "macron")
4. Click **"Add Custom Voice"**
5. Wait a few seconds for processing

**[Screenshot: Custom voice upload interface]**

**Step 3: Generate Speech**

1. Under **"Speaker"** dropdown, select your custom voice
2. Enter your script text
3. Click **"Generate Podcast"**
4. Audio plays in real-time during generation

**[Screenshot: Generated audio player]**

---

### Example 1: Donald Trump Voice Clone

**Source Audio:**
```
"Well, I think maybe the border is the most significant because our 
country was really going bad. They were allowing people to come in 
from prisons as you know and you've heard..."
```

**Generated Script:**
```
Let me tell you folks, nobody understands technology better than me. 
They say, "Sir, how do you know so much about computers?" And I said, 
"Look, I had the best emails. Everybody knows it. Beautiful emails, 
perfect emails..."
```

**[Screenshot: Trump voice settings]**

**Result Quality:** Nearly indistinguishable from real speech!

---

### Example 2: Video Game Character (Snake - Metal Gear)

**Source Audio:**
```
"I can't smoke a cigar if I don't have one, can I? 
Some kind of drug. The label says pentazamine."
```

**Generated Script:**
```
Life isn't just about passing on your genes. We can leave behind 
much more than just DNA. Through speech, music, literature, and movies...
```

**[Screenshot: Snake voice clone settings]**

---

## Multi-Speaker Conversations

### Setup for Multiple Speakers

1. Set **"Number of Speakers"** to 2 (or more)
2. Upload separate audio samples for each speaker
3. Name each voice distinctly (e.g., "snake", "majorzero")

**[Screenshot: Multi-speaker setup interface]**

### Script Format

**Important:** Use this exact format in your script:

```
Speaker 1: [First character's dialogue]
Speaker 2: [Second character's dialogue]
Speaker 1: [First character's next line]
Speaker 2: [Second character's next line]
```

**Example Script:**
```
Speaker 1: Snake do you copy?
Speaker 2: Loud and clear, Major. What's the situation?
Speaker 1: Intel suggests the enemy is transporting a new type of weapon.
Speaker 2: Another secret weapon. Feels like I've heard this story before.
```

**[Screenshot: Multi-speaker script example]**

### Voice Assignment

1. **Speaker 1 Voice:** Select first character (e.g., "Major Zero")
2. **Speaker 2 Voice:** Select second character (e.g., "Snake")
3. Click **"Generate Podcast"**

**[Screenshot: Voice assignment dropdowns for multiple speakers]**

**Result:** Natural-sounding conversation between two distinct characters!

---

## Multi-Language Support

### Supported Languages

VibeVoice supports numerous languages:
- ✅ English
- ✅ French
- ✅ Spanish
- ✅ German
- ✅ Dutch
- ✅ Russian
- ✅ Japanese
- ✅ And many more!

**[Screenshot: Multi-language examples]**

### How to Clone in Different Languages

**Process:**
1. Upload audio sample **in the target language**
2. Script must be **in the same language** as the audio sample
3. The model automatically detects and matches the language

---

### Example 1: French (Emmanuel Macron)

**Source:** French audio of Emmanuel Macron speaking  
**Script:** French text  
**Result:** Perfect French voice clone

**[Screenshot: French voice settings]**

---

### Example 2: Japanese (Voice Actor)

**Source:** Japanese voice actor sample (Kenji Uda)  
**Script:** Japanese text  
**Result:** Authentic Japanese voice replication

**Example Script with Romanji:**
```
[Japanese text with English translation shown]
```

**[Screenshot: Japanese voice clone interface]**

**Note:** Perfect for anime fans, voice actor cloning, or content localization!

---

## Enhancing with RVC

### What is RVC?

**RVC (Retrieval-based Voice Conversion)** is the best tool for voice training and cloning. It can:
- Train on ~1 hour of audio samples
- Convert any audio into a trained voice
- Further enhance VibeVoice outputs
- Share trained models with community

**[Screenshot: RVC interface]**

### When to Use RVC

**VibeVoice alone:** Already produces excellent quality (95%+ accuracy)

**VibeVoice + RVC:** 
- Slightly cleaner audio
- More precise voice matching
- Better for very specific voice characteristics
- **Optional but recommended** for professional use

---

### Finding Pre-Trained RVC Models

#### Voice Models Website

**URL:** [voice-models.com](https://voice-models.com)

**[Screenshot: voice-models.com homepage]**

**Features:**
- Community-trained RVC models
- Politicians, actors, anime characters, celebrities
- Rating system for quality
- Free downloads

**How to Use:**

1. Search for your desired voice (e.g., "Trump", "Snake", "Naruto")
2. Sort by **highest rating**
3. Click on the model
4. Download the ZIP file

**[Screenshot: Search results with ratings]**

---

### RVC Model Installation

**Step 1: Extract Files**

Downloaded ZIP contains:
- **`.pth` file** - The trained voice model
- **`.index` file** - Index for faster processing

**[Screenshot: Extracted RVC files]**

**Step 2: Install Model Files**

1. Navigate to RVC installation directory
2. **PTH file:** Copy to `assets/weights/` folder
3. **Index file:** Copy to `logs/` folder

**[Screenshot: File locations in RVC directory]**

---

### Using RVC to Enhance Audio

**Step 1: Load Model**

1. In RVC interface, click **"Refresh Voice List and Index Path"**
2. Select your voice from **"Inferencing Voice"** dropdown
3. Select corresponding **index file**

**[Screenshot: RVC model selection]**

**Step 2: Load Audio File**

1. Right-click your VibeVoice output file
2. Click **"Copy as Path"**
3. Paste path into **"Audio File to Process"** field

**[Screenshot: Audio file path input]**

**Step 3: Configure Settings**

- **Transpose:** Keep at `0` if using same voice
- **F0 Method:** Keep default
- Other settings: Leave as default for first try

**[Screenshot: RVC conversion settings]**

**Step 4: Convert**

1. Click **"Convert"**
2. Wait 5-10 seconds
3. Output file generated automatically

**[Screenshot: Conversion progress]**

---

### Quality Comparison

**Before RVC (VibeVoice only):**
```
"Let me tell you folks, nobody understands technology better than me..."
```
- Quality: Excellent
- Clarity: Very Good
- Accuracy: 95%

**After RVC Enhancement:**
```
"Let me tell you folks, nobody understands technology better than me..."
```
- Quality: Exceptional
- Clarity: Crystal Clear
- Accuracy: 98%

**[Screenshot: Waveform comparison before/after RVC]**

**Difference:** More crisp, cleaner, slightly better voice matching

---

## ComfyUI Workflow

### Why Use ComfyUI Workflow?

**Advantages:**
- **Automated pipeline:** VibeVoice → RVC in one workflow
- **Better multi-speaker stability** (3+ speakers)
- **No manual file transfers**
- **Customizable parameters**
- **Batch processing capable**

**[Screenshot: Complete ComfyUI workflow]**

---

### Workflow Setup

#### Installation

**For Patreon Supporters:**
1. Download ComfyUI workflow file from Patreon
2. Drag and drop into ComfyUI interface
3. Workflow loads with all nodes connected

**[Screenshot: Workflow loaded in ComfyUI]**

#### Model Installation in ComfyUI

**RVC Models:**
1. Copy `.pth` file to: `ComfyUI/models/TTS/RVC/`
2. Copy `.index` file to: `ComfyUI/models/TTS/RVC/index/`

**[Screenshot: ComfyUI models folder structure]**

---

### Using the Workflow

#### Basic Single Speaker Generation

**Step 1: Input Text**
- Locate text input node
- Enter your script

**[Screenshot: Text input node]**

**Step 2: Select Voice**
- **Speaker 1 Voice:** Choose your custom voice or standard voice
- **Disable unused speakers** (Speaker 2, 3, 4) by clicking bypass button

**[Screenshot: Speaker selection nodes]**

**Step 3: Configure RVC (Optional)**
- **Enable/Disable RVC node:** Toggle if you want RVC enhancement
- **Select Model:** Choose your RVC model from dropdown
- **Select Index:** Choose corresponding index file
- **Pitch Adjustment:** Set to `0` for same voice, adjust ±1-3 as needed

**[Screenshot: RVC configuration node]**

**Step 4: Generate**
- Click **Run** (or press Ctrl+Enter)
- First run downloads models (may take a few minutes)
- Subsequent runs are fast

**[Screenshot: Generate button]**

---

#### Multiple Speaker Conversations

**Script Format for ComfyUI:**

**Important:** Different syntax than Web UI!

```
[1] First speaker's dialogue
[2] Second speaker's dialogue
[1] First speaker's next line
[2] Second speaker's next line
```

**Example:**
```
[1] Snake do you copy?
[2] Loud and clear, Major.
[1] Intel suggests the enemy is transporting a new weapon.
[2] Another secret weapon. Feels familiar.
```

**[Screenshot: Multi-speaker script in ComfyUI]**

**Configuration:**
1. **Enable all speakers** you need (up to 4)
2. Assign voice to each speaker number
3. Increase **Diffusion Steps to 40-50** for multiple speakers/languages

**[Screenshot: Multi-speaker configuration]**

---

### Workflow Outputs

**Two Audio Files Generated:**

1. **VibeVoice Output:** `output_vibevoice.wav`
2. **RVC Enhanced Output:** `output_rvc.wav` (if RVC enabled)

**[Screenshot: Output files in ComfyUI]**

**You can:**
- Listen to both and compare
- Use whichever sounds better
- Adjust pitch and regenerate if needed

---

### Advanced Settings

#### Diffusion Steps
- **Default:** 20 steps
- **Multiple speakers:** Increase to 40-50
- **Complex multi-language:** Use 50+
- Higher = Better quality but slower

**[Screenshot: Diffusion steps parameter]**

#### Pitch Adjustment
- **0:** No pitch change (same voice)
- **+1 to +3:** Higher pitch
- **-1 to -3:** Lower pitch
- Adjust if voice sounds too deep/high

**[Screenshot: Pitch adjustment slider]**

---

## RunPod Installation

### Why Use RunPod?

- No powerful GPU required
- Pay only for usage (cents per hour)
- Access from anywhere
- Full functionality as local install

---

## RunPod Setup - VibeVoice Web UI

### Step 1: Create Account
- Visit RunPod (link in video description)
- Create new account

**[Screenshot: RunPod signup page]**

### Step 2: Select GPU
1. Click **"Pods"**
2. Choose GPU with **at least 24GB VRAM** (RTX 4090 recommended)

**[Screenshot: GPU selection screen]**

### Step 3: Configure Template
1. Click **"Change Template"**
2. Select **"RunPod PyTorch 2.1"**

**[Screenshot: Template selection]**

### Step 4: Set Storage
1. Click **"Edit"**
2. Set **Container Disk:** 50GB
3. Set **Volume Disk:** 50GB
4. Click **"Set Overrides"**

**[Screenshot: Storage configuration]**

### Step 5: Deploy
1. Click **"Deploy On Demand"**
2. Wait for deployment (1-2 minutes)

**[Screenshot: Deployment status]**

### Step 6: Access Jupyter Lab
1. Click on the Jupyter Lab link
2. Interface opens in new tab

**[Screenshot: Jupyter Lab interface]**

---

### Step 7: Install VibeVoice (Patreon Method)

**For Patreon Supporters:**

1. Download **"VibeVoice Web UI RunPod Installer"** from Patreon
2. Drag and drop into Jupyter workspace
3. Click **"Terminal"** icon
4. Copy and paste the two command lines from Patreon post:

```bash
# Commands provided in Patreon post
# [Line 1: Extraction command]
# [Line 2: Installation command]
```

5. Press **Enter**
6. Wait for installation to complete

**[Screenshot: Terminal with installation commands]**

**Manual Installation:**
- Guide available in video description
- Link: [Manual Installation Pastebin](https://pastebin.com/FX07hPLc)

---

### Step 8: Launch Web UI

1. After installation completes, terminal shows **public URL**
2. Click the URL
3. VibeVoice Web UI opens in new tab
4. Ready to use!

**[Screenshot: Public URL in terminal]**

---

### Step 9: Download Model
1. **First time:** Scroll down, click **"Download Model"**
2. Wait for VibeVoice Large model to download
3. Scroll up, select **"VibeVoice Large"**
4. Click **"Load Selected Model"**

**[Screenshot: Model download and load]**

---

### Step 10: Generate Speech
1. Upload custom voice or use standard voice
2. Enter script
3. Click **"Generate Podcast"**
4. Audio generates on RunPod server

**[Screenshot: Generation on RunPod]**

**✅ Now running as if on local computer!**

---

## RunPod Setup - RVC Web UI

### Step 1: Create New Pod
- Same as before: Select 24GB+ GPU
- Template: **"RunPod PyTorch 2.1"**
- Storage: 50GB for both

**[Screenshot: RVC pod configuration]**

### Step 2: Expose HTTP Port
**Important:** Before deploying:
1. In template settings, find **"Expose HTTP Port"**
2. Enter: `7865`
3. Click **"Set Overrides"**

**[Screenshot: HTTP port configuration]**

### Step 3: Deploy and Access
1. Deploy on demand
2. Click Jupyter Lab link

**[Screenshot: RVC Jupyter interface]**

### Step 4: Install RVC (Patreon Method)
1. Download **"RVC RunPod Installer"** from Patreon
2. Drag and drop into workspace
3. Open Terminal
4. Copy and paste installation commands
5. Press Enter

**[Screenshot: RVC installation progress]**

### Step 5: Launch RVC
1. After installation, go back to pod page
2. Click **second link** (port 7865)
3. RVC Web UI opens

**[Screenshot: RVC Web UI on RunPod]**

---

### Using RVC on RunPod

**File Management:**
- Upload audio files to workspace folder
- Copy path: Right-click → Copy Path
- **Important:** Add `/` before `workspace` in path

**Example Path:**
```
/workspace/audio/trump_audio.wav
```

**[Screenshot: File path correction]**

**Model Installation:**
- Same as local: Place files in `assets/weights/` and `logs/`
- Upload via Jupyter interface

**[Screenshot: Uploading models to RunPod]**

---

## RunPod Setup - ComfyUI with VibeVoice

### Step 1: Select Template
1. Choose 24GB+ GPU (RTX 4090)
2. Click **"Change Template"**
3. Search: **"Aitrepreneur"**
4. Select: **"ComfyUI Template"**

**[Screenshot: Aitrepreneur ComfyUI template]**

### Step 2: Configure Storage
1. Edit template
2. Container Disk: **80GB**
3. Volume Disk: **80GB**
4. Set Overrides

**[Screenshot: ComfyUI storage settings]**

### Step 3: Deploy and Update
1. Deploy on demand
2. Click to access ComfyUI
3. Click **"Manager"** → **"Update All"**

**[Screenshot: ComfyUI Manager update]**

**Optional - Follow Update Progress:**
1. Go back → Click terminal link
2. Navigate to `logs/` folder
3. Paste monitoring command
4. Watch live update progress

**[Screenshot: Update log monitoring]**

### Step 4: Restart
1. After update: Click **"Restart"**
2. Press **F5** to refresh
3. ComfyUI reloads

**[Screenshot: Restart confirmation]**

---

### Step 5: Install VibeVoice + RVC

**For Patreon Supporters:**

1. Go to `workspace/ComfyUI/`
2. Drag and drop **"RunPod ComfyUI Installer"**
3. Open Terminal
4. Copy and paste installation commands
5. Press Enter
6. Wait for completion

**[Screenshot: ComfyUI installation commands]**

### Step 6: Final Restart
1. Go back to ComfyUI
2. Click **"Manager"** → **"Restart"**
3. Press **F5** to refresh

**[Screenshot: Final restart]**

### Step 7: Load Workflow
1. Download workflow from Patreon
2. Drag and drop into ComfyUI
3. Workflow loads with all nodes

**[Screenshot: Workflow loaded on RunPod]**

---

### Step 8: First Test Run

**Important:** Run a test generation first!
1. Upload a sample audio file
2. Enter simple test text
3. Click **Run**
4. Models download automatically
5. Creates necessary folder structure

**[Screenshot: First test run progress]**

---

### Step 9: Install RVC Models

**Locate Models Folder:**
1. Navigate to: `ComfyUI/models/TTS/RVC/`
2. Upload `.pth` files here
3. **Show Hidden Files:** View → Show Hidden Files
4. Reveal `.index/` folder
5. Upload `.index` files to `.index/` folder

**[Screenshot: Hidden index folder revealed]**

**Refresh Models:**
- Press **R** on keyboard
- Models appear in dropdowns

**[Screenshot: Models appearing in node dropdowns]**

---

## Best Practices

### Audio Sample Quality

**For Best Results:**
- ✅ **Length:** 10-30 seconds (longer usually better)
- ✅ **Clarity:** Clear speech, no background noise
- ✅ **Quality:** High bitrate audio (128kbps+ for MP3)
- ✅ **Content:** Natural speaking, no music/effects
- ✅ **Single speaker:** No multiple voices in sample

**[Screenshot: Good vs bad audio samples]**

---

### Script Writing Tips

**General Guidelines:**
- Write naturally as you would speak
- Include punctuation for proper pauses
- Use quotation marks for emphasis
- Keep paragraphs reasonable length

**Multi-Speaker Scripts:**
- Always label speakers clearly
- Use consistent naming
- Start new line for each speaker change

---

### Choosing Between Platforms

**Use Web UI When:**
- ✅ Single speaker generation
- ✅ Want highest possible quality
- ✅ Simple, quick tasks
- ✅ Don't need RVC integration

**Use ComfyUI When:**
- ✅ Multiple speakers (3+)
- ✅ Want automated RVC enhancement
- ✅ Need workflow automation
- ✅ Complex multi-language scenarios
- ✅ Batch processing

---

### Optimization Tips

**For Faster Generation:**
1. Keep diffusion steps at **20** for single speaker
2. Use **Sage Attention** if available
3. Use appropriate GPU (24GB+ VRAM)

**For Better Quality:**
1. Increase diffusion steps to **40-50** (multi-speaker)
2. Use high-quality audio samples
3. Apply RVC enhancement for final output
4. Test different pitch values

**For Stability:**
1. ComfyUI better for 3+ speakers
2. Increase diffusion steps with multiple languages
3. Keep audio samples consistent quality

---

### Troubleshooting

**Voice Sounds Too High/Low:**
- Adjust pitch value in RVC (+/- 1-3)
- Try different RVC model

**Poor Quality Output:**
- Check source audio quality
- Increase diffusion steps
- Try Web UI for single speaker
- Apply RVC enhancement

**Multi-Speaker Audio Glitches:**
- Switch to ComfyUI workflow
- Increase diffusion steps to 40-50
- Ensure proper script formatting

**Model Not Loading:**
- Verify model is fully downloaded
- Check file paths are correct
- Restart application

---

## Comparison: VibeVoice vs Competitors

### VibeVoice Advantages

✅ **Completely Free**  
✅ **Runs Locally** (no privacy concerns)  
✅ **10-second voice cloning**  
✅ **Multiple language support**  
✅ **Near-perfect quality**  
✅ **Multi-speaker conversations**  
✅ **No usage limits**  
✅ **Active development**

### vs ElevenLabs
- **Cost:** VibeVoice free vs ElevenLabs paid subscription
- **Quality:** Comparable or better
- **Privacy:** Local processing vs cloud
- **Limits:** None vs subscription tiers

### vs Index TTS 2
- **Quality:** VibeVoice superior
- **Speed:** VibeVoice faster
- **Multi-language:** VibeVoice better

**[Screenshot: Quality comparison chart]**

---

## Creative Use Cases

### Content Creation
- YouTube voiceovers
- Podcast generation
- Audiobook narration
- Character voices for videos

### Localization
- Translate content to multiple languages
- Maintain same voice across languages
- Dub videos with original actor's voice

### Entertainment
- Create conversations between celebrities
- Generate character dialogues
- Make comedy skits
- Role-play scenarios

### Accessibility
- Convert text content to speech
- Create audio versions of documents
- Assist visually impaired users

### Business
- Generate training materials
- Create promotional content
- Multilingual announcements
- Automated customer service scripts

---

## Ethical Considerations

**Important Reminders:**

⚠️ **Consent:** Only clone voices with permission  
⚠️ **Disclosure:** Clearly label AI-generated content  
⚠️ **No Impersonation:** Don't pretend to be someone else  
⚠️ **Respect Copyright:** Don't use for fraudulent purposes  
⚠️ **Legal Compliance:** Follow local laws and regulations

**Recommended Use:**
- Personal projects
- Educational content
- Clearly labeled creative works
- With proper permissions

---

## Resources

### Official Links
- **Patreon:** [https://www.patreon.com/aitrepreneur](https://www.patreon.com/aitrepreneur)
- **Discord:** [Join Server](https://discord.gg/3ErYSdyUPt)
- **RunPod:** [Sign Up](https://bit.ly/runpodAi)
- **Manual Installation:** [Pastebin Guide](https://pastebin.com/FX07hPLc)

### Community Resources
- **Voice Models:** [voice-models.com](https://voice-models.com)
- **RVC Models:** Community-trained on voice-models.com

### Patreon Exclusive Content
- One-click installers (Web UI, RVC, ComfyUI)
- RunPod installers
- ComfyUI workflow files
- Priority support

---

## Conclusion

VibeVoice represents a breakthrough in accessible, high-quality text-to-speech technology. Combined with RVC, it provides professional-grade voice cloning that rivals or exceeds paid services—completely free and running on your own hardware.

**Key Takeaways:**
- ✅ 10 seconds of audio = perfect voice clone
- ✅ Web UI for simplicity, ComfyUI for advanced features
- ✅ Multi-language and multi-speaker support
- ✅ Optional RVC enhancement for extra quality
- ✅ RunPod for cloud-based generation

Whether you're a content creator, developer, or just exploring AI voice technology, VibeVoice is the ultimate local TTS solution.

---

## Quick Reference

### Web UI Workflow
```
1. Download & Load Model
2. Upload Voice Sample (10-30 seconds)
3. Name & Add Custom Voice
4. Select Voice from Dropdown
5. Enter Script
6. Generate Podcast
```

### ComfyUI Workflow
```
1. Load Workflow
2. Input Text (use [1], [2] for multi-speaker)
3. Select Voice(s)
4. Configure RVC (optional)
5. Set Diffusion Steps (20-50)
6. Run
7. Get Two Outputs (VibeVoice + RVC)
```

### RVC Enhancement
```
1. Generate with VibeVoice
2. Download RVC model from voice-models.com
3. Install model files
4. Load model in RVC
5. Input audio path
6. Adjust pitch (0 for same voice)
7. Convert
```

---

## Credits

**Video Creator:** Aitrepreneur  
**Original Video:** [Watch on YouTube](https://www.youtube.com/watch?v=XtaPZmlyMMw)  
**Tutorial Based On:** Full video transcript

---

*Note: This tutorial is based on the video transcript. For actual screenshots and visual examples, please watch the original video at the link provided above.*

---

## Appendix: Script Templates

### Template 1: Single Speaker
```
[Your text here. Write naturally with proper punctuation 
and paragraph breaks for natural-sounding speech.]
```

### Template 2: Two-Speaker Conversation (Web UI)
```
Speaker 1: First character's dialogue here.
Speaker 2: Second character responds.
Speaker 1: First character continues.
Speaker 2: Second character replies.
```

### Template 3: Two-Speaker Conversation (ComfyUI)
```
[1] First character's dialogue here.
[2] Second character responds.
[1] First character continues.
[2] Second character replies.
```

### Template 4: Multi-Speaker (ComfyUI)
```
[1] First speaker's line.
[2] Second speaker's line.
[3] Third speaker's line.
[1] First speaker continues.
[2] Second speaker responds.
[4] Fourth speaker joins.
```
