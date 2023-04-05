import os

import openai

api_endpoint = 'https://api.openai.com/v1/chat/completions'

openai.api_key = os.environ.get('OPEN_AI_KEY')

SYSTEM_MESSAGE = ("You are a precise and helpful teaching assistant. You explain concepts in great depth using "
                  "simple terms. You analyze the entire dialogue and communicate with the user in his language.")


def eval_prompt(request, context=None):
    messages = [
        {'role': 'system', 'content': SYSTEM_MESSAGE},
        {'role': 'user', 'content': request},
    ]
    if context:
        messages = context + messages

    response = openai.ChatCompletion.create(
        messages=messages,
        model="gpt-3.5-turbo",
        max_tokens=800,
        temperature=0.6
    )
    return response['choices'][0]["message"]["content"]
