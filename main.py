import logging
import os

from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from prompt_engine import eval_prompt

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

START_STATE, DIALOGUE_STATE, LOCATION, BIO = range(4)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Hi! write me to start a conversation."
    )

    return START_STATE


async def dialogue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    request = update.message.text
    dialogue_context = context.user_data.get('dialogue')
    response = eval_prompt(request, dialogue_context)
    if dialogue_context:
        dialogue_context.extend([{'role': 'user', 'content': request},
                                 {'role': 'assistant', 'content': response}])
        if len(dialogue_context) > 20:
            dialogue_context = dialogue_context[1:]
    else:
        dialogue_context = [{'role': 'user', 'content': request},
                            {'role': 'assistant', 'content': response}]

    context.user_data['dialogue'] = dialogue_context

    await update.message.reply_text(
        text=response
    )

    return DIALOGUE_STATE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text(
        "Bye! I hope we can talk again some day.", reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


def main() -> None:
    application = Application.builder().token(os.environ.get('TG_TOKEN_GPT')).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            START_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, dialogue)],
            DIALOGUE_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, dialogue)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
