import os
import json
import logging
import random
from telegram import Update, Poll
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, PollAnswerHandler
)

# Load token securely
TOKEN = os.getenv("5503691929:AAHruRPFP3998zJCM4PGHOnmltkFYyeu8zk")
ADMIN_IDS = [5050578106]  # List of admin IDs

# File Paths
CHAT_IDS_FILE = 'chat_ids.json'
LEADERBOARD_FILE = 'leaderboard.json'

# Logger Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load Data Functions
def load_data(file):
    if os.path.exists(file):
        with open(file, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_data(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

# Load chat & leaderboard data
chat_data = load_data(CHAT_IDS_FILE)
leaderboard = load_data(LEADERBOARD_FILE)

# Questions
quizzes = [
    {"question": "Capital of France?", "options": ["Berlin", "Madrid", "Paris", "Rome"], "answer": "Paris"},
    {"question": "Symbol of Oxygen?", "options": ["Gold", "Oxygen", "Silver", "Iron"], "answer": "Oxygen"},
]

# Send Quiz Function
def send_quiz(context: CallbackContext):
    job = context.job
    chat_id = job.context["chat_id"]
    used_questions = job.context["used_questions"]

    available_quizzes = [q for q in quizzes if q not in used_questions]
    if not available_quizzes:
        job.schedule_removal()
        chat_data[chat_id]["active"] = False
        save_data(CHAT_IDS_FILE, chat_data)
        return

    quiz = random.choice(available_quizzes)
    used_questions.append(quiz)
    
    context.bot.send_poll(
        chat_id=chat_id,
        question=quiz["question"],
        options=quiz["options"],
        type=Poll.QUIZ,
        correct_option_id=quiz["options"].index(quiz["answer"]),
        is_anonymous=False
    )
    
# Start Quiz
def start_quiz(update: Update, context: CallbackContext):
    chat_id = str(update.effective_chat.id)
    
    if chat_id in chat_data and chat_data[chat_id].get("active", False):
        update.message.reply_text("A quiz is already running!")
        return
    
    interval = chat_data.get(chat_id, {}).get("interval", 30)
    chat_data[chat_id] = {"active": True, "interval": interval}
    save_data(CHAT_IDS_FILE, chat_data)

    update.message.reply_text(f"Quiz started! Interval: {interval}s")
    context.job_queue.run_repeating(
        send_quiz, interval=interval, first=0, context={"chat_id": chat_id, "used_questions": []}
    )

# Stop Quiz
def stop_quiz(update: Update, context: CallbackContext):
    chat_id = str(update.effective_chat.id)

    if chat_id in chat_data:
        chat_data[chat_id]["active"] = False
        save_data(CHAT_IDS_FILE, chat_data)

        jobs = context.job_queue.jobs()
        for job in jobs:
            if job.context and job.context["chat_id"] == chat_id:
                job.schedule_removal()

        update.message.reply_text("Quiz stopped.")
    else:
        update.message.reply_text("No active quiz to stop.")

# Handle Quiz Answers
def handle_poll_answer(update: Update, context: CallbackContext):
    poll_answer = update.poll_answer
    user_id = str(poll_answer.user.id)
    selected_option = poll_answer.option_ids[0] if poll_answer.option_ids else None

    for quiz in quizzes:
        if selected_option == quiz["options"].index(quiz["answer"]):
            leaderboard[user_id] = leaderboard.get(user_id, 0) + 1
            save_data(LEADERBOARD_FILE, leaderboard)
            return

# Show Leaderboard
def show_leaderboard(update: Update, context: CallbackContext):
    sorted_scores = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
    message = "🏆 *Leaderboard* 🏆\n\n"

    for rank, (user_id, score) in enumerate(sorted_scores[:10], start=1):
        try:
            user = context.bot.get_chat(int(user_id))
            username = f"@{user.username}" if user.username else f"{user.first_name}"
        except:
            username = f"User {user_id}"

        message += f"#{rank} {username} - {score} points\n"

    update.message.reply_text(message, parse_mode="Markdown")

# Broadcast Message (Admin Only)
def broadcast(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("You are not authorized.")
        return

    message = ' '.join(context.args)
    if not message:
        update.message.reply_text("Usage: /broadcast <message>")
        return

    for chat_id in chat_data.keys():
        try:
            context.bot.send_message(chat_id=int(chat_id), text=message)
        except Exception as e:
            logger.error(f"Failed to send to {chat_id}: {e}")

    update.message.reply_text("Broadcast sent.")

# Bot Start Function
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", lambda update, context: update.message.reply_text("Welcome! Use /sendgroup to start a quiz in a group or /prequiz to start a quiz personally.")))
    dp.add_handler(CommandHandler("sendgroup", sendgroup))
   # dp.add_handler(CommandHandler("prequiz", prequiz))
    dp.add_handler(CommandHandler("stopquiz", stop_quiz))
    dp.add_handler(CommandHandler("setinterval", set_interval))
    dp.add_handler(PollAnswerHandler(handle_poll_answer))
    dp.add_handler(CommandHandler("leaderboard", show_leaderboard))
    dp.add_handler(CommandHandler("broadcast", broadcast))
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
