import os

import openai
import tiktoken

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

    return messages


def send_prompt(messages):
    response = openai.ChatCompletion.create(
        messages=messages,
        model="gpt-3.5-turbo",
        max_tokens=600,
        temperature=0.6
    )
    return response['choices'][0]["message"]["content"]


def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301"):
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    tokens_per_message = 4
    tokens_per_name = -1
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3
    print(num_tokens)
    return num_tokens >= 3000
