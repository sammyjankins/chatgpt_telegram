import os

import openai
import tiktoken

api_endpoint = 'https://api.openai.com/v1/chat/completions'

openai.api_key = os.environ.get('OPEN_AI_KEY')

SYSTEM_MESSAGE = ("You are a precise and helpful teaching assistant. You explain concepts in great depth using "
                  "simple terms. You analyze the entire dialogue and communicate with the user in his language."
                  "In the end of your responses add a separator <::> "
                  "after the separator put the communication language's googletrans LANGCODE constant")


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

    num_tokens = sum(tokens_per_message +
                     sum(len(encoding.encode(value)) + (tokens_per_name if key == "name" else 0)
                         for key, value in message.items())
                     for message in messages)

    num_tokens += 3

    return num_tokens >= 3000