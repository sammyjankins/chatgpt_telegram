import os

import openai
import tiktoken

api_endpoint = 'https://api.openai.com/v1/chat/completions'

openai.api_key = os.environ.get('OPEN_AI_KEY')

SYSTEM_MESSAGE = ("You are a precise and helpful teaching assistant. You explain concepts in great depth using "
                  "simple terms. You communicate with the user in his language."
                  "At the end of every response to the user, add the following ||| constant value "
                  "of the user's language available for googletrans.")


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
        temperature=0.4
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


def text_to_img_prompt():
    messages = [
        {'role': 'system', 'content': "You are the system designed to compose prompts for generating "
                                      "images to dall.e. When the user asks to generate a prompt, you randomly choose "
                                      "from various possible image options and modifiers. The response to the user "
                                      "should contain only the text of the requested prompt to generate the image"},
        {'role': 'user', 'content': "Come up with any prompt to generate an image to the dall.e system."
                                    "Your answer should contain only the text of the requested prompt"},
    ]
    response = openai.ChatCompletion.create(
        messages=messages,
        model="gpt-3.5-turbo",
        max_tokens=100,
        temperature=1
    )
    return response['choices'][0]["message"]["content"]


def error_prompt():
    messages = [
        {'role': 'system', 'content': "You are a chatbot that reluctantly answers questions with sarcastic responses"},
        {'role': 'user', 'content': "Sarcastically funny notification about an error due to which the bot cannot "
                                    "respond to the user's message and request to resend the message. "
                                    "Provide only the message text."},
    ]
    response = openai.ChatCompletion.create(
        messages=messages,
        model="gpt-3.5-turbo",
        max_tokens=200,
        temperature=1
    )
    return response['choices'][0]["message"]["content"]
