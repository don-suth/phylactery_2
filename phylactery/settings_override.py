from environs import Env

env = Env()
env.read_env()

# This file exists solely to be over-written by Docker
# The main settings module will import this one.

DEBUG = True

SOCIALACCOUNT_PROVIDERS = {
	"discord": {
		"APPS": [
			{
				"client_id": "934080121881649233",
				"secret": env.str("DISCORD_SECRET"),
			}
		]
	}
}
