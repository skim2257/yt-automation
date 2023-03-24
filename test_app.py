
import os, json
import flask
import requests
from copy import copy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
from googleapiclient.errors import HttpError

# This variable specifies the name of a file that contains the OAuth 2.0
# information for this application, including its client_id and client_secret.
CLIENT_SECRETS_FILE = 'credentials_web.json'

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
SCOPES = ['https://www.googleapis.com/auth/youtube', \
          'https://www.googleapis.com/auth/youtube.force-ssl', \
          'https://www.googleapis.com/auth/youtube.upload']

API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'
daysOfWeek = [1, 3] #0-6 for Mon-Sun (yes, it's 0-6 for sun-sat but this is the range for when selecting our weekday)


app = flask.Flask(__name__)
app.secret_key = 'blahblahblah' # necessary for flask apps to run

def suffix(d):
    return 'th' if 11<=d<=13 else {1:'st',2:'nd',3:'rd'}.get(d%10, 'th')

def custom_strftime(format, t):
    return t.strftime(format).replace('{S}', str(t.day) + suffix(t.day))

@app.route('/')
def index():
  return print_index_table()


@app.route('/test')
def test_api_request():
  if 'credentials' not in flask.session:
    return flask.redirect('authorize')

  # Load credentials from the session.
  credentials = google.oauth2.credentials.Credentials(
      **flask.session['credentials'])

  youtube = googleapiclient.discovery.build(
      API_SERVICE_NAME, API_VERSION, credentials=credentials)

  zone = ZoneInfo("America/New_York")
  now  = datetime.now(zone)
    # Set the date and time for the scheduled livestreams
  tuesday_date = copy(now.date()) + timedelta(days=(1 - now.weekday() + 7))
  tuesday_time = datetime.combine(tuesday_date, datetime(2020, 1, 1, tzinfo=zone).min.time()) + timedelta(hours=6) #6am
  thursday_date = copy(now.date()) + timedelta(days=(3 - now.weekday() + 7)) 
  thursday_time = datetime.combine(thursday_date, datetime(2020, 1, 1, tzinfo=zone).min.time()) + timedelta(hours=6) #6am

  # Create the scheduled livestreams
  for date, time in [(tuesday_date, tuesday_time), (thursday_date, thursday_time)]:
      start_time = time.isoformat() #+ '.000Z'
      end_time = (time + timedelta(hours=1)).isoformat() #+ '.000Z'  # End time is 1 hour after start time
      request_body = {
          'snippet': {
              'title': f'LIVESTREAM - {custom_strftime("%b {S}", date)}',
              'description': 'Join me for a livestream next week!',
              'scheduledStartTime': start_time,
              'scheduledEndTime': end_time
          },
          'status': {
              'privacyStatus': 'unlisted'
          }
      }
      print(datetime.now().tzname())
      try:
          response = youtube.liveBroadcasts().insert(part='id,status,snippet', body=request_body).execute()
          id = response["id"]
          print(f'Scheduled livestream for {date.strftime("%A, %B %d, %Y")} created. Broadcast ID: {response["id"]}')
          print(response)
      except HttpError as e:
          print(f'Error creating scheduled livestream for {date.strftime("%A, %B %d, %Y")}: {json.loads(e.content)["error"]["message"]}')
          print(e)

  # Save credentials back to session in case access token was refreshed.
  # ACTION ITEM: In a production app, you likely want to save these
  #              credentials in a persistent database instead.
  flask.session['credentials'] = credentials_to_dict(credentials)

  return print_index_table()


@app.route('/authorize')
def authorize():
  # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
  flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
      CLIENT_SECRETS_FILE, scopes=SCOPES)

  # The URI created here must exactly match one of the authorized redirect URIs
  # for the OAuth 2.0 client, which you configured in the API Console. If this
  # value doesn't match an authorized URI, you will get a 'redirect_uri_mismatch'
  # error.
  flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

  authorization_url, state = flow.authorization_url(
      # Enable offline access so that you can refresh an access token without
      # re-prompting the user for permission. Recommended for web server apps.
      access_type='offline',
      # Enable incremental authorization. Recommended as a best practice.
      include_granted_scopes='true')

  # Store the state so the callback can verify the auth server response.
  flask.session['state'] = state

  return flask.redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
  # Specify the state when creating the flow in the callback so that it can
  # verified in the authorization server response.
  state = flask.session['state']

  flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
      CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
  flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

  # Use the authorization server's response to fetch the OAuth 2.0 tokens.
  authorization_response = flask.request.url
  flow.fetch_token(authorization_response=authorization_response)

  # Store credentials in the session.
  # ACTION ITEM: In a production app, you likely want to save these
  #              credentials in a persistent database instead.
  credentials = flow.credentials
  flask.session['credentials'] = credentials_to_dict(credentials)

  return flask.redirect(flask.url_for('test_api_request'))


@app.route('/revoke')
def revoke():
  if 'credentials' not in flask.session:
    return ('You need to <a href="/authorize">authorize</a> before ' +
            'testing the code to revoke credentials.')

  credentials = google.oauth2.credentials.Credentials(
    **flask.session['credentials'])

  revoke = requests.post('https://oauth2.googleapis.com/revoke',
      params={'token': credentials.token},
      headers = {'content-type': 'application/x-www-form-urlencoded'})

  status_code = getattr(revoke, 'status_code')
  if status_code == 200:
    return('Credentials successfully revoked.' + print_index_table())
  else:
    return('An error occurred.' + print_index_table())


@app.route('/clear')
def clear_credentials():
  if 'credentials' in flask.session:
    del flask.session['credentials']
  return ('Credentials have been cleared.<br><br>' +
          print_index_table())


def credentials_to_dict(credentials):
  return {'token': credentials.token,
          'refresh_token': credentials.refresh_token,
          'token_uri': credentials.token_uri,
          'client_id': credentials.client_id,
          'client_secret': credentials.client_secret,
          'scopes': credentials.scopes}

def print_index_table():
  return ('<h1>YOU MUST DISABLE ADBLOCK/UBLOCK FOR THIS TO WORK</h1>' +
          '<table>' +
          '<tr><td><a href="/test">Test an API request</a></td>' +
          '<td>Submit an API request and see a formatted JSON response. ' +
          '    Go through the authorization flow if there are no stored ' +
          '    credentials for the user.</td></tr>' +
          '<tr><td><a href="/authorize">Test the auth flow directly</a></td>' +
          '<td>Go directly to the authorization flow. If there are stored ' +
          '    credentials, you still might not be prompted to reauthorize ' +
          '    the application.</td></tr>' +
          '<tr><td><a href="/revoke">Revoke current credentials</a></td>' +
          '<td>Revoke the access token associated with the current user ' +
          '    session. After revoking credentials, if you go to the test ' +
          '    page, you should see an <code>invalid_grant</code> error.' +
          '</td></tr>' +
          '<tr><td><a href="/clear">Clear Flask session credentials</a></td>' +
          '<td>Clear the access token currently stored in the user session. ' +
          '    After clearing the token, if you <a href="/test">test the ' +
          '    API request</a> again, you should go back to the auth flow.' +
          '</td></tr></table>')


if __name__ == '__main__':
  # When running locally, disable OAuthlib's HTTPs verification.
  # ACTION ITEM for developers:
  #     When running in production *do not* leave this option enabled.
  os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

  # Specify a hostname and port that are set as a valid redirect URI
  # for your API project in the Google API Console.
  app.run('localhost', 4567, debug=True)