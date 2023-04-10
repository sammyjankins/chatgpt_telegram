import os

import openai

api_endpoint = 'https://api.openai.com/v1/images/generations'

openai.api_key = os.environ.get('OPEN_AI_KEY')


def request_image(prompt):
    response = openai.Image.create(
        prompt=prompt,
        n=3,
        size="512x512"
    )
    return [item['url'] for item in response['data']]
