---
name: strm-get-provider-codes
description: Use this skill for repeatable maintenance of the streaming infrastructure and email handling.
---

# Skill Instructions

use the hermes agent to build and run this skill.
build all scripts in python and allscripts are to be placed in scripts.
use a framework functions module to make as many functions reusable as possible.
if you need to install any dependencies, please add them to the requirements.txt file in .venv.
make scripts that can be run from the command line, and also callable from other scripts.
set default to cover all providers, but allow for a provider to be specified as an argument to the script.
also allow for a user to be specified as an argument to the script, and if no user is specified, use the default user.
use framework.py as default framework.

# objective

when a user wants to log in to a streaming service, the user is questioned about whether they are part of the home network or not.

the procedure can differ depending on the provider, but in general, if the user is part of the home network, they can log in directly.

this is the sequence of events for a user who wants to login to Viaplay.
if they are not a part of the home network, they can press "request a temporary code" for logging in.
this is usually if you are on a mobile device, or if you are away on a computer that is not part of the home network.

when users press the request a temporary code button, it will email the owner of the streaming service account, with a code to be used for logging in. When the owner receives the email, we must forward the mail to a backup account.

We shall also extract the code from the mail, and save it in this project.

We shall have a list of approved users, and only those users can request a code. If the user is not approved, we shall not return a code.

the approved users are listed in the `config/code-forward-destinations.csv` file.

in the `config/code-forward-providers.csv` file, we have a list of supported providers, and the search string to use for extracting the code from the email.

we shall monitor the email account bennyskov@hotmail.com for incoming emails from the providers.

When an email is received, extract the code from the email, and forward it to email bsjunk13@hotmail.com, telegram bot, and the WhatsApp bot

we have these streaming services supported: Netflix, Viaplay, TV2Play.
