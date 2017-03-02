# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import ReplyKeyboardMarkup, KeyboardButton
from django.db import models
from django.contrib.postgres.fields import JSONField

from const import *


class User(models.Model):
    telegram_id = models.IntegerField()
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    username = models.CharField(max_length=255)


class Discussion(models.Model):
    name = models.CharField(max_length=255)
    user_limit = models.IntegerField()
    members = models.ManyToManyField(User, through='DiscussionMembership')


class PromoCode(models.Model):
    code = models.CharField(max_length=255)
    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE)


BANNED_FACTORS_LEN = 4
CHOSEN_FACTORS_LEN = 4

START_USER_STATE = {
    'category': 0,
    'question': 0
}


class Game(models.Model):
    name = models.CharField(max_length=255)
    choose_command = models.CharField(max_length=255)
    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE)
    description = models.TextField(blank=True)

    def process_state(self, state, msg_text):
        fact_name = u'Факторизация'
        if self.name == fact_name:
            return self.process_fact_state(state, msg_text)
        else:
            send_text = GAME_OVER_MSG
            keyboard = [[InlineKeyboardButton(NEXT_QUESTION_CMD)]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            return state, send_text, reply_markup

    def process_fact_state(self, state, msg_text):
        msg_text = msg_text.replace('/', '')
        # TODO reorder game cats
        game_categories = self.questioncategory_set.all()

        if state.get('category'):
            matched_categories = game_categories.filter(id=state.get('category'))
        else:
            matched_categories = game_categories.filter(name__contains=msg_text)

        if state.get('category') or matched_categories:

            matched_category = matched_categories[0]
            state['category'] = matched_category.id

            cat_questions = list(matched_category.questions.all())

            if state.get('question') >= len(cat_questions):
                send_text = NO_MORE_QUESTIONS_MSG
                state = START_USER_STATE.copy()

                keyboard = [[InlineKeyboardButton(BACK_CMD)]]
            else:
                current_question = cat_questions[state.get('question')]
                send_text = current_question.text

                state['question'] += 1

                keyboard = [[InlineKeyboardButton(NEXT_QUESTION_CMD)],
                            [InlineKeyboardButton(BACK_CMD)]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        else:
            send_text = SELECT_CATEGORY_MSG

            fact_cats = [
                    [KeyboardButton("{}".format(cat.name))] for cat in reversed(game_categories)
                    ]
            fact_cats.append([KeyboardButton(FINISH_FACT_CMD)])
            reply_markup = ReplyKeyboardMarkup(fact_cats, one_time_keyboard=True)
            state['category'] = 0

        return state, send_text, reply_markup

    def __unicode__(self):
        return self.name


class Question(models.Model):
    text = models.TextField(blank=True)

    class Meta:
        ordering = ['id']


class QuestionCategory(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    questions = models.ManyToManyField(Question)


class DiscussionMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE)
    state = JSONField(null=True)
    promo_code = models.CharField(max_length=255)
    active_game = models.ForeignKey(Game,  null=True, on_delete=models.SET_NULL)
    ready = models.BooleanField(default=False)
    category = models.CharField(max_length=255,null=True)
