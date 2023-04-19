import logging
import os

from openai.error import RateLimitError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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

from chat_prompt_engine import eval_prompt, num_tokens_from_messages, send_prompt, text_to_img_prompt, error_prompt
from dalle_engine import request_image_dalle, request_image_edit_dalle, request_image_variation_dalle
from trans_to_en import detect_and_translate

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

(START_STATE,
 DIALOGUE_STATE,
 ASKING_PROMPT_STATE,
 RETURN_GEN_IM_STATE,
 ASKING_IM_TO_EDIT_STATE,
 CHOSING_IMAGE_MODE_STATE,
 TEXT_TO_IMAGE_CB,
 IMAGE_EDIT_CB,
 IMAGE_VARI_CB,
 BOT_PROMPT_CB,
 ASKING_PROMPT_TO_EDIT_STATE,
 ASKING_MASK_TO_EDIT_STATE,
 ASKING_IM_TO_VARI_STATE,
 ) = range(13)

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


async def start_image_processing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info(f"User {user.username} requested image processing.")

    language = context.user_data.get('language') or 'en'

    buttons = [
        [
            InlineKeyboardButton(text=await detect_and_translate("Image Generation", language),
                                 callback_data=str(TEXT_TO_IMAGE_CB)),
        ],
        [
            InlineKeyboardButton(text=await detect_and_translate("Image Editing", language),
                                 callback_data=str(IMAGE_EDIT_CB)),
        ],
        [
            InlineKeyboardButton(text=await detect_and_translate("Image Variation", language),
                                 callback_data=str(IMAGE_VARI_CB)),
        ],
        [
            InlineKeyboardButton(text=await detect_and_translate("Cancel", language), callback_data=str(END_CB)),
        ],

    ]
    keyboard = InlineKeyboardMarkup(buttons)

    text = "Select image processing method"
    await update.message.reply_text(
        await detect_and_translate(text, language), reply_markup=keyboard
    )

    return CHOSING_IMAGE_MODE_STATE


async def dialogue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    request = update.message.text
    user = update.message.from_user
    language = context.user_data.get('language') or 'en'

    logger.info(f"A request was received from the user {user.username}.")

    dialogue_context = context.user_data.setdefault('dialogue', [])

    while num_tokens_from_messages(eval_prompt(request, dialogue_context)):
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

    if '###' not in response:
        text = error_prompt()
        await update.message.reply_text(await detect_and_translate(text, language))
        return DIALOGUE_STATE

    response_text, language = response.split('###')
    context.user_data['language'] = language.strip()

    dialogue_context.extend([{'role': 'user', 'content': request},
                             {'role': 'assistant', 'content': response}])

    context.user_data['dialogue'] = dialogue_context

    await update.message.reply_text(
        text=response_text
    )

    return DIALOGUE_STATE


async def image_generation_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language = context.user_data.get('language') or 'en'

    user = update.callback_query.from_user
    logger.info(f"User {user.username} requested image generation.")

    buttons = [
        [
            InlineKeyboardButton(text=await detect_and_translate("Cancel", language), callback_data=str(END_CB)),
        ],
        [
            InlineKeyboardButton(text=f'{await detect_and_translate("Prompt from", language)} Xen',
                                 callback_data=str(BOT_PROMPT_CB)),
        ],

    ]
    keyboard = InlineKeyboardMarkup(buttons)

    text = "Provide text to generate image"
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=await detect_and_translate(text, language), reply_markup=keyboard
                                   )

    return ASKING_PROMPT_STATE


async def image_generation_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        request = update.message.text
        user = update.message.from_user
        prompt = await detect_and_translate(request)
    else:
        user = update.callback_query.from_user
        prompt = text_to_img_prompt()

    language = context.user_data.get('language') or 'en'
    logger.info(f"User {user.username} received generated image.")

    buttons = [
        [
            InlineKeyboardButton(text=await detect_and_translate("Cancel", language), callback_data=str(END_CB)),
        ],
        [
            InlineKeyboardButton(text=f'{await detect_and_translate("Prompt from", language)} Xen',
                                 callback_data=str(BOT_PROMPT_CB)),
        ],
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await update.effective_chat.send_photo(request_image_dalle(prompt)[0])

    text = f'Prompt: {prompt}\n' \
           'You can send another text to generate a new image or return to the dialogue by pressing "Cancel"'

    if update.message:
        await update.message.reply_text(
            text=await detect_and_translate(text, language),
            reply_markup=keyboard
        )
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=await detect_and_translate(text, language), reply_markup=keyboard)

    return RETURN_GEN_IM_STATE


async def image_edit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language = context.user_data.get('language') or 'en'

    user = update.callback_query.from_user
    logger.info(f"User {user.username} requested editing image.")

    buttons = [
        [
            InlineKeyboardButton(text=await detect_and_translate("Cancel", language), callback_data=str(END_CB)),
        ],

    ]
    keyboard = InlineKeyboardMarkup(buttons)

    text = 'Please send an image to edit. It must be a png file no larger than 4 mb with equal width and height.'
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=await detect_and_translate(text, language), reply_markup=keyboard)
    return ASKING_IM_TO_EDIT_STATE


