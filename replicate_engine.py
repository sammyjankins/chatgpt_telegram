import replicate


def request_image_stable_diffusion(prompt):

    image_url = replicate.run(
        "stability-ai/stable-diffusion:27b93a2413e7f36cd83da926f3656280b2931564ff050bf9575f1fdf9bcd7478",
        input={"prompt": prompt,
               "num_inference_steps": 125,
               "negative_prompt": "boring background, simple background, out of frame, ugly, extra limbs, bad anatomy,"
                                  "gross proportions, blurry, jpeg artifacts, normal quality"}
    )[0]

    return image_url
