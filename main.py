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
from dalle_engine import request_image_dalle
from replicate_engine import request_image_stable_diffusion
from trans_to_en import detect_and_translate

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

(START_STATE,
 DIALOGUE_STATE,
 ASKING_PROMPT_STATE,
 RETURN_GEN_IM_STATE,
 MODEL_CHOSING_STATE,
 MODEL_DALLE_CB,
 MODEL_STAB_DIFF_CB,
 ) = range(7)

END_CB = ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language = context.user_data.get('language') or 'en'

    if context.user_data.get('dialogue'):
        context.user_data.clear()
        text = "The dialogue was reset, now I don't remember anything we discussed."
    else:
        text = "Hi! write me to start a conversation."

    await update.message.reply_text(await detect_and_translate(text, language))

    return DIALOGUE_STATE


async def dialogue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    request = update.message.text
    user = update.message.from_user
    language = context.user_data.get('language') or 'en'

    logger.info(f"A request was received from the user {user.username}.")

    dialogue_context = context.user_data.setdefault('dialogue', [])

    while num_tokens := num_tokens_from_messages(eval_prompt(request, dialogue_context)):
        logger.info(f"User {user.first_name} using {num_tokens} tokens.")
        context.user_data['dialogue'] = context.user_data.get('dialogue')[1:]
        dialogue_context = context.user_data.get('dialogue')

    messages = eval_prompt(request, dialogue_context)

    try:
        response = send_prompt(messages)
        logger.info("A response was received from the model.")
    except RateLimitError:
        text = 'That model is currently overloaded with other requests. You can retry your request.'
        await update.message.reply_text(await detect_and_translate(text, language))
        return DIALOGUE_STATE

    response_text, language = response.split('<::>')
    context.user_data['language'] = language.strip()

    dialogue_context.extend([{'role': 'user', 'content': request},
                             {'role': 'assistant', 'content': response_text}])

    context.user_data['dialogue'] = dialogue_context

    await update.message.reply_text(
        text=response_text
    )

    return DIALOGUE_STATE


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    language = context.user_data.get('language') or 'en'

    logger.info(f"User {user.username} canceled the conversation.")
    context.user_data.clear()
    text = "Bye! I hope we can talk again some day."
    await update.message.reply_text(
        await detect_and_translate(text, language), reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


async def image_generation_model_chosing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info(f"User {user.username} requested image generation.")

    language = context.user_data.get('language') or 'en'

    buttons = [
        [
            InlineKeyboardButton(text="DALL.E", callback_data=str(MODEL_DALLE_CB)),
        ],
        [
            InlineKeyboardButton(text="Stable Diffusion", callback_data=str(MODEL_STAB_DIFF_CB)),
        ],
        [
            InlineKeyboardButton(text=await detect_and_translate("Cancel", language), callback_data=str(END_CB)),
        ],

    ]
    keyboard = InlineKeyboardMarkup(buttons)

    text = "Choose a model for image generation"
    await update.message.reply_text(
        await detect_and_translate(text, language), reply_markup=keyboard
    )

    return MODEL_CHOSING_STATE


async def image_generation_model_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['image_model'] = update.callback_query.data.split('-')[-1]
    return await image_generation_prompt_handler(update, context)


async def image_generation_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.callback_query.from_user
    language = context.user_data.get('language') or 'en'

    logger.info(f"User {user.username} have chosen model for image generation.")

    buttons = [
        [
            InlineKeyboardButton(text=await detect_and_translate("Cancel", language), callback_data=str(END_CB)),
        ],

    ]
    keyboard = InlineKeyboardMarkup(buttons)

    text = "Provide text to generate image"
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=await detect_and_translate(text, language), reply_markup=keyboard
                                   )

    return ASKING_PROMPT_STATE


def compile_media_group(links):
    media_group = []

    for link in links:
        media_group.append(InputMediaPhoto(link))

    return media_group


async def image_generation_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    request = update.message.text
    language = context.user_data.get('language') or 'en'

    buttons = [
        [
            InlineKeyboardButton(text=await detect_and_translate("Cancel", language), callback_data=str(END_CB)),
        ],

    ]
    keyboard = InlineKeyboardMarkup(buttons)
    prompt = await detect_and_translate(request)
    if int(context.user_data['image_model']) == MODEL_DALLE_CB:
        images_links = request_image_dalle(prompt)
        await update.effective_chat.send_media_group(compile_media_group(images_links))
    elif int(context.user_data['image_model']) == MODEL_STAB_DIFF_CB:
        images_link = request_image_stable_diffusion(prompt)
        await update.effective_chat.send_photo(images_link)

    text = f'You can send another text to generate a new image or return to the dialogue by pressing "Cancel"'
    await update.message.reply_text(
        text=await detect_and_translate(text, language),
        reply_markup=keyboard
    )
    return RETURN_GEN_IM_STATE


async def continue_dialogue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language = context.user_data.get('language') or 'en'
    text = "You have returned to the dialogue mode and we can continue the conversation."
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=await detect_and_translate(text, language),
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
                CommandHandler("generate", image_generation_model_chosing),
            ],
            MODEL_CHOSING_STATE: [
                CallbackQueryHandler(image_generation_model_select, pattern="^" + str(MODEL_DALLE_CB) + "$"),
                CallbackQueryHandler(image_generation_model_select, pattern="^" + str(MODEL_STAB_DIFF_CB) + "$"),
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
