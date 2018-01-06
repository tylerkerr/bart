# bart
stupid slack integration so you and your friends can have a private internet currency

# setup
on the slack side of things, you need to set up a slash command (/bart in my case)
you also need an incoming webhook in the channel of your choice for the public chats.

you'll need to launch the app with three environment variables:
SLACK_SECRET, the token associated with the slash command
SLACK_URL, the final section of the URL for the incoming webhook for chat messages
and SLACK_API_TOKEN, the legacy API token for user lookups

e.g. `SLACK_SECRET='asdfghjkl' SLACK_API_TOKEN='xoxp-123412341234' SLACK_URL='fAKSJDkaJKEJWQknf' python3 bart.py`

by default the "API" runs on localhost using port 4999. if you have nginx already running on the server you want to use to host the ""API"", adding this location block will have nginx reverse proxy requests made to the """API""" URL into the listening flask app:

```            location /bart {
                    proxy_pass http://127.0.0.1:4999;
                    proxy_set_header Host $host;
                    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            }```