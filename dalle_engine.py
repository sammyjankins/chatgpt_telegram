import os

import openai

api_endpoint = 'https://api.openai.com/v1/images/generations'

openai.api_key = os.environ.get('OPEN_AI_KEY')


def request_image_dalle(prompt):
    response = openai.Image.create(
        prompt=prompt,
        n=1,
        size="1024x1024"
    )
    return [item['url'] for item in response['data']]


def request_image_edit_dalle(prompt, image_path, mask_path):
    with (open(image_path, "rb") as img, open(mask_path, "rb") as mask):
        response = openai.Image.create_edit(
            image=img,
            prompt=prompt,
            mask=mask,
            n=1,
            size="1024x1024"
        )
    os.remove(image_path)
    os.remove(mask_path)
    return response['data'][0]['url']


def request_image_variation_dalle(image_path):
    with open(image_path, "rb") as img:
        response = openai.Image.create_variation(
            image=img,
            n=1,
            size="1024x1024"
        )
    os.remove(image_path)
    return response['data'][0]['url']
