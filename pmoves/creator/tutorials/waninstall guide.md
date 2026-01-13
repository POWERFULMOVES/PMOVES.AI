EDIT: COMMON ERROR AND FIXE PLEASE READ:

"self and mat2 must have the same dtype, but got Half and Float8_e4m3fn"
it is a wanvideowrapper node update issue that is not up to date

go into the ComfyUI_windows_portable\ComfyUI\custom_nodes folder

and delete the ComfyUI-WanVideoWrapper folder

then if you click on the folder path, type cmd press enter, it will open a cmd window in that folder and inside you can type:

git clone https://github.com/kijai/ComfyUI-WanVideoWrapper

..\..\python_embeded\python.exe -m pip install -r ComfyUI-WanVideoWrapper\requirements.txt

it will clone the latest version of the node and install the requirements, then you can reopen comfyui and redrag and drop the workflow in again.


PoseAndFaceDetection

[ONNXRuntimeError] : 1 : FAIL : Non-zero status code returned while running QuickGelu node. Name:'/model.0/act/Mul/QuickGeluFusion/' Status Message: CUDA error cudaErrorNoKernelImageForDevice:no kernel image is available for execution on the device

It's usually a 5000 series GPU issue (thanks Nvidia), so for those who have the same error, you can try this:

go inside the ComfyUI_windows_portable\python_embeded folder, click on the folder path, type cmd press enter, this will open a cmd window inside that folder and there type:

python.exe -m pip uninstall -y onnxruntime-gpu

python.exe -m pip install --upgrade "onnxruntime==1.20.1"

finish the install and then relaunch comfyui if everything else was installed



Hey everyone! I've created a 1-click installer for "THE NEW OPEN-SOURCE IMAGE TO VIDEO TO VIDEO KING", called "WAN ANIMATE 2.2 V2". And it’s AN AMAZING VIDEO MODEL that lets you replace ANY character in a video with just a single reference image… or take the motion from one clip and transfer it perfectly onto another character WITH INSANE PRECISION AND with my new workflow, you'll be able to replace ANYTHING inside a video, character, outfits, objects, animals, etc...the sky is the limit!

You can check out the video right here: https://youtu.be/apd68jTrxYc

The workflow: https://www.patreon.com/posts/141515195

The installer of course automates the entire install process for comfyUI and the models downloads!

LOCAL INSTALL!!! RECOMMENDED TO START FROM SCRATCH SINCE YOU NEED THE LATEST COMFYUI TORCH VERSION + SAGE ATTENTION AND TRITON INSTALLED FOR THE BEST SPEED POSSIBLE!

Download the WAN-ANIMATE-COMFYUI-MANAGER_AUTO_INSTALL.bat

Run the bat file

Wait for the install to finish

The webui will launch, load the WAN_ANIMATE_ULTRA_WORKFLOW.json file and there you go😎

DON'T FORGET TO GO UPDATE COMFYUI BY GOING INSIDE THE UPDATE FOLDER AND RUNNING THE COMFYUI UPDATE BAT FILE!!!!



IF YOU ALREADY HAVE COMFYUI INSTALLED USING A PREVIOUS INSTALLER:

Download the WAN-ANIMATE-MODELS-NODES_INSTALL.bat and place it in the ComfyUI_windows_portable\ComfyUI folder

Run the bat file

Wait for the install to finish

???

Profit 😎

IF YOU GET AN ERROR WHEN LAUNCHING COMFYUI AFTER USING THIS INSTALLER SAYING "AssertionError: Torch not compiled with CUDA enabled" it's ok don't panic.

Just go inside the python embedded folder, click on the folder path, type cmd press enter, this will bring the command prompt window and there type:

python.exe -m pip uninstall torch

python.exe -s -m pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

--->replace cu128 by your cuda version (if you don't know your cuda version just open a new cmd window and type nvcc --version it will then tell you at the end Cuda compilation tools, release 12.8, V12.8.93 or something different like 12.6, in that case just use cu126 instead of cu128)


IF YOU ALREADY HAVE COMFYUI INSTALLED AND JUST NEED THE SAGEATTENTION AND TRITON TO INSTALL:
Download the install_triton_and_sageattention_auto.bat and place it in the ComfyUI_windows_portable\python_embeded folder

Run the bat file

Wait for the install to finish

???

Profit 😎



IF YOU ARE USING RUNPOD:

Create an account if you haven't already: Runpod

Click on Pod (on the left side) then click deploy

Choose a GPU with at least 24gb of VRAM (4090 is best), click here for the comfyui template (aitrepreneur/comfyui), then edit the template and choose 80gb for both the container and volume disk, then deploy on demand

Go to my pods, wait for everything to finish and then click "connect", then "Connect to HTTP SERVICE port 3000" and click on the manager to update comfyui and restart it

Then go to the port 8888, go inside the comfyui folder and then drag and drop the WAN-ANIMATE-AUTO_INSTALL-RUNPOD.sh file on the left side of the UI then click on the "Terminal" icon on the right side on the UI

Copy and paste these two lines then press enter:

chmod +x WAN-ANIMATE-AUTO_INSTALL-RUNPOD.sh

./WAN-ANIMATE-AUTO_INSTALL-RUNPOD.sh

Wait for everything to be installed

Go back to the port 3000 and click on the manager and restart it

Load the WAN_ANIMATE_ULTRA_WORKFLOW.json file and there you go😎

Also use the command:

tail -f comfyui.log

inside the workspace/logs to get the real time logs so that you always know when the install is done. It will then ask you to restart, so click on that restart button, wait for the webui to reboot, click refresh once it's done and there you go.

PS: Once again, sorry for being quiet the last few weeks, you guys know the drill by now, if not: A Quick Update on Health, Support & Gratitude ❤️ | Patreon

As always, supporting me on Patreon allows me to keep creating helpful resources like this for the community. Thank you for your support - now go have some fun😉!