import os
import json
from django.core.management.base import BaseCommand, CommandError
from backend.models import Video
import pathlib
from django.contrib import auth

from backend.plugin_manager import PluginManager


class Command(BaseCommand):
    help = "Closes the specified poll for voting"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        username = input("username: ")
        password = input("password: ")
        email = input("email: ")

        print(f"{username} {password}")

        if auth.get_user_model().objects.filter(username=username).count() > 0:
            self.stdout.write(self.style.ERROR(f"User with name {username} already exists."))

        user = auth.get_user_model().objects.create_user(username, email, password)
        user.save()

        self.stdout.write(self.style.SUCCESS(f"User with id {user.id} created."))
