from asyncio import sleep

from googletrans import Translator


async def detect_and_translate(text, language='en'):
    translator = Translator()

    while True:
        try:
            translation = translator.translate(text, dest=language)
            break
        except Exception as e:
            print('googletrans failed one more time')
            await sleep(2)
    return translation.text
