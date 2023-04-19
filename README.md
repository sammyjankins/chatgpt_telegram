# chatgpt_telegram
 Simple script to use model gpt-3.5-turbo in telegram + image generation

httpx must be updated to the last version.

In the file "client.py" you need to change line 62 to:
```
proxies: typing.Dict[str, httpcore.AsyncHTTPProxy] = None,
```
