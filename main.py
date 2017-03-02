#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

# Django specific settings
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

# Have to do this for it to work in 1.9.x!
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
#############

# Your application specific imports
from data.models import *

from telegram import InlineKeyboardButton
from telegram import ReplyKeyboardMarkup
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, RegexHandler,
                          ConversationHandler)

from const import *
from config import TOKEN


PROMO, GAME_CHOOSE, FACT_GAME, QUESTION, WAIT = range(5)

logging.basicConfig(format='%(asctime)s - %(name)s '
                           '- %(levelname)s - %(message)s',
                    level=logging.INFO)
DEBUG = False


def start(bot, update, **args):
    telegram_id = update.message.from_user.id

    keyboard = [[KeyboardButton(EXIT_CMD)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    try:
        user = User.objects.get(telegram_id=telegram_id)
        disc_member_set = user.discussionmembership_set.all()
        if len(disc_member_set) is 0:

            update.message.reply_text(ASK_FOR_PROMO_MSG, reply_markup=reply_markup)

            return PROMO
        else:
            # TODO pipe to active game
            current_discussion = disc_member_set[0]
            return choose_game(bot, update, **args)

    except User.DoesNotExist:
        # TODO add logging
        update.message.reply_text(ASK_FOR_PROMO_MSG, reply_markup=reply_markup)
        return PROMO


def fact_game(bot, update, **args):
    cat = update.message.text
    cats = [cat.name for cat in QuestionCategory.objects.all()]

    # update.message.reply_text("Вы выбрали {}".format(cat))
    user = User.objects.get(telegram_id=update.message.from_user.id)
    disc_member_set = user.discussionmembership_set.all().filter(active_game__isnull=False)
    if not len(disc_member_set):
        return choose_game(bot, update, **args)
    current_membership = disc_member_set[0]

    disc_members = DiscussionMembership.objects.filter(promo_code=current_membership.promo_code)
    if cat in cats:
        current_membership.category = cat
        current_membership.save()

        if len(set([m.category for m in disc_members])) > 1:
            for member in disc_members:
                bot.sendMessage(member.user.telegram_id,
                                "Для продолжения игры вам с партнером нужно выбрать одинаковый фактор.")
            return FACT_GAME

    discussion_state = START_USER_STATE.copy()
    for member in disc_members:
        if member.state.get('category') != discussion_state.get('category') or \
           member.state.get('question') > discussion_state.get('question'):

            discussion_state = member.state

    new_state, question, reply_markup = current_membership.active_game.process_state(discussion_state,
                                                                                     update.message.text)

    for member in disc_members:
        try:
            bot.sendMessage(member.user.telegram_id, question, reply_markup=reply_markup)
        except Exception as e:
            print('Failed to send: ' + str(e))

        member.state = new_state

        member.ready = False
        member.save()

    return WAIT


def end_game(bot, update, **args):
    user = User.objects.get(telegram_id=update.message.from_user.id)
    disc_member_set = user.discussionmembership_set.all().filter(active_game__isnull=False)
    if not len(disc_member_set):
        return choose_game(bot, update, **args)
    current_membership = disc_member_set[0]

    disc_members = DiscussionMembership.objects.filter(promo_code=current_membership.promo_code)

    for member in disc_members:
        member.active_game = None
        member.state = START_USER_STATE.copy()
        member.save()
    return choose_game(bot, update, **args)


def end_discussion(bot, update, **args):
    user = User.objects.get(telegram_id=update.message.from_user.id)
    disc_member_set = user.discussionmembership_set.all()
    current_membership = disc_member_set[0]

    current_membership.delete()

    return start(bot, update, **args)


def end_conversation(bot, update, **args):
    update.message.reply_text(START_MSG,
                              reply_markup=ReplyKeyboardMarkup([[KeyboardButton(START_CMD)]]))
    return -1


def get_discussion_from_promo(update):

    try:
        promo_code = PromoCode.objects.get(
            code=update.message.text
        )
        memberships = DiscussionMembership.objects.all().filter(
            discussion=promo_code.discussion,
            promo_code=update.message.text
        )
        if len(memberships) > promo_code.discussion.user_limit:
            # update.message.reply_text("Discussion has already been filled up biatch !")
            return False
        else:
            return promo_code.discussion
    except PromoCode.DoesNotExist:
        # update.message.reply_text("Wrong promo ! Give me another try biatch !")
        return False


def check_promo(bot, update, **args):
    discussion = get_discussion_from_promo(update)

    if discussion:

        user, user_created = User.objects.get_or_create(
            telegram_id=update.message.from_user.id,
        )

        user.first_name = update.message.from_user.first_name
        user.last_name = update.message.from_user.last_name
        user.username = update.message.from_user.username
        user.save()

        membership, memb_created = DiscussionMembership.objects.get_or_create(
            user=user,
            discussion=discussion,
            state=START_USER_STATE,
            promo_code=update.message.text
        )

        if memb_created:
            partner_memberships = DiscussionMembership.objects.all().filter(promo_code=update.message.text)
            membership.active_game = partner_memberships[0].active_game
            membership.save()

        return choose_game(bot, update, **args)
    else:
        update.message.reply_text("Такого промокода у меня нет!")
        return PROMO


def choose_game(bot, update, **args):
    user = User.objects.get(telegram_id=update.message.from_user.id)
    disc_member_set = user.discussionmembership_set.all()
    current_membership = disc_member_set[0]

    if current_membership.active_game:
        return game_starter(bot, update, **args)

    disc_members = DiscussionMembership.objects.filter(promo_code=current_membership.promo_code)
    if len(disc_members) == current_membership.discussion.user_limit:
        # desired amount of users joined - choose the game

        # fetch all games and make them choose
        keyboard = []
        message = ""

        # TODO inline keyboard for category choosing
        for disc_game in current_membership.discussion.game_set.all():
            keyboard.append([KeyboardButton(START_CMD)])
            message += "*" + disc_game.name + "*: " + disc_game.description + "\n"
        keyboard.append([KeyboardButton(EXIT_CMD)])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

        for member in disc_members:
            try:
                bot.sendMessage(
                    member.user.telegram_id,
                    message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(e)
    else:
        # waiting for users to fill up the discussion
        update.message.reply_text(SEND_PROMO_MSG)

    return GAME_CHOOSE


def start_game(bot, update, **args):
    # assign game to members and start it.
    try:

        user = User.objects.get(telegram_id=update.message.from_user.id)
        disc_member_set = user.discussionmembership_set.all()
        current_membership = disc_member_set[0]

        if current_membership.active_game:
            return game_starter(bot, update, **args)

        disc_members = current_membership.discussion.discussionmembership_set.all()
        desired_game = Game.objects.get(choose_command="факторизация")
        for member in disc_members:
            member.active_game = desired_game
            member.save()
        return game_starter(bot, update, **args)
    except Game.DoesNotExist:
        update.message.reply_text(NO_SUCH_GAME_MSG)
        return GAME_CHOOSE


def game_starter(bot, update, **args):
    user = User.objects.get(telegram_id=update.message.from_user.id)
    disc_member_set = user.discussionmembership_set.all()
    current_membership_game = disc_member_set[0].active_game
    fact_name = u'Факторизация'
    if current_membership_game.name == fact_name:
        return fact_game(bot, update, **args)


def help(bot, update):
    update.message.reply_text(HELP_MSG)


def wait_for_partner(bot, update, *args, **kwargs):
    user = User.objects.get(telegram_id=update.message.from_user.id)
    ds_user = DiscussionMembership.objects.filter(user=user)[0]
    ds_user.ready = True
    ds_user.save()
    promo_code = user.discussionmembership_set.all()[0].promo_code
    code_holders = DiscussionMembership.objects.filter(promo_code=str(promo_code))
    if not all([u.ready for u in code_holders]):
        update.message.reply_text(WAIT_FOR_PARTNER_MSG)
        return WAIT
    else:
        for u in code_holders:
            u.ready = False
            u.save()
        return fact_game(bot, update)


def main():
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN)

    cats = [cat.name for cat in QuestionCategory.objects.all()]

    fact_game_handlers = [
        RegexHandler('^{}'.format(FINISH_FACT_CMD), end_game, pass_update_queue=True, pass_user_data=True),
        *[RegexHandler('^{}'.format(cat), fact_game, pass_update_queue=True, pass_user_data=True) for cat in cats]
    ]

    for category in Game.objects.get(name=u'Факторизация').questioncategory_set.all():
        command_name = category.name.split(' ')[0]
        fact_game_handlers.append(
            CommandHandler(command_name, fact_game, pass_update_queue=True, pass_user_data=True)
        )
    conv_handler = ConversationHandler(
        entry_points=[
            RegexHandler("^{}".format(START_CMD), start, pass_update_queue=True, pass_user_data=True),
            CommandHandler("start", start, pass_update_queue=True, pass_user_data=True)
        ],

        states={
            PROMO: [
                RegexHandler('^{}'.format(EXIT_CMD), end_conversation, pass_update_queue=True, pass_user_data=True),
                MessageHandler(Filters.text, check_promo, pass_update_queue=True, pass_user_data=True)
            ],
            GAME_CHOOSE: [
                RegexHandler('^{}'.format(EXIT_CMD), end_discussion, pass_update_queue=True, pass_user_data=True),
                RegexHandler('^{}'.format(START_CMD), start_game, pass_update_queue=True, pass_user_data=True)
            ],
            FACT_GAME: [
                RegexHandler('^{}'.format(NEXT_QUESTION_CMD), wait_for_partner, pass_update_queue=True,
                             pass_user_data=True),
                RegexHandler(u'^{}'.format(BACK_CMD), end_game, pass_update_queue=True, pass_user_data=True),
                RegexHandler(u'^{}'.format(FINISH_FACT_CMD), end_game, pass_update_queue=True, pass_user_data=True),
                *fact_game_handlers
                ],
            WAIT:
            [
                RegexHandler('^{}'.format(NEXT_QUESTION_CMD), wait_for_partner, pass_update_queue=True, pass_user_data=True),
                RegexHandler(u'^{}'.format(BACK_CMD), end_game, pass_update_queue=True, pass_user_data=True),
                RegexHandler(u'^{}'.format(FINISH_FACT_CMD), end_game, pass_update_queue=True, pass_user_data=True),
                *fact_game_handlers
            ]

        },

        fallbacks=[MessageHandler(Filters.text, start, pass_user_data=True)]
    )

    updater.dispatcher.add_handler(conv_handler)

    # Start the Bot
    updater.start_polling()

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()

if __name__ == '__main__' and not DEBUG:
    main()

