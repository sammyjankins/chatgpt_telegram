import os

import openai

api_endpoint = 'https://api.openai.com/v1/completions'

openai.api_key = os.environ.get('OPEN_AI_KEY')


def eval_prompt(request, context=None):
    if context:
        dialogue = ''.join([f"1: {item[0]}\n2: {item[1]}\n" for item in context])
        prompt = f"continue the dialogue -\n{dialogue}1: {request}\n2: "
    else:
        prompt = request
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=prompt,
        max_tokens=400,
        temperature=0.8
    )
    return response['choices'][0]['text']

