# Remind

A discord bot that sends reminders for future contests using [clist](https://clist.by/) API.


## Installation

Clone the repository

```bash
git clone https://github.com/aryanc403/remind
```

### Dependencies

Now all dependencies need to be installed. Dependencies are listed in [requirements.txt](requirements.txt)

```bash
pip install -r requirements.txt
```

### Final steps

To start remind. Fill up variables in [env_file_variables.txt](env_file_variables.txt) and rename it to `.env`.

You will need to setup a bot on your server before continuing, follow the directions [here](https://github.com/reactiflux/discord-irc/wiki/Creating-a-discord-bot-&-getting-a-token). Following this, you should have your bot appearing in your server and you should have the Discord bot token.

You will need [clist.by](https://clist.by/) api key for updation of contest list. You can find it [here](https://clist.by/api/v1/doc/) after creating an account.

You can also setup an logger channel by creating a channel for bot to log errors and supplying a channel id as `LOGGING_COG_CHANNEL_ID` variable. But this is not required for running the bot.

```bash
./run.sh
```

#### Deployment

If you want to just host bot then you can skip installing dependencies and just follow [Final steps](#Final-steps) and just install Docker [Dockerfile](Dockerfile) will take care of rest.


## Contributing

We are using [autopep8](https://github.com/hhatto/autopep8) for formatting the code.

`pycodestyle .` must generate no errors before accepting the PR. Use `autopep8 --in-place --aggressive --aggressive <file name>` for formatting before send a PR.
  
Shotout to [TLE](https://github.com/cheran-senthil/TLE) developers for the idea and initial contributions to this bot. Their bot used to remind about Codeforces contests and we enhanced it for all other judges.

## License
[MIT License](https://github.com/aryanc403/remind/blob/master/LICENSE)
