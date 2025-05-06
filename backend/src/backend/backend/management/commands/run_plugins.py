import json
from django.core.management.base import BaseCommand, CommandError
from backend.models import Video

from backend.plugin_manager import PluginManager
from multiprocessing import Pool
from contextlib import nullcontext


def job(args):
    video_id = args["video_id"]
    plugin_manager = args["plugin_manager"]
    plugin = args["plugin"]
    parameters = args["parameters"]
    dry_run = args["dry_run"]

    try:
        video_db = Video.objects.get(pk=video_id)
        user_db = video_db.owner
    except Video.DoesNotExist:
        raise CommandError('Poll "%s" does not exist' % video_id)

    result = plugin_manager(
        plugin,
        parameters=parameters,
        user=user_db,
        video=video_db,
        run_async=False,
        dry_run=dry_run,
    )

    return {"video_id": video_id, "plugin": plugin, **result}


# ee1b9286b87344de95c2b4556526e9ab aa06ebb887254815ad3871feae38ce32 1e0af16722f74da2b01325f7c01732c0 9be743f95269496ba7d189a88f2e8fc5 5e426e6bdc4943dd8e7d99312dc9dd70 fd276ddff9aa48d5b5ebdcb446599b60


class Command(BaseCommand):
    help = "Closes the specified poll for voting"

    def add_arguments(self, parser):
        parser.add_argument("--video_ids", nargs="+", type=str)
        parser.add_argument("--plugin", type=str)
        parser.add_argument("--num_threads", type=int, default=2)
        parser.add_argument("--parameters", type=str)
        parser.add_argument("--output", type=str)
        parser.add_argument("--dry_run", action="store_true")

    def handle(self, *args, **options):
        plugin_manager = PluginManager()
        parameters = []
        if options["parameters"]:
            parameters = json.loads(options["parameters"])

        pool = Pool(options["num_threads"])
        if options["output"]:
            context = open(options["output"], "w")
        else:
            context = nullcontext()
        with context as f:
            for result in pool.imap(
                job,
                [
                    {
                        "video_id": x,
                        "plugin_manager": plugin_manager,
                        "parameters": parameters,
                        "plugin": options["plugin"],
                        "dry_run": options["dry_run"],
                    }
                    for x in options["video_ids"]
                ],
            ):
                if f:
                    f.write(json.dumps(result) + "\n")
                print(result)
            # self.stdout.write(self.style.SUCCESS('Successfully start plugin "%s"'))
