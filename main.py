import logging
import os

from openai.error import RateLimitError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

from chat_prompt_engine import eval_prompt, num_tokens_from_messages, send_prompt
from dalle_engine import request_image

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

(START_STATE,
 DIALOGUE_STATE,
 ASKING_PROMPT_STATE,
 RETURN_GEN_IM_STATE) = range(4)

END_CB = ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data.get('dialogue'):
        context.user_data.clear()
        await update.message.reply_text(
            "The dialogue was reset, now I don't remember anything we discussed."
        )
    else:
        await update.message.reply_text(
            "Hi! write me to start a conversation."
        )

    return DIALOGUE_STATE


async def dialogue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    request = update.message.text
    user = update.message.from_user

    dialogue_context = context.user_data.setdefault('dialogue', [])

    while num_tokens := num_tokens_from_messages(eval_prompt(request, dialogue_context)):
        logger.info("User %s using %s tokens.", user.first_name, num_tokens)
        context.user_data['dialogue'] = context.user_data.get('dialogue')[1:]
        dialogue_context = context.user_data.get('dialogue')

    messages = eval_prompt(request, dialogue_context)

    try:
        response = send_prompt(messages)
    except RateLimitError:
        await update.message.reply_text(
            text='That model is currently overloaded with other requests. You can retry your request.'
        )
        return DIALOGUE_STATE

    dialogue_context.extend([{'role': 'user', 'content': request},
                             {'role': 'assistant', 'content': response}])

    context.user_data['dialogue'] = dialogue_context

    await update.message.reply_text(
        text=response
    )

    return DIALOGUE_STATE


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    context.user_data.clear()
    await update.message.reply_text(
        "Bye! I hope we can talk again some day.", reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


async def image_generation_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info("User %s requested image generation.", user.first_name)

    buttons = [
        [
            InlineKeyboardButton(text="Cancel", callback_data=str(END_CB)),
        ],

    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(
        "Provide text to generate image", reply_markup=keyboard
    )

    return ASKING_PROMPT_STATE


def compile_media_group(links):
    media_group = []

    for link in links:
        media_group.append(InputMediaPhoto(link))

    return media_group


async def image_generation_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    request = update.message.text
    buttons = [
        [
            InlineKeyboardButton(text="Cancel", callback_data=str(END_CB)),
        ],

    ]
    keyboard = InlineKeyboardMarkup(buttons)

    images_links = request_image(request)

    await update.effective_chat.send_media_group(compile_media_group(images_links))
    await update.message.reply_text(
        f'You can provide another text for image generation or return to dialogue by pressing "Cancel"',
        reply_markup=keyboard
    )
    return RETURN_GEN_IM_STATE


async def continue_dialogue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="You have returned to the dialogue mode and we can continue the conversation."
    )

    return DIALOGUE_STATE


def main() -> None:
    application = Application.builder().token(os.environ.get('TG_TOKEN_GPT')).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            DIALOGUE_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, dialogue),
                CommandHandler("start", start),
                CommandHandler("generate", image_generation_prompt_handler)
            ],
            ASKING_PROMPT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, image_generation_session),
            ],
            RETURN_GEN_IM_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, image_generation_session),
            ],
        },
        fallbacks=[
            CommandHandler("stop", stop),
            CallbackQueryHandler(continue_dialogue, pattern="^" + str(END_CB) + "$"),
        ],
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