async def image_mask_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language = context.user_data.get('language') or 'en'

    user = update.message.from_user
    logger.info(f"User {user.username} sent an image to edit.")

    file = await context.bot.get_file(update.message.document.file_id)
    f_name = file.file_path.split('/')[-1]
    context.user_data['img_to_edit'] = f_name
    await file.download_to_drive(f_name)

    buttons = [
        [
            InlineKeyboardButton(text=await detect_and_translate("Cancel", language), callback_data=str(END_CB)),
        ],

    ]
    keyboard = InlineKeyboardMarkup(buttons)

    text = 'Please send the mask. It must be a png file no larger than 4 mb the same size as the original image.' \
           'The mask must have a transparent area'
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=await detect_and_translate(text, language), reply_markup=keyboard)
    return ASKING_MASK_TO_EDIT_STATE


async def image_edit_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language = context.user_data.get('language') or 'en'

    user = update.message.from_user
    logger.info(f"User {user.username} sent the mask to edit.")

    file = await context.bot.get_file(update.message.document.file_id)
    f_name = file.file_path.split('/')[-1]
    context.user_data['mask_to_edit'] = f_name
    await file.download_to_drive(f_name)

    buttons = [
        [
            InlineKeyboardButton(text=await detect_and_translate("Cancel", language), callback_data=str(END_CB)),
        ],

    ]
    keyboard = InlineKeyboardMarkup(buttons)

    text = 'Please provide a prompt to edit image.'
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=await detect_and_translate(text, language), reply_markup=keyboard)
    return ASKING_PROMPT_TO_EDIT_STATE


async def image_edit_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    request = update.message.text
    prompt = await detect_and_translate(request)

    language = context.user_data.get('language') or 'en'

    text = 'The image has been edited. Please wait for result.'
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=await detect_and_translate(text, language))
    await update.effective_chat.send_photo(request_image_edit_dalle(prompt, context.user_data['img_to_edit'],
                                                                    context.user_data['mask_to_edit']))

    user = update.message.from_user
    logger.info(f"User {user.username} received edited image.")

    return await start_image_processing(update, context)


async def image_variation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language = context.user_data.get('language') or 'en'

    user = update.callback_query.from_user
    logger.info(f"User {user.username} requested image variation.")

    buttons = [
        [
            InlineKeyboardButton(text=await detect_and_translate("Cancel", language), callback_data=str(END_CB)),
        ],

    ]
    keyboard = InlineKeyboardMarkup(buttons)

    text = 'Please send an image to create variations. It must be a png file no larger than ' \
           '4 mb with equal width and height.'
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=await detect_and_translate(text, language), reply_markup=keyboard)
    return ASKING_IM_TO_VARI_STATE


async def image_variation_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language = context.user_data.get('language') or 'en'

    file = await context.bot.get_file(update.message.document.file_id)
    f_name = file.file_path.split('/')[-1]
    await file.download_to_drive(f_name)

    text = 'The variation of the image was created. Please wait for result.'
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=await detect_and_translate(text, language))
    await update.effective_chat.send_photo(request_image_variation_dalle(f_name))

    user = update.message.from_user
    logger.info(f"User {user.username} received image variation.")

    return await start_image_processing(update, context)


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
                CommandHandler("images", start_image_processing),
            ],
            CHOSING_IMAGE_MODE_STATE: [
                CallbackQueryHandler(image_generation_prompt_handler, pattern="^" + str(TEXT_TO_IMAGE_CB) + "$"),
                CallbackQueryHandler(image_edit_handler, pattern="^" + str(IMAGE_EDIT_CB) + "$"),
                CallbackQueryHandler(image_variation_handler, pattern="^" + str(IMAGE_VARI_CB) + "$"),
            ],
            ASKING_PROMPT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, image_generation_session),
                CallbackQueryHandler(image_generation_session, pattern="^" + str(BOT_PROMPT_CB) + "$"),
            ],
            RETURN_GEN_IM_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, image_generation_session),
                CallbackQueryHandler(image_generation_session, pattern="^" + str(BOT_PROMPT_CB) + "$"),
            ],
            ASKING_IM_TO_EDIT_STATE: [
                MessageHandler(filters.ATTACHMENT, image_mask_handler),
            ],
            ASKING_MASK_TO_EDIT_STATE: [
                MessageHandler(filters.ATTACHMENT, image_edit_prompt_handler),
            ],
            ASKING_PROMPT_TO_EDIT_STATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, image_edit_result),
            ],
            ASKING_IM_TO_VARI_STATE: [
                MessageHandler(filters.ATTACHMENT, image_variation_result),
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
