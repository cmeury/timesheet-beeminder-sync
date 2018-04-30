# timesheet-beeminder-sync

Adding Beeminder datapoints from the [Timesheet Android app](https://play.google.com/store/apps/details?id=com.rauscha.apps.timesheet)'s
XML backups stored in a Dropbox folder.

## Prerequisites:

* Docker installed and running.
* Create a new "Do Less" goal with a maximum of 40 hours or so per weekat https://www.beeminder.com/new and call it "work".
* Get your auth token by visiting (need to be logged in): https://www.beeminder.com/api/v1/auth_token.json

### Create a Dropbox App

1. Go to: https://www.dropbox.com/developers/apps/create
2. Choose "Dropbox API"
3. Choose "Full Dropbox"
4. Name your app, for example: "timesheet-beeminder-sync"
5. Agree to conditions and click "Create app"
6. Generate an access token as explained in [this Dropbox blog post](https://blogs.dropbox.com/developers/2014/05/generate-an-access-token-for-your-own-account/).
7. Use the token to populate `.env`

## Run locally

* Copy the `.env.template` file to `.env` and fill in the variables.

    make dev

The `dev` target creates a Docker image and runs it in dev mode, meaning the source directory is mounted inside the container. So, any changes will be reflected - just run `make run-dev` afterwards, no need to build the image again.

## Deploy to Heroku

Create a heroku account, then:

    heroku login
    heroku create
    heroku config:set DROPBOX_ACCESS_TOKEN=
    heroku config:set DROPBOX_FOLDER=/timesheet/backup
    heroku config:set BM_USERNAME=username
    heroku config:set BM_AUTH_TOKEN=auth-token
    heroku config:set BM_GOAL=work


Deploy the app:

    git push heroku master

Look at the logs:

    heroku logs --tail

Then, open the [scheduler](https://devcenter.heroku.com/articles/scheduler#scheduling-jobs) add-on:

    heroku addons:open scheduler

And create a new job with the command: `python src/main.py` and a frequency of `hourly`.


