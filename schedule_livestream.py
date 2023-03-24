from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import json, os, flask
from dotenv import load_dotenv



## Set up the OAuth credentials

SCOPES = ['https://www.googleapis.com/auth/youtube', \
          'https://www.googleapis.com/auth/youtube.force-ssl', \
          'https://www.googleapis.com/auth/youtube.upload']

CREDENTIALS = 'credentials_web.json'

import google.oauth2.credentials
import google_auth_oauthlib.flow

# Use the client_secret.json file to identify the application requesting
# authorization. The client ID (from that file) and access scopes are required.
flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    CREDENTIALS,
    scopes=['https://www.googleapis.com/auth/drive.metadata.readonly'])

# Indicate where the API server will redirect the user after the user completes
# the authorization flow. The redirect URI is required. The value must exactly
# match one of the authorized redirect URIs for the OAuth 2.0 client, which you
# configured in the API Console. If this value doesn't match an authorized URI,
# you will get a 'redirect_uri_mismatch' error.
flow.redirect_uri = 'https://www.example.com/oauth2callback'

# Generate URL for request to Google's OAuth 2.0 server.
authorization_url, state = flow.authorization_url(
    access_type='offline',
    login_hint=os.environ["EMAIL"],
    include_granted_scopes='true')

print(authorization_url, state)
auth = flask.redirect(authorization_url)

state = flask.session['state']
flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    CREDENTIALS,
    scopes=SCOPES,
    state=state)
flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

authorization_response = flask.request.url
flow.fetch_token(authorization_response=authorization_response)

# Store the credentials in the session.
# ACTION ITEM for developers:
#     Store user's access and refresh tokens in your data store if
#     incorporating this code into your real app.
creds = flow.credentials
flask.session['credentials'] = {
    'token': creds.token,
    'refresh_token': creds.refresh_token,
    'token_uri': creds.token_uri,
    'client_id': creds.client_id,
    'client_secret': creds.client_secret,
    'scopes': creds.scopes}

"""credentials"""
# from google.oauth2.service_account import Credentials
# creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# from google.oauth2.credentials import Credentials
# creds = Credentials.from_authorized_user_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# Set up the YouTube API client
youtube = build('youtube', 'v3', credentials=creds)

# Set the date and time for the scheduled livestreams
tuesday_date = datetime.now().date() + timedelta(days=(1 - datetime.now().weekday() + 7))
tuesday_time = datetime.combine(tuesday_date, datetime.min.time()) + timedelta(hours=6)
thursday_date = datetime.now().date() + timedelta(days=(3 - datetime.now().weekday() + 7))
thursday_time = datetime.combine(thursday_date, datetime.min.time()) + timedelta(hours=6)

# Create the scheduled livestreams
for date, time in [(tuesday_date, tuesday_time), (thursday_date, thursday_time)]:
    start_time = time.isoformat() + '.000Z'
    end_time = (time + timedelta(hours=1)).isoformat() + '.000Z'  # End time is 1 hour after start time
    request_body = {
        'snippet': {
            'title': 'My scheduled livestream',
            'description': 'Join me for a livestream next week!',
            'scheduledStartTime': start_time,
            'scheduledEndTime': end_time
        },
        'status': {
            'privacyStatus': 'public'
        }
    }
    try:
        response = youtube.liveBroadcasts().insert(part='id,status,snippet', body=request_body).execute()
        print(f'Scheduled livestream for {date.strftime("%A, %B %d, %Y")} created. Broadcast ID: {response["id"]}')
        print(response)
    except HttpError as e:
        print(f'Error creating scheduled livestream for {date.strftime("%A, %B %d, %Y")}: {json.loads(e.content)["error"]["message"]}')
        print(e)

