import requests
import os
import json
import urllib.parse
from flask import Flask, redirect, send_file, make_response, render_template, request, jsonify, session
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw

app = Flask(__name__)
app.secret_key = '53d355f&-571a-4590-a310-1f9579440851'

CLIENT_ID = '6482d51f91994ef49489b00ab84f02d1'
CLIENT_SECRET = '8c77fa2823e147edb04bcd7446ef7a9e'
REDIRECT_URI = 'http://localhost:5000/callback'

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1/'

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login')
def login():
    scope = 'user-read-private user-read-email user-top-read'

    params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': REDIRECT_URI,
        'show_dialog': True
    }

    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    return redirect(auth_url)

@app.route('/callback')
def callback():
    if 'error' in request.args:
        return jsonify({"error": request.args['error']})

    if 'code' in request.args:
        req_body = {
            'code': request.args['code'],
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URI,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }

        response = requests.post(TOKEN_URL, data=req_body)
        token_info = response.json()

        session['access_token'] = token_info['access_token']
        session['refresh_token'] = token_info['refresh_token']
        session['expires_at'] = datetime.now().timestamp() + token_info['expires_in']

        return redirect('/albums')


# Import statements and app setup...

@app.route('/albums')
def get_albums():
    if 'access_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }

    # Update the 'limit' parameter to 25
    response = requests.get(API_BASE_URL + 'me/top/tracks', headers=headers, params={'time_range': 'long_term', 'limit': 50})

    if not response.text:
        print("Empty response received.")
        return render_template('error.html', error="Failed to fetch top albums. Please try again. Response is empty.")

    try:
        top_tracks = response.json()
    except json.JSONDecodeError:
        print(f"Failed to decode JSON response: {response.text}")
        return render_template('error.html', error=f"Failed to fetch top albums. Please try again. Response: {response.text}")

    if response.status_code != 200:
        print(f"Failed to fetch top albums. Status Code: {response.status_code}, Response: {response.text}")
        return render_template('error.html', error=f"Failed to fetch top albums. Please try again. Status Code: {response.status_code}, Response: {response.text}")

    # Extract only the tracks with at least 2 tracks
    filtered_tracks = [track for track in top_tracks['items'] if track['album']['total_tracks'] >= 2]

    # Extract unique album names and album covers
    unique_albums = set((track['album']['name'], track['album']['images'][0]['url']) for track in filtered_tracks)

    # Limit the list to the first 25 unique albums
    top_albums = list(unique_albums)[:25]

    session['top_albums'] = top_albums

    return render_template('albums.html', top_albums=top_albums)









@app.route('/refresh-token')
def refresh_token():
    if 'refresh_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        req_body = {
            'grant_type': 'refresh_token',
            'refresh_token': session['refresh_token'],
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }

        response = requests.post(TOKEN_URL, data=req_body)
        new_token_info = response.json()

        session['access_token'] = new_token_info['access_token']
        session['expires_at'] = datetime.now().timestamp() + new_token_info['expires_in']

        return redirect('/albums')




# ... img generate

@app.route('/generate_collage')
def generate_collage():
    # Show buffering page
    return render_template('buffering.html')

# Add a new route for generating the collage
@app.route('/generate_collage_now')
def generate_collage_now():
    # Inside the /generate_collage_now route
    top_albums = session.get('top_albums', [])
    album_covers = [Image.open(BytesIO(requests.get(album[1]).content)) for album in top_albums]

    # Calculate collage dimensions based on a grid layout
    collage_width = 500
    collage_height = 500
    num_cols = 5
    num_rows = 5
    thumbnail_size = (collage_width // num_cols, collage_height // num_rows)

    # Resize and arrange album covers in a grid
    collage = Image.new('RGB', (collage_width, collage_height), (255, 255, 255))
    for i, album_cover in enumerate(album_covers):
        col = i % num_cols
        row = i // num_cols
        resized_cover = album_cover.resize(thumbnail_size, Image.LANCZOS)
        collage.paste(resized_cover, (col * thumbnail_size[0], row * thumbnail_size[1]))

    filename = f"collage_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
    
    # Create the 'static' directory if it doesn't exist
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    os.makedirs(static_dir, exist_ok=True)

    # Save the collage to the static folder
    collage_path = os.path.join(static_dir, filename)
    collage.save(collage_path)

    # Return the URL of the generated image
    return jsonify({'redirect_url': f'/static/{filename}'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

