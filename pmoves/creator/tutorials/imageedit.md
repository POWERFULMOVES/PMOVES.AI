1-Click INSTALL QWEN IMAGE EDIT 2509 (PLUS) ComfyUI WebUI!
Creator profile picture
Aitrepreneur
September 27


27

134


EDIT 1st October: I updated the workflow (https://www.patreon.com/posts/qwen-image-edit-139876435) for the people who had those weird "ghosting" issues, this should solve the problem. DO NOT ALSO FORGET, to dl the
Qwen-Image-Edit-Lightning-4steps lora (EDIT not NORMAL like before), either use this link :
https://huggingface.co/Aitrepreneur/FLX/resolve/main/Qwen-Image-Edit-Lightning-4steps-V1.0.safetensors?download=true
to dl the lora into the ComfyUI_windows_portable\ComfyUI\models\loras folder
or just use the nodes model installer if you need it.
I explain it + color editing trick in this short update video: https://youtu.be/-DRDZZd2zKs
I will update the workflow further once nunchaku get the lora support ready


Hey everyone! I've created a 1-click installer for "THE NEW OPEN-SOURCE NANO BANANA COMPETITOR!", called "QWEN IMAGE EDIT 2509 (PLUS)". And it’s basically Qwen image edit but much more powerful…A model that is able to automatically edits multiple images together with just a simple text prompt with insane precision!

You can check out the video right here: https://youtu.be/1VzPOLkcN64

The workflow: https://www.patreon.com/posts/139876435

The installer of course automates the entire install process for comfyUI and the models downloads!


LOCAL INSTALL!!! RECOMMENDED TO START FROM SCRATCH SINCE YOU NEED THE LATEST COMFYUI TORCH VERSION!!!

Download the QWEN-IMAGE-EDIT-PLUS-COMFYUI-MANAGER_AUTO_INSTALL.bat

Run the bat file and select either option 1, 2 or 3 depending on your GPU vram.

Wait for the install to finish

The webui will launch, load the QWEN-IMAGE-EDIT-PLUS_ULTRA.json file and there you go😎

DON'T FORGET TO GO UPDATE COMFYUI BY GOING INSIDE THE UPDATE FOLDER AND RUNNING THE COMFYUI UPDATE BAT FILE!!!!




IF YOU ALREADY HAVE COMFYUI INSTALLED USING A PREVIOUS INSTALLER:

Download the QWEN-IMAGE-EDIT-PLUS-MODELS-NODES_INSTALL.bat and place it in the ComfyUI_windows_portable\ComfyUI folder

Run the bat file and select either option 1, 2 or 3 depending on your GPU vram.

Wait for the install to finish

???

Profit 😎


IF YOU GET AN ERROR WHEN LAUNCHING COMFYUI AFTER USING THIS INSTALLER SAYING "AssertionError: Torch not compiled with CUDA enabled" it's ok don't panic.

Just go inside the python embedded folder, click on the folder path, type cmd press enter, this will bring the command prompt window and there type:

python.exe -m pip uninstall torch

python.exe -s -m pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

--->replace cu128 by your cuda version (if you don't know your cuda version just open a new cmd window and type nvcc --version it will then tell you at the end Cuda compilation tools, release 12.8, V12.8.93 or something different like 12.6, in that case just use cu126 instead of cu128)



IF YOU ARE USING RUNPOD:

Create an account if you haven't already: Runpod

Click on Pod (on the left side) then click deploy

Choose a GPU with at least 24gb of VRAM (4090 is best), click here for the comfyui template (aitrepreneur/comfyui), then edit the template and choose 80gb for both the container and volume disk, then deploy on demand

Go to my pods, wait for everything to finish and then click "connect", then "Connect to HTTP SERVICE port 3000" and click on the manager to update comfyui and restart it

Then go to the port 8888, go inside the comfyui folder and then drag and drop the QWEN-IMAGE-EDIT-PLUS-AUTO_INSTALL-RUNPOD.sh file on the left side of the UI then click on the "Terminal" icon on the right side on the UI

Copy and paste these two lines then press enter:

chmod +x QWEN-IMAGE-EDIT-PLUS-AUTO_INSTALL-RUNPOD.sh

./QWEN-IMAGE-EDIT-PLUS-AUTO_INSTALL-RUNPOD.sh

Wait for everything to be installed

Go back to the port 3000 and click on the manager, choose the Nightly build and restart it

Load the QWEN-IMAGE-EDIT-PLUS_ULTRA.json file and there you go😎

Also use the command:

tail -f comfyui.log

inside the workspace/logs to get the real time logs so that you always know when the install is done. It will then ask you to restart, so click on that restart button, wait for the webui to reboot, click refresh once it's done and there you go.


IF YOU ARE USING RUNPOD AND YOU WANT TO STOP THE POD THEN RESTART IT:

Go inside your pod

SERVICE port 8888

Go inside the Comfyui folder, open a terminal icon and re copy and paste those two lines:

chmod +x QWEN-IMAGE-EDIT-PLUS-AUTO_INSTALL-RUNPOD.sh

./QWEN-IMAGE-EDIT-PLUS-AUTO_INSTALL-RUNPOD.sh

And then in a few seconds it will reinstall all the requirements for the nodes

Go back to comfyui port 3000, click on manager, click update all, wait for everything to be updated then restart.


Re drag and drop the QWEN-IMAGE-EDIT-PLUS_ULTRA.json file inside and there you go😎

As always, supporting me on Patreon allows me to keep creating helpful resources like this for the community. Thank you for your support - now go have some fun😉!

Attachments

