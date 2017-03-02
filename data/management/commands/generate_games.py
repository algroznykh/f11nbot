# -*- coding: utf-8 -*-
import os
import csv
from django.core.management.base import BaseCommand, CommandError
from data.models import Game, Discussion, QuestionCategory, Question

from collections import OrderedDict


class Command(BaseCommand):
    help = 'Creates StVal Discussion + Promos'

    @staticmethod
    def read_questions(path):
        with open(path, 'r') as f:
            reader = csv.reader(f)
            return {int(l[0]): [l[1], int(l[2])] for l in reader}

    @staticmethod
    def read_categories(path):
        with open(path, 'r') as f:
            reader = csv.reader(f)
            return OrderedDict([(int(l[0]), l[1]) for l in reader])

    def handle(self, *args, **options):
        discussion, created = Discussion.objects.get_or_create(
            name="StVal",
            user_limit=2
        )

        fact_game, fact_created = Game.objects.get_or_create(
            name=u'Факторизация',
            choose_command=u"факторизация",
            discussion=discussion,
            description=u"В этой игре бот предложит рассмотреть ваши отношения как набор различных факторов и задаст вопросы про каждый из них по отдельности"
        )
        fact_game.save()

        root_dir = os.path.dirname(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
        categories = self.read_categories(os.path.join(root_dir, 'storage/fact_categories.csv'))
        questions = self.read_questions(os.path.join(root_dir, 'storage/fact_questions.csv'))
        for category_id, name in categories.items():
            category, cat_created = QuestionCategory.objects.get_or_create(
                name=name,
                game=fact_game
            )
            for question, question_data in questions.items():
                if question_data[1] == category.id:
                    question, question_created = Question.objects.get_or_create(
                        text=question_data[0]
                    )
                    category.questions.add(question)

        self.stdout.write(self.style.SUCCESS(u'Successfully created game "%s"' % fact_game))
