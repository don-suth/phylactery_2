# These tasks are imported here so that celery can auto-discover them.
from phylactery.communication.discord import send_to_discord
from phylactery.communication.email import send_single_email_task, send_mass_email_task
