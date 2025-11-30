I'm currently working on a new AI filmmaking workflow that I think you'll really like! One part of it will be the ability to accurately move the camera around in your scene.


For that, I wanted to see if the Qwen Image model could generate 360-degree equirectangular images, but unfortunately the results weren't great.


So I created a dataset of 20 equirectangular HDRI image pairs of different scenes (CC0 licensed) from Polyhaven.com to train my own Qwen Image Edit LoRA. I trained the LoRA on Runpod using Ostris guide.

👉Runpod for Lora Training https://runpod.io?ref=o2xn5klc*

👉 Guide I followed: https://youtu.be/0IaY8V5hCdU?si=EaeenLVqb0q59UCq

The results with the LoRA aren't perfect yet, but they're MUCH BETTER than the base model!

Just download the workflow & LoRA below and start generating.


Download the models and place them in your ComfyUI folders.

Your Input image

You can change the padding here.

Use a prompt like: "Create a 360 panoramic image of [very short description of surrounding scene]. An HDRI image captured on a 360 degree camera, insta 360, equirectagular projection. Keep the style the same."

Change the seed if you are not happy with the result.

This is still work in progress, but I wanted to share it early so you can test it out. I think it'll be a useful feature for many of you! Let me know if you have any feedback on Discord.

*This is an affiliate link. Use it at no extra cost for you!

Attachments

Download all
251018_MICKMUMPITZ_QWEN-EDIT_360_03.safetensors

251018_MICKMUMPITZ_QWEN-IMAGE-EDIT-360_1-0.json