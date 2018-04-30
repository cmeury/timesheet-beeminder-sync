# timesheet-beeminder-sync

Adding Beeminder datapoints from the [Timesheet Android app](https://play.google.com/store/apps/details?id=com.rauscha.apps.timesheet)'s
XML backups stored in a Dropbox folder.


## Create a Dropbox App

1. Go to: https://www.dropbox.com/developers/apps/create
2. Choose "Dropbox API"
3. Choose "Full Dropbox"
4. Name your app, for example: "timesheet-beeminder-sync"
5. Agree to conditions and click "Create app"
6. Generate an access token as explained in [this Dropbox blog post](https://blogs.dropbox.com/developers/2014/05/generate-an-access-token-for-your-own-account/).
7. Use the token to populate `.env`
